"""Deterministic game simulation (no rendering, no keyboard, no wall clock).

    sim = Simulation(Level.from_file("levels/exam/level.txt"))
    while sim.status == Status.RUNNING:
        sim.step(Action(right=True))

Frame order (identical for human play and bot):
    1. player input (walk, jump, shoot)   2. player moves (x, then y)
    3. enemies activate / move            4. bullets move and hit
    5. player vs enemy (stomp or death)   6. chest (win) / pit (death)
"""

from __future__ import annotations

from enum import Enum
from typing import List

from jumpnrun.core.actions import Action
from jumpnrun.core.constants import (
    BULLET_H,
    BULLET_RANGE,
    BULLET_W,
    ENEMY_ACTIVATION_DIST,
    JUMP_SPEED,
    PLAYER_SPEED,
    SHOOT_COOLDOWN,
    STOMP_BOUNCE,
    STOMP_TOLERANCE,
)
from jumpnrun.core.entities import Bullet, Enemy, Player
from jumpnrun.core.level import Level


class Status(str, Enum):
    RUNNING = "running"
    WON = "won"
    DIED_PIT = "died_pit"
    DIED_ENEMY = "died_enemy"


class Simulation:
    """One running game on one level."""

    def __init__(self, level: Level):
        self.level = level
        self.reset()

    # ----------------------------------------------------------------- setup
    def reset(self) -> None:
        self.frame = 0
        self.status = Status.RUNNING
        self.player = Player(*self.level.spawn)
        self.enemies: List[Enemy] = [Enemy(x, y) for (x, y) in self.level.enemy_spawns]
        self.bullets: List[Bullet] = []
        self.kills_stomp = 0
        self.kills_shot = 0
        self.jumps = 0
        self.max_x = self.player.x
        self._settle_enemies()

    def _settle_enemies(self) -> None:
        """Drop sleeping enemies onto the ground so they don't float before activation."""

        for enemy in self.enemies:
            for _ in range(self.level.pixel_height):
                enemy.move_y(self.level)
                if enemy.on_ground or enemy.y > self.level.pixel_height:
                    break
            enemy.vy = 0
            if enemy.y > self.level.pixel_height:
                enemy.alive = False
        self.enemies = [enemy for enemy in self.enemies if enemy.alive]

    def clone(self) -> "Simulation":
        """Cheap independent copy (the level is shared, it never changes)."""

        other = Simulation.__new__(Simulation)
        other.level = self.level
        other.frame = self.frame
        other.status = self.status
        other.player = self.player.clone()
        other.enemies = [enemy.clone() for enemy in self.enemies]
        other.bullets = [bullet.clone() for bullet in self.bullets]
        other.kills_stomp = self.kills_stomp
        other.kills_shot = self.kills_shot
        other.jumps = self.jumps
        other.max_x = self.max_x
        return other

    # ------------------------------------------------------------------ step
    def step(self, action: Action, frames: int = 1) -> Status:
        """Advance `frames` frames with the same input. Returns the status."""

        for _ in range(frames):
            if self.status != Status.RUNNING:
                break
            self._frame(action)
        return self.status

    def _frame(self, action: Action) -> None:
        level = self.level
        player = self.player

        # 1. input
        direction = int(action.right) - int(action.left)
        player.vx = direction * PLAYER_SPEED
        if direction:
            player.facing = direction
        if action.jump and player.on_ground:
            player.vy = JUMP_SPEED
            player.last_jump_frame = self.frame
            self.jumps += 1
        if player.shoot_cooldown > 0:
            player.shoot_cooldown -= 1
        elif action.shoot:
            bullet_x = player.x + player.w if player.facing > 0 else player.x - BULLET_W
            bullet_y = player.y + (player.h * 45) // 100
            self.bullets.append(Bullet(bullet_x, bullet_y, player.facing))
            player.shoot_cooldown = SHOOT_COOLDOWN
            player.last_shot_frame = self.frame

        # 2. player movement
        prev_bottom = player.y + player.h
        player.move_x(level)
        player.move_y(level)
        if player.x > self.max_x:
            self.max_x = player.x

        # 3. enemies
        prev_enemy_tops = {}
        for enemy in self.enemies:
            if not enemy.active:
                if abs(enemy.x - player.x) >= ENEMY_ACTIVATION_DIST:
                    continue
                enemy.active = True
            prev_enemy_tops[id(enemy)] = enemy.y
            enemy.update(level)

        # 4. bullets
        for bullet in self.bullets:
            bullet.update(level, BULLET_RANGE)
            if not bullet.alive:
                continue
            for enemy in self.enemies:
                if enemy.alive and bullet.overlaps(enemy):
                    enemy.alive = False
                    bullet.alive = False
                    self.kills_shot += 1
                    break
        self.bullets = [bullet for bullet in self.bullets if bullet.alive]

        # 5. player vs enemies
        falling = player.y + player.h > prev_bottom
        for enemy in self.enemies:
            if not enemy.alive or not player.overlaps(enemy):
                continue
            enemy_top = prev_enemy_tops.get(id(enemy), enemy.y)
            if falling and prev_bottom <= enemy_top + STOMP_TOLERANCE:
                enemy.alive = False
                player.vy = STOMP_BOUNCE
                self.kills_stomp += 1
            else:
                self.status = Status.DIED_ENEMY
        self.enemies = [enemy for enemy in self.enemies if enemy.alive]

        self.frame += 1
        if self.status != Status.RUNNING:
            return

        # 6. goal / pit
        px, py, pw, ph = player.x, player.y, player.w, player.h
        for cx, cy, cw, ch in level.chests:
            if px < cx + cw and cx < px + pw and py < cy + ch and cy < py + ph:
                self.status = Status.WON
                return
        if py > level.pixel_height:
            self.status = Status.DIED_PIT

    # --------------------------------------------------------------- helpers
    def state_signature(self) -> tuple:
        """Compact, hashable snapshot of the full dynamic state (used by tests)."""

        p = self.player
        return (
            self.frame,
            self.status,
            (p.x, p.y, p.vx, p.vy, p.on_ground, p.facing, p.shoot_cooldown),
            tuple((e.x, e.y, e.vy, e.direction, e.active) for e in self.enemies),
            tuple((b.x, b.y, b.direction) for b in self.bullets),
        )
