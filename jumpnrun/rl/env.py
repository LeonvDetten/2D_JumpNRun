"""Gymnasium environment: the game as seen by the bot.

Observation (what the bot "sees" - roughly the human's screen, as tiles):
    grid  float32 (4, 13, 25): 13 rows x 25 columns around the player
          (5 columns behind, 19 ahead), channels:
            0 solid block (the level border counts as solid)
            1 chest
            2 enemy (+1 walking right, -1 walking left)
            3 player (where exactly inside the grid the player is)
    vec   float32 (15,): vy, on_ground, facing, shoot cooldown,
          sub-tile x offset, y position, and for the 3 nearest enemies
          (dx, dy, present)

Actions: 6 discrete (see core.actions.BOT_ACTIONS), each held for 4 frames.

Reward (deliberately minimal):
    +0.1 per tile of new rightmost progress, -1 on death, +2 on the chest.
Episodes end on win / death (terminated) or after too long without new
progress (truncated).
"""

from __future__ import annotations

import random
from typing import Callable, Optional

import gymnasium as gym
import numpy as np

from jumpnrun.core.actions import ACTION_REPEAT, BOT_ACTIONS
from jumpnrun.core.constants import MAX_FALL_SPEED, ROWS, SHOOT_COOLDOWN, TILE
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status

VIEW_BEHIND = 5
VIEW_AHEAD = 19
VIEW_COLS = VIEW_BEHIND + 1 + VIEW_AHEAD
GRID_CHANNELS = 4
VEC_SIZE = 15
NEAREST_ENEMIES = 3

REWARD_PER_TILE = 0.1
REWARD_DEATH = -1.0
REWARD_WIN = 2.0
NO_PROGRESS_STEPS = 150

# A level source returns (level, tier) for each new episode. tier = -1 for hand-made levels.
LevelSource = Callable[[random.Random], "tuple[Level, int]"]


def fixed_levels(levels) -> LevelSource:
    """Level source that cycles randomly through a fixed list of levels."""

    levels = list(levels)
    return lambda rng: (rng.choice(levels), -1)


class JumpNRunEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, level_source: LevelSource, seed: Optional[int] = None, max_steps_per_tile: float = 3.0):
        super().__init__()
        self.level_source = level_source
        self.rng = random.Random(seed)
        self.max_steps_per_tile = max_steps_per_tile
        self.action_space = gym.spaces.Discrete(len(BOT_ACTIONS))
        self.observation_space = gym.spaces.Dict(
            {
                "grid": gym.spaces.Box(-1.0, 1.0, (GRID_CHANNELS, ROWS, VIEW_COLS), np.float32),
                "vec": gym.spaces.Box(-1.0, 1.0, (VEC_SIZE,), np.float32),
            }
        )
        self.sim: Optional[Simulation] = None
        self.tier = -1
        self.actions_taken: list = []

    # ---------------------------------------------------------------- gym api
    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        if seed is not None:
            self.rng = random.Random(seed)
        if options and "level" in options:
            level, self.tier = options["level"], options.get("tier", -1)
        else:
            level, self.tier = self.level_source(self.rng)
        self._set_level(level)
        self.sim = Simulation(level)
        self.steps = 0
        self.steps_since_progress = 0
        self.max_steps = int(level.cols * self.max_steps_per_tile) + 50
        self.actions_taken = []
        return self._observe(), {}

    def step(self, action: int):
        before = self.sim.max_x
        self.sim.step(BOT_ACTIONS[int(action)], frames=ACTION_REPEAT)
        return self.finish_step(int(action), before)

    def finish_step(self, action: int, max_x_before: int):
        """Reward / termination bookkeeping after the frames of one bot step.

        Split from step() so the ghost view can advance many games frame by frame.
        """

        sim = self.sim
        status = sim.status
        self.steps += 1
        self.actions_taken.append(action)

        gained = sim.max_x - max_x_before
        reward = REWARD_PER_TILE * gained / TILE
        self.steps_since_progress = 0 if gained > 0 else self.steps_since_progress + 1

        terminated = status != Status.RUNNING
        if status == Status.WON:
            reward += REWARD_WIN
        elif terminated:
            reward += REWARD_DEATH
        truncated = not terminated and (
            self.steps_since_progress >= NO_PROGRESS_STEPS or self.steps >= self.max_steps
        )

        info = {}
        if terminated or truncated:
            info["episode_end"] = {
                "outcome": status.value if terminated else "timeout",
                "won": status == Status.WON,
                "tier": self.tier,
                "level": sim.level.name,
                "progress": min(1.0, sim.max_x / max(1, sim.level.goal_x)),
                "steps": self.steps,
                "kills": sim.kills_stomp + sim.kills_shot,
            }
        return self._observe(), float(reward), terminated, truncated, info

    def set_tier_weights(self, weights) -> None:
        """Called by the curriculum (training process) to steer level difficulty."""

        if hasattr(self.level_source, "weights"):
            self.level_source.weights = list(weights)

    def observe(self):
        return self._observe()

    # ------------------------------------------------------------ observation
    def _set_level(self, level: Level) -> None:
        """Precompute the padded static grid (blocks + chests) for fast slicing."""

        self.level = level
        pad_l, pad_r = VIEW_BEHIND + 1, VIEW_AHEAD + 1
        static = np.zeros((2, ROWS, level.cols + pad_l + pad_r), np.float32)
        static[0, :, :pad_l] = 1.0  # left border
        static[0, :, pad_l + level.cols:] = 1.0  # right border
        static[0, :, pad_l:pad_l + level.cols] = np.array([list(row) for row in level.solid], np.float32)
        for cx, cy, _, _ in level.chests:
            static[1, min(cy // TILE, ROWS - 1), pad_l + cx // TILE] = 1.0
        self._static = static
        self._pad_l = pad_l

    def _observe(self):
        sim = self.sim
        p = sim.player
        pcol = (p.x + p.w // 2) // TILE
        c0 = pcol - VIEW_BEHIND  # level column shown in grid column 0

        grid = np.zeros((GRID_CHANNELS, ROWS, VIEW_COLS), np.float32)
        grid[0:2] = self._static[:, :, c0 + self._pad_l: c0 + self._pad_l + VIEW_COLS]
        prow = (p.y + p.h // 2) // TILE
        if 0 <= prow < ROWS:
            grid[3, prow, VIEW_BEHIND] = 1.0

        nearest = []
        for e in sim.enemies:
            ecol = (e.x + e.w // 2) // TILE - c0
            erow = (e.y + e.h // 2) // TILE
            if 0 <= ecol < VIEW_COLS and 0 <= erow < ROWS:
                grid[2, erow, ecol] = float(e.direction)
            nearest.append((abs(e.x - p.x) + abs(e.y - p.y), e))
        nearest.sort(key=lambda item: item[0])

        vec = np.zeros(VEC_SIZE, np.float32)
        vec[0] = p.vy / MAX_FALL_SPEED
        vec[1] = 1.0 if p.on_ground else 0.0
        vec[2] = float(p.facing)
        vec[3] = p.shoot_cooldown / SHOOT_COOLDOWN
        vec[4] = ((p.x + p.w // 2) % TILE) / TILE
        vec[5] = min(1.0, p.y / (ROWS * TILE))
        for i, (_, e) in enumerate(nearest[:NEAREST_ENEMIES]):
            vec[6 + 3 * i] = np.clip((e.x - p.x) / 600.0, -1.0, 1.0)
            vec[7 + 3 * i] = np.clip((e.y - p.y) / 400.0, -1.0, 1.0)
            vec[8 + 3 * i] = 1.0
        return {"grid": grid, "vec": np.clip(vec, -1.0, 1.0)}
