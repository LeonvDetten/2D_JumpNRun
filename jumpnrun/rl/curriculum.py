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


def load_pool_texts(pool_dir, min_count: int = 100) -> dict:
    """Solver-verified levels as stored text ({tier: [level text, ...]}) from `<pool_dir>/demos*.jsonl`.

    Using the stored text (instead of re-generating from the seed) means the pool can never drift
    away from what the solver verified when the generator changes later.
    """

    import json
    from pathlib import Path

    texts: dict = {}
    for path in sorted(Path(pool_dir).glob("demos*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    demo = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if demo.get("level"):
                    texts.setdefault(int(demo["tier"]), []).append(demo["level"])
    return {tier: t for tier, t in texts.items() if len(t) >= min_count}


MID_START_TIER = -2  # episodes that start in the middle of a level (not counted for the curriculum)
REWIND_TIER = -3  # episodes restarted shortly before the bot's own last failure (not counted either)
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


PLR_SIZE = 400  # levels kept per env
PLR_MIN = 50  # replay starts once the buffer holds this many levels


def _plr_score(item: dict) -> float:
    p = (item["wins"] + 1) / (item["n"] + 2)
    return p * (1 - p)


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
        pool_share: float = 1.0,
        augment_prob: float = 0.0,
        plr: float = 0.0,
        gen_variant: str = "v9",
        augment_v2: bool = False,
    ):
        self.min_tier = min_tier
        # phase 8: tiers with a stored pool draw a stored level only with this probability, otherwise a
        # fresh one from the current generator (phase 7 bug: with 1.0 generator changes never arrived)
        self.pool_share = pool_share
        # phase 8: share of episodes whose level gets augmented (jumpnrun/levelgen/augment.py)
        self.augment_prob = augment_prob
        # phase 8 round 3: Prioritized Level Replay - replay generated levels with the highest learning
        # potential (score p * (1 - p), p = estimated win rate), filled from the outcomes reported by the env
        self.plr = plr
        # phase 9: generator variant for fresh levels ("v9" | "gabel" | "v10") and augmentation config V2
        self.gen_variant = gen_variant
        self.augment_v2 = augment_v2
        self._plr: dict = {}
        self.max_tier = max_tier
        self.weights: List[float] = [0.0] * NUM_TIERS
        self.weights[min_tier] = 1.0
        self.handmade = list(handmade or [])
        self.handmade_prob = handmade_prob if self.handmade else 0.0
        # optional pool of solver-verified seeds per tier (tier -> list of seeds)
        self.pool = load_pool(pool_dir) if pool_dir else {}
        self.pool_texts = load_pool_texts(pool_dir) if pool_dir else {}
        self._parsed: dict = {}
        # "random start points": sometimes begin somewhere along a teacher's winning run
        self.starts = load_starts(start_dirs) if start_prob and start_dirs else []
        self.start_prob = start_prob if self.starts else 0.0

    def __call__(self, rng: random.Random):
        if self.start_prob and rng.random() < self.start_prob:
            tier, seed, text, repeat, actions = rng.choice(self.starts)
            level = Level.from_text(text) if text else generate(tier, seed)
            level.source, level.augmentations = "midstart", []
            cut = rng.randrange(len(actions) // 10, len(actions) - 30)
            return level, MID_START_TIER, (repeat, actions[:cut])
        if self.handmade_prob and rng.random() < self.handmade_prob:
            return self._augmented(rng.choice(self.handmade), rng, "handmade"), -1
        if self.plr and len(self._plr) >= PLR_MIN and rng.random() < self.plr:
            return self._replay(rng)
        tier = rng.choices(range(NUM_TIERS), weights=self.weights)[0]
        texts = self.pool_texts.get(tier)
        if texts and (self.pool_share >= 1.0 or rng.random() < self.pool_share):
            text = rng.choice(texts)
            if text not in self._parsed:
                if len(self._parsed) > 4000:
                    self._parsed.clear()
                self._parsed[text] = Level.from_text(text)
            return self._augmented(self._parsed[text], rng, "pool", tier), tier
        seeds = self.pool.get(tier) if not texts else None
        seed = rng.choice(seeds) if seeds else rng.randrange(EVAL_SEED_OFFSET)
        return self._augmented(generate(tier, seed, self.gen_variant), rng, "fresh", tier), tier

    def _replay(self, rng: random.Random):
        keys = list(self._plr)
        weights = [_plr_score(self._plr[k]) + 0.02 for k in keys]
        key = rng.choices(keys, weights=weights)[0]
        item = self._plr[key]
        item["level"].source = "plr"
        return item["level"], item["tier"]

    def feedback(self, level: Level, tier: int, won: bool, **_) -> None:
        """Outcome of an episode (called by the env); feeds the PLR buffer."""

        if not self.plr or tier < 6 or getattr(level, "source", None) not in ("fresh", "pool", "plr"):
            return
        key = id(level)
        item = self._plr.get(key)
        if item is None:
            if len(self._plr) >= PLR_SIZE:
                worst = min(self._plr, key=lambda k: _plr_score(self._plr[k]))
                del self._plr[worst]
            item = self._plr[key] = {"level": level, "tier": tier, "n": 0, "wins": 0}
        item["n"] += 1
        item["wins"] += int(won)

    def _augmented(self, level: Level, rng: random.Random, source: str, tier: int = -1) -> Level:
        if self.augment_prob and rng.random() < self.augment_prob:
            from jumpnrun.levelgen.augment import DEFAULT, V2, augment

            partner = None
            if self.augment_v2 and tier >= 6:  # a second level for "concat" (longer levels)
                partner = generate(tier, rng.randrange(EVAL_SEED_OFFSET), self.gen_variant)
            level, _ = augment(level, rng, V2 if self.augment_v2 else DEFAULT, partner=partner)
        else:
            level.augmentations = getattr(level, "augmentations", None) or []
        level.source = source
        return level


class MixSource:
    """Phase 10: several level sources mixed by TRAINING STEPS, in stages ("erst üben, dann mischen").

    sources  {"p8": CurriculumSource, "v10": CurriculumSource, "skill": SkillSource}
    schedule [[stage_start_steps, {"skill": 0.55, "v10": 0.0, "p8": 0.45}], ...] (steps relative to the phase start;
             the stage is set from outside by the MixScheduler callback via set_mix_stage)
    Deficit control: each new episode comes from the source furthest behind its target share of the steps played
    in the current stage, so the shares hold in steps although practice episodes are much shorter.
    """

    def __init__(self, sources: dict, schedule: list):
        self.sources = sources
        self.schedule = sorted(([int(a), dict(b)] for a, b in schedule), key=lambda x: x[0])
        self.stage = 0
        self.steps = {n: 0 for n in sources}

    @property
    def weights(self):
        return self.sources["p8"].weights

    @weights.setter
    def weights(self, value):  # the tier curriculum only steers the phase-8 source
        self.sources["p8"].weights = value

    def set_skill_state(self, levels: dict, p: dict) -> None:
        if "skill" in self.sources:
            self.sources["skill"].set_state(levels, p)

    def set_mix_stage(self, idx: int) -> None:
        if idx != self.stage:
            self.stage = idx
            self.steps = {n: 0 for n in self.sources}

    def shares(self) -> dict:
        return self.schedule[min(self.stage, len(self.schedule) - 1)][1]

    def __call__(self, rng: random.Random):
        shares = {n: v for n, v in self.shares().items() if v > 0 and n in self.sources}
        total = sum(self.steps.values())
        if total == 0:
            name = rng.choices(list(shares), weights=list(shares.values()))[0]
        else:
            name = max(shares, key=lambda n: (shares[n] * total - self.steps[n], rng.random()))
        level, tier, *rest = self.sources[name](rng)
        level.mix_source = name
        return (level, tier, *rest)

    def feedback(self, level: Level, tier: int, won: bool, steps: int = 0, fresh: bool = True) -> None:
        # mid-start episodes (demos4 levels, chosen by the env, not by this source) are phase-8 data
        name = getattr(level, "mix_source", None) or "p8"
        if name not in self.sources:
            return
        self.steps[name] += steps
        src = self.sources[name]
        if name == "skill":
            src.feedback(level, won, fresh)
        else:
            src.feedback(level, tier, won)


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
