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
    overview float32 (4, 13, 32), only with overview=True (phase 6+): a coarse map
          far ahead - 32 columns of 4 tiles each, from 8 tiles behind to 120 ahead:
            0 share of solid blocks in the 4 tiles (0, .25, .5, .75, 1)
            1 standable surface (a block with free space above) in any of the 4 tiles
            2 enemy present
            3 chest
          It lets the bot notice a dead end or the chest long before it is on screen.

Actions: 6 discrete (see core.actions.BOT_ACTIONS; 7 with obs_v3: + left+jump), each held for `action_repeat` frames
(4 for models up to phase 3, 2 from phase 5 on).

Reward (deliberately minimal):
    +0.1 per tile of new rightmost progress, -1 on death, +2 on the chest.
Episodes end on win / death (terminated) or after too long without new
progress (truncated).
"""

from __future__ import annotations

import math
import random
from collections import deque
from typing import Callable, Optional

import gymnasium as gym
import numpy as np

from jumpnrun.core.actions import ACTION_REPEAT, BOT_ACTIONS, BOT_ACTIONS_V3
from jumpnrun.core.constants import MAX_FALL_SPEED, ROWS, SHOOT_COOLDOWN, TILE
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status

REWIND_TIER = -3  # same value as jumpnrun.rl.curriculum.REWIND_TIER
MID_START_TIER = -2  # same value as jumpnrun.rl.curriculum.MID_START_TIER

VIEW_BEHIND = 5
VIEW_AHEAD = 19
VIEW_COLS = VIEW_BEHIND + 1 + VIEW_AHEAD
GRID_CHANNELS = 4
VEC_SIZE = 15
VEC_SIZE_V2 = 21  # phase 8 (--obs-v2): + distance behind the furthest point, no-progress and time budget, enemy fall speeds
VEC_SIZE_V3 = 23  # phase 9 (--obs-v3): + direction to the chest (dx, dy) - a compass, not a way map
VIEW_BEHIND_V3 = 13  # phase 9: the grid shows 13 tiles behind (turning back, channels going left)
OV_BEHIND_V3 = 40  # phase 9: the overview reaches 40 tiles behind ...
OV_COLS_V3 = 40  # ... with 8 more columns (the part ahead stays the same)
NEAREST_ENEMIES = 3
OV_BEHIND = 8  # tiles
OV_COLS = 32
OV_SCALE = 4  # tiles per overview column
OV_CHANNELS = 4
OV_AHEAD = OV_COLS * OV_SCALE - OV_BEHIND

REWARD_PER_TILE = 0.1
REWARD_DEATH = -1.0
REWARD_WIN = 2.0
NO_PROGRESS_FRAMES = 600  # episode is truncated after this many frames without new progress
PATH_TIME_FACTOR = 1.2  # phase 10: time limit covers 1.2 x the way to the chest (at least the level width)
NO_PROGRESS_STEPS = NO_PROGRESS_FRAMES // ACTION_REPEAT  # (at the legacy repeat of 4)

# A level source returns (level, tier) for each new episode. tier = -1 for hand-made levels.
LevelSource = Callable[[random.Random], "tuple[Level, int]"]


def fixed_levels(levels) -> LevelSource:
    """Level source that cycles randomly through a fixed list of levels."""

    levels = list(levels)
    return lambda rng: (rng.choice(levels), -1)


class JumpNRunEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        level_source: LevelSource,
        seed: Optional[int] = None,
        max_frames_per_tile: float = 12.0,
        action_repeat: int = ACTION_REPEAT,
        overview: bool = False,
        rewind_prob: float = 0.0,
        rewind_every: int = 20,
        rewind_budget: int = 2,
        obs_v2: bool = False,
        stuck_death: bool = False,
        obs_v3: bool = False,
        path_reward: bool = False,
        path_delta: bool = False,
        progress: str = "x",
        path_time_factor: float = 0.0,
    ):
        super().__init__()
        self.level_source = level_source
        self.rng = random.Random(seed)
        self.action_repeat = int(action_repeat)
        self.max_steps_per_tile = max_frames_per_tile / self.action_repeat
        self.no_progress_steps = NO_PROGRESS_FRAMES // self.action_repeat
        self.action_space = gym.spaces.Discrete(len(BOT_ACTIONS_V3) if obs_v3 else len(BOT_ACTIONS))
        self.overview = bool(overview)
        self.obs_v3 = bool(obs_v3)
        self.obs_v2 = bool(obs_v2) or self.obs_v3
        self.view_behind = VIEW_BEHIND_V3 if self.obs_v3 else VIEW_BEHIND
        self.view_cols = self.view_behind + 1 + VIEW_AHEAD
        self.ov_behind = OV_BEHIND_V3 if self.obs_v3 else OV_BEHIND
        self.ov_cols = OV_COLS_V3 if self.obs_v3 else OV_COLS
        vec_size = VEC_SIZE_V3 if self.obs_v3 else VEC_SIZE_V2 if self.obs_v2 else VEC_SIZE
        # phase 9: reward progress along the way to the chest (distance map) instead of new rightmost x
        self.path_reward = bool(path_reward) or bool(path_delta)
        # path_delta: potential-based shaping - every tile closer to the chest +0.1, every tile further away
        # -0.1 (walking onto a dead end costs, turning back pays at once; loops sum to zero)
        self.path_delta = bool(path_delta)
        self.cur_dist = None
        # phase 10: "stuck" counts frames without a new best of the way distance (progress="path") instead of
        # frames without a new rightmost x - turning back is no longer cut off as "stuck" (phase-9 measurement
        # bug: even the solver's solutions of serpentine / spiegelweg ended as "stuck"). Without a reward change.
        self.progress = "path" if self.path_reward else progress
        # phase 10: time limit from the length of the way, max(cols, factor * start distance) tiles
        self.path_time_factor = float(path_time_factor or (PATH_TIME_FACTOR if self.progress == "path" else 0.0))
        self.dm = None
        self.best_dist = None
        # phase 8: getting stuck (no new progress for NO_PROGRESS_FRAMES) ends the episode like a death
        self.stuck_death = bool(stuck_death)
        spaces = {
            "grid": gym.spaces.Box(-1.0, 1.0, (GRID_CHANNELS, ROWS, self.view_cols), np.float32),
            "vec": gym.spaces.Box(-1.0, 1.0, (vec_size,), np.float32),
        }
        if self.overview:
            spaces["overview"] = gym.spaces.Box(0.0, 1.0, (OV_CHANNELS, ROWS, self.ov_cols), np.float32)
        self.observation_space = gym.spaces.Dict(spaces)
        self.sim: Optional[Simulation] = None
        self.tier = -1
        self.actions_taken: list = []
        # rewind starts: after a failure, sometimes restart shortly before it (practise the weak spot)
        self.rewind_prob = float(rewind_prob)
        self.rewind_every = int(rewind_every)
        self.rewind_budget = int(rewind_budget)
        self._snapshots: deque = deque(maxlen=8)
        self._pending = None  # (simulation snapshot, origin tier, depth)
        self.origin_tier = -1
        self.rewind_depth = 0

    # ---------------------------------------------------------------- gym api
    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        if seed is not None:
            self.rng = random.Random(seed)
        prefix = None
        self._snapshots.clear()
        pending, self._pending = self._pending, None
        if pending is not None and not options and self.rng.random() < self.rewind_prob:
            snapshot, self.origin_tier, self.rewind_depth = pending
            self.tier = REWIND_TIER
            self.sim = snapshot.clone()
            self.start_col = self.sim.player.x // TILE
            self._begin_episode(self.level)
            return self._observe(), {}
        self.rewind_depth = 0
        if options and "level" in options:
            level, self.tier = options["level"], options.get("tier", -1)
        else:
            level, self.tier, *rest = self.level_source(self.rng)
            prefix = rest[0] if rest else None
        self.origin_tier = self.tier
        self._set_level(level)
        self.sim = Simulation(level)
        self.start_col = 0
        if prefix is not None:  # start in the middle: replay the first part of a teacher's run
            repeat, actions = prefix
            for action in actions:
                self.sim.step(BOT_ACTIONS_V3[action], frames=repeat)
            if self.sim.status != Status.RUNNING:  # should not happen (won demos), fall back to the start
                self.sim = Simulation(level)
            self.start_col = self.sim.player.x // TILE
        self._begin_episode(level)
        return self._observe(), {}

    def _begin_episode(self, level: Level) -> None:
        self.steps = 0
        self.steps_since_progress = 0
        self.max_steps = int(level.cols * self.max_steps_per_tile) + 200 // self.action_repeat
        self.actions_taken = []
        if self.rewind_prob and self.sim.player.on_ground:
            self._snapshots.append(self.sim.clone())
        self.best_dist = None
        if self.progress == "path":
            from jumpnrun.levelgen.distmap import DistanceMap

            if self.dm is None or self.dm.level is not level:
                self.dm = DistanceMap(level)
            p = self.sim.player
            here = self.dm.at_xy(p.x, p.y, p.w, p.h) if self.dm.reachable else None
            if here is None and self.dm.reachable:
                here = self.dm.start
            self.best_dist = here  # None: no way known - this episode falls back to the x reward
            self.cur_dist = here
            self.start_dist = here
            if here is not None and self.path_time_factor:
                tiles = max(level.cols, math.ceil(self.path_time_factor * here))
                self.max_steps = int(tiles * self.max_steps_per_tile) + 200 // self.action_repeat

    def step(self, action: int):
        before = self.sim.max_x
        self.sim.step(BOT_ACTIONS_V3[int(action)], frames=self.action_repeat)
        return self.finish_step(int(action), before)

    def finish_step(self, action: int, max_x_before: int):
        """Reward / termination bookkeeping after the frames of one bot step.

        Split from step() so the ghost view can advance many games frame by frame.
        """

        sim = self.sim
        status = sim.status
        self.steps += 1
        self.actions_taken.append(action)

        if self.best_dist is not None:
            gained = 0.0
            here = self.dm.at_player(sim.player)
            if here is not None and here < self.best_dist:
                gained, self.best_dist = self.best_dist - here, here
            reward = REWARD_PER_TILE * gained
            if not self.path_reward:  # path progress only for "stuck": the reward stays "new rightmost x"
                reward = REWARD_PER_TILE * (sim.max_x - max_x_before) / TILE
            elif self.path_delta:
                reward = 0.0
                if here is not None:
                    reward = REWARD_PER_TILE * (self.cur_dist - here)
                    self.cur_dist = here
        else:
            gained = sim.max_x - max_x_before
            reward = REWARD_PER_TILE * gained / TILE
        self.steps_since_progress = 0 if gained > 0 else self.steps_since_progress + 1

        terminated = status != Status.RUNNING
        if status == Status.WON:
            reward += REWARD_WIN
        elif terminated:
            reward += REWARD_DEATH
        stuck = not terminated and self.steps_since_progress >= self.no_progress_steps
        if stuck and self.stuck_death:
            terminated = True
            reward += REWARD_DEATH
        truncated = not terminated and (stuck or self.steps >= self.max_steps)

        if self.rewind_prob:
            if status == Status.RUNNING and self.steps % self.rewind_every == 0 and sim.player.on_ground:
                self._snapshots.append(sim.clone())
            if (terminated or truncated) and status != Status.WON and self._snapshots \
                    and self.rewind_depth < self.rewind_budget:
                back = min(len(self._snapshots), self.rng.randint(2, 4))
                self._pending = (self._snapshots[-back], self.origin_tier, self.rewind_depth + 1)

        info = {"p8_level": (getattr(sim.level, "mix_source", None) or "p8") == "p8",  # phase 10 D: teacher mask
                "teacher": getattr(sim.level, "teacher_id", -1)}  # phase 12: teacher of the level's family
        if terminated or truncated:
            feedback = getattr(self.level_source, "feedback", None)
            if feedback is not None:
                fresh = self.rewind_depth == 0 and self.tier not in (REWIND_TIER, MID_START_TIER)
                try:  # phase 10: the mix source counts steps per source
                    feedback(sim.level, self.origin_tier, status == Status.WON, steps=self.steps, fresh=fresh)
                except TypeError:
                    feedback(sim.level, self.origin_tier, status == Status.WON)
            info["episode_end"] = {
                "outcome": status.value if status != Status.RUNNING else ("stuck" if stuck else "timeout"),
                "won": status == Status.WON,
                "tier": self.tier,
                "level": sim.level.name,
                "progress": self._progress(),
                "path": self.best_dist is not None,
                "steps": self.steps,
                "kills": sim.kills_stomp + sim.kills_shot,
                "blocks": sorted(getattr(sim.level, "building_blocks", {})),
                "start_col": self.start_col,
                "origin_tier": self.origin_tier,
                "rewind_depth": self.rewind_depth,
                "source": getattr(sim.level, "source", None),
                "aug": getattr(sim.level, "augmentations", None) or [],
                "mix": getattr(sim.level, "mix_source", None),
                "kind": getattr(sim.level, "skill_kind", None),
                "difficulty": getattr(sim.level, "difficulty", None),
            }
        return self._observe(), float(reward), terminated, truncated, info

    def _progress(self) -> float:
        if self.sim.status == Status.WON:
            return 1.0
        if self.best_dist is not None and self.start_dist:
            return max(0.0, min(1.0, 1.0 - self.best_dist / self.start_dist))
        return min(1.0, self.sim.max_x / max(1, self.sim.level.goal_x))

    def set_mix_stage(self, idx: int) -> None:
        """Called by the MixScheduler callback (phase 10)."""

        if hasattr(self.level_source, "set_mix_stage"):
            self.level_source.set_mix_stage(idx)

    def set_skill_state(self, levels: dict, p: dict) -> None:
        """Phase 11: practice difficulty pooled over all envs (SkillTracker in the training process)."""

        if hasattr(self.level_source, "set_skill_state"):
            self.level_source.set_skill_state(levels, p)

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
        pad_l, pad_r = self.view_behind + 1, VIEW_AHEAD + 1
        static = np.zeros((2, ROWS, level.cols + pad_l + pad_r), np.float32)
        static[0, :, :pad_l] = 1.0  # left border
        static[0, :, pad_l + level.cols:] = 1.0  # right border
        static[0, :, pad_l:pad_l + level.cols] = np.array([list(row) for row in level.solid], np.float32)
        for cx, cy, _, _ in level.chests:
            static[1, min(cy // TILE, ROWS - 1), pad_l + cx // TILE] = 1.0
        self._static = static
        self._pad_l = pad_l
        if self.overview:
            self._set_overview(level)

    def _set_overview(self, level: Level) -> None:
        """Window sums over 4 tiles for every start column, so observing is just an index lookup."""

        pad_l, pad_r = self.ov_behind + 1, self.ov_cols * OV_SCALE - self.ov_behind + OV_SCALE + 1
        width = level.cols + pad_l + pad_r
        solid = np.ones((ROWS, width), np.float32)  # outside the level counts as wall
        solid[:, pad_l:pad_l + level.cols] = np.array([list(row) for row in level.solid], np.float32)
        stand = np.zeros_like(solid)
        stand[1:] = solid[1:] * (1.0 - solid[:-1])
        stand[:, :pad_l] = 0.0
        stand[:, pad_l + level.cols:] = 0.0
        chest = np.zeros_like(solid)
        for cx, cy, _, _ in level.chests:
            chest[min(cy // TILE, ROWS - 1), pad_l + cx // TILE] = 1.0
        n = width - OV_SCALE + 1
        share = sum(solid[:, i:i + n] for i in range(OV_SCALE)) / OV_SCALE
        stand_any = np.maximum.reduce([stand[:, i:i + n] for i in range(OV_SCALE)])
        chest_any = np.maximum.reduce([chest[:, i:i + n] for i in range(OV_SCALE)])
        self._ov_static = np.stack([share, stand_any, chest_any])
        self._ov_pad = pad_l

    def _observe(self):
        sim = self.sim
        p = sim.player
        pcol = (p.x + p.w // 2) // TILE
        c0 = pcol - self.view_behind  # level column shown in grid column 0

        grid = np.zeros((GRID_CHANNELS, ROWS, self.view_cols), np.float32)
        grid[0:2] = self._static[:, :, c0 + self._pad_l: c0 + self._pad_l + self.view_cols]
        prow = (p.y + p.h // 2) // TILE
        if 0 <= prow < ROWS:
            grid[3, prow, self.view_behind] = 1.0

        nearest = []
        for e in sim.enemies:
            ecol = (e.x + e.w // 2) // TILE - c0
            erow = (e.y + e.h // 2) // TILE
            if 0 <= ecol < self.view_cols and 0 <= erow < ROWS:
                grid[2, erow, ecol] = float(e.direction)
            nearest.append((abs(e.x - p.x) + abs(e.y - p.y), e))
        nearest.sort(key=lambda item: item[0])

        vec = np.zeros(self.observation_space["vec"].shape[0], np.float32)
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
        if self.obs_v2:
            vec[15] = (p.x - sim.max_x) / 600.0  # how far behind the furthest point reached (turning back)
            vec[16] = self.steps_since_progress / max(1, self.no_progress_steps)
            vec[17] = 1.0 - self.steps / max(1, self.max_steps)
            for i, (_, e) in enumerate(nearest[:NEAREST_ENEMIES]):
                vec[18 + i] = e.vy / MAX_FALL_SPEED
        if self.obs_v3:
            cx, cy, cw, ch = min(sim.level.chests, key=lambda c: abs(c[0] - p.x) + abs(c[1] - p.y))
            vec[21] = (cx + cw // 2 - p.x - p.w // 2) / 3000.0
            vec[22] = (cy + ch - p.y - p.h) / (ROWS * TILE)
        obs = {"grid": grid, "vec": np.clip(vec, -1.0, 1.0)}
        if self.overview:
            obs["overview"] = self._observe_overview(pcol)
        return obs

    def _observe_overview(self, pcol: int) -> np.ndarray:
        start = pcol - self.ov_behind  # level column where overview column 0 begins
        idx = start + self._ov_pad + OV_SCALE * np.arange(self.ov_cols)
        ov = np.zeros((OV_CHANNELS, ROWS, self.ov_cols), np.float32)
        ov[0] = self._ov_static[0][:, idx]
        ov[1] = self._ov_static[1][:, idx]
        ov[3] = self._ov_static[2][:, idx]
        for e in self.sim.enemies:
            j = ((e.x + e.w // 2) // TILE - start) // OV_SCALE
            row = (e.y + e.h // 2) // TILE
            if 0 <= j < self.ov_cols and 0 <= row < ROWS:
                ov[2, row, j] = 1.0
        return ov
