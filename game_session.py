import os
import random
from dataclasses import asdict
from typing import Optional

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame

from game_types import EpisodeStatus, GameAction
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
        killed_enemies = 0
        for _ in range(frames):
            killed_enemies += self._simulate_frame(action)
            if self.status.is_done:
                break

        self.status.step_count += 1
        self.status.max_progress_x = max(self.status.max_progress_x, float(self.player.playerPos.x))

        return {
            "observation": self.get_observation(),
            "killed_enemies": killed_enemies,
            "status": asdict(self.get_status()),
        }

    def get_observation(self):
        return [
            float(self.player.playerPos.x),
            float(self.player.playerPos.y),
            float(self.player.speed_y),
            float(self.status.max_progress_x),
        ]

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
