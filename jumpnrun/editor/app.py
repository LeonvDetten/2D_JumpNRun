"""Level editor window: paint with the mouse, check solvability with the real bot actions, test-play, save.

    python leveleditor.py [level.txt]

Mouse: left paints with the selected tool (drag to paint more), right erases, Shift+drag fills a rectangle,
wheel scrolls, Ctrl+wheel zooms, middle drag pans, click the overview map to jump.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List, Optional, Tuple

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")
import pygame

from jumpnrun.core.actions import BOT_ACTIONS_V3, Action
from jumpnrun.core.constants import DEFAULT_SPAWN, FPS, ROWS, SCREEN_H, SCREEN_W, TILE
from jumpnrun.core.sim import Simulation, Status
from jumpnrun.editor import proof as pf
from jumpnrun.editor.model import (
    BLOCK, CHEST, EMPTY, ENEMY, LEVELS_DIR, OWN_DIR, START, LevelModel, is_protected, load_solution, save_solution,
    solution_path,
)
from jumpnrun.ui.widgets import (
    ACCENT, BG, BLUE, GREEN, MUTED, PANEL, PANEL_LINE, RED, TEXT, YELLOW, Button, ConfirmDialog,
    OpenDialog, SaveAsDialog, alpha_rect, font, panel, text, tooltip,
)

TOOLBAR_H = 68
RULER_H = 20
MINIMAP_H = 46
STATUS_H = 30
BOTTOM_H = MINIMAP_H + STATUS_H + 8
ZOOMS = (16, 20, 24, 32, 40, 48, 60)
REVALIDATE_DELAY = 0.15  # s after the last edit (no re-check while painting)

# tool key -> (tile it paints, name, tooltip)
TOOLS = [
    ("block", BLOCK, "Block", "Block setzen (1) – Umschalt+Ziehen: Rechteck"),
    ("enemy", ENEMY, "Gegner", "Gegner setzen (2) – läuft los, wenn er ins Bild kommt"),
    ("chest", CHEST, "Kiste", "Kiste = Ziel (3) – mehrere erlaubt"),
    ("start", START, "Start", "Startpunkt des Piraten (4) – es gibt genau einen"),
    ("erase", EMPTY, "Radierer", "Radieren (5) – rechte Maustaste radiert mit jedem Werkzeug"),
    ("rect", BLOCK, "Rechteck", "Rechteck aus Blöcken ziehen (6) – rechte Maustaste: Rechteck löschen"),
    ("colins", None, "Spalte +", "Leere Spalte einfügen (7) – schiebt alles rechts davon weiter"),
    ("coldel", None, "Spalte −", "Spalte löschen (8) – zieht alles rechts davon heran"),
]

STATE_COLORS = {pf.NONE: MUTED, pf.RUNNING: BLUE, pf.COMPLETE: GREEN, pf.STUCK: RED, pf.CHANGED: YELLOW,
                pf.INVALID: RED, pf.ERROR: RED}


def keys_to_action(pressed) -> Action:
    """Same key mapping as game.py."""

    return Action(
        left=bool(pressed[pygame.K_a] or pressed[pygame.K_LEFT]),
        right=bool(pressed[pygame.K_d] or pressed[pygame.K_RIGHT]),
        jump=bool(pressed[pygame.K_w] or pressed[pygame.K_SPACE] or pressed[pygame.K_UP]),
        shoot=bool(pressed[pygame.K_RETURN]),
    )


class EditorApp:
    def __init__(self, path: Optional[str] = None, size: Tuple[int, int] = (SCREEN_W, SCREEN_H), on_exit=None):
        from jumpnrun.render.assets import get_assets

        self.on_exit = on_exit  # inside the game app: back to the menu instead of ending the program

        self.assets = get_assets()
        self.size = size
        self.model = LevelModel()
        self.keeper = pf.ProofKeeper(self.model)
        self.tool = "block"
        self.z = 48
        self.scroll = 0.0
        self.dialog = None
        self.mode = "edit"  # edit | play | replay | help
        self.play_sim: Optional[Simulation] = None
        self.replay_index = 0
        self.frames_since_end = 0
        self.acc = 0.0
        self.toast: Tuple[str, tuple, float] = ("", TEXT, 0.0)
        self.painting: Optional[str] = None  # tile being painted while a mouse button is down
        self.rect_start: Optional[Tuple[int, int]] = None
        self.rect_tile = BLOCK
        self.last_cell: Optional[Tuple[int, int]] = None
        self.panning: Optional[Tuple[int, float]] = None
        self.minimap_drag = False
        self.last_edit = 0.0
        self.hover_since = (None, 0.0)
        self.running = True
        self._sprite_cache = {}
        self._minimap = (None, None)
        self._renderer = None
        self._play_surface = None
        self._make_buttons()
        self.layout(size)
        if path:
            self.open(Path(path))
        else:
            self._fit_zoom()

    # ================================================================ layout
    def _make_buttons(self) -> None:
        self.tool_buttons = [Button(key, "", tip, icon=self._tool_icon(key)) for key, _, _, tip in TOOLS]
        self.undo_buttons = [
            Button("undo", "", "Rückgängig (Strg+Z)", icon=lambda s, r: self._arrow_icon(s, r, -1), width=44),
            Button("redo", "", "Wiederholen (Strg+Y)", icon=lambda s, r: self._arrow_icon(s, r, 1), width=44),
        ]
        self.action_buttons = [
            Button("new", "Neu", "Neues Level (Strg+N)"),
            Button("open", "Öffnen", "Vorhandenes Level öffnen (Strg+O)"),
            Button("save", "Speichern", "Altes Level aktualisieren (Strg+S)"),
            Button("saveas", "Speichern als", "Als neues Level speichern (Strg+Umschalt+S)"),
            Button("check", "Prüfen", "Weg für den Bot suchen (P) – im Hintergrund, weiterbauen geht", accent=True),
            Button("play", "Testspielen", "Selbst spielen (T) – Esc zurück"),
            Button("replay", "Weg zeigen", "Den bewiesenen Bot-Weg abspielen (L)"),
            Button("help", "?", "Hilfe: alle Tasten (F1)", width=40),
        ]
        for b in self.action_buttons:
            b.tooltip_label = b.label
        check = self.action_buttons[4]
        check.measure = lambda height: font(17, True).size("Weiterprüfen")[0] + check.pad  # label changes

    def layout(self, size: Tuple[int, int]) -> None:
        self.size = size
        w, h = size
        short = {"saveas": "Als neu", "play": "Testen", "replay": "Weg"}
        for compact in (0, 1, 2):  # narrow window: smaller tool tiles, shorter labels
            tile = (52, 44, 38)[compact]
            for b in self.action_buttons:
                b.pad = (28, 18, 14)[compact]
                if b.key in short:
                    b.label = short[b.key] if compact else b.tooltip_label
            need = 10 + 8 * (tile + 6) + 8 + 2 * 50 + 16 + sum(b.measure(44) + 8 for b in self.action_buttons)
            if need <= w:
                break
        x, y = 10, (TOOLBAR_H - tile) // 2
        for b in self.tool_buttons:
            b.rect = pygame.Rect(x, y, tile, tile)
            x += tile + 6
        x += 8
        for b in self.undo_buttons:
            b.rect = pygame.Rect(x, (TOOLBAR_H - 44) // 2, 44, 44)
            x += 50
        right = w - 10
        for b in reversed(self.action_buttons):
            bw = b.measure(44)
            b.rect = pygame.Rect(right - bw, (TOOLBAR_H - 44) // 2, bw, 44)
            right -= bw + 8
        self.canvas = pygame.Rect(0, TOOLBAR_H, w, max(100, h - TOOLBAR_H - BOTTOM_H))
        self.minimap_rect = pygame.Rect(10, self.canvas.bottom + 6, w - 20, MINIMAP_H - 6)
        self.status_rect = pygame.Rect(0, h - STATUS_H, w, STATUS_H)
        self._background = None
        self._clamp_scroll()

    def _fit_zoom(self) -> None:
        fit = (self.canvas.h - RULER_H - 4) // ROWS
        self.z = max(z for z in ZOOMS if z <= max(fit, ZOOMS[0]))

    @property
    def level_top(self) -> int:
        return self.canvas.y + RULER_H + max(0, (self.canvas.h - RULER_H - ROWS * self.z) // 2)

    @property
    def visible_cols(self) -> float:
        return self.canvas.w / self.z

    def _clamp_scroll(self) -> None:
        if not hasattr(self, "model"):
            return
        limit = max(0.0, self.model.width + 12 - self.visible_cols)
        self.scroll = max(0.0, min(self.scroll, limit))

    def col_x(self, col: float) -> int:
        return int(self.canvas.x + (col - self.scroll) * self.z)

    def world_to_screen(self, px: float, py: float) -> Tuple[int, int]:
        return self.col_x(px / TILE), int(self.level_top + py * self.z / TILE)

    def cell_at(self, pos) -> Optional[Tuple[int, int]]:
        x, y = pos
        if not self.canvas.collidepoint(pos) or y < self.level_top:
            return None
        col = int(self.scroll + (x - self.canvas.x) / self.z)
        row = (y - self.level_top) // self.z
        if not 0 <= row < ROWS:
            return None
        return col, row

    def boundary_at(self, pos) -> int:
        """Nearest column boundary (insert position) under the mouse."""

        return max(0, int(round(self.scroll + (pos[0] - self.canvas.x) / self.z)))

    # ================================================================ sprites
    def sprite(self, tile: str, z: int, alpha: int = 255) -> pygame.Surface:
        key = (tile, z, alpha)
        if key not in self._sprite_cache:
            a = self.assets
            if tile == BLOCK:
                img = pygame.transform.smoothscale(a.block, (z, z))
            elif tile == ENEMY:
                img = pygame.transform.smoothscale(a.enemy[-1][0], (z * 2 // 3, z * 2 // 3))
            elif tile == CHEST:
                img = pygame.transform.smoothscale(a.chest[0], (z, z * 2 // 3))
            else:
                img = pygame.transform.smoothscale(a.player["IDLE"][1][0], (z * 2 // 3, z))
            if alpha < 255:
                img = img.copy()
                img.set_alpha(alpha)
            self._sprite_cache[key] = img
        return self._sprite_cache[key]

    def blit_tile(self, surface: pygame.Surface, tile: str, col: int, row: int, alpha: int = 255) -> None:
        z = self.z
        img = self.sprite(tile, z, alpha)
        x, y = self.col_x(col), self.level_top + row * z
        surface.blit(img, (x + (z - img.get_width()) // 2, y + z - img.get_height()))

    def _tool_icon(self, key: str):
        tile = dict((k, t) for k, t, _, _ in TOOLS)[key]

        def draw(surface: pygame.Surface, rect: pygame.Rect) -> None:
            z = rect.h
            if key in ("block", "enemy", "chest", "start"):
                img = self.sprite(tile, z)
                surface.blit(img, img.get_rect(midbottom=rect.midbottom))
            elif key == "erase":
                pts = [(rect.x + 6, rect.bottom - 10), (rect.x + 20, rect.y + 6), (rect.right - 4, rect.y + 18),
                       (rect.x + 20, rect.bottom - 2)]
                pygame.draw.polygon(surface, (236, 140, 160), pts)
                pygame.draw.polygon(surface, TEXT, pts, 2)
                pygame.draw.line(surface, TEXT, (rect.x + 4, rect.bottom), (rect.right, rect.bottom), 2)
            elif key == "rect":
                small = self.sprite(BLOCK, z // 2)
                for dx in (0, z // 2):
                    for dy in (0, z // 2):
                        surface.blit(small, (rect.x + dx, rect.y + dy))
                pygame.draw.rect(surface, ACCENT, rect, 2)
            else:
                cx = rect.centerx
                pygame.draw.line(surface, TEXT, (cx, rect.y), (cx, rect.bottom), 3)
                color = GREEN if key == "colins" else RED
                pygame.draw.rect(surface, color, (cx - 9, rect.centery - 9, 18, 18), border_radius=4)
                pygame.draw.line(surface, TEXT, (cx - 5, rect.centery), (cx + 5, rect.centery), 3)
                if key == "colins":
                    pygame.draw.line(surface, TEXT, (cx, rect.centery - 5), (cx, rect.centery + 5), 3)

        return draw

    @staticmethod
    def _arrow_icon(surface: pygame.Surface, rect: pygame.Rect, direction: int) -> None:
        """Curved arrow (undo: pointing left, redo: pointing right)."""

        arc = rect.inflate(-6, -4).move(0, 5)
        pygame.draw.arc(surface, TEXT, arc, 0.35, 2.8, 3)
        x = arc.x + 3 if direction < 0 else arc.right - 3
        y = arc.centery + 2
        pygame.draw.polygon(surface, TEXT, [(x - 7, y - 4), (x + 7, y - 4), (x, y + 6)])

    # ================================================================ files
    def open(self, path: Path) -> None:
        try:
            model = LevelModel.from_file(path)
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            self.flash(f"Kann {path} nicht öffnen: {exc}", RED)
            return
        self.keeper.stop()
        self.model = model
        self.keeper = pf.ProofKeeper(model)
        self.keeper.load(load_solution(path))
        self.scroll = 0.0
        self._fit_zoom()
        note = " – gespeicherte Lösung geladen" if self.keeper.proof.complete else ""
        self.flash(f"Geöffnet: {self._rel(path)}{note}", GREEN if note else TEXT)

    def new(self) -> None:
        self.keeper.stop()
        self.model = LevelModel()
        self.keeper = pf.ProofKeeper(self.model)
        self.scroll = 0.0
        self.flash("Neues Level", TEXT)

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return path.resolve().relative_to(LEVELS_DIR.parent.resolve()).as_posix()
        except ValueError:
            return str(path)

    def unsaved_then(self, action) -> None:
        """Run `action` - after asking, if there are unsaved changes."""

        if not self.model.dirty:
            action()
            return

        def done(key):
            if key == "discard":
                action()

        self.dialog = ConfirmDialog("Ungespeicherte Änderungen", ["Die Änderungen am Level sind noch nicht gespeichert."],
                                    [("cancel", "Zurück"), ("discard", "Verwerfen")], done)

    def save(self) -> None:
        if self.model.path is None:
            self.save_as()
            return
        if self.model.protected:
            self.save_as(note="Mess-Level (Prüfung, Validierung, Test-Serie) werden nie überschrieben.")
            return
        self._write(self.model.path)

    def save_as(self, note: str = "") -> None:
        folders = [OWN_DIR.name]
        if self.model.path is not None and not self.model.protected:
            try:
                rel = self.model.path.resolve().parent.relative_to(LEVELS_DIR.resolve()).as_posix()
                if rel not in folders and rel != ".":
                    folders.append(rel)
            except ValueError:
                pass
        stem = self.model.path.stem if self.model.path is not None else ""
        name = f"{stem}_umbau" if stem else ""
        self.dialog = SaveAsDialog(name, folders, self._save_as_chosen, note)

    def _save_as_chosen(self, folder: str, name: str) -> None:
        path = LEVELS_DIR / folder / f"{name}.txt"
        if is_protected(path):
            self.flash("In Mess-Level-Ordnern wird nicht gespeichert.", RED)
            return
        same = self.model.path is not None and path.resolve() == self.model.path.resolve()
        if path.exists() and not same:
            def done(key):
                if key == "overwrite":
                    self._write(path)

            self.dialog = ConfirmDialog("Datei gibt es schon", [f"{self._rel(path)} existiert bereits."],
                                        [("cancel", "Abbrechen"), ("overwrite", "Überschreiben")], done)
            return
        self._write(path)

    def _write(self, path: Path, confirmed: bool = False) -> None:
        if self.model.problems() and not confirmed:
            def done(key):
                if key == "save":
                    self._write(path, confirmed=True)

            self.dialog = ConfirmDialog("Level hat keine Kiste", ["Ohne Kiste kann das Spiel das Level nicht laden.",
                                                                  "Trotzdem speichern?"],
                                        [("cancel", "Abbrechen"), ("save", "Trotzdem speichern")], done)
            return
        self.keeper.revalidate()
        self.model.save(path)
        self.keeper.seen_version = -1  # the level text is the same, but re-read the saved state
        self.keeper.revalidate()
        sol = solution_path(path)
        if self.keeper.proof.complete:
            if load_solution(path) != self.keeper.proof.actions:
                save_solution(path, self.keeper.proof.actions)
                self.flash(f"Gespeichert: {self._rel(path)} + bewiesene Lösung", GREEN)
            else:
                self.flash(f"Gespeichert: {self._rel(path)}", GREEN)
            return
        self.flash(f"Gespeichert: {self._rel(path)} (Lösbarkeit nicht bewiesen)", YELLOW)
        if sol.exists():
            def done(key):
                if key == "remove":
                    sol.unlink()
                    self.flash(f"Veraltete Lösung entfernt: {self._rel(sol)}", YELLOW)

            self.dialog = ConfirmDialog("Veraltete Lösung", [f"{self._rel(sol)} passt nicht mehr zum geänderten Level.",
                                                             "Entfernen, damit nichts Falsches liegen bleibt?"],
                                        [("remove", "Entfernen"), ("keep", "Behalten")], done)

    # ================================================================ actions
    def flash(self, msg: str, color=TEXT, seconds: float = 4.0) -> None:
        self.toast = (msg, color, time.time() + seconds)

    def do(self, key: str) -> None:
        if key in dict((k, t) for k, t, _, _ in TOOLS):
            self.tool = key
        elif key == "undo":
            if self.model.undo():
                self._edited()
        elif key == "redo":
            if self.model.redo():
                self._edited()
        elif key == "new":
            self.unsaved_then(self.new)
        elif key == "open":
            self.unsaved_then(lambda: setattr(self, "dialog", OpenDialog(
                LEVELS_DIR, self.open, is_protected, lambda p: solution_path(p).exists())))
        elif key == "save":
            self.save()
        elif key == "saveas":
            self.save_as()
        elif key == "check":
            if self.keeper.job is not None:
                self.keeper.stop()
                self.flash("Prüfung gestoppt", YELLOW)
            else:
                self.flash(self.keeper.check(), BLUE)
        elif key == "play":
            self.start_play()
        elif key == "replay":
            self.start_replay()
        elif key == "help":
            self.mode = "help"

    def _edited(self) -> None:
        self.last_edit = time.time()
        self._clamp_scroll()

    def start_play(self) -> None:
        self.keeper.revalidate()
        if self.keeper.level is None:
            self.flash("Erst eine Kiste setzen – ohne Ziel ist das Level nicht spielbar.", RED)
            return
        self.play_sim = Simulation(self.keeper.level)
        self.frames_since_end = 0
        self.mode = "play"

    def start_replay(self) -> None:
        self.keeper.revalidate()
        if self.keeper.level is None or not len(self.keeper.proof):
            self.flash("Noch kein bewiesener Weg – erst „Prüfen“.", YELLOW)
            return
        self.play_sim = Simulation(self.keeper.level)
        self.replay_index = 0
        self.frames_since_end = 0
        self.mode = "replay"

    # ================================================================ events
    def handle(self, event) -> None:
        if event.type == pygame.QUIT:
            self.unsaved_then(self.quit)
            return
        if event.type == pygame.VIDEORESIZE:
            self.layout((max(1200, event.w), max(560, event.h)))
            return
        if self.dialog is not None:
            dialog = self.dialog
            if not dialog.handle(event) and self.dialog is dialog:
                self.dialog = None  # (its callback may already have opened the next dialog)
            return
        if self.mode in ("play", "replay"):
            self._handle_play(event)
            return
        if self.mode == "help":
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.mode = "edit"
            return
        if event.type == pygame.KEYDOWN:
            self._handle_key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._mouse_down(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._mouse_up(event)
        elif event.type == pygame.MOUSEMOTION:
            self._mouse_move(event)
        elif event.type == pygame.MOUSEWHEEL:
            self._wheel(event)

    def quit(self) -> None:
        self.keeper.stop()
        self.running = False
        if self.on_exit is not None:
            self.on_exit()

    def _handle_key(self, event) -> None:
        ctrl = event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
        shift = event.mod & pygame.KMOD_SHIFT
        k = event.key
        if ctrl:
            if k == pygame.K_z:
                self.do("redo" if shift else "undo")
            elif k == pygame.K_y:
                self.do("redo")
            elif k == pygame.K_s:
                self.do("saveas" if shift else "save")
            elif k == pygame.K_o:
                self.do("open")
            elif k == pygame.K_n:
                self.do("new")
            return
        digits = {getattr(pygame, f"K_{i + 1}"): key for i, (key, _, _, _) in enumerate(TOOLS)}
        if k in digits:
            self.tool = digits[k]
        elif k == pygame.K_p:
            self.do("check")
        elif k == pygame.K_t:
            self.do("play")
        elif k == pygame.K_l:
            self.do("replay")
        elif k == pygame.K_F1:
            self.do("help")
        elif k in (pygame.K_LEFT, pygame.K_a):
            self.scroll -= 4 if not shift else 20
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.scroll += 4 if not shift else 20
        elif k == pygame.K_HOME:
            self.scroll = 0
        elif k == pygame.K_END:
            self.scroll = self.model.width
        elif k in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
            self._zoom(1, pygame.mouse.get_pos())
        elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._zoom(-1, pygame.mouse.get_pos())
        elif k in (pygame.K_INSERT, pygame.K_DELETE):
            cell = self.cell_at(pygame.mouse.get_pos())
            if cell is not None:
                done = self.model.insert_column(cell[0]) if k == pygame.K_INSERT else self.model.delete_column(cell[0])
                if done:
                    self._edited()
        elif k == pygame.K_ESCAPE:
            self.unsaved_then(self.quit)
        self._clamp_scroll()

    def _zoom(self, step: int, pos) -> None:
        i = min(range(len(ZOOMS)), key=lambda j: abs(ZOOMS[j] - self.z))
        j = max(0, min(len(ZOOMS) - 1, i + step))
        if j == i:
            return
        anchor = self.scroll + (pos[0] - self.canvas.x) / self.z
        self.z = ZOOMS[j]
        self.scroll = anchor - (pos[0] - self.canvas.x) / self.z
        self._clamp_scroll()

    def _wheel(self, event) -> None:
        if self.minimap_rect.collidepoint(pygame.mouse.get_pos()) or not (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self.scroll -= 3 * (event.y if event.y else -event.x)
            if event.x and event.y:
                self.scroll += 3 * event.x
        else:
            self._zoom(1 if event.y > 0 else -1, pygame.mouse.get_pos())
        self._clamp_scroll()

    def _button_at(self, pos) -> Optional[Button]:
        for b in self.tool_buttons + self.undo_buttons + self.action_buttons:
            if b.enabled and b.rect.collidepoint(pos):
                return b
        return None

    def _mouse_down(self, event) -> None:
        if event.button in (4, 5):
            return  # old-style wheel events (MOUSEWHEEL handles them)
        b = self._button_at(event.pos)
        if b is not None and event.button == 1:
            self.do(b.key)
            return
        if self.minimap_rect.collidepoint(event.pos) and event.button == 1:
            self.minimap_drag = True
            self._minimap_jump(event.pos)
            return
        if event.button == 2:
            self.panning = (event.pos[0], self.scroll)
            return
        cell = self.cell_at(event.pos)
        if cell is None:
            return
        shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
        if self.tool in ("colins", "coldel"):
            if self.tool == "colins" and event.button == 1 or self.tool == "coldel" and event.button == 3:
                done = self.model.insert_column(self.boundary_at(event.pos))
            else:
                done = self.model.delete_column(cell[0])
            if done:
                self._edited()
            return
        tile = dict((k, t) for k, t, _, _ in TOOLS)[self.tool] if event.button == 1 else EMPTY
        if self.tool == "rect" or (shift and tile in (BLOCK, EMPTY)):
            self.rect_start = cell
            self.rect_tile = tile
            self.last_cell = cell
            return
        self.model.begin()
        self.painting = tile
        self.last_cell = cell
        self._paint(cell)

    def _paint(self, cell) -> None:
        if self.model.set(cell[0], cell[1], self.painting):
            self._edited()

    def _mouse_move(self, event) -> None:
        if self.minimap_drag:
            self._minimap_jump(event.pos)
            return
        if self.panning is not None:
            x0, s0 = self.panning
            self.scroll = s0 - (event.pos[0] - x0) / self.z
            self._clamp_scroll()
            return
        cell = self.cell_at(event.pos)
        if self.rect_start is not None:
            if cell is not None:
                self.last_cell = cell
            return
        if self.painting is None or cell is None or self.painting == START:
            if self.painting == START and cell is not None and cell != self.last_cell:
                self.last_cell = cell
                self._paint(cell)
            return
        (c0, r0), (c1, r1) = self.last_cell, cell
        steps = max(abs(c1 - c0), abs(r1 - r0))
        for i in range(1, steps + 1):  # no gaps on fast strokes
            self._paint((round(c0 + (c1 - c0) * i / steps), round(r0 + (r1 - r0) * i / steps)))
        self.last_cell = cell

    def _mouse_up(self, event) -> None:
        if event.button == 2:
            self.panning = None
            return
        self.minimap_drag = False
        if self.rect_start is not None and self.last_cell is not None:
            (c0, r0), (c1, r1) = self.rect_start, self.last_cell
            if self.model.fill(c0, r0, c1, r1, self.rect_tile):
                self._edited()
            self.rect_start = None
        if self.painting is not None:
            self.model.end()
            self.painting = None

    def _minimap_jump(self, pos) -> None:
        scale = self._minimap_scale()
        col = (pos[0] - self.minimap_rect.x) / scale
        self.scroll = col - self.visible_cols / 2
        self._clamp_scroll()

    def _handle_play(self, event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.mode = "edit"
            self.play_sim = None
        elif event.key == pygame.K_r:
            if self.mode == "play":
                self.start_play()
            else:
                self.start_replay()

    # ================================================================ update
    def update(self, dt: float) -> None:
        if self.painting is None and self.rect_start is None and time.time() - self.last_edit >= REVALIDATE_DELAY:
            self.keeper.revalidate()
        self.keeper.update()
        if self.mode in ("play", "replay") and self.play_sim is not None:
            self.acc += dt
            frames = 0
            while self.acc >= 1.0 / FPS and frames < 4:
                self.acc -= 1.0 / FPS
                frames += 1
                self._play_frame()
        else:
            self.acc = 0.0

    def _play_frame(self) -> None:
        sim = self.play_sim
        if sim.status != Status.RUNNING:
            self.frames_since_end += 1
            return
        if self.mode == "play":
            sim.step(keys_to_action(pygame.key.get_pressed()))
            return
        actions = self.keeper.proof.actions
        step = self.replay_index // pf.REPEAT
        if step >= len(actions):
            self.frames_since_end += 1
            return
        sim.step(BOT_ACTIONS_V3[actions[step]])
        self.replay_index += 1

    # ================================================================ drawing
    def draw(self, surface: pygame.Surface) -> None:
        if self.mode in ("play", "replay"):
            self._draw_play(surface)
        else:
            surface.fill(BG)
            self._draw_canvas(surface)
            self._draw_toolbar(surface)
            self._draw_minimap(surface)
            self._draw_status(surface)
            if self.mode == "help":
                self._draw_help(surface)
        if self.dialog is not None:
            self.dialog.draw(surface)
        elif self.mode == "edit":
            self._draw_tooltip(surface)

    def _draw_canvas(self, surface: pygame.Surface) -> None:
        c = self.canvas
        z = self.z
        if self._background is None or self._background.get_size() != c.size:
            bg = pygame.transform.smoothscale(self.assets.background, c.size)
            dark = pygame.Surface(c.size, pygame.SRCALPHA)
            dark.fill((6, 8, 20, 150))
            bg.blit(dark, (0, 0))
            self._background = bg
        surface.blit(self._background, c.topleft)
        surface.set_clip(c)
        top = self.level_top
        c0 = max(0, int(self.scroll))
        c1 = int(self.scroll + self.visible_cols) + 1
        width = self.model.width
        # area right of the level end
        end_x = self.col_x(width)
        if end_x < c.right:
            alpha_rect(surface, (end_x, top, c.right - end_x, ROWS * z), (90, 110, 160, 40))
            for y in range(top, top + ROWS * z, 12):
                pygame.draw.line(surface, (150, 170, 220), (end_x, y), (end_x, y + 6), 2)
            text(surface, "Level-Ende – hier weitermalen verlängert", (end_x + 8, top + 6), 14, MUTED)
        # grid
        grid = pygame.Surface(c.size, pygame.SRCALPHA)
        for col in range(c0, c1 + 1):
            x = self.col_x(col) - c.x
            pygame.draw.line(grid, (255, 255, 255, 60 if col % 10 == 0 else 22), (x, top - c.y), (x, top - c.y + ROWS * z))
        for row in range(ROWS + 1):
            y = top - c.y + row * z
            pygame.draw.line(grid, (255, 255, 255, 22), (0, y), (c.w, y))
        surface.blit(grid, c.topleft)
        # pit marker under the bottom row
        pygame.draw.line(surface, (200, 60, 60), (c.x, top + ROWS * z), (c.right, top + ROWS * z), 2)
        # tiles
        for row in range(ROWS):
            line = self.model.grid[row]
            for col in range(c0, min(c1, width)):
                ch = line[col]
                if ch != EMPTY:
                    self.blit_tile(surface, ch, col, row)
        if not self.model.find(START):  # default start of the game
            x, y = self.world_to_screen(*DEFAULT_SPAWN)
            img = self.sprite(START, z, 110)
            surface.blit(img, (x, y))
            text(surface, "Start (Standard)", (x, y - 16), 13, MUTED)
        self._draw_proof(surface)
        self._draw_hover(surface)
        # ruler
        pygame.draw.rect(surface, PANEL, (c.x, c.y, c.w, RULER_H))
        step = 5 if z >= 32 else 10
        for col in range((c0 // step) * step, c1 + 1, step):
            x = self.col_x(col)
            pygame.draw.line(surface, PANEL_LINE, (x, c.y + RULER_H - 6), (x, c.y + RULER_H))
            text(surface, str(col), (x + 3, c.y + 2), 13, MUTED)
        surface.set_clip(None)

    def _draw_proof(self, surface: pygame.Surface) -> None:
        k = self.keeper
        z = self.z
        top = self.level_top
        points = k.proof.points
        color = {pf.COMPLETE: GREEN, pf.RUNNING: BLUE}.get(k.state, GREEN if len(k.proof) else MUTED)
        r = max(2, z // 14)
        lo, hi = self.scroll * TILE - TILE, (self.scroll + self.visible_cols + 1) * TILE
        for i in range(0, len(points), 2):
            px, py = points[i]
            if lo <= px <= hi:
                pygame.draw.circle(surface, color, self.world_to_screen(px, py), r)
        if k.state == pf.STUCK:
            col = k.stuck_x // TILE
            x = self.col_x(col)
            alpha_rect(surface, (x, top, 2 * z, ROWS * z), (238, 60, 60, 70))
            pygame.draw.rect(surface, RED, (x, top, 2 * z, ROWS * z), 2)
            text(surface, "kein Weg gefunden", (x + 4, top + 4), 14, RED, True)
            for cx, cy, cw, ch in k.level.chests if k.level is not None else []:
                sx, sy = self.world_to_screen(cx, cy)
                pygame.draw.rect(surface, RED, (sx - 3, sy - 3, cw * z // TILE + 6, ch * z // TILE + 6), 3, border_radius=4)
        end = k.proof.end_point
        if end is not None and len(k.proof) and not k.proof.complete:
            sx, sy = self.world_to_screen(*end)
            ring = {pf.RUNNING: BLUE, pf.STUCK: RED}.get(k.state, YELLOW)
            pulse = 3 * abs((pygame.time.get_ticks() // 60) % 10 - 5) if k.state == pf.RUNNING else 0
            pygame.draw.circle(surface, ring, (sx, sy), z // 2 + pulse, 3)
            label = {pf.RUNNING: "prüfe …", pf.STUCK: "bewiesen bis hier"}.get(k.state, "bewiesen bis hier – danach geändert")
            text(surface, label, (sx + z // 2 + 6, sy - 9), 14, ring, True)
        elif k.state == pf.RUNNING and not len(k.proof):
            x, y = self.world_to_screen(*self._start_px())
            pulse = 3 * abs((pygame.time.get_ticks() // 60) % 10 - 5)
            pygame.draw.circle(surface, BLUE, (x, y), z // 2 + pulse, 3)

    def _start_px(self) -> Tuple[int, int]:
        level = self.keeper.level
        sx, sy = level.spawn if level is not None else DEFAULT_SPAWN
        return sx + 20, sy + 30

    def _draw_hover(self, surface: pygame.Surface) -> None:
        pos = pygame.mouse.get_pos()
        z, top = self.z, self.level_top
        if self.rect_start is not None and self.last_cell is not None:
            (c0, r0), (c1, r1) = self.rect_start, self.last_cell
            x0, x1 = self.col_x(min(c0, c1)), self.col_x(max(c0, c1) + 1)
            y0, y1 = top + min(r0, r1) * z, top + (max(r0, r1) + 1) * z
            color = (82, 156, 255, 80) if self.rect_tile == BLOCK else (238, 84, 84, 80)
            alpha_rect(surface, (x0, y0, x1 - x0, y1 - y0), color)
            pygame.draw.rect(surface, ACCENT if self.rect_tile == BLOCK else RED, (x0, y0, x1 - x0, y1 - y0), 2)
            return
        cell = self.cell_at(pos)
        if cell is None or self.dialog is not None or self.mode != "edit":
            return
        col, row = cell
        if self.tool == "colins":
            x = self.col_x(self.boundary_at(pos))
            pygame.draw.line(surface, GREEN, (x, top), (x, top + ROWS * z), 4)
            return
        if self.tool == "coldel":
            x = self.col_x(col)
            alpha_rect(surface, (x, top, z, ROWS * z), (238, 84, 84, 70))
            return
        rect = pygame.Rect(self.col_x(col), top + row * z, z, z)
        tile = dict((k, t) for k, t, _, _ in TOOLS)[self.tool]
        if tile == EMPTY:
            pygame.draw.rect(surface, RED, rect, 2)
        else:
            if self.painting is None:
                self.blit_tile(surface, tile, col, row, 130)
            pygame.draw.rect(surface, ACCENT, rect, 2)
        text(surface, f"{col},{row}", (rect.x + 2, rect.bottom + 2), 12, MUTED)

    def _draw_toolbar(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, PANEL, (0, 0, self.size[0], TOOLBAR_H))
        pygame.draw.line(surface, PANEL_LINE, (0, TOOLBAR_H - 1), (self.size[0], TOOLBAR_H - 1))
        mouse = pygame.mouse.get_pos()
        running = self.keeper.job is not None
        for b in self.action_buttons:
            if b.key == "check":
                b.label = "Stopp" if running else ("Weiterprüfen" if len(self.keeper.proof) and not self.keeper.proof.complete
                                                    else "Prüfen")
            if b.key == "replay":
                b.enabled = bool(len(self.keeper.proof))
        for i, b in enumerate(self.tool_buttons):
            b.active = b.key == self.tool
            b.draw(surface, b.rect.collidepoint(mouse))
            text(surface, str(i + 1), (b.rect.x + 4, b.rect.y + 2), 12, MUTED)
        for b in self.undo_buttons + self.action_buttons:
            b.draw(surface, b.rect.collidepoint(mouse))

    def _minimap_scale(self) -> float:
        return self.minimap_rect.w / max(self.model.width + 12, self.visible_cols)

    def _draw_minimap(self, surface: pygame.Surface) -> None:
        m = self.minimap_rect
        panel(surface, m, (20, 22, 34), 6)
        key = (self.model.version, m.size)
        if self._minimap[0] != key:
            small = pygame.Surface((self.model.width, ROWS))
            small.fill((20, 22, 34))
            colors = {BLOCK: (150, 156, 186), ENEMY: (238, 84, 84), CHEST: (244, 192, 64), START: (72, 204, 122)}
            for r, line in enumerate(self.model.grid):
                for c, ch in enumerate(line):
                    if ch != EMPTY:
                        small.set_at((c, r), colors[ch])
            scale = self._minimap_scale()
            w = max(1, int(self.model.width * scale))
            self._minimap = (key, pygame.transform.scale(small, (w, m.h - 4)))
        surface.blit(self._minimap[1], (m.x, m.y + 2))
        scale = self._minimap_scale()
        k = self.keeper
        if len(k.proof):
            color = {pf.COMPLETE: GREEN, pf.RUNNING: BLUE, pf.STUCK: GREEN}.get(k.state, YELLOW)
            pygame.draw.line(surface, color, (m.x, m.bottom - 2), (m.x + int(k.proven_col * scale), m.bottom - 2), 3)
        if k.state == pf.STUCK:
            x = m.x + int(k.stuck_x / TILE * scale)
            pygame.draw.rect(surface, RED, (x, m.y, max(3, int(2 * scale)), m.h), 0)
        view = pygame.Rect(m.x + int(self.scroll * scale), m.y, max(6, int(self.visible_cols * scale)), m.h)
        pygame.draw.rect(surface, ACCENT, view.clip(m), 2, border_radius=4)

    def status_line(self) -> Tuple[str, tuple]:
        k = self.keeper
        col = k.proven_col
        seconds = len(k.proof) * pf.REPEAT / FPS
        if k.state == pf.INVALID:
            return "Keine Kiste – das Level ist so nicht spielbar. Werkzeug 3 (Kiste) wählen.", RED
        if k.state == pf.RUNNING:
            return f"Prüfe … bewiesen bis Spalte {col}. Du kannst nebenher weiterbauen.", BLUE
        if k.state == pf.COMPLETE:
            return f"Lösbar: Der Bot-Weg bis zur Kiste ist bewiesen ({seconds:.1f} s Spielzeit).", GREEN
        if k.state == pf.STUCK:
            where = f"bewiesen bis Spalte {col}, " if len(k.proof) else ""
            return (f"Kein Weg gefunden ab Spalte {k.stuck_x // TILE} ({where}Suchbudget {k.budget // 1000}k). "
                    "Umbauen – oder ohne Änderung nochmal prüfen = gründlicher.", RED)
        if k.state == pf.CHANGED:
            return f"Bewiesen bis Spalte {col}, danach geändert. „Weiterprüfen“ (P) macht ab dort weiter.", YELLOW
        if k.state == pf.ERROR:
            return f"Prüfung abgebrochen: {k.message}", RED
        return "Noch nicht geprüft. „Prüfen“ (P) sucht im Hintergrund einen Weg für den Bot.", MUTED

    def _draw_status(self, surface: pygame.Surface) -> None:
        s = self.status_rect
        pygame.draw.rect(surface, PANEL, s)
        pygame.draw.line(surface, PANEL_LINE, s.topleft, s.topright)
        msg, color = self.status_line()
        pygame.draw.circle(surface, color, (s.x + 16, s.centery), 7)
        text(surface, msg, (s.x + 30, s.centery), 16, color, True, "midleft")
        name = self._rel(self.model.path) if self.model.path else "neues Level"
        flags = (" *" if self.model.dirty else "") + ("  [Mess-Level]" if self.model.protected else "")
        text(surface, f"{name}{flags}   ·   {self.model.used_width} Spalten   ·   Zoom {self.z}px",
                     (s.right - 12, s.centery), 15, MUTED, anchor="midright")
        toast, tcolor, until = self.toast
        if toast and time.time() < until:
            f = font(16, True)
            w = f.size(toast)[0] + 28
            rect = pygame.Rect(0, 0, w, 36)
            rect.midbottom = (self.size[0] // 2, self.minimap_rect.y - 10)
            panel(surface, rect, (12, 14, 22), 10, tcolor)
            text(surface, toast, rect.center, 16, tcolor, True, "center")

    def _draw_tooltip(self, surface: pygame.Surface) -> None:
        pos = pygame.mouse.get_pos()
        b = next((b for b in self.tool_buttons + self.undo_buttons + self.action_buttons if b.rect.collidepoint(pos)), None)
        if b is None:
            self.hover_since = (None, 0.0)
            return
        if self.hover_since[0] is not b:
            self.hover_since = (b, time.time())
        if time.time() - self.hover_since[1] > 0.35:
            tooltip(surface, b.tooltip, pos)

    def _draw_help(self, surface: pygame.Surface) -> None:
        alpha_rect(surface, surface.get_rect(), (0, 0, 0, 170))
        rect = pygame.Rect(0, 0, 820, 560)
        rect.center = (self.size[0] // 2, self.size[1] // 2)
        panel(surface, rect, PANEL, 12, ACCENT)
        text(surface, "Level-Editor – Bedienung", (rect.x + 24, rect.y + 18), 22, TEXT, True)
        lines = [
            ("Linke Maustaste", "mit dem gewählten Werkzeug malen (gedrückt halten und ziehen)"),
            ("Rechte Maustaste", "radieren"),
            ("Umschalt + Ziehen", "Rechteck aus Blöcken (rechts: Rechteck löschen)"),
            ("1 – 8", "Werkzeuge: Block, Gegner, Kiste, Start, Radierer, Rechteck, Spalte +/−"),
            ("Mausrad / A D / ← →", "nach links/rechts scrollen (Umschalt: schneller)"),
            ("Strg + Mausrad, + −", "zoomen"),
            ("Mittlere Maustaste", "Ansicht ziehen; Klick in die Übersicht unten springt dorthin"),
            ("Einfg / Entf", "Spalte unter der Maus einfügen / löschen"),
            ("Strg+Z / Strg+Y", "rückgängig / wiederholen"),
            ("Strg+S", "altes Level aktualisieren (Mess-Level: nur als neu)"),
            ("Strg+Umschalt+S", "als neues Level speichern (Standard: levels/eigene/)"),
            ("P", "prüfen: echter Bot-Weg wird gesucht, weiterbauen geht dabei"),
            ("T / L", "selbst testspielen / bewiesenen Weg abspielen (Esc zurück, R neu)"),
            ("Esc", "beenden"),
        ]
        for i, (key, desc) in enumerate(lines):
            y = rect.y + 66 + 30 * i
            text(surface, key, (rect.x + 24, y), 16, ACCENT, True)
            text(surface, desc, (rect.x + 250, y), 16, TEXT)
        text(surface, "Grün = Weg bewiesen · Gelb = bis hier bewiesen, danach geändert · Rot = kein Weg gefunden",
             (rect.x + 24, rect.bottom - 64), 15, MUTED)
        text(surface, "Taste oder Klick schließt die Hilfe", (rect.x + 24, rect.bottom - 36), 15, MUTED)

    def _draw_play(self, surface: pygame.Surface) -> None:
        from jumpnrun.render.renderer import Renderer

        if self._renderer is None:
            self._renderer = Renderer()
            self._play_surface = pygame.Surface((SCREEN_W, SCREEN_H))
        sim = self.play_sim
        self._renderer.draw(self._play_surface, sim, self.frames_since_end)
        if self.mode == "replay":
            done = self.replay_index // pf.REPEAT >= len(self.keeper.proof.actions)
            if done and sim.status == Status.RUNNING:
                self._renderer.text(self._play_surface, "Bis hierher bewiesen", color=(244, 192, 64))
        sw, sh = surface.get_size()
        scale = min(sw / SCREEN_W, sh / SCREEN_H)
        size = (int(SCREEN_W * scale), int(SCREEN_H * scale))
        surface.fill((0, 0, 0))
        surface.blit(pygame.transform.smoothscale(self._play_surface, size), ((sw - size[0]) // 2, (sh - size[1]) // 2))
        label = "Testspiel – Esc zurück zum Editor, R neu" if self.mode == "play" else "Bewiesener Bot-Weg – Esc zurück, R von vorn"
        rect = pygame.Rect(0, 0, font(16, True).size(label)[0] + 28, 34)
        rect.midtop = (sw // 2, 10)
        panel(surface, rect, (12, 14, 22), 10, ACCENT)
        text(surface, label, rect.center, 16, TEXT, True, "center")

    # ================================================================ main loop
    def run(self) -> None:
        clock = pygame.time.Clock()
        screen = pygame.display.get_surface()
        while self.running:
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                self.handle(event)
                if event.type == pygame.VIDEORESIZE:
                    screen = pygame.display.set_mode(self.size, pygame.RESIZABLE)
            self.update(dt)
            self.draw(screen)
            caption = f"Level-Editor – {self.model.path.name if self.model.path else 'neues Level'}"
            pygame.display.set_caption(caption + (" *" if self.model.dirty else ""))
            pygame.display.flip()
        self.keeper.stop()


def main(argv: Optional[List[str]] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Level-Editor für Space Pirate")
    parser.add_argument("level", nargs="?", help="Level-Datei zum Bearbeiten (ohne: neues Level)")
    args = parser.parse_args(argv)
    pygame.init()
    try:
        desk_w, desk_h = pygame.display.get_desktop_sizes()[0]
    except (pygame.error, IndexError, AttributeError):
        desk_w, desk_h = SCREEN_W, SCREEN_H
    size = (min(SCREEN_W, max(1200, desk_w - 40)), min(SCREEN_H, max(560, desk_h - 90)))
    pygame.display.set_mode(size, pygame.RESIZABLE)
    pygame.display.set_caption("Level-Editor")
    app = EditorApp(args.level, size)
    app.run()
    pygame.quit()
