"""Phase 13: training levels that go LEFT with the hardest jumps (MixSource name "links").

Why: in phase 12 the mirrored source only mirrored random v9 levels (tiers 4-12) - half unsolvable, half easy -
and the precise jump chains of v11 and the exam skills were never seen going left. The game is symmetric, so a
mirrored level IS a left level; what was missing were the right levels to mirror. Families:

    links_spruenge    v11 jump families (half from the solver-proven pool runs/demos12, half fresh), mirrored
    links_trittsteine v9 tiers 8-12 in the "pruefung" variant (stones, chains, rain stairs, jump sequences x3),
                      mirrored - own adaptive curriculum over the tiers (frontier: >= 50 % won)
    links_lang        two such levels joined (<= 480 tiles), mirrored

Half of the levels let the enemies start walking left (mirrored behaviour), half keep the default.
Own seed space "links13"; never built from dev / exam / probe geometry.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

from jumpnrun.core.level import Level
from jumpnrun.levelgen import generator as G
from jumpnrun.levelgen.skills import concat_levels, mirror_level

ROOT = Path(__file__).resolve().parent.parent.parent
POOL = ROOT / "runs/demos12/demos.jsonl"
FAMILIES = {"links_spruenge": 0.40, "links_trittsteine": 0.45, "links_lang": 0.15}
TIERS = list(range(8, 13))
MAX_LONG = 480


def _reachable(level: Level) -> bool:
    from jumpnrun.levelgen.distmap import DistanceMap

    dm = DistanceMap(level)
    if not dm.reachable:
        return False
    x, y = level.spawn
    return dm.at_xy(x, y, 40, 60) is not None or dm.below(x, y, 40, 60) is not None


class LeftSource:
    """MixSource "links" - see the module doc. `feedback` drives the tier curriculum of links_trittsteine."""

    LEFT_TIER = -9
    WINDOW = 30

    def __init__(self, weights=None, pool: Optional[Path] = POOL, seed_space: str = "links13",
                 start_frontier: int = 9):
        self.weights = dict(weights or FAMILIES)
        self.pool_path, self._pool = pool, None
        self.seed_space = seed_space
        self.start_frontier = start_frontier
        self.hist = {t: [] for t in TIERS}

    # ---------------------------------------------------------------------------------------- curriculum
    def frontier(self) -> int:
        f = TIERS[0] - 1
        for t in TIERS:
            h = self.hist[t]
            if len(h) >= 10:
                if sum(h) / len(h) < 0.5:
                    break
            elif t > self.start_frontier:
                break
            f = t
        return f

    def _tier(self, rng: random.Random) -> int:
        if rng.random() < 0.1:
            return rng.choice(TIERS)
        f = self.frontier()
        weights = [2.0 if t == f + 1 else 1.0 if t <= f else 0.0 for t in TIERS]
        if not any(weights):
            weights[0] = 1.0
        return rng.choices(TIERS, weights)[0]

    def feedback(self, level: Level = None, tier: int = None, won: bool = False, *args, **kwargs) -> None:
        t = getattr(level, "links_tier", None)
        if t in self.hist:
            self.hist[t] = (self.hist[t] + [1.0 if won else 0.0])[-self.WINDOW:]

    # ------------------------------------------------------------------------------------------ families
    def _pool_level(self, rng: random.Random) -> Optional[Level]:
        if self._pool is None:
            p = Path(self.pool_path) if self.pool_path else None
            self._pool = [d for d in (json.loads(l) for l in p.read_text().splitlines() if l.strip())
                          if d.get("family") in ("spruenge", "gemischt")] if p and p.exists() else []
        if not self._pool:
            return None
        d = rng.choice(self._pool)
        return Level.from_text(d["level"], name=f"links_pool_{d['seed']}")

    def _spruenge(self, rng: random.Random) -> Level:
        if rng.random() < 0.5:
            level = self._pool_level(rng)
            if level is not None:
                return level
        from jumpnrun.levelgen.hard import make_hard_level

        fam = rng.choice(("spruenge", "spruenge", "gemischt"))
        for _ in range(5):
            try:
                return make_hard_level(fam, f"{self.seed_space}:{fam}:{rng.randrange(10**9)}")
            except RuntimeError:
                continue
        return G.generate(12, rng.randrange(10**8), "pruefung")

    def _trittsteine(self, rng: random.Random, tier: int) -> Level:
        return G.generate(tier, 70_000_000 + rng.randrange(10**7), "pruefung")

    def _lang(self, rng: random.Random) -> Optional[Level]:
        for _ in range(10):
            a = G.generate(rng.choice(TIERS[:3]), 80_000_000 + rng.randrange(10**7), "pruefung")
            b = G.generate(rng.choice(TIERS[:3]), 80_000_000 + rng.randrange(10**7), "pruefung")
            level = concat_levels(a, b, name="links_lang")
            if level is not None and level.cols <= MAX_LONG:
                return level
        return None

    def __call__(self, rng: random.Random):
        for _ in range(10):
            fam = rng.choices(list(self.weights), weights=list(self.weights.values()))[0]
            tier = self._tier(rng) if fam == "links_trittsteine" else None
            base = (self._spruenge(rng) if fam == "links_spruenge" else
                    self._trittsteine(rng, tier) if fam == "links_trittsteine" else self._lang(rng))
            if base is None:
                continue
            level = mirror_level(base, name=f"{fam}_{base.name}")
            if not _reachable(level):
                continue
            if rng.random() < 0.5 and level.enemy_spawns:
                level.enemy_directions = [-1] * len(level.enemy_spawns)  # enemies mirrored too
            level.family = fam
            level.links_tier = tier
            level.source = "links"
            level.augmentations = ["mirror"]
            return level, self.LEFT_TIER
        raise RuntimeError("no reachable left level in 10 tries")
