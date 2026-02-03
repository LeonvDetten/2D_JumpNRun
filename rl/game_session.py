import os
import random
from dataclasses import asdict
from typing import Optional

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame
import numpy as np

from rl.game_types import EpisodeStatus, GameAction
from player import Player
from world import World


WINDOW_WIDTH = 1520
WINDOW_HEIGHT = 800
PLAYER_SPAWN_X = 120
PLAYER_SPAWN_Y = 50
BLOCK_SIZE = 60


class _GameContext:
    def __init__(self, level_path: str):
        self.level = self._read_level(level_path)
        self.level_width = max((len(line.rstrip("\n")) for line in self.level), default=1) * BLOCK_SIZE
        self.level_height = max(len(self.level), 1) * BLOCK_SIZE
        self.gameFinished = False

    @staticmethod
    def _read_level(level_path: str):
        with open(level_path, "r", encoding="utf-8") as level_file:
            return list(level_file.readlines())

    def end_game(self):
        self.gameFinished = True


class GameSession:
    def __init__(self, level_path: str = "level.txt", headless: bool = True, render_mode: str = "none", fps: int = 30):
        self.level_path = level_path
        self.headless = headless
        self.render_mode = render_mode
        self.fps = fps

        if self.headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

        pygame.init()
        self.clock = pygame.time.Clock()
        self.screen = None
        self.surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))

        if self.render_mode == "human" and not self.headless:
            self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
            pygame.display.set_caption("2D Game (RL Session)")

        self.status = EpisodeStatus()
        self.context = None
        self.player = None
        self.world = None
        self.reset(level_path=level_path)

    def _build_world(self):
        self.context = _GameContext(self.level_path)
        self.player = Player(PLAYER_SPAWN_X, PLAYER_SPAWN_Y, 40, 60)
        self.world = World(self.context, BLOCK_SIZE, self.player)
        self.player.setWorld(self.world)
        self.world.on_player_death = self._on_player_death
        self.world.main(self.surface)

        self.status = EpisodeStatus(
            is_win=False,
            is_dead=False,
            is_done=False,
            step_count=0,
            max_progress_x=float(self.player.playerPos.x),
        )

    def _on_player_death(self):
        self.status.is_dead = True
        self.status.is_done = True

    def reset(self, level_path: Optional[str] = None, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
        if level_path is not None:
            self.level_path = level_path
        self._build_world()
        return self.get_observation()

    def _simulate_frame(self, action: Optional[GameAction] = None):
        if self.status.is_done:
            return 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.status.is_done = True
                return 0

        self.world.main(self.surface)
        if action is None:
            self.player.main()
        else:
            self.player.main(action)

        for bullet in self.player.bulletGroup:
            bullet.update()

        for chest in self.world.chestGroup:
            if self.player.getCurrentChunk() - 1 <= chest.getChunk() <= self.player.getCurrentChunk() + 1:
                chest.update()

        self.world.chunkEnemyGroup.empty()
        for enemy in self.world.enemyGroup:
            if self.player.getCurrentChunk() - 1 <= enemy.getCurrentChunk() <= self.player.getCurrentChunk() + 1:
                enemy.update()
                self.world.chunkEnemyGroup.add(enemy)

        collisions = pygame.sprite.groupcollide(self.player.bulletGroup, self.world.chunkEnemyGroup, True, True)
        killed_enemies = sum(len(v) for v in collisions.values())

        if self.context.gameFinished:
            self.status.is_win = True
            self.status.is_done = True

        if self.render_mode == "human" and self.screen is not None:
            self.screen.blit(self.surface, (0, 0))
            pygame.sprite.Group.draw(self.world.chunkEnemyGroup, self.screen)
            pygame.sprite.Group.draw(self.player.bulletGroup, self.screen)
            pygame.sprite.Group.draw(self.world.chestGroup, self.screen)
            self.player.player_plain.draw(self.screen)
            pygame.display.update()
            self.clock.tick(self.fps)

        return killed_enemies

    def step(self, action: Optional[GameAction], frames: int = 4):
        start_x = float(self.player.playerPos.x)
        killed_enemies = 0
        for _ in range(frames):
            killed_enemies += self._simulate_frame(action)
            if self.status.is_done:
                break

        self.status.step_count += 1
        current_x = float(self.player.playerPos.x)
        self.status.max_progress_x = max(self.status.max_progress_x, current_x)

        return {
            "observation": self.get_observation(),
            "killed_enemies": killed_enemies,
            "current_x": current_x,
            "delta_x": current_x - start_x,
            "status": asdict(self.get_status()),
        }

    def get_observation(self):
        level_width = max(float(self.context.level_width), 1.0)
        level_height = max(float(self.context.level_height), 1.0)
        px = float(self.player.playerPos.x)
        py = float(self.player.playerPos.y)
        vx = float(self.player.get_speed_x())
        vy = float(self.player.speed_y)

        chest_dx, chest_dy = self._nearest_chest_delta()
        enemy_dx, enemy_dy = self._nearest_enemy_delta()

        collision_side = self.world.check_object_collision_sideblock(self.player.playerPos)
        wall_left = 1.0 if collision_side == -2 else 0.0
        wall_right = 1.0 if collision_side == -1 else 0.0

        on_ground = 1.0 if self.world.collided_get_y(self.player.base, self.player.height) >= 0 and self.player.speed_y == 0 else 0.0
        direction = float(self.player.get_direction())
        enemy_ahead = 1.0 if (direction > 0 and 0 < enemy_dx < 300) or (direction < 0 and -300 < enemy_dx < 0) else 0.0
        gap_ahead = self._gap_ahead_flag()

        obs = np.array(
            [
                np.clip(px / level_width, 0.0, 1.0),
                np.clip(py / level_height, 0.0, 1.0),
                np.clip(vx / 12.0, -1.0, 1.0),
                np.clip(vy / 20.0, -1.0, 1.0),
                on_ground,
                np.clip(direction, -1.0, 1.0),
                np.clip(chest_dx / level_width, -1.0, 1.0),
                np.clip(chest_dy / level_height, -1.0, 1.0),
                np.clip(enemy_dx / level_width, -1.0, 1.0),
                np.clip(enemy_dy / level_height, -1.0, 1.0),
                enemy_ahead,
                gap_ahead,
                wall_left,
                wall_right,
                np.clip(self.status.max_progress_x / level_width, 0.0, 1.0),
                np.clip(self.status.step_count / 2500.0, 0.0, 1.0),
            ],
            dtype=np.float32,
        )
        return obs

    def _nearest_chest_delta(self):
        if len(self.world.chestGroup) == 0:
            return 0.0, 0.0
        nearest = min(
            self.world.chestGroup,
            key=lambda chest: abs(chest.chestPos.x - self.player.playerPos.x),
        )
        return float(nearest.chestPos.x - self.player.playerPos.x), float(nearest.chestPos.y - self.player.playerPos.y)

    def _nearest_enemy_delta(self):
        if len(self.world.enemyGroup) == 0:
            return 0.0, 0.0
        nearest = min(
            self.world.enemyGroup,
            key=lambda enemy: abs(enemy.enemyPos.x - self.player.playerPos.x),
        )
        return float(nearest.enemyPos.x - self.player.playerPos.x), float(nearest.enemyPos.y - self.player.playerPos.y)

    def _gap_ahead_flag(self):
        direction = 1 if self.player.get_direction() >= 0 else -1
        probe_x = self.player.playerPos.x + (direction * (self.player.width + 12))
        probe_rect = pygame.Rect(int(probe_x), self.player.base.y + 4, 4, 2)
        return 1.0 if self.world.collided_get_y(probe_rect, 2) < 0 else 0.0

    def get_status(self):
        if self.status.is_win or self.status.is_dead:
            self.status.is_done = True
        return self.status

    def render(self):
        if self.render_mode != "human" and self.screen is None:
            self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
            pygame.display.set_caption("2D Game (RL Session)")
        self.screen.blit(self.surface, (0, 0))
        pygame.display.update()

    def close(self):
        pygame.quit()
