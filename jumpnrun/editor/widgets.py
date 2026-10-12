"""Small pygame UI kit for the level editor: theme, fonts, buttons, dialogs."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

import pygame

# ---------------------------------------------------------------- theme
BG = (16, 18, 28)
PANEL = (28, 32, 46)
PANEL_HI = (44, 50, 72)
PANEL_LINE = (62, 70, 98)
TEXT = (228, 232, 242)
MUTED = (140, 150, 172)
ACCENT = (82, 156, 255)
GREEN = (72, 204, 122)
RED = (238, 84, 84)
YELLOW = (244, 192, 64)
BLUE = (96, 170, 255)

_FONTS = {}


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _FONTS:
        pygame.font.init()
        _FONTS[key] = pygame.font.SysFont("dejavusans,segoeui,arial,helvetica", size, bold=bold)
    return _FONTS[key]


def text(surface: pygame.Surface, msg: str, pos, size: int = 16, color=TEXT, bold: bool = False,
         anchor: str = "topleft") -> pygame.Rect:
    image = font(size, bold).render(msg, True, color)
    rect = image.get_rect(**{anchor: pos})
    surface.blit(image, rect)
    return rect


def panel(surface: pygame.Surface, rect: pygame.Rect, color=PANEL, radius: int = 8, border=PANEL_LINE) -> None:
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border is not None:
        pygame.draw.rect(surface, border, rect, width=1, border_radius=radius)


def alpha_rect(surface: pygame.Surface, rect, rgba) -> None:
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill(rgba)
    surface.blit(s, rect.topleft)


# ---------------------------------------------------------------- buttons
class Button:
    def __init__(self, key: str, label: str = "", tooltip: str = "", icon: Optional[Callable] = None,
                 width: Optional[int] = None, accent: bool = False):
        self.key = key
        self.label = label
        self.tooltip = tooltip
        self.icon = icon  # icon(surface, rect) draws into the button
        self.width = width
        self.accent = accent
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.enabled = True
        self.active = False  # selected tool
        self.pad = 28

    def measure(self, height: int) -> int:
        if self.width:
            return self.width
        return font(17, True).size(self.label)[0] + self.pad

    def draw(self, surface: pygame.Surface, hover: bool) -> None:
        if self.active:
            color, border = PANEL_HI, ACCENT
        elif self.accent and self.enabled:
            color, border = (40, 92, 170) if not hover else (52, 112, 200), ACCENT
        else:
            color, border = (PANEL_HI if hover and self.enabled else PANEL), PANEL_LINE
        panel(surface, self.rect, color, 8, border)
        if self.active:
            pygame.draw.rect(surface, ACCENT, self.rect, width=2, border_radius=8)
        if self.icon is not None:
            self.icon(surface, self.rect.inflate(-12, -12))
        if self.label:
            text(surface, self.label, self.rect.center, 17, TEXT if self.enabled else MUTED, True, "center")


def tooltip(surface: pygame.Surface, msg: str, pos) -> None:
    f = font(15)
    w, h = f.size(msg)
    rect = pygame.Rect(0, 0, w + 16, h + 10)
    rect.topleft = (pos[0] + 14, pos[1] + 18)
    rect.right = min(rect.right, surface.get_width() - 4)
    if rect.bottom > surface.get_height() - 4:
        rect.bottom = pos[1] - 8
    panel(surface, rect, (12, 14, 22), 6, ACCENT)
    text(surface, msg, (rect.x + 8, rect.y + 5), 15)


# ---------------------------------------------------------------- dialogs
class Dialog:
    """Modal window. handle() returns False when the dialog is finished."""

    width = 640

    def __init__(self, title: str):
        self.title = title
        self.rect = pygame.Rect(0, 0, self.width, 240)
        self.buttons: List[Button] = []
        self.hover: Optional[Button] = None

    def layout(self, size, height: int) -> None:
        self.rect = pygame.Rect(0, 0, min(self.width, size[0] - 40), min(height, size[1] - 40))
        self.rect.center = (size[0] // 2, size[1] // 2)
        x = self.rect.right - 20
        for b in reversed(self.buttons):
            w = b.measure(40)
            b.rect = pygame.Rect(x - w, self.rect.bottom - 58, w, 40)
            x -= w + 12

    def draw_frame(self, surface: pygame.Surface) -> None:
        alpha_rect(surface, surface.get_rect(), (0, 0, 0, 150))
        panel(surface, self.rect, PANEL, 12, ACCENT)
        text(surface, self.title, (self.rect.x + 22, self.rect.y + 16), 22, TEXT, True)
        mouse = pygame.mouse.get_pos()
        for b in self.buttons:
            b.draw(surface, b.rect.collidepoint(mouse))

    def button_at(self, pos) -> Optional[Button]:
        return next((b for b in self.buttons if b.enabled and b.rect.collidepoint(pos)), None)


class ConfirmDialog(Dialog):
    """Message with buttons. `on_result(key)`; Esc gives None, Enter the first (default) button."""

    def __init__(self, title: str, lines: Sequence[str], buttons: Sequence[Tuple[str, str]],
                 on_result: Callable[[Optional[str]], None]):
        super().__init__(title)
        self.lines = list(lines)
        self.buttons = [Button(k, label, accent=(i == 0)) for i, (k, label) in enumerate(buttons)]
        self.on_result = on_result

    def handle(self, event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.on_result(None)
                return False
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.on_result(self.buttons[0].key)
                return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            b = self.button_at(event.pos)
            if b is not None:
                self.on_result(b.key)
                return False
        return True

    def draw(self, surface: pygame.Surface) -> None:
        self.layout(surface.get_size(), 150 + 26 * len(self.lines))
        self.draw_frame(surface)
        for i, line in enumerate(self.lines):
            text(surface, line, (self.rect.x + 22, self.rect.y + 58 + 26 * i), 17, TEXT)


class OpenDialog(Dialog):
    """List of all level files, grouped by folder."""

    width = 860

    def __init__(self, levels_dir: Path, on_open: Callable[[Path], None], is_protected, has_solution):
        super().__init__("Level öffnen")
        self.on_open = on_open
        self.rows: List[Tuple[str, Optional[Path], str]] = []  # (label, path or None for a folder, info)
        files = sorted(levels_dir.rglob("*.txt"), key=lambda p: (p.parent.relative_to(levels_dir).as_posix(), p.name))
        folder = None
        for p in files:
            rel = p.parent.relative_to(levels_dir).as_posix()
            if rel != folder:
                folder = rel
                self.rows.append((f"levels/{rel}", None, ""))
            try:
                width = max((len(line.rstrip()) for line in p.read_text(encoding="utf-8").split("\n")), default=0)
            except (OSError, UnicodeDecodeError):
                continue
            info = [f"{width} Spalten"]
            if has_solution(p):
                info.append("Lösung gespeichert")
            if is_protected(p):
                info.append("Mess-Level: nur „Speichern als“")
            self.rows.append((p.stem, p, " · ".join(info)))
        self.scroll = 0
        self.row_h = 30
        self.buttons = [Button("cancel", "Abbrechen")]

    def _list_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.x + 16, self.rect.y + 56, self.rect.w - 32, self.rect.h - 56 - 72)

    def _row_at(self, pos) -> Optional[int]:
        lr = self._list_rect()
        if not lr.collidepoint(pos):
            return None
        i = (pos[1] - lr.y) // self.row_h + self.scroll
        return i if 0 <= i < len(self.rows) else None

    def handle(self, event) -> bool:
        lr = self._list_rect()
        visible = max(1, lr.h // self.row_h)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return False
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(len(self.rows) - visible, self.scroll - 3 * event.y))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.button_at(event.pos) is not None:
                return False
            i = self._row_at(event.pos)
            if i is not None and self.rows[i][1] is not None:
                self.on_open(self.rows[i][1])
                return False
        return True

    def draw(self, surface: pygame.Surface) -> None:
        self.layout(surface.get_size(), surface.get_height() - 60)
        self.draw_frame(surface)
        lr = self._list_rect()
        visible = max(1, lr.h // self.row_h)
        self.scroll = max(0, min(self.scroll, len(self.rows) - visible))
        mouse_row = self._row_at(pygame.mouse.get_pos())
        surface.set_clip(lr)
        for k in range(visible + 1):
            i = self.scroll + k
            if i >= len(self.rows):
                break
            label, path, info = self.rows[i]
            y = lr.y + k * self.row_h
            if path is None:
                text(surface, label, (lr.x + 6, y + 6), 16, ACCENT, True)
                continue
            if i == mouse_row:
                pygame.draw.rect(surface, PANEL_HI, (lr.x, y, lr.w, self.row_h - 2), border_radius=6)
            text(surface, label, (lr.x + 28, y + 5), 17, TEXT)
            text(surface, info, (lr.right - 10, y + 7), 14, YELLOW if "Mess" in info else MUTED, anchor="topright")
        surface.set_clip(None)
        if len(self.rows) > visible:  # scroll bar
            h = max(30, lr.h * visible // len(self.rows))
            y = lr.y + (lr.h - h) * self.scroll // max(1, len(self.rows) - visible)
            pygame.draw.rect(surface, PANEL_LINE, (lr.right + 4, y, 6, h), border_radius=3)
        text(surface, "Klick öffnet · Mausrad scrollt · Esc schließt", (self.rect.x + 22, self.rect.bottom - 46), 14, MUTED)


NAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-äöüÄÖÜß")


class SaveAsDialog(Dialog):
    """File name input plus a choice of folder."""

    width = 700

    def __init__(self, name: str, folders: Sequence[str], on_save: Callable[[str, str], None], note: str = ""):
        super().__init__("Speichern als neues Level")
        self.name = name
        self.folders = list(folders)
        self.folder = self.folders[0]
        self.on_save = on_save
        self.note = note
        self.chips: List[Tuple[pygame.Rect, str]] = []
        self.buttons = [Button("save", "Speichern", accent=True), Button("cancel", "Abbrechen")]
        pygame.key.start_text_input()

    def _done(self, save: bool) -> bool:
        pygame.key.stop_text_input()
        if save and self.name:
            self.on_save(self.folder, self.name)
        return False

    def handle(self, event) -> bool:
        if event.type == pygame.TEXTINPUT:
            self.name += "".join(ch for ch in event.text if ch in NAME_CHARS)
            self.name = self.name[:60]
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return self._done(False)
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self._done(bool(self.name))
            if event.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            b = self.button_at(event.pos)
            if b is not None:
                return self._done(b.key == "save" and bool(self.name))
            for rect, folder in self.chips:
                if rect.collidepoint(event.pos):
                    self.folder = folder
        return True

    def draw(self, surface: pygame.Surface) -> None:
        self.layout(surface.get_size(), 300)
        self.buttons[0].enabled = bool(self.name)
        self.draw_frame(surface)
        x0, y = self.rect.x + 22, self.rect.y + 60
        text(surface, "Name:", (x0, y + 8), 17, MUTED)
        box = pygame.Rect(x0 + 90, y, self.rect.w - 134, 38)
        panel(surface, box, (14, 16, 24), 6, ACCENT)
        r = text(surface, self.name, (box.x + 10, box.y + 8), 18)
        if pygame.time.get_ticks() // 500 % 2:
            pygame.draw.line(surface, TEXT, (r.right + 2, box.y + 8), (r.right + 2, box.bottom - 8), 2)
        y += 54
        text(surface, "Ordner:", (x0, y + 6), 17, MUTED)
        self.chips = []
        x = x0 + 90
        for folder in self.folders:
            w = font(16, True).size(folder)[0] + 24
            rect = pygame.Rect(x, y, w, 32)
            panel(surface, rect, PANEL_HI if folder == self.folder else PANEL, 16, ACCENT if folder == self.folder else PANEL_LINE)
            text(surface, folder, rect.center, 16, TEXT, True, "center")
            self.chips.append((rect, folder))
            x += w + 10
        y += 46
        text(surface, f"→ levels/{self.folder}/{self.name or '…'}.txt", (x0, y), 16, TEXT)
        if self.note:
            text(surface, self.note, (x0, y + 26), 14, YELLOW)
