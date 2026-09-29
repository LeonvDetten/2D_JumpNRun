"""Curriculum: which difficulty tier should the next training level have?

Idea ("learning frontier"): the bot learns most from levels it wins about
half of the time. Too easy = nothing new, too hard = only failures.

    * Tiers are unlocked one by one: the next tier opens once the currently
      hardest tier is won often enough (UNLOCK_SUCCESS).
    * Among unlocked tiers, a tier is picked with weight
      success * (1 - success) + EXPLORE, so frontier tiers are preferred,
      but easy tiers keep appearing now and then (no forgetting).
"""

from __future__ import annotations

import random
from typing import List, Optional, Sequence

from jumpnrun.core.level import Level
from jumpnrun.levelgen.generator import NUM_TIERS, generate

UNLOCK_SUCCESS = 0.6
EXPLORE = 0.05
EMA = 0.05  # how fast the success estimate follows new results
EVAL_SEED_OFFSET = 10**12  # evaluation levels use seeds the training never sees


def load_pool(pool_dir) -> dict:
    """Read `<pool_dir>/pool.json` ({tier: [seed, ...]}) written by jumpnrun.imitation.demos."""

    import json
    from pathlib import Path

    path = Path(pool_dir) / "pool.json"
    if not path.exists():
        return {}
    # tiers with only a few verified levels keep generating fresh ones (those tiers are always solvable)
    return {int(tier): seeds for tier, seeds in json.loads(path.read_text()).items() if len(seeds) >= 100}


MID_START_TIER = -2  # episodes that start in the middle of a level (not counted for the curriculum)
_START_CACHE: dict = {}


def load_starts(demo_dirs, min_tier: int = 4) -> list:
    """Won teacher demos as (tier, seed, level text or None, repeat, actions) - the start-point pool."""

    key = tuple(str(d) for d in demo_dirs)
    if key not in _START_CACHE:
        import json
        from pathlib import Path

        starts = []
        for folder in demo_dirs:
            for path in sorted(Path(folder).glob("demos*.jsonl")):
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        demo = json.loads(line)
                        if demo.get("won") and demo["tier"] >= min_tier and len(demo["actions"]) > 60:
                            entry = (demo["tier"], demo["seed"], demo.get("level"), demo["repeat"],
                                     demo["actions"])
                            # long levels hold most of the hard late sections: offered 3x as often
                            starts += [entry] * (3 if demo["tier"] >= 10 else 1)
        _START_CACHE[key] = starts
    return _START_CACHE[key]


class CurriculumSource:
    """Level source for JumpNRunEnv. Lives inside each (sub-process) env."""

    def __init__(
        self,
        min_tier: int = 0,
        max_tier: int = NUM_TIERS - 1,
        handmade: Optional[Sequence[Level]] = None,
        handmade_prob: float = 0.0,
        pool_dir=None,
        start_prob: float = 0.0,
        start_dirs=(),
    ):
        self.min_tier = min_tier
        self.max_tier = max_tier
        self.weights: List[float] = [0.0] * NUM_TIERS
        self.weights[min_tier] = 1.0
        self.handmade = list(handmade or [])
        self.handmade_prob = handmade_prob if self.handmade else 0.0
        # optional pool of solver-verified seeds per tier (tier -> list of seeds)
        self.pool = load_pool(pool_dir) if pool_dir else {}
        # "random start points": sometimes begin somewhere along a teacher's winning run
        self.starts = load_starts(start_dirs) if start_prob and start_dirs else []
        self.start_prob = start_prob if self.starts else 0.0

    def __call__(self, rng: random.Random):
        if self.start_prob and rng.random() < self.start_prob:
            tier, seed, text, repeat, actions = rng.choice(self.starts)
            level = Level.from_text(text) if text else generate(tier, seed)
            cut = rng.randrange(len(actions) // 10, len(actions) - 30)
            return level, MID_START_TIER, (repeat, actions[:cut])
        if self.handmade_prob and rng.random() < self.handmade_prob:
            return rng.choice(self.handmade), -1
        tier = rng.choices(range(NUM_TIERS), weights=self.weights)[0]
        seeds = self.pool.get(tier)
        seed = rng.choice(seeds) if seeds else rng.randrange(EVAL_SEED_OFFSET)
        return generate(tier, seed), tier


class CurriculumTracker:
    """Runs in the training process: tracks success per tier, computes weights."""

    def __init__(self, min_tier: int = 0, max_tier: int = NUM_TIERS - 1):
        self.min_tier = min_tier
        self.max_tier = max_tier
        self.success = [0.0] * NUM_TIERS
        self.episodes = [0] * NUM_TIERS
        self.unlocked = min_tier

    def record(self, tier: int, won: bool) -> None:
        if tier < 0:
            return
        self.episodes[tier] += 1
        rate = EMA if self.episodes[tier] > 1 / EMA else 1.0 / self.episodes[tier]
        self.success[tier] += rate * (float(won) - self.success[tier])
        if (
            tier == self.unlocked
            and self.unlocked < self.max_tier
            and self.episodes[tier] >= 50
            and self.success[tier] >= UNLOCK_SUCCESS
        ):
            self.unlocked += 1

    def weights(self) -> List[float]:
        weights = [0.0] * NUM_TIERS
        for tier in range(self.min_tier, self.unlocked + 1):
            s = self.success[tier] if self.episodes[tier] else 0.5
            weights[tier] = s * (1.0 - s) + EXPLORE
        return weights
