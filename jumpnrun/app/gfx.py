"""Drawing helpers for the app screens: space background, logo, menu buttons, level thumbnails, particles."""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pygame

from jumpnrun.core.constants import ROWS, SCREEN_H, SCREEN_W
from jumpnrun.core.level import Level
from jumpnrun.ui.widgets import ACCENT, MUTED, PANEL_LINE, TEXT, font

GOLD = (255, 204, 84)
GOLD_DARK = (170, 110, 30)
CYAN = (92, 224, 255)
NIGHT = (8, 10, 24)


class SpaceBackground:
    """The game's background image, slowly drifting, with three layers of twinkling stars on top."""

    def __init__(self, image: pygame.Surface, dim: int = 120, seed: int = 7):
        w, h = SCREEN_W, SCREEN_H
        self.image = pygame.transform.smoothscale(image, (int(w * 1.15), int(h * 1.15)))
        shade = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
        shade.fill((4, 6, 18, dim))
        self.image.blit(shade, (0, 0))
        rng = random.Random(seed)
        self.stars = [(rng.uniform(0, w), rng.uniform(0, h), rng.choice((0.2, 0.5, 1.0)), rng.uniform(0, 6.28))
                      for _ in range(140)]
        self.t = 0.0

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        ox = (math.sin(self.t * 0.05) * 0.5 + 0.5) * (self.image.get_width() - w)
        oy = (math.cos(self.t * 0.037) * 0.5 + 0.5) * (self.image.get_height() - h)
        surface.blit(self.image, (-ox, -oy))
        for x, y, speed, phase in self.stars:
            sx = (x - self.t * 12 * speed) % w
            glow = 0.5 + 0.5 * math.sin(self.t * (1.5 + speed * 2) + phase)
            c = int(120 + 135 * glow * speed)
            r = 1 if speed < 1 else 2
            pygame.draw.circle(surface, (c, c, min(255, c + 30)), (int(sx), int(y)), r)


def vertical_gradient(size: Tuple[int, int], top, bottom) -> pygame.Surface:
    surf = pygame.Surface(size, pygame.SRCALPHA)
    h = max(1, size[1] - 1)
    for y in range(size[1]):
        k = y / h
        color = [int(top[i] + (bottom[i] - top[i]) * k) for i in range(len(top))]
        pygame.draw.line(surf, color, (0, y), (size[0], y))
    return surf


