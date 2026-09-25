"""Level loading and tile collision queries.

Level text format (one line per tile row, 13 rows, top row first):
    ' '  empty
    'B'  solid block
    'E'  enemy spawn
    'C'  chest (goal)
    'P'  player spawn (optional, default: DEFAULT_SPAWN)
Any other character is treated as empty. Rows are padded to the same width.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from jumpnrun.core.constants import (
    CHEST_H,
    CHEST_W,
    DEFAULT_SPAWN,
    ENEMY_H,
    ENEMY_W,
    PLAYER_H,
    PLAYER_W,
    ROWS,
    TILE,
)


class Level:
    """Immutable tile map plus spawn points. Shared by all simulations that play it."""

    def __init__(self, lines: List[str], name: str = ""):
        lines = [line.rstrip("\n\r") for line in lines]
        while lines and not lines[-1].strip():
            lines.pop()  # ignore trailing empty lines
        if len(lines) > ROWS:
            raise ValueError(f"level '{name}' has {len(lines)} rows, max is {ROWS}")
        lines = lines + [""] * (ROWS - len(lines))

        self.name = name
        self.rows = ROWS
        self.cols = max(1, max(len(line) for line in lines))
        self.solid: List[bytearray] = []
        self.enemy_spawns: List[Tuple[int, int]] = []
        self.chests: List[Tuple[int, int, int, int]] = []
        spawn = None

        for r, line in enumerate(lines):
            row = bytearray(self.cols)
            for c, ch in enumerate(line):
                if ch == "B":
                    row[c] = 1
                elif ch == "E":
                    # enemy sits bottom-centred in its tile
                    self.enemy_spawns.append((c * TILE + (TILE - ENEMY_W) // 2, r * TILE + TILE - ENEMY_H))
                elif ch == "C":
                    self.chests.append((c * TILE, r * TILE + TILE - CHEST_H, CHEST_W, CHEST_H))
                elif ch == "P":
                    spawn = (c * TILE + (TILE - PLAYER_W) // 2, r * TILE + TILE - PLAYER_H)
            self.solid.append(row)

        if not self.chests:
            raise ValueError(f"level '{name}' has no chest ('C')")
        self.spawn = spawn if spawn is not None else DEFAULT_SPAWN
        self._lines = [line.ljust(self.cols) for line in lines]

    # ------------------------------------------------------------------ io
    @classmethod
    def from_file(cls, path) -> "Level":
        path = Path(path)
        with open(path, "r", encoding="utf-8") as level_file:
            return cls(level_file.readlines(), name=path.stem)

    @classmethod
    def from_text(cls, text: str, name: str = "") -> "Level":
        return cls(text.split("\n"), name=name)

    def to_text(self) -> str:
        return "\n".join(line.rstrip() for line in self._lines) + "\n"

    # ------------------------------------------------------------ geometry
    @property
    def pixel_width(self) -> int:
        return self.cols * TILE

    @property
    def pixel_height(self) -> int:
        return self.rows * TILE

    @property
    def goal_x(self) -> int:
        """x of the first chest - used as 'finish line' for progress metrics."""
        return min(chest[0] for chest in self.chests)

    def is_solid(self, col: int, row: int) -> bool:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.solid[row][col] == 1
        return False

    def overlaps_solid(self, x: int, y: int, w: int, h: int) -> bool:
        """True if the pixel rect (x, y, w, h) overlaps any solid tile."""

        r0 = max(y // TILE, 0)
        r1 = min((y + h - 1) // TILE, self.rows - 1)
        if r0 > r1:
            return False
        c0 = max(x // TILE, 0)
        c1 = min((x + w - 1) // TILE, self.cols - 1)
        if c0 > c1:
            return False
        for r in range(r0, r1 + 1):
            row = self.solid[r]
            for c in range(c0, c1 + 1):
                if row[c]:
                    return True
        return False
