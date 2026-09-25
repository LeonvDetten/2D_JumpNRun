"""Sprite loading. Every image is loaded from disk exactly once per process."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import pygame

from jumpnrun.core.constants import (
    BULLET_H,
    BULLET_W,
    CHEST_H,
    CHEST_W,
    ENEMY_H,
    ENEMY_W,
    PLAYER_H,
    PLAYER_W,
    SCREEN_H,
    SCREEN_W,
    TILE,
)

IMG_DIR = Path(__file__).resolve().parents[2] / "img"
PLAYER_STATES = ("IDLE", "RUN", "JUMP", "ATTACK")
PLAYER_FRAMES = 7


def _load(path: Path) -> pygame.Surface:
    image = pygame.image.load(str(path))
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        image = image.convert_alpha()
    return image


class Assets:
    """All game sprites, already scaled to their in-game size."""

    def __init__(self):
        self.background = pygame.transform.scale(_load(IMG_DIR / "background_img" / "bg.jpg"), (SCREEN_W, SCREEN_H))
        self.block = pygame.transform.scale(_load(IMG_DIR / "ground_img" / "spaceground.png"), (TILE, TILE))
        self.bullet = pygame.transform.scale(_load(IMG_DIR / "bullet_img" / "bullet.png"), (BULLET_W, BULLET_H))
        self.chest = [
            pygame.transform.scale(_load(IMG_DIR / "chest_img" / f"chest1_{i}.png"), (CHEST_W, CHEST_H))
            for i in range(10)
        ]
        self.enemy: Dict[int, List[pygame.Surface]] = {1: [], -1: []}
        for i in range(3):
            self.enemy[1].append(pygame.transform.scale(_load(IMG_DIR / "enemy_img" / f"e1_r{i}.png"), (ENEMY_W, ENEMY_H)))
            self.enemy[-1].append(pygame.transform.scale(_load(IMG_DIR / "enemy_img" / f"e1_l{i}.png"), (ENEMY_W, ENEMY_H)))

        # player[state][facing] -> list of frames (same crop as the original game)
        self.player: Dict[str, Dict[int, List[pygame.Surface]]] = {}
        for state in PLAYER_STATES:
            self.player[state] = {1: [], -1: []}
            for i in range(PLAYER_FRAMES):
                image = _load(IMG_DIR / "player_img" / f"2_entity_000_{state}_00{i}.png")
                cropped = pygame.transform.scale(image.subsurface(pygame.Rect(200, 250, 825, 850)), (PLAYER_W, PLAYER_H))
                self.player[state][1].append(cropped)
                self.player[state][-1].append(pygame.transform.flip(cropped, True, False))


@lru_cache(maxsize=1)
def get_assets() -> Assets:
    return Assets()
