"""Procedural level generator with difficulty tiers.

Levels are built left to right from small segments whose sizes respect the
jump physics (apex 78 px, ~3 tiles horizontal reach):

    flat          walk (maybe with a step up / down)
    gap           pit of 1..max_gap tiles
    valley        drop down, flat floor with an enemy, climb back up
                  (the enemy is trapped between the walls)
    platforms     pit with floating platforms to hop across
    climb         floating blocks leading up to a high plateau; below it the
                  ground runs into a dead end (the upper route is the only way)

Every level is reproducible from (tier, seed). The solver checks samples in
the tests, so "solvable for the bot" is verified, not assumed.

CLI:
    python -m jumpnrun.levelgen.generator --tier 3 --seed 7 [--out level.txt]
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from typing import List

from jumpnrun.core.constants import ROWS
from jumpnrun.core.level import Level

GROUND = ROWS - 1  # surface row of the lowest possible ground
HIGHEST_SURFACE = 5  # never build terrain higher than this row (headroom for jumps)


@dataclass(frozen=True)
class TierConfig:
    length: int
    max_gap: int = 0  # 0 = no gaps
    steps: bool = False  # step up / down
    max_drop: int = 1
    valleys: float = 0.0  # probability weight of enemy valleys
    platforms: float = 0.0  # probability weight of platform chains
    platform_enemies: bool = False
    free_enemies: float = 0.0  # chance of an enemy walking on open flat ground
    climbs: float = 0.0  # probability weight of climbing routes (upper path, dead end below)
    enemy_groups: bool = False  # valleys may hold 2-3 enemies
    rain: float = 0.0  # chance that enemies start high up and drop down
    high_roads: float = 0.0  # probability weight of a long upper road above a long dead-end floor
    stones: float = 0.0  # probability weight of single-block stepping stones with 3-tile gaps
    tunnels: float = 0.0  # low tunnel (1 row high): no jumping inside, enemies must be shot
    shafts: float = 0.0  # staircase up, then drop onto a small platform (needs braking in mid-air)
    ceilings: float = 0.0  # low ceiling over gaps: short jumps only
    two_routes: float = 0.0  # upper road and floor both lead on
    hard: int = 0  # 0 = easy, 1 = medium, 2 = hard form of the new building blocks


TIERS = (
    TierConfig(length=25),                                                              # 0 walk to the chest
    TierConfig(length=35, max_gap=1, steps=True),                                       # 1 small gaps, steps
    TierConfig(length=45, max_gap=2, steps=True, max_drop=2),                           # 2 real gaps
    TierConfig(length=55, max_gap=2, steps=True, max_drop=2, valleys=1.0),              # 3 enemies
    TierConfig(length=65, max_gap=2, steps=True, max_drop=2, valleys=1.0, platforms=1.0),    # 4 platforms
    TierConfig(length=80, max_gap=2, steps=True, max_drop=3, valleys=1.5, platforms=1.5,
               free_enemies=0.15, tunnels=0.4, ceilings=0.4, shafts=0.3),               # 5 everything
    TierConfig(length=100, max_gap=2, steps=True, max_drop=3, valleys=2.0, platforms=2.0,
               platform_enemies=True, free_enemies=0.25, tunnels=0.6, ceilings=0.6,
               shafts=0.5, two_routes=0.5, hard=1),                                     # 6 dense
    TierConfig(length=130, max_gap=3, steps=True, max_drop=4, valleys=2.5, platforms=2.5,
               platform_enemies=True, free_enemies=0.35, tunnels=0.8, ceilings=0.8,
               shafts=0.8, two_routes=0.8, hard=1),                                     # 7 expert
    TierConfig(length=150, max_gap=3, steps=True, max_drop=4, valleys=2.5, platforms=2.0,
               platform_enemies=True, free_enemies=0.35, climbs=1.5, enemy_groups=True,
               rain=0.3, high_roads=1.0, stones=1.0, tunnels=1.0, ceilings=1.0, shafts=1.0,
               two_routes=1.0, hard=2),                                                 # 8 climbing, groups
    TierConfig(length=200, max_gap=3, steps=True, max_drop=4, valleys=3.0, platforms=2.5,
               platform_enemies=True, free_enemies=0.4, climbs=2.5, enemy_groups=True,
               rain=0.5, high_roads=2.0, stones=1.5, tunnels=1.2, ceilings=1.2, shafts=1.2,
               two_routes=1.2, hard=2),                                                 # 9 like the exam
)
NUM_TIERS = len(TIERS)


class _Builder:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.columns: List[List[str]] = []  # each column: ROWS chars, top row first
        self.surface = GROUND  # row of the current ground surface
        self.style: dict = {}
        self.stats: dict = {}  # how often each building block was used

    def column(self, surface=None, extra=None) -> List[str]:
        """Append a column with terrain from `surface` down (None = pit)."""

        col = [" "] * ROWS
        if surface is not None:
            for r in range(surface, ROWS):
                col[r] = "B"
        for row, ch in (extra or {}).items():
            col[row] = ch
        self.columns.append(col)
        return col

    def flat(self, n: int, enemy: bool = False) -> None:
        start = len(self.columns)
        for _ in range(n):
            self.column(self.surface)
        if enemy and n >= 3:
            self.columns[start + n // 2][self.surface - 1] = "E"

    def gap(self, width: int) -> None:
        for _ in range(width):
            self.column(None)

    def rise(self) -> bool:
        if self.surface - 1 < HIGHEST_SURFACE:
            return False
        self.surface -= 1
        return True

    def drop(self, rows: int) -> None:
        self.surface = min(GROUND, self.surface + rows)


def _style(rng: random.Random, cfg: TierConfig) -> dict:
    """Per-level mix of building blocks: tier weights x random factors (Dirichlet-like).

    Each level gets its own character (gap-heavy, enemy-heavy, vertical, ...) while
    a tier never contains blocks it does not allow.
    """

    base = {
        "flat": 1.0,
        "gap": 1.2 if cfg.max_gap else 0.0,
        "step": 1.0 if cfg.steps else 0.0,
        "valley": cfg.valleys,
        "platforms": cfg.platforms,
        "climb": cfg.climbs,
        "high_road": cfg.high_roads,
        "stones": cfg.stones,
        "tunnel": cfg.tunnels,
        "shaft": cfg.shafts,
        "ceiling": cfg.ceilings,
        "two_routes": cfg.two_routes,
    }
    return {kind: w * (0.3 + rng.gammavariate(1.0, 1.0)) for kind, w in base.items() if w > 0}


def _segment(b: _Builder, cfg: TierConfig) -> None:
    rng = b.rng
    allowed = {
        "valley": b.surface <= GROUND - 1,
        "high_road": b.surface == GROUND,
        "two_routes": b.surface == GROUND,
        "shaft": b.surface >= HIGHEST_SURFACE + 3,  # room for the staircase
        "tunnel": b.surface >= 4,
        "ceiling": b.surface >= 5,
    }
    choices = [(kind, w) for kind, w in b.style.items() if allowed.get(kind, True)]
    kind = rng.choices([c[0] for c in choices], weights=[c[1] for c in choices])[0]
    b.stats[kind] = b.stats.get(kind, 0) + 1

    if kind == "flat":
        b.flat(rng.randint(2, 6), enemy=rng.random() < cfg.free_enemies)

    elif kind == "gap":
        width = rng.randint(1, cfg.max_gap)
        # a 3-tile gap is only allowed when landing lower (more air time)
        drop = rng.randint(1, cfg.max_drop) if width == 3 or (cfg.steps and rng.random() < 0.3) else 0
        b.gap(width)
        b.drop(drop)
        if width == 1 and cfg.steps and rng.random() < 0.3:
            b.rise()  # small gap onto a higher ledge
        b.flat(rng.randint(2, 4))

    elif kind == "step":
        if rng.random() < 0.55 and b.rise():
            b.flat(rng.randint(2, 4))
            if rng.random() < 0.3 and b.rise():  # staircase
                b.flat(rng.randint(2, 3))
        else:
            b.drop(rng.randint(1, cfg.max_drop))
            b.flat(rng.randint(2, 4))

    elif kind == "valley":
        depth = rng.randint(1, min(2, GROUND - b.surface))
        top = b.surface
        b.drop(depth)
        width = rng.randint(5, 8)
        start = len(b.columns)
        b.flat(width, enemy=True)
        if cfg.enemy_groups and rng.random() < 0.5:
            for offset in rng.sample(range(1, width - 1), k=min(2, width - 2)):
                b.columns[start + offset][b.surface - 1] = "E"
        if cfg.rain and rng.random() < cfg.rain:
            # an enemy waiting high above the valley; it drops when it becomes active
            b.columns[start + rng.randrange(width)][rng.randint(1, 3)] = "E"
        for _ in range(depth):  # climb back out, one row per step
            b.rise()
            b.flat(2)
        b.surface = top

    elif kind == "climb":
        _climb(b, cfg)

    elif kind == "high_road":
        _high_road(b, cfg)

    elif kind == "tunnel":
        _tunnel(b, cfg)

    elif kind == "shaft":
        _shaft(b, cfg)

    elif kind == "ceiling":
        _ceiling(b, cfg)

    elif kind == "two_routes":
        _two_routes(b, cfg)

    elif kind == "stones":
        # single blocks over a pit, 3 tiles apart at the same height (the exam's hardest jumps)
        row = max(HIGHEST_SURFACE, b.surface - rng.randint(0, 1))
        b.flat(1)
        b.gap(2)
        for i in range(rng.randint(2, 5)):
            if i and cfg.max_drop >= 4 and rng.random() < 0.5:
                # one row up or down: needs braking in mid-air to land on the single block
                row = max(4, min(GROUND - 1, row + rng.choice((-1, 1))))
            b.column(None, {row: "B"})
            b.gap(3)
        b.surface = max(row, min(GROUND, row + rng.randint(0, 2)))
        b.flat(rng.randint(2, 4))

    elif kind == "platforms":
        # pit with floating platforms; heights change by at most one row per hop
        level_row = b.surface
        b.flat(1)
        for _ in range(rng.randint(1, 3)):
            b.gap(rng.randint(1, 2))
            change = rng.choice((-1, 0, 0, 1))
            level_row = max(HIGHEST_SURFACE, min(GROUND - 1, level_row + change))
            width = rng.randint(2, 3)
            start = len(b.columns)
            for _ in range(width):
                b.column(None, {level_row: "B"})
            if cfg.platform_enemies and width == 3 and rng.random() < 0.35:
                b.columns[start + 1][level_row - 1] = "E"
        b.gap(rng.randint(1, 2))
        b.surface = max(level_row, min(GROUND, level_row + rng.randint(0, 1)))
        b.flat(rng.randint(2, 4))


def _climb(b: _Builder, cfg: TierConfig) -> None:
    """Upper route: hop up floating blocks, cross a plateau, come back down.

    Under the climb the ground continues for a while and then ends at a pit
    that is too wide to jump - a dead end for bots that stay on the floor.
    """

    rng = b.rng
    start_surface = b.surface
    b.flat(2)
    row = start_surface
    climb_cols = []
    hops = rng.randint(2, 4)
    for _ in range(hops):
        if row - 1 < 3:
            break
        row -= 1  # one row higher per hop
        climb_cols.append(("gap", 1))
        climb_cols.append(("block", row, rng.randint(1, 2)))
    plateau = rng.randint(3, 5)
    climb_cols.append(("gap", rng.randint(1, 2)))
    climb_cols.append(("block", row, plateau))
    if cfg.platform_enemies and rng.random() < 0.4:
        climb_cols.append(("enemy_on_last", row))

    trap = start_surface == GROUND and rng.random() < 0.7
    columns_before = len(b.columns)
    for item in climb_cols:
        if item[0] == "gap":
            for _ in range(item[1]):
                b.column(None)
        elif item[0] == "block":
            for _ in range(item[2]):
                b.column(None, {item[1]: "B"})
        else:
            b.columns[-2][item[1] - 1] = "E"
    if trap:
        # dead-end floor under the first part of the climb (never under the plateau)
        span = len(b.columns) - columns_before
        for i in range(max(1, span - plateau - 3)):
            b.columns[columns_before + i][GROUND] = "B"
    b.gap(rng.randint(1, 2))
    b.surface = min(GROUND, row + rng.randint(1, 4))
    b.flat(rng.randint(2, 4))


def _high_road(b: _Builder, cfg: TierConfig) -> None:
    """A long upper road over a comfortable floor that ends in a pit far ahead.

    Like the exam level: from the start the floor looks fine, the dead end is
    20-35 tiles away (beyond the bot's view). The road is at least 2 rows higher
    than anything reachable from the floor, so the choice has to be made early.
    """

    rng = b.rng
    b.flat(2)
    start = len(b.columns)
    road_row = GROUND
    items = []
    for _ in range(3):  # stairs up: one row per hop
        road_row -= 1
        items.append((1, None))
        items.append((rng.randint(1, 2), road_row))
    length = rng.randint(20, 70 if cfg.hard >= 2 else 35)
    placed = 0
    while placed < length:
        gap = rng.randint(1, 2)
        change = rng.choice((-1, 0, 0, 1)) if gap == 1 else rng.choice((0, 0, 1))
        road_row = max(4, min(GROUND - 3, road_row - change))
        width = rng.randint(2, 4)
        items.append((gap, None))
        items.append((width, road_row))
        placed += gap + width
    for count, row in items:
        for _ in range(count):
            b.column(None, {row: "B"} if row is not None else None)
    if cfg.platform_enemies and rng.random() < 0.5:
        b.columns[-2][road_row - 1] = "E"
    end = len(b.columns)
    # the tempting floor: starts right away, ends 6+ tiles before the road does
    for c in range(start, end - rng.randint(6, 9)):
        b.columns[c][GROUND] = "B"
    if rng.random() < cfg.free_enemies:
        b.columns[start + rng.randint(4, 10)][GROUND - 1] = "E"
    b.gap(rng.randint(1, 2))
    b.surface = min(GROUND, road_row + rng.randint(1, 3))
    b.flat(rng.randint(3, 5))


def _tunnel(b: _Builder, cfg: TierConfig) -> None:
    """Tunnel one row high: jumping is impossible inside, an enemy has to be shot."""

    rng = b.rng
    b.flat(2)
    length = rng.randint(3, 4) if cfg.hard == 0 else rng.randint(5, 9)
    start = len(b.columns)
    for _ in range(length):
        b.column(b.surface, {b.surface - 2: "B"})
    if cfg.hard >= 1:
        enemies = 1 if cfg.hard == 1 or rng.random() < 0.6 else 2
        for offset in rng.sample(range(2, length), k=min(enemies, length - 2)):
            b.columns[start + offset][b.surface - 1] = "E"
    b.flat(rng.randint(2, 3))


def _shaft(b: _Builder, cfg: TierConfig) -> None:
    """Climb a staircase, then drop onto a small platform over a pit.

    Landing on the platform needs braking in mid-air - the manoeuvre the exam level demands.
    """

    rng = b.rng
    low = b.surface
    for _ in range(3):
        if not b.rise():
            break
        b.flat(2)
    b.flat(1)
    fall = rng.randint(2, 3)
    platform_row = min(GROUND - 1, b.surface + fall)
    b.gap(rng.randint(1, 2) if cfg.hard == 0 else rng.randint(2, 3))
    width = 2 if cfg.hard == 0 else rng.choice((1, 2)) if cfg.hard == 1 else 1
    for _ in range(width):
        b.column(None, {platform_row: "B"})
    b.gap(rng.randint(1, 2))
    b.surface = max(platform_row, low)
    b.flat(rng.randint(2, 4))


def _ceiling(b: _Builder, cfg: TierConfig) -> None:
    """Low ceiling (two free rows): only short jumps fit underneath."""

    rng = b.rng
    ceiling_row = b.surface - 3
    parts = rng.randint(1, 2) if cfg.hard == 0 else rng.randint(2, 4)
    b.flat(1)
    for _ in range(parts):
        for _ in range(rng.randint(2, 3)):
            b.column(b.surface, {ceiling_row: "B"})
        width = 1 if cfg.hard < 2 else rng.randint(1, 2)
        for _ in range(width):
            b.column(None, {ceiling_row: "B"})
    for _ in range(2):
        b.column(b.surface, {ceiling_row: "B"})
    b.flat(2)


def _two_routes(b: _Builder, cfg: TierConfig) -> None:
    """Upper road and floor both lead on: two valid ways."""

    rng = b.rng
    b.flat(2)
    start = len(b.columns)
    road_row = GROUND
    items = []
    for _ in range(3):  # stairs: the first step is a small obstacle on the floor path
        road_row -= 1
        items.append((1, None))
        items.append((rng.randint(1, 2), road_row))
    length = rng.randint(12, 24)
    placed = 0
    while placed < length:
        gap = rng.randint(1, 2)
        if gap == 1:
            road_row = max(5, min(GROUND - 3, road_row + rng.choice((-1, 0, 0, 1))))
        width = rng.randint(2, 4)
        items += [(gap, None), (width, road_row)]
        placed += gap + width
    for count, row in items:
        for _ in range(count):
            b.column(GROUND, {row: "B"} if row is not None else None)
    end = len(b.columns)
    for _ in range(rng.randint(0, 2) if cfg.free_enemies else 0):
        b.columns[rng.randrange(start + 3, end - 1)][GROUND - 1] = "E"
    b.flat(rng.randint(2, 4))


def generate(tier: int, seed: int) -> Level:
    """Build a level of the given difficulty tier (0 .. NUM_TIERS-1)."""

    cfg = TIERS[max(0, min(tier, NUM_TIERS - 1))]
    rng = random.Random(f"{tier}:{seed}")
    b = _Builder(rng)
    b.style = _style(rng, cfg)
    b.flat(5)
    b.columns[1][b.surface - 1] = "P"
    while len(b.columns) < cfg.length:
        _segment(b, cfg)
    b.flat(4)
    b.columns[-2][b.surface - 1] = "C"
    b.column(b.surface - 3)  # wall behind the chest

    lines = ["".join(col[r] for col in b.columns).rstrip() for r in range(ROWS)]
    level = Level(lines, name=f"gen_t{tier}_s{seed}")
    level.building_blocks = dict(b.stats)  # which blocks this level contains (for statistics)
    return level


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a level and print or save it.")
    parser.add_argument("--tier", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out")
    args = parser.parse_args()
    level = generate(args.tier, args.seed)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as out:
            out.write(level.to_text())
    else:
        print(level.to_text().replace(" ", "."))


if __name__ == "__main__":
    main()
