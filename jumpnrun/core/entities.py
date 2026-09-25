"""Game entities: pure state + physics, no sprites, no pygame.

Collision uses axis-separated AABB resolution against the tile grid:
move along x, push out of blocks, then move along y, push out of blocks.
Speeds are always smaller than one tile, so a single push-out is enough.
"""

from __future__ import annotations

from jumpnrun.core.constants import (
    BULLET_H,
    BULLET_SPEED,
    BULLET_W,
    ENEMY_H,
    ENEMY_SPEED,
    ENEMY_W,
    GRAVITY,
    MAX_FALL_SPEED,
    PLAYER_H,
    PLAYER_W,
    TILE,
)
from jumpnrun.core.level import Level


class Body:
    """Axis-aligned box that moves through the tile grid under gravity."""

    __slots__ = ("x", "y", "w", "h", "vx", "vy", "on_ground")

    def __init__(self, x: int, y: int, w: int, h: int):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.vx = 0
        self.vy = 0
        self.on_ground = False

    def move_x(self, level: Level) -> bool:
        """Move by vx, stop at blocks / level borders. Returns True if blocked."""

        if self.vx == 0:
            return False
        self.x += self.vx
        blocked = False
        if self.x < 0:
            self.x = 0
            blocked = True
        elif self.x > level.pixel_width - self.w:
            self.x = level.pixel_width - self.w
            blocked = True
        if level.overlaps_solid(self.x, self.y, self.w, self.h):
            if self.vx > 0:
                self.x = ((self.x + self.w - 1) // TILE) * TILE - self.w
            else:
                self.x = (self.x // TILE + 1) * TILE
            blocked = True
        return blocked

    def move_y(self, level: Level) -> None:
        """Move by vy, land on / bump against blocks, then apply gravity."""

        if self.vy != 0:
            self.y += self.vy
            if level.overlaps_solid(self.x, self.y, self.w, self.h):
                if self.vy > 0:
                    self.y = ((self.y + self.h - 1) // TILE) * TILE - self.h
                else:
                    self.y = (self.y // TILE + 1) * TILE
                self.vy = 0
        self.on_ground = level.overlaps_solid(self.x, self.y + 1, self.w, self.h)
        if self.on_ground and self.vy >= 0:
            self.vy = 0
        else:
            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)

    def overlaps(self, other: "Body") -> bool:
        return (
            self.x < other.x + other.w
            and other.x < self.x + self.w
            and self.y < other.y + other.h
            and other.y < self.y + self.h
        )

    def _copy_body_into(self, other: "Body") -> None:
        other.vx = self.vx
        other.vy = self.vy
        other.on_ground = self.on_ground


class Player(Body):
    __slots__ = ("facing", "shoot_cooldown", "last_shot_frame", "last_jump_frame")

    def __init__(self, x: int, y: int):
        super().__init__(x, y, PLAYER_W, PLAYER_H)
        self.facing = 1
        self.shoot_cooldown = 0
        self.last_shot_frame = -10_000
        self.last_jump_frame = -10_000

    def clone(self) -> "Player":
        other = Player(self.x, self.y)
        self._copy_body_into(other)
        other.facing = self.facing
        other.shoot_cooldown = self.shoot_cooldown
        other.last_shot_frame = self.last_shot_frame
        other.last_jump_frame = self.last_jump_frame
        return other


class Enemy(Body):
    """Walks left/right, turns at walls, walks off ledges (and may fall into pits)."""

    __slots__ = ("direction", "active", "alive")

    def __init__(self, x: int, y: int):
        super().__init__(x, y, ENEMY_W, ENEMY_H)
        self.direction = 1
        self.active = False
        self.alive = True

    def update(self, level: Level) -> None:
        self.vx = self.direction * ENEMY_SPEED
        if self.move_x(level):
            self.direction = -self.direction
        self.move_y(level)
        if self.y > level.pixel_height:
            self.alive = False

    def clone(self) -> "Enemy":
        other = Enemy(self.x, self.y)
        self._copy_body_into(other)
        other.direction = self.direction
        other.active = self.active
        other.alive = self.alive
        return other


class Bullet:
    __slots__ = ("x", "y", "w", "h", "direction", "start_x", "alive")

    def __init__(self, x: int, y: int, direction: int):
        self.x = x
        self.y = y
        self.w = BULLET_W
        self.h = BULLET_H
        self.direction = direction
        self.start_x = x
        self.alive = True

    def update(self, level: Level, max_range: int) -> None:
        self.x += self.direction * BULLET_SPEED
        if abs(self.x - self.start_x) > max_range or level.overlaps_solid(self.x, self.y, self.w, self.h):
            self.alive = False

    def overlaps(self, other: Body) -> bool:
        return (
            self.x < other.x + other.w
            and other.x < self.x + self.w
            and self.y < other.y + other.h
            and other.y < self.y + self.h
        )

    def clone(self) -> "Bullet":
        other = Bullet(self.x, self.y, self.direction)
        other.start_x = self.start_x
        other.alive = self.alive
        return other
