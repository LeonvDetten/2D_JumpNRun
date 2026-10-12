"""App controls on top of the shared UI kit: tabs, toggles, sliders, choice chips, small buttons."""

from __future__ import annotations

from typing import List, Optional, Sequence

import pygame

from jumpnrun.app.gfx import CYAN, GOLD, glass_panel
from jumpnrun.ui.widgets import ACCENT, MUTED, PANEL, PANEL_HI, PANEL_LINE, TEXT, font, panel, text


class SmallButton:
    def __init__(self, key: str, label: str, rect=None, accent: bool = False):
        self.key, self.label, self.accent = key, label, accent
        self.rect = pygame.Rect(rect) if rect is not None else pygame.Rect(0, 0, 160, 46)
        self.enabled = True

    def draw(self, surface: pygame.Surface, mouse) -> None:
        hover = self.enabled and self.rect.collidepoint(mouse)
        if self.accent and self.enabled:
            color = (60, 130, 230) if hover else (40, 96, 190)
            border = CYAN
        else:
            color, border = (PANEL_HI if hover else PANEL), (ACCENT if hover else PANEL_LINE)
        panel(surface, self.rect, color, 10, border)
        text(surface, self.label, self.rect.center, 19, TEXT if self.enabled else MUTED, True, "center")

    def hit(self, pos) -> bool:
        return self.enabled and self.rect.collidepoint(pos)


class Tabs:
    def __init__(self, labels: Sequence[str], pos, height: int = 44):
        self.labels = list(labels)
        self.index = 0
        self.rects: List[pygame.Rect] = []
        x, y = pos
        for label in self.labels:
            w = font(19, True).size(label)[0] + 40
            self.rects.append(pygame.Rect(x, y, w, height))
            x += w + 8

    @property
    def current(self) -> str:
        return self.labels[self.index]

    def handle_click(self, pos) -> bool:
        for i, r in enumerate(self.rects):
            if r.collidepoint(pos):
                self.index = i
                return True
        return False

    def draw(self, surface: pygame.Surface, mouse) -> None:
        for i, (label, r) in enumerate(zip(self.labels, self.rects)):
            active = i == self.index
            if active:
                glass_panel(surface, r, 235, CYAN, 12)
            else:
                panel(surface, r, PANEL_HI if r.collidepoint(mouse) else PANEL, 12, PANEL_LINE)
            text(surface, label, r.center, 19, TEXT if active else MUTED, True, "center")


class Toggle:
    def __init__(self, rect, value: bool):
        self.rect = pygame.Rect(rect)
        self.value = value

    def handle_click(self, pos) -> bool:
        if self.rect.collidepoint(pos):
            self.value = not self.value
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        r = self.rect
        pygame.draw.rect(surface, (60, 150, 255) if self.value else (60, 64, 84), r, border_radius=r.h // 2)
        knob_x = r.right - r.h // 2 if self.value else r.x + r.h // 2
        pygame.draw.circle(surface, (240, 244, 255), (knob_x, r.centery), r.h // 2 - 4)
        text(surface, "An" if self.value else "Aus", (r.right + 14, r.centery), 17, TEXT if self.value else MUTED,
             True, "midleft")


class Slider:
    def __init__(self, rect, value: float, show_percent: bool = True):
        self.rect = pygame.Rect(rect)
        self.value = float(value)
        self.dragging = False
        self.show_percent = show_percent

    def _set(self, x: int) -> None:
        self.value = max(0.0, min(1.0, (x - self.rect.x) / self.rect.w))

    def handle(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.inflate(0, 24).collidepoint(event.pos):
            self.dragging = True
            self._set(event.pos[0])
            return True
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._set(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and self.dragging:
            self.dragging = False
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        r = self.rect
        pygame.draw.rect(surface, (50, 54, 76), r, border_radius=r.h // 2)
        fill = r.copy()
        fill.w = max(r.h, int(r.w * self.value))
        pygame.draw.rect(surface, CYAN, fill, border_radius=r.h // 2)
        pygame.draw.circle(surface, (240, 244, 255), (r.x + int(r.w * self.value), r.centery), r.h)
        if self.show_percent:
            text(surface, f"{int(round(self.value * 100))} %", (r.right + 18, r.centery), 17, TEXT, True, "midleft")


class Chips:
    """One-of-n choice (e.g. head start 0/2/5/10 s)."""

    def __init__(self, pos, options: Sequence, labels: Optional[Sequence[str]] = None, value=None):
        self.options = list(options)
        self.labels = list(labels) if labels else [str(o) for o in options]
        self.value = value if value in self.options else self.options[0]
        self.rects = []
        x, y = pos
        for label in self.labels:
            w = font(17, True).size(label)[0] + 30
            self.rects.append(pygame.Rect(x, y, w, 38))
            x += w + 8

    def handle_click(self, pos) -> bool:
        for option, r in zip(self.options, self.rects):
            if r.collidepoint(pos):
                self.value = option
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        for option, label, r in zip(self.options, self.labels, self.rects):
            active = option == self.value
            panel(surface, r, (40, 96, 190) if active else PANEL, 19, GOLD if active else PANEL_LINE)
            text(surface, label, r.center, 17, TEXT if active else MUTED, True, "center")
