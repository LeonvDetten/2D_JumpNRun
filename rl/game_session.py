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
    def __init__(
        self,
        level_path: str = "level.txt",
        headless: bool = True,
        render_mode: str = "none",
        fps: int = 30,
        max_episode_steps: int = 2500,
        obs_profile: str = "balanced",
    ):
        self.level_path = level_path
        self.headless = headless
        self.render_mode = render_mode
        self.fps = fps
        self.max_episode_steps = max(1, int(max_episode_steps))
        self.obs_profile = obs_profile
        if self.obs_profile not in {"balanced", "legacy"}:
            raise ValueError(f"Unsupported obs_profile: {self.obs_profile}")

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
        start_y = float(self.player.playerPos.y)
        killed_enemies = 0
        for _ in range(frames):
            killed_enemies += self._simulate_frame(action)
            if self.status.is_done:
                break

        self.status.step_count += 1
        current_x = float(self.player.playerPos.x)
        current_y = float(self.player.playerPos.y)
        self.status.max_progress_x = max(self.status.max_progress_x, current_x)

        return {
            "observation": self.get_observation(),
            "killed_enemies": killed_enemies,
            "current_x": current_x,
            "current_y": current_y,
            "delta_x": current_x - start_x,
            "delta_y": current_y - start_y,
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
        enemy_dx, enemy_dy, has_enemy = self._nearest_enemy_info()

        on_ground = 1.0 if self.world.collided_get_y(self.player.base, self.player.height) >= 0 and self.player.speed_y == 0 else 0.0
        direction = float(self.player.get_direction())
        if self.obs_profile == "legacy":
            feature_10 = 1.0 if has_enemy and ((direction > 0 and 0 < enemy_dx < 300) or (direction < 0 and -300 < enemy_dx < 0)) else 0.0
            feature_11 = self._gap_ahead_flag()
            feature_12 = 1.0 if has_enemy and abs(enemy_dx) <= 120.0 and abs(enemy_dy) <= 100.0 else 0.0
            feature_13 = self._safe_ground_ahead_distance()
        else:
            gap_ahead_short = self._gap_in_distance_window(min_distance=0, max_distance=90)
            gap_ahead_mid = self._gap_in_distance_window(min_distance=90, max_distance=240)
            enemy_hazard_short, enemy_hazard_mid, enemy_threat_ahead, enemy_threat_behind = self._enemy_threat_bands(
                short_distance=90.0,
                mid_distance=240.0,
                vertical_tolerance=100.0,
            )
            feature_10 = 1.0 if (gap_ahead_short > 0.5 or enemy_hazard_short > 0.5) else 0.0
            feature_11 = 1.0 if (gap_ahead_mid > 0.5 or enemy_hazard_mid > 0.5) else 0.0
            feature_12 = enemy_threat_ahead
            feature_13 = enemy_threat_behind

        # Slots 10-13 stay shape-compatible (legacy or balanced semantics).
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
                feature_10,
                feature_11,
                feature_12,
                feature_13,
                np.clip(self.status.max_progress_x / level_width, 0.0, 1.0),
                np.clip(self.status.step_count / float(self.max_episode_steps), 0.0, 1.0),
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

    def get_goal_distance(self):
        chest_dx, chest_dy = self._nearest_chest_delta()
        return abs(float(chest_dx)) + abs(float(chest_dy))

    def get_player_position(self):
        return float(self.player.playerPos.x), float(self.player.playerPos.y)

    def get_level_size(self):
        return float(self.context.level_width), float(self.context.level_height)

    def _nearest_enemy_delta(self):
        enemy_dx, enemy_dy, _ = self._nearest_enemy_info()
        return enemy_dx, enemy_dy

    def _nearest_enemy_info(self):
        if len(self.world.enemyGroup) == 0:
            return 0.0, 0.0, False
        nearest = min(
            self.world.enemyGroup,
            key=lambda enemy: abs(enemy.enemyPos.x - self.player.playerPos.x),
        )
        return (
            float(nearest.enemyPos.x - self.player.playerPos.x),
            float(nearest.enemyPos.y - self.player.playerPos.y),
            True,
        )

    def _gap_in_distance_window(self, min_distance: int, max_distance: int, step: int = 12):
        direction = 1 if self.player.get_direction() >= 0 else -1
        start = max(0, int(min_distance))
        end = max(start, int(max_distance))
        for distance in range(start, end + step, step):
            probe_x = self.player.playerPos.x + (direction * (self.player.width + distance))
            probe_rect = pygame.Rect(int(probe_x), self.player.base.y + 4, 4, 2)
            if self.world.collided_get_y(probe_rect, 2) < 0:
                return 1.0
        return 0.0

    def _gap_ahead_flag(self):
        direction = 1 if self.player.get_direction() >= 0 else -1
        probe_x = self.player.playerPos.x + (direction * (self.player.width + 12))
        probe_rect = pygame.Rect(int(probe_x), self.player.base.y + 4, 4, 2)
        return 1.0 if self.world.collided_get_y(probe_rect, 2) < 0 else 0.0

    def _safe_ground_ahead_distance(self, max_scan: int = 360, step: int = 12):
        direction = 1 if self.player.get_direction() >= 0 else -1
        for distance in range(0, max_scan + step, step):
            probe_x = self.player.playerPos.x + (direction * (self.player.width + distance))
            probe_rect = pygame.Rect(int(probe_x), self.player.base.y + 4, 4, 2)
            if self.world.collided_get_y(probe_rect, 2) >= 0:
                return float(np.clip(distance / float(max_scan), 0.0, 1.0))
        return 1.0

    def _enemy_threat_bands(self, short_distance: float, mid_distance: float, vertical_tolerance: float):
        direction = 1.0 if self.player.get_direction() >= 0 else -1.0
        enemy_hazard_short = 0.0
        enemy_hazard_mid = 0.0
        enemy_threat_ahead = 0.0
        enemy_threat_behind = 0.0
        px = float(self.player.playerPos.x)
        py = float(self.player.playerPos.y)

        for enemy in self.world.enemyGroup:
            dx = float(enemy.enemyPos.x - px)
            dy = float(enemy.enemyPos.y - py)
            if abs(dy) > vertical_tolerance:
                continue

            distance_x = abs(dx)
            is_ahead = (dx * direction) > 0.0
            if is_ahead:
                enemy_threat_ahead = 1.0
                if distance_x <= short_distance:
                    enemy_hazard_short = 1.0
                elif distance_x <= mid_distance:
                    enemy_hazard_mid = 1.0
            elif distance_x <= short_distance:
                enemy_threat_behind = 1.0

        return enemy_hazard_short, enemy_hazard_mid, enemy_threat_ahead, enemy_threat_behind

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
