"""Draws a Simulation onto a pygame Surface. Rendering never changes game state."""

from __future__ import annotations

from typing import Optional

import pygame

from jumpnrun.core.constants import CAMERA_PLAYER_X, FPS, ROWS, SCREEN_H, SCREEN_W, SHOOT_COOLDOWN, TILE
from jumpnrun.core.entities import Player
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status
from jumpnrun.render.assets import PLAYER_FRAMES, get_assets

SPRITE_LOOP_SPEED = 0.3  # animation frames per game frame (as in the original game)


def camera_x(level: Level, focus_x: float) -> int:
    """Camera follows the player (drawn at CAMERA_PLAYER_X) and stops at the level borders."""

    cam = int(focus_x) - CAMERA_PLAYER_X
    return max(0, min(cam, max(0, level.pixel_width - SCREEN_W)))


def player_sprite(player: Player, frame: int) -> pygame.Surface:
    """Pick the animation frame from the player's state (IDLE / RUN / JUMP / ATTACK)."""

    assets = get_assets()
    since_shot = frame - player.last_shot_frame
    if since_shot < SHOOT_COOLDOWN:
        state = "ATTACK"
        index = min(3 + int(since_shot * SPRITE_LOOP_SPEED), PLAYER_FRAMES - 1)
    elif not player.on_ground:
        state = "JUMP"
        index = min(int((frame - player.last_jump_frame) * SPRITE_LOOP_SPEED), PLAYER_FRAMES - 1)
    else:
        state = "RUN" if player.vx != 0 else "IDLE"
        index = int(frame * SPRITE_LOOP_SPEED) % PLAYER_FRAMES
    return assets.player[state][player.facing][index]


class Renderer:
    """Draws background, tiles, chest, enemies, bullets and player."""

    def __init__(self):
        self.assets = get_assets()
        self._font_big: Optional[pygame.font.Font] = None
        self._font_small: Optional[pygame.font.Font] = None

    # --------------------------------------------------------------- pieces
    def draw_level(self, surface: pygame.Surface, level: Level, cam_x: int) -> None:
        surface.blit(self.assets.background, (0, 0))
        c0 = max(cam_x // TILE, 0)
        c1 = min((cam_x + SCREEN_W) // TILE + 1, level.cols)
        block = self.assets.block
        for r in range(ROWS):
            row = level.solid[r]
            y = r * TILE
            for c in range(c0, c1):
                if row[c]:
                    surface.blit(block, (c * TILE - cam_x, y))

    def draw_chests(self, surface: pygame.Surface, level: Level, cam_x: int, open_frames: int = 0) -> None:
        index = min(int(open_frames * 0.2), len(self.assets.chest) - 1)
        for cx, cy, _, _ in level.chests:
            surface.blit(self.assets.chest[index], (cx - cam_x, cy))

    def draw_sim_objects(self, surface: pygame.Surface, sim: Simulation, cam_x: int) -> None:
        enemy_index = int(sim.frame * SPRITE_LOOP_SPEED) % 3
        for enemy in sim.enemies:
            if -TILE < enemy.x - cam_x < SCREEN_W:
                surface.blit(self.assets.enemy[enemy.direction][enemy_index], (enemy.x - cam_x, enemy.y))
        for bullet in sim.bullets:
            surface.blit(self.assets.bullet, (bullet.x - cam_x, bullet.y))

    def draw_player(self, surface: pygame.Surface, player: Player, frame: int, cam_x: int) -> None:
        surface.blit(player_sprite(player, frame), (player.x - cam_x, player.y))

    def text(self, surface: pygame.Surface, message: str, big: bool = True, center=None, color=(255, 255, 0)) -> None:
        if self._font_big is None:
            pygame.font.init()
            self._font_big = pygame.font.SysFont("Arial", 80)
            self._font_small = pygame.font.SysFont("Arial", 32)
        font = self._font_big if big else self._font_small
        image = font.render(message, True, color)
        rect = image.get_rect()
        rect.center = center or (SCREEN_W // 2, SCREEN_H // 2)
        surface.blit(image, rect)

    # ---------------------------------------------------------------- frame
    def draw(self, surface: pygame.Surface, sim: Simulation, frames_since_end: int = 0) -> None:
        """Draw one complete frame of `sim` (plus win / game-over overlay)."""

        cam_x = camera_x(sim.level, sim.player.x)
        self.draw_level(surface, sim.level, cam_x)
        self.draw_chests(surface, sim.level, cam_x, frames_since_end if sim.status == Status.WON else 0)
        self.draw_sim_objects(surface, sim, cam_x)
        self.draw_player(surface, sim.player, sim.frame, cam_x)

        if sim.status == Status.WON:
            self.text(surface, f"You won! Within: {sim.frame / FPS:.2f}s")
            self.text(surface, "R = restart, ESC = quit", big=False, center=(SCREEN_W // 2, SCREEN_H // 2 + 70))
        elif sim.status != Status.RUNNING:
            reason = "fell into a pit" if sim.status == Status.DIED_PIT else "caught by an enemy"
            self.text(surface, "Game over", color=(255, 80, 80))
            self.text(surface, f"You {reason}. R = restart, ESC = quit", big=False, center=(SCREEN_W // 2, SCREEN_H // 2 + 70))
