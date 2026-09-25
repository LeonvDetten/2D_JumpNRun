"""Ghost view: many bots playing the same level at once, drawn semi-transparently.

    +--------------------------------------------------------------+
    |  level (zoomed out), all ghosts, their enemies (faint),     |
    |  red crosses where ghosts died, the leading ghost opaque     |
    |  (medium levels wrap into two rows so the whole level shows) |
    +--------------------------------------------------------------+
    |  title / statistics                                          |
    |  minimap (only for long levels, where the camera follows)    |
    +--------------------------------------------------------------+
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import pygame

from jumpnrun.core.constants import ROWS, SCREEN_H, SCREEN_W, TILE
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status
from jumpnrun.render.assets import get_assets
from jumpnrun.render.renderer import SPRITE_LOOP_SPEED, player_sprite

PANEL_MIN_ZOOM_2ROWS = 0.43  # two rows of 780 px * 0.43 leave ~130 px for the panel
GHOST_ALPHA = 90
ENEMY_ALPHA = 55
PANEL_BG = (14, 12, 34)
TEXT = (235, 235, 245)
DIM = (160, 160, 185)
WIN = (120, 230, 120)
DEATH = (240, 70, 70)

_alpha_cache: Dict[Tuple[int, int], pygame.Surface] = {}


def _with_alpha(image: pygame.Surface, alpha: int) -> pygame.Surface:
    key = (id(image), alpha)
    cached = _alpha_cache.get(key)
    if cached is None:
        cached = image.copy()
        cached.set_alpha(alpha)
        _alpha_cache[key] = cached
    return cached


class GhostView:
    """Renders a list of simulations that all play the same level."""

    def __init__(self, level: Level):
        self.level = level
        self.assets = get_assets()
        level_px = level.pixel_width
        self.level_h = ROWS * TILE
        # layout: 1 row, 2 wrapped rows, or a camera following the leading ghost
        one_row = min(0.75, SCREEN_W / level_px)
        two_rows = min(PANEL_MIN_ZOOM_2ROWS, 2 * SCREEN_W / level_px)
        if one_row >= 0.5:
            self.rows, self.zoom = 1, one_row
        elif two_rows >= 0.36:
            self.rows, self.zoom = 2, two_rows
        else:
            self.rows, self.zoom = 1, 0.6
        self.row_w = int(min(SCREEN_W / self.zoom, -(-level_px // self.rows)))
        self.fits = self.row_w * self.rows >= level_px
        self.view_w = level_px if self.fits else self.row_w
        self.base = self._prerender_level()
        self.minimap = self._prerender_minimap()
        pygame.font.init()
        self.font_title = pygame.font.SysFont("Arial", 34, bold=True)
        self.font = pygame.font.SysFont("Arial", 24)

    def _prerender_level(self) -> pygame.Surface:
        level = self.level
        base = pygame.Surface((level.pixel_width, self.level_h))
        bg = pygame.transform.smoothscale(self.assets.background, (int(SCREEN_W * self.level_h / SCREEN_H), self.level_h))
        for x in range(0, level.pixel_width, bg.get_width()):
            base.blit(bg, (x, 0))
        for r in range(ROWS):
            for c in range(level.cols):
                if level.solid[r][c]:
                    base.blit(self.assets.block, (c * TILE, r * TILE))
        for cx, cy, _, _ in level.chests:
            base.blit(self.assets.chest[0], (cx, cy))
        return base

    def _prerender_minimap(self) -> pygame.Surface:
        level = self.level
        tiny = pygame.Surface((level.cols, ROWS))
        tiny.fill((40, 36, 80))
        for r in range(ROWS):
            for c in range(level.cols):
                if level.solid[r][c]:
                    tiny.set_at((c, r), (150, 150, 170))
        for cx, cy, _, _ in level.chests:
            tiny.set_at((cx // TILE, min(ROWS - 1, cy // TILE)), (255, 215, 0))
        return pygame.transform.scale(tiny, (SCREEN_W - 40, 52))

    # ------------------------------------------------------------------ draw
    def draw(
        self,
        surface: pygame.Surface,
        sims: Sequence[Simulation],
        running: Sequence[bool],
        deaths: List[Tuple[int, int]],
        title: str = "",
        subtitle: str = "",
    ) -> None:
        level = self.level
        alive_x = [s.player.x for s, r in zip(sims, running) if r]
        leader_x = max(alive_x) if alive_x else max(s.player.x for s in sims)
        leader = None
        if alive_x:
            leader = max((s for s, r in zip(sims, running) if r), key=lambda s: s.player.x)

        cam = 0 if self.fits else int(max(0, min(leader_x - 0.6 * self.view_w, level.pixel_width - self.view_w)))
        view = self.base.subsurface((cam, 0, self.view_w, self.level_h)).copy()

        enemy_index = int(sims[0].frame * SPRITE_LOOP_SPEED) % 3 if sims else 0
        for sim, run in zip(sims, running):
            if not run:
                continue
            for enemy in sim.enemies:
                if enemy.active and cam - TILE < enemy.x < cam + self.view_w:
                    view.blit(_with_alpha(self.assets.enemy[enemy.direction][enemy_index], ENEMY_ALPHA),
                              (enemy.x - cam, enemy.y))

        for dx, dy in deaths:
            x, y = dx - cam, min(dy, self.level_h - 20)
            if -20 < x < self.view_w + 20:
                pygame.draw.line(view, DEATH, (x - 10, y - 10), (x + 10, y + 10), 4)
                pygame.draw.line(view, DEATH, (x - 10, y + 10), (x + 10, y - 10), 4)

        for sim, run in zip(sims, running):
            if sim is leader:
                continue
            p = sim.player
            if run or sim.status == Status.WON:
                view.blit(_with_alpha(player_sprite(p, sim.frame), GHOST_ALPHA), (p.x - cam, p.y))
        if leader is not None:
            p = leader.player
            view.blit(player_sprite(p, leader.frame), (p.x - cam, p.y))

        surface.fill(PANEL_BG)
        row_h = int(self.level_h * self.zoom)
        for r in range(self.rows):
            x0 = r * self.row_w
            width = min(self.row_w, self.view_w - x0)
            if width <= 0:
                break
            part = view.subsurface((x0, 0, width, self.level_h))
            scaled = pygame.transform.smoothscale(part, (int(width * self.zoom), row_h))
            surface.blit(scaled, ((SCREEN_W - int(self.row_w * self.zoom)) // 2, r * (row_h + 4)))

        # panel
        y = self.rows * (row_h + 4) + 10
        if title:
            surface.blit(self.font_title.render(title, True, TEXT), (20, y))
            y += 44
        won = sum(1 for s in sims if s.status == Status.WON)
        pit = sum(1 for s in sims if s.status == Status.DIED_PIT)
        enemy = sum(1 for s in sims if s.status == Status.DIED_ENEMY)
        timeout = sum(1 for s, r in zip(sims, running) if not r and s.status == Status.RUNNING)
        on_way = sum(1 for r in running if r)
        best = max(s.max_x for s in sims) / max(1, level.goal_x)
        parts = [
            (f"Im Ziel: {won}/{len(sims)}", WIN),
            (f"Grube: {pit}", DEATH),
            (f"Gegner: {enemy}", DEATH),
            (f"Zeit um: {timeout}", DIM),
            (f"unterwegs: {on_way}", TEXT),
            (f"weiteste Position: {min(best, 1.0):.0%}", TEXT),
        ]
        x = 20
        for text, color in parts:
            image = self.font.render(text, True, color)
            surface.blit(image, (x, y))
            x += image.get_width() + 28
        y += 34
        if subtitle:
            surface.blit(self.font.render(subtitle, True, DIM), (20, y))
            y += 34

        if self.fits:
            return
        # minimap
        mm_y = min(y + 4, SCREEN_H - self.minimap.get_height() - 8)
        surface.blit(self.minimap, (20, mm_y))
        scale = self.minimap.get_width() / level.pixel_width
        pygame.draw.rect(surface, TEXT, (20 + int(cam * scale), mm_y, int(self.view_w * scale), 52), 1)
        for dx, _ in deaths:
            pygame.draw.circle(surface, DEATH, (20 + int(dx * scale), mm_y + 48), 2)
        for sim, run in zip(sims, running):
            p = sim.player
            color = WIN if sim.status == Status.WON else (TEXT if run else DIM)
            my = mm_y + int(min(max(p.y, 0), self.level_h) / self.level_h * 52)
            pygame.draw.circle(surface, color, (20 + int(p.x * scale), my), 3)
