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


class CurriculumSource:
    """Level source for JumpNRunEnv. Lives inside each (sub-process) env."""

    def __init__(
        self,
        min_tier: int = 0,
        max_tier: int = NUM_TIERS - 1,
        handmade: Optional[Sequence[Level]] = None,
        handmade_prob: float = 0.0,
    ):
        self.min_tier = min_tier
        self.max_tier = max_tier
        self.weights: List[float] = [0.0] * NUM_TIERS
        self.weights[min_tier] = 1.0
        self.handmade = list(handmade or [])
        self.handmade_prob = handmade_prob if self.handmade else 0.0

    def __call__(self, rng: random.Random):
        if self.handmade_prob and rng.random() < self.handmade_prob:
            return rng.choice(self.handmade), -1
        tier = rng.choices(range(NUM_TIERS), weights=self.weights)[0]
        return generate(tier, rng.randrange(EVAL_SEED_OFFSET)), tier


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