def glow(surface_in: pygame.Surface, radius: int = 8) -> pygame.Surface:
    """Cheap blur (scale down and up) for glow effects."""

    w, h = surface_in.get_size()
    small = pygame.transform.smoothscale(surface_in, (max(1, w // radius), max(1, h // radius)))
    return pygame.transform.smoothscale(small, (w, h))


def fancy_text(msg: str, size: int, top=(255, 240, 180), bottom=GOLD_DARK, outline=(30, 16, 6), glow_color=None,
               outline_px: int = 4) -> pygame.Surface:
    """Text with a vertical colour gradient, a dark outline and an optional glow."""

    f = font(size, True)
    base = f.render(msg, True, (255, 255, 255))
    w, h = base.get_size()
    pad = outline_px + 18
    out = pygame.Surface((w + 2 * pad, h + 2 * pad), pygame.SRCALPHA)
    if glow_color is not None:
        g = f.render(msg, True, glow_color)
        layer = pygame.Surface(out.get_size(), pygame.SRCALPHA)
        layer.blit(g, (pad, pad))
        out.blit(glow(layer, 6), (0, 0))
        out.blit(glow(layer, 3), (0, 0))
    dark = f.render(msg, True, outline)
    for dx in range(-outline_px, outline_px + 1, 2):
        for dy in range(-outline_px, outline_px + 1, 2):
            if dx * dx + dy * dy <= outline_px * outline_px + 1:
                out.blit(dark, (pad + dx, pad + dy))
    fill = base.copy()
    fill.blit(vertical_gradient((w, h), top, bottom), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    out.blit(fill, (pad, pad))
    return out


class Logo:
    """'SPACE PIRATE' title with gradient, outline, glow and a gentle float."""

    def __init__(self, assets):
        self.space = fancy_text("SPACE", 84, (210, 250, 255), (60, 150, 230), (6, 14, 40), CYAN)
        self.pirate = fancy_text("PIRATE", 112, (255, 246, 200), GOLD_DARK, (34, 16, 4), (255, 170, 60))
        hero = assets.player["IDLE"][1][0]
        self.hero = pygame.transform.smoothscale(hero, (hero.get_width() * 2, hero.get_height() * 2))

    def draw(self, surface: pygame.Surface, center: Tuple[int, int], t: float, scale: float = 1.0) -> pygame.Rect:
        cx, cy = center
        bob = math.sin(t * 1.6) * 6
        s, p = self.space, self.pirate
        if scale != 1.0:
            s = pygame.transform.smoothscale(s, (int(s.get_width() * scale), int(s.get_height() * scale)))
            p = pygame.transform.smoothscale(p, (int(p.get_width() * scale), int(p.get_height() * scale)))
        r1 = s.get_rect(midbottom=(cx, cy - 20 * scale + bob))
        r2 = p.get_rect(midtop=(cx, cy - 46 * scale + bob))
        surface.blit(s, r1)
        surface.blit(p, r2)
        return r1.union(r2)


class MenuButton:
    """Large glassy menu button with hover slide and glow."""

    def __init__(self, key: str, label: str, hint: str = "", icon: Optional[pygame.Surface] = None):
        self.key, self.label, self.hint, self.icon = key, label, hint, icon
        self.rect = pygame.Rect(0, 0, 420, 66)
        self.enabled = True
        self.hot = 0.0  # 0..1 hover animation

    def update(self, dt: float, focused: bool) -> None:
        target = 1.0 if focused and self.enabled else 0.0
        self.hot += (target - self.hot) * min(1.0, dt * 12)

    def draw(self, surface: pygame.Surface) -> None:
        r = self.rect.move(int(14 * self.hot), 0)
        body = pygame.Surface(r.size, pygame.SRCALPHA)
        top = (40, 60, 110, 210) if self.enabled else (36, 40, 56, 170)
        bottom = (16, 22, 48, 230) if self.enabled else (24, 26, 36, 170)
        if self.hot > 0.05:
            top = tuple(int(a + (b - a) * self.hot) for a, b in zip(top, (70, 120, 220, 235)))
        body.blit(vertical_gradient(r.size, top, bottom), (0, 0))
        mask = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=14)
        body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        if self.hot > 0.05:
            halo = pygame.Surface((r.w + 40, r.h + 40), pygame.SRCALPHA)
            pygame.draw.rect(halo, (*CYAN, int(90 * self.hot)), halo.get_rect().inflate(-20, -20), border_radius=20)
            surface.blit(glow(halo, 8), (r.x - 20, r.y - 20))
        surface.blit(body, r)
        pygame.draw.rect(surface, CYAN if self.hot > 0.5 else PANEL_LINE, r, 2, border_radius=14)
        x = r.x + 22
        if self.icon is not None:
            surface.blit(self.icon, self.icon.get_rect(midleft=(x, r.centery)))
            x += self.icon.get_width() + 16
        color = TEXT if self.enabled else MUTED
        label = font(28, True).render(self.label, True, color)
        surface.blit(label, label.get_rect(midleft=(x, r.centery - (8 if self.hint else 0))))
        if self.hint:
            hint = font(15).render(self.hint, True, MUTED if self.enabled else (110, 116, 136))
            surface.blit(hint, hint.get_rect(midleft=(x + 2, r.centery + 17)))


def level_thumbnail(level: Level, size: Tuple[int, int], assets=None) -> pygame.Surface:
    """Small picture of the whole level (blocks, enemies, chest, start), fitted into `size`."""

    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.blit(vertical_gradient(size, (22, 26, 58, 255), (10, 12, 30, 255)), (0, 0))
    used = [c for r in range(ROWS) for c in range(level.cols) if level.solid[r][c]]
    cols = max(max(used, default=0) + 2, level.goal_x // 60 + 3, 10)  # without empty columns at the end
    tx = min(w / cols, h / ROWS)
    ty = min(h / ROWS, tx * 3)  # long levels: stretched upwards so the shape stays readable
    ox = (w - cols * tx) / 2
    oy = (h - ROWS * ty) / 2
    block_color = (150, 160, 196)
    for r in range(ROWS):
        row = level.solid[r]
        c = 0
        while c < min(cols, level.cols):
            if row[c]:
                start = c
                while c < level.cols and row[c]:
                    c += 1
                pygame.draw.rect(surf, block_color, (ox + start * tx, oy + r * ty, max(1, (c - start) * tx), max(1, ty)))
            c += 1

    def px(x, y):
        return int(ox + x / 60 * tx), int(oy + y / 60 * ty)

    dot = max(1.5, min(tx, ty) * 0.35)
    for x, y in level.enemy_spawns:
        pygame.draw.circle(surf, (240, 90, 90), px(x + 20, y + 20), dot)
    for cx, cy, _, _ in level.chests:
        x, y = px(cx, cy)
        pygame.draw.rect(surf, GOLD, (x - 1, y - 1, max(4, tx), max(4, ty * 0.7)))
    sx, sy = level.spawn
    pygame.draw.circle(surf, (90, 230, 140), px(sx + 20, sy + 30), dot + 2)
    return surf


def stars(surface: pygame.Surface, center: Tuple[int, int], count: int, size: int = 18, total: int = 3,
          filled_color=GOLD, empty_color=(70, 76, 100)) -> None:
    cx, cy = center
    gap = size * 2 + 6
    x0 = cx - gap * (total - 1) / 2
    for i in range(total):
        star(surface, (x0 + i * gap, cy), size, filled_color if i < count else empty_color)


def star(surface: pygame.Surface, center, size: float, color, rotation: float = 0.0) -> None:
    cx, cy = center
    pts = []
    for k in range(10):
        r = size if k % 2 == 0 else size * 0.45
        a = -math.pi / 2 + k * math.pi / 5 + rotation
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (40, 30, 10) if color == GOLD else (40, 44, 60), pts, 2)


class Confetti:
    COLORS = [GOLD, CYAN, (255, 110, 150), (130, 240, 140), (190, 140, 255)]

    def __init__(self, n: int = 160, seed: int = 3):
        rng = random.Random(seed)
        self.parts: List[list] = []
        for _ in range(n):
            self.parts.append([rng.uniform(0, SCREEN_W), rng.uniform(-SCREEN_H, 0), rng.uniform(-40, 40),
                               rng.uniform(80, 220), rng.uniform(0, 6.28), rng.uniform(-6, 6), rng.choice(self.COLORS)])

    def update(self, dt: float) -> None:
        for p in self.parts:
            p[0] += p[2] * dt + math.sin(p[4]) * 30 * dt
            p[1] += p[3] * dt
            p[4] += p[5] * dt
            if p[1] > SCREEN_H + 20:
                p[1] -= SCREEN_H + 60

    def draw(self, surface: pygame.Surface) -> None:
        for x, y, _, _, a, _, color in self.parts:
            w = abs(math.cos(a)) * 9 + 2
            pygame.draw.rect(surface, color, (x, y, w, 6))


def shade(surface: pygame.Surface, alpha: int = 150, color=(4, 6, 16)) -> None:
    s = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    s.fill((*color, alpha))
    surface.blit(s, (0, 0))


def glass_panel(surface: pygame.Surface, rect: pygame.Rect, alpha: int = 215, border=ACCENT, radius: int = 18) -> None:
    rect = pygame.Rect(rect)
    body = pygame.Surface(rect.size, pygame.SRCALPHA)
    body.blit(vertical_gradient(rect.size, (30, 38, 74, alpha), (12, 14, 34, alpha)), (0, 0))
    mask = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(body, rect)
    if border is not None:
        pygame.draw.rect(surface, border, rect, 2, border_radius=radius)
