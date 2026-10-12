"""Editable level grid (no graphics): painting, columns, undo/redo, loading and saving.

The file format is the game's level text (13 rows, ' ' empty, 'B' block, 'E' enemy, 'C' chest, 'P' start).
Saving keeps every unchanged row byte for byte (trailing spaces, line endings), so updating an existing
level only shows the rows that really changed in a git diff.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

from jumpnrun.core.constants import ROWS
from jumpnrun.core.level import Level

ROOT = Path(__file__).resolve().parents[2]
LEVELS_DIR = ROOT / "levels"
OWN_DIR = LEVELS_DIR / "eigene"
# measuring levels: never overwritten from the editor (only "save as new")
PROTECTED_DIRS = ("exam", "exam2", "validierung", "test_serie")

EMPTY, BLOCK, ENEMY, CHEST, START = " ", "B", "E", "C", "P"
TILES = (BLOCK, ENEMY, CHEST, START)
UNDO_LIMIT = 300


def is_protected(path) -> bool:
    """True for files inside the measuring-level folders (exam*, validierung, test_serie)."""

    try:
        rel = Path(path).resolve().relative_to(LEVELS_DIR.resolve())
    except ValueError:
        return False
    first = rel.parts[0] if len(rel.parts) > 1 else ""
    return first in PROTECTED_DIRS or first.startswith("exam")


def solution_path(path) -> Path:
    """levels/x/name.txt -> levels/x/name.loesung.json"""

    path = Path(path)
    return path.with_name(path.stem + ".loesung.json")


def load_solution(path) -> Optional[List[int]]:
    """Stored solver solution next to a level, converted to 2 frames per action (None if there is none)."""

    sol = solution_path(path)
    if not sol.exists():
        return None
    try:
        data = json.loads(sol.read_text())
    except (OSError, ValueError):
        return None
    if isinstance(data, list):  # exam format: plain list, 4 frames per action
        actions, repeat = data, 4
    else:
        actions, repeat = data.get("actions", []), int(data.get("action_repeat", 2))
    if repeat % 2:
        return None  # cannot be expressed in 2-frame steps
    return [a for a in actions for _ in range(repeat // 2)]


def save_solution(path, actions: List[int]) -> Path:
    sol = solution_path(path)
    sol.write_text(json.dumps({"action_repeat": 2, "actions": list(actions)}))
    return sol


class LevelModel:
    """The level being edited. Rows are lists of characters, all of the same width."""

    def __init__(self, text: Optional[str] = None, path: Optional[Path] = None):
        self.path: Optional[Path] = Path(path) if path is not None else None
        self._undo: List[Tuple[List[List[str]], int]] = []
        self._redo: List[Tuple[List[List[str]], int]] = []
        self._stroke_open = False
        self.version = 0  # grows with every change (the proof uses it to notice edits)
        self._parse(text if text is not None else self.default_text())
        self.saved_version = self.version

    # ------------------------------------------------------------------ io
    @staticmethod
    def default_text() -> str:
        rows = [""] * ROWS
        rows[11] = "  P" + " " * 22 + "C"
        rows[12] = "B" * 30
        return "\n".join(rows) + "\n"

    @classmethod
    def from_file(cls, path) -> "LevelModel":
        path = Path(path)
        with open(path, "r", encoding="utf-8", newline="") as f:
            return cls(f.read(), path)

    def _parse(self, text: str) -> None:
        self._eol = "\r\n" if "\r\n" in text else "\n"
        lines = text.replace("\r\n", "\n").split("\n")
        self._final_newline = text.endswith("\n") or not text
        if self._final_newline and lines and lines[-1] == "":
            lines.pop()
        self._orig_lines = lines  # raw rows as in the file (without line ends)
        rows = (lines + [""] * ROWS)[:ROWS]
        if any(line.strip() for line in lines[ROWS:]):
            raise ValueError(f"level has more than {ROWS} rows")
        width = max(1, max(len(r.rstrip()) for r in rows))
        self.grid: List[List[str]] = [list(self._clean(r).ljust(width)[:width]) for r in rows]
        self._saved_grid = [row[:] for row in self.grid]
        self._dirty_cache = (-1, False)

    @staticmethod
    def _clean(row: str) -> str:
        return "".join(ch if ch in TILES else EMPTY for ch in row.rstrip())

    def to_text(self) -> str:
        """File text. Rows that did not change are written exactly as they were in the file."""

        out = []
        for r in range(ROWS):
            row = "".join(self.grid[r]).rstrip()
            orig = self._orig_lines[r] if r < len(self._orig_lines) else None
            out.append(orig if orig is not None and self._clean(orig) == row else row)
        n = max(len(self._orig_lines), max((r + 1 for r in range(ROWS) if out[r]), default=0))
        out += self._orig_lines[ROWS:n]  # blank tail lines of the original file
        out = out[:n]
        return self._eol.join(out) + (self._eol if self._final_newline else "")

    def save(self, path=None) -> Path:
        path = Path(path) if path is not None else self.path
        if path is None:
            raise ValueError("no file name")
        path.parent.mkdir(parents=True, exist_ok=True)
        text = self.to_text()
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        grid = self.grid
        self._parse(text)  # the saved file is the new reference for "unchanged rows"
        self._grow_to(grid)
        self.path = path
        self.saved_version = self.version
        return path

    def to_level(self) -> Level:
        """Game level of the current grid (ValueError if it has no chest)."""

        return Level.from_text(self.to_text(), name=self.path.stem if self.path else "neu")

    @property
    def dirty(self) -> bool:
        """Unsaved changes (undoing back to the saved state counts as clean)."""

        if self.version == self.saved_version:
            return False
        if self._dirty_cache[0] != self.version:
            self._dirty_cache = (self.version, self.grid != self._saved_grid)
        return self._dirty_cache[1]

    @property
    def protected(self) -> bool:
        return self.path is not None and is_protected(self.path)

    # ------------------------------------------------------------ geometry
    @property
    def width(self) -> int:
        return len(self.grid[0])

    def get(self, col: int, row: int) -> str:
        if 0 <= row < ROWS and 0 <= col < self.width:
            return self.grid[row][col]
        return EMPTY

    def find(self, ch: str) -> List[Tuple[int, int]]:
        return [(c, r) for r in range(ROWS) for c in range(self.width) if self.grid[r][c] == ch]

    @property
    def used_width(self) -> int:
        """Columns up to the last non-empty tile."""

        return max((c + 1 for r in range(ROWS) for c in range(self.width) if self.grid[r][c] != EMPTY), default=0)

    # ---------------------------------------------------------------- undo
    def begin(self) -> None:
        """Start one undo step (a mouse stroke); all changes until end() are undone together."""

        if not self._stroke_open:
            self._undo.append(([row[:] for row in self.grid], self.version))
            self._undo = self._undo[-UNDO_LIMIT:]
            self._stroke_open = True
            self._stroke_changed = False

    def end(self) -> None:
        if self._stroke_open:
            self._stroke_open = False
            if not self._stroke_changed:
                self._undo.pop()
            else:
                self._redo.clear()

    def _changed(self) -> None:
        self.version += 1
        if self._stroke_open:
            self._stroke_changed = True

    def undo(self) -> bool:
        self.end()
        if not self._undo:
            return False
        self._redo.append(([row[:] for row in self.grid], self.version))
        self.grid, _ = self._undo.pop()
        self.version += 1
        return True

    def redo(self) -> bool:
        self.end()
        if not self._redo:
            return False
        self._undo.append(([row[:] for row in self.grid], self.version))
        self.grid, _ = self._redo.pop()
        self.version += 1
        return True

    # --------------------------------------------------------------- edits
    def _grow_to(self, grid: List[List[str]]) -> None:
        """Keep the editing width (empty columns at the end) after re-reading the saved text."""

        self._grow(len(grid[0]))
        self._saved_grid = [row[:] for row in self.grid]

    def _grow(self, width: int) -> None:
        if width > self.width:
            for row in self.grid:
                row.extend(EMPTY * (width - len(row)))

    def set(self, col: int, row: int, ch: str) -> bool:
        """Put one tile (EMPTY erases). The level grows to the right as needed. Returns True if it changed."""

        if not (0 <= row < ROWS) or col < 0 or (ch == EMPTY and col >= self.width):
            return False
        if self.get(col, row) == ch:
            return False
        auto = not self._stroke_open
        if auto:
            self.begin()
        self._grow(col + 1)
        if ch == START:  # exactly one start
            for c, r in self.find(START):
                self.grid[r][c] = EMPTY
        self.grid[row][col] = ch
        self._changed()
        if auto:
            self.end()
        return True

    def fill(self, c0: int, r0: int, c1: int, r1: int, ch: str) -> bool:
        """Fill a rectangle (corners inclusive) with BLOCK or EMPTY."""

        c0, c1 = sorted((max(0, c0), max(0, c1)))
        r0, r1 = sorted((max(0, min(ROWS - 1, r0)), max(0, min(ROWS - 1, r1))))
        auto = not self._stroke_open
        if auto:
            self.begin()
        changed = False
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                changed |= self.set(c, r, ch)
        if auto:
            self.end()
        return changed

    def insert_column(self, col: int) -> bool:
        if col < 0 or col > self.width:
            return False
        self.begin()
        for row in self.grid:
            row.insert(col, EMPTY)
        self._changed()
        self.end()
        return True

    def delete_column(self, col: int) -> bool:
        if not (0 <= col < self.width) or self.width <= 1:
            return False
        self.begin()
        for row in self.grid:
            del row[col]
        self._changed()
        self.end()
        return True

    def problems(self) -> List[str]:
        """Things that make the level unplayable (shown instead of a proof)."""

        out = []
        if not self.find(CHEST):
            out.append("Keine Kiste (Ziel) – Werkzeug 'Kiste' wählen und setzen.")
        return out
