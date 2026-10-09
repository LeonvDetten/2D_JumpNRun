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

Generator v3 (phase 6) adds tiers 10 and 11: long levels (~220 / ~320 tiles) with
combinations like the exam level - enemy rain over floating stairs, a dead-end
floor 40-80 tiles long, long chains of stepping stones going up and down, and a
trench full of enemies on a high plateau. Tiers 0-9 are unchanged (v2).
Levels also carry `waypoints` (tiles on the right route) so the solver can plan
long levels in legs.

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

GENERATOR_VERSION = 10  # 10 (phase 9, only with variant "v10" / tier 13): repaired forks, channels, Mario-inspired blocks; 9: bait forks (upper road dead-ends) in tiers 10-12; 8: enemy ramps in tiers 10-12, tier 12 upper roads x2; 5: widest jumps x3; 6: chest on the edge; 7: edge chest in tiers 10-12 (~30 %), no extra enemies
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
    hard: int = 0  # 0 = easy, 1 = medium, 2 = hard, 3 = exam-like form of the building blocks
    rain_stairs: float = 0.0  # floating stairs up, enemies dropping from above (v3)
    chains: float = 0.0  # long chains of stepping stones with height changes (v3)
    trenches: float = 0.0  # enemies trapped in a trench on a high floating plateau (v3)
    jumps: float = 0.0  # sequences of single jumps drawn evenly from the jump catalogue (v4)
    start_enemies: bool = False  # enemies near the start, walking or dropping (v4)
    hard_jumps: float = 1.0  # weight of the widest robust jump per height change in jump sequences
    enemy_ramps: float = 0.0  # solid staircase up with enemies walking down from the top (v8)
    bait_forks: float = 0.0  # tempting upper road that dead-ends at a wall; the floor is the way (v9)
    # phase 9 (generator v10) - only used with variant "v10" (tier 13 always):
    channels: float = 0.0  # serpentine: along the floor to the right, stairs up, left, stairs up, right
    pipes: float = 0.0  # Mario-inspired: 2-wide pipes of 1-2 rows, enemies trapped between them
    pyramids: float = 0.0  # Mario-inspired: block staircase up and down, often a pit at the top
    bridges: float = 0.0  # Mario-inspired: floating brick steps up to a bridge over a wide pit, enemies on it
    groups: float = 0.0  # Mario-inspired: a group of 2-3 enemies close together on flat ground
    channel_end: float = 0.0  # probability that the level ends in a channel with the chest on the left


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
    TierConfig(length=220, max_gap=3, steps=True, max_drop=4, valleys=2.0, platforms=2.0,
               platform_enemies=True, free_enemies=0.4, climbs=1.5, enemy_groups=True,
               rain=0.5, high_roads=1.5, stones=1.0, tunnels=1.0, ceilings=1.0, shafts=1.0,
               two_routes=1.0, hard=3, rain_stairs=1.2, chains=1.5, trenches=1.0,
               enemy_ramps=1.0, bait_forks=1.0),                                         # 10 exam patterns
    TierConfig(length=320, max_gap=3, steps=True, max_drop=4, valleys=2.0, platforms=2.0,
               platform_enemies=True, free_enemies=0.45, climbs=1.5, enemy_groups=True,
               rain=0.6, high_roads=2.0, stones=1.2, tunnels=1.0, ceilings=1.0, shafts=1.0,
               two_routes=1.0, hard=3, rain_stairs=1.5, chains=2.0, trenches=1.3,
               enemy_ramps=1.2, bait_forks=1.2),                                         # 11 long journey
    TierConfig(length=250, max_gap=3, steps=True, max_drop=4, valleys=1.5, platforms=1.0,
               platform_enemies=True, free_enemies=0.4, climbs=1.0, enemy_groups=True,
               rain=0.5, high_roads=2.0, stones=0.5, tunnels=1.0, ceilings=1.0, shafts=0.8,
               two_routes=0.8, hard=3, rain_stairs=1.0, chains=1.0, trenches=1.0,
               jumps=4.0, start_enemies=True, hard_jumps=3.0, enemy_ramps=1.0, bait_forks=1.0),                           # 12 jump catalogue
               # phase 7: widest jumps x3 (v5; the extra free enemies of v5 were taken back in v7)
    TierConfig(length=260, max_gap=3, steps=True, max_drop=4, valleys=1.0, platforms=1.0,
               platform_enemies=True, free_enemies=0.35, climbs=0.8, enemy_groups=True,
               rain=0.4, high_roads=0.8, stones=0.6, tunnels=0.6, ceilings=0.6, shafts=0.5,
               two_routes=0.8, hard=3, rain_stairs=0.6, chains=0.8, trenches=0.5, jumps=1.0,
               enemy_ramps=0.6, bait_forks=2.0, channels=2.0, pipes=1.0, pyramids=1.0, bridges=1.0,
               groups=1.0, channel_end=0.4),                                               # 13 channels & forks (v10)
)
V10_EXTRA = dict(channels=0.6, pipes=0.4, pyramids=0.4, bridges=0.4, groups=0.4, channel_end=0.15)  # tiers 10-12
VARIANTS = ("v9", "gabel", "v10")  # gabel = v9 with the repaired fork only (phase 9 round 1)
NUM_TIERS = len(TIERS)


class _Builder:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.columns: List[List[str]] = []  # each column: ROWS chars, top row first
        self.surface = GROUND  # row of the current ground surface
        self.style: dict = {}
        self.stats: dict = {}  # how often each building block was used
        self.waypoints: list = []  # (col, row) tiles on the right route (for the solver)
        self.variant = "v9"
        self.needs_path = False  # the way is not simply "to the right" (solver: use the distance map)

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


def _style(rng: random.Random, cfg: TierConfig, variant: str = "v9") -> dict:
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
        "rain_stairs": cfg.rain_stairs,
        "chain": cfg.chains,
        "trench": cfg.trenches,
        "jump_seq": cfg.jumps,
        "enemy_ramp": cfg.enemy_ramps,
        "bait_fork": cfg.bait_forks,
    }
    if variant == "v10":
        base.update(channel=cfg.channels, pipes=cfg.pipes, pyramid=cfg.pyramids, bridge=cfg.bridges,
                    group=cfg.groups)
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
        "rain_stairs": b.surface >= GROUND - 1,
        "trench": b.surface >= 6,
        "enemy_ramp": b.surface >= HIGHEST_SURFACE + 3,
        "bait_fork": b.surface == GROUND,
        "channel": b.surface == GROUND,
        "pipes": b.surface >= HIGHEST_SURFACE + 2,
        "pyramid": b.surface >= HIGHEST_SURFACE + 4,
        "bridge": b.surface >= HIGHEST_SURFACE + 3,
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

    elif kind == "rain_stairs":
        _rain_stairs(b, cfg)

    elif kind == "chain":
        _chain(b, cfg)

    elif kind == "trench":
        _trench(b, cfg)

    elif kind == "jump_seq":
        _jump_sequence(b, cfg)

    elif kind == "enemy_ramp":
        _enemy_ramp(b, cfg)

    elif kind == "bait_fork":
        if b.variant == "v9":
            _bait_fork(b, cfg)
        else:
            _fork_v10(b, cfg)

    elif kind == "channel":
        _channel(b, cfg)

    elif kind == "pipes":
        _pipes(b, cfg)

    elif kind == "pyramid":
        _pyramid(b, cfg)

    elif kind == "bridge":
        _bridge(b, cfg)

    elif kind == "group":
        b.flat(2)
        start = len(b.columns)
        width = rng.randint(6, 9)
        b.flat(width)
        for offset in rng.sample(range(1, width - 1), k=rng.randint(2, 3)):
            b.columns[start + offset][b.surface - 1] = "E"
        b.flat(2)

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
    length = rng.randint(40, 80) if cfg.hard >= 3 else rng.randint(20, 70 if cfg.hard >= 2 else 35)
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


TOP_ROW = 3  # v3 blocks may float this high (standing on row 3 still leaves room to jump)


def _floating(b: _Builder, row, count: int = 1, floor: bool = False) -> None:
    """Columns with a single block at `row` (None = air); optionally with the ground below."""

    for _ in range(count):
        extra = {row: "B"} if row is not None else None
        b.column(GROUND if floor else None, extra)


def _rain_stairs(b: _Builder, cfg: TierConfig) -> None:
    """Floating stairs up from the ground while enemies rain down from the sky.

    The enemies start in the top rows and fall onto the stairs when they become
    active - like the start of the exam level. The ground runs on below the
    stairs and ends at a wall: going up is the only way.
    """

    rng = b.rng
    b.flat(2)
    row = GROUND
    start = len(b.columns)
    target = rng.randint(TOP_ROW + 1, 6)
    while row > target:
        row -= 1
        _floating(b, None, 1, floor=True)
        width = rng.randint(2, 4)
        first = len(b.columns)
        _floating(b, row, width, floor=True)
        if rng.random() < 0.8:  # an enemy waiting in the sky above this step
            b.columns[first + rng.randrange(width)][rng.randint(0, 1)] = "E"
    for c in range(start + 2, len(b.columns), rng.randint(3, 5)):
        if rng.random() < 0.5 and b.columns[c][GROUND - 1] == " ":
            b.columns[c][GROUND - 1] = "E"  # enemies on the floor below
    b.surface = row
    b.waypoints.append((len(b.columns) - 1, row))
    b.flat(rng.randint(2, 4))
    b.waypoints.append((len(b.columns) - 1, b.surface))


def _bait_fork(b: _Builder, cfg: TierConfig) -> None:
    """The mirror image of _high_road: a tempting stair up to an upper road that dead-ends at a wall.

    The floor below runs on (with a short pit right under the road's end), so the right choice is to stay
    low - or to turn back and drop down early. Seeing the wall early needs the overview map; in phase 7 the
    upper road was always right, so the overview was hardly used.
    """

    rng = b.rng
    b.flat(2)
    start = len(b.columns)
    road_row = GROUND
    items = []
    for _ in range(3):  # floating stairs up, one row per hop
        road_row -= 1
        items.append((1, None))
        items.append((rng.randint(1, 2), road_row))
    length = rng.randint(14, 30)
    placed = 0
    while placed < length:
        gap = rng.randint(1, 2)
        change = rng.choice((-1, 0, 0)) if gap == 1 else 0
        road_row = max(5, min(GROUND - 3, road_row - change))
        width = rng.randint(2, 4)
        items.append((gap, None))
        items.append((width, road_row))
        placed += gap + width
    for count, row in items:
        for _ in range(count):
            b.column(None, {row: "B"} if row is not None else None)
    end = len(b.columns)
    for r in range(max(0, road_row - 3), road_row):  # the wall at the road's end
        b.columns[end - 1][r] = "B"
    pit = (end - 2, end - 1)
    for c in range(start, end):
        if c not in pit:
            b.columns[c][GROUND] = "B"
    if rng.random() < cfg.free_enemies:
        b.columns[start + rng.randint(3, 8)][GROUND - 1] = "E"
    b.waypoints.append((pit[0] - 1, GROUND))
    b.surface = GROUND
    b.flat(rng.randint(3, 5))
    b.waypoints.append((len(b.columns) - 1, b.surface))


def _fork_v10(b: _Builder, cfg: TierConfig, kind: str = "", length: int = None) -> None:
    """Phase 9 (v10): the repaired fork. Stairs up to an upper road over a floor - which branch goes on is random.

    unten     the road dead-ends at a wall, the floor goes on (no deadly pit under the road's end any more,
              dropping down through a gap of the road is fine)
    umkehren  like unten, but the road has no gaps: the only way back down is to walk back to the stairs
    oben      the road goes on, the floor ends in a pit too wide to cross: back to the stairs and up
    v9's pit right under the road's end taught "never drop down there" - in phase 8 the bot always got stuck
    at the dead-end wall and never turned back.
    """

    rng = b.rng
    kind = kind or rng.choice(("unten", "unten", "umkehren", "oben"))
    b.flat(2)
    start = len(b.columns)
    road_row = GROUND
    items = []
    for _ in range(3):  # floating stairs up, one row per hop
        road_row -= 1
        items.append((1, None))
        items.append((rng.randint(1, 2), road_row))
    length = rng.randint(14, 30) if length is None else length  # phase 11: lange_sackgasse sets it
    placed = 0
    while placed < length:
        gap = 0 if kind == "umkehren" else rng.randint(1, 2)
        change = rng.choice((-1, 0, 0)) if gap == 1 else 0
        road_row = max(5, min(GROUND - 3, road_row - change))
        width = rng.randint(2, 4)
        if gap:
            items.append((gap, None))
        items.append((width, road_row))
        placed += gap + width
    for count, row in items:
        for _ in range(count):
            b.column(None, {row: "B"} if row is not None else None)
    end = len(b.columns)
    if kind == "oben":
        floor_end = end - rng.randint(6, 8)  # the floor stops: a pit that cannot be crossed down there
    else:
        floor_end = end
        for r in range(max(0, road_row - 3), road_row):  # the wall at the road's end
            b.columns[end - 1][r] = "B"
    for c in range(start, floor_end):
        b.columns[c][GROUND] = "B"
    if rng.random() < cfg.free_enemies:
        b.columns[start + rng.randint(3, 8)][GROUND - 1] = "E"
    b.needs_path = True
    b.stats["gabel_" + kind] = b.stats.get("gabel_" + kind, 0) + 1
    if kind == "oben":
        b.waypoints.append((end - 1, road_row))
        b.surface = road_row
        b.flat(rng.randint(3, 5))
        b.waypoints.append((len(b.columns) - 1, b.surface))
        return
    b.waypoints.append((end - 1, GROUND - 1))
    b.surface = GROUND
    b.flat(rng.randint(3, 5))
    b.waypoints.append((len(b.columns) - 1, b.surface))


def _channel(b: _Builder, cfg: TierConfig, final: bool = False) -> None:
    """Phase 9 (v10): a serpentine in the 13 rows. Needs b.surface == GROUND.

        row 3   ##########>  (3rd layer: to the right, out of the channel; final: missing)
        row 4   #  ##########
        rows 5-7 #<---------    2nd layer: back to the left (final: the chest at its left end)
        row 8   ##########  #
        rows 9-11 -------->  #  bottom: to the right, stairs up at the end
        row 12  ##############

    Each layer change is a 3-step staircase plus a jump up and back over the stair's opening (needs left+jump
    for the way back). Optional enemies in every layer and a hole in the 2nd layer that drops back down.
    """

    rng = b.rng
    w = rng.randint(18, 30)
    s = len(b.columns)
    cols = [[" "] * ROWS for _ in range(w)]
    for c in range(w):
        cols[c][GROUND] = "B"
    for r in range(0, 9):  # left wall above the entrance (rows 9-11 stay open)
        cols[0][r] = "B"
    for c in range(0, w - 4):  # floor of the 2nd layer, opening on the right
        cols[c][8] = "B"
    for c, top in ((w - 4, 11), (w - 3, 10), (w - 2, 9)):  # stairs up on the right (bottom -> 2nd layer)
        for r in range(top, GROUND):
            cols[c][r] = "B"
    right_top = 0 if final else 4
    for r in range(right_top, ROWS):  # right wall (final: closed to the top)
        cols[w - 1][r] = "B"
    enemies = cfg.free_enemies
    if rng.random() < enemies:
        cols[rng.randint(3, w - 7)][GROUND - 1] = "E"
    if final:
        chest = rng.randint(1, 3)
        cols[chest][7] = "C"
        if rng.random() < enemies:
            cols[rng.randint(chest + 4, w - 6)][7] = "E"
        b.stats["channel_end"] = b.stats.get("channel_end", 0) + 1
    else:
        for c in range(4, w - 1):  # floor of the 3rd layer, opening on the left
            cols[c][4] = "B"
        for c, top in ((3, 7), (2, 6), (1, 5)):  # stairs up on the left (2nd -> 3rd layer)
            for r in range(top, 8):
                cols[c][r] = "B"
        if rng.random() < enemies:
            cols[rng.randint(6, w - 6)][7] = "E"
        if rng.random() < enemies:
            cols[rng.randint(6, w - 3)][3] = "E"
        if w >= 22 and rng.random() < 0.4:  # a hole in the 2nd layer: falling back to the bottom
            h = rng.randint(8, w - 10)
            cols[h][8] = " "
            if rng.random() < 0.5:
                cols[h + 1][8] = " "
    b.columns += cols
    b.needs_path = True
    b.waypoints += [(s + w - 2, 8), (s + 4, 7)]
    if final:
        return
    b.waypoints.append((s + w - 2, 3))
    b.surface = HIGHEST_SURFACE  # out at the top right, one row down
    b.flat(rng.randint(3, 5))
    b.waypoints.append((len(b.columns) - 1, b.surface))


def _pipes(b: _Builder, cfg: TierConfig) -> None:
    """Phase 9 (v10), Mario-inspired: 2-wide pipes, 1 row (or 2 with a step) high; enemies walk between them."""

    rng = b.rng
    base = b.surface
    for i in range(rng.randint(2, 4)):
        width = rng.randint(2, 4)
        start = len(b.columns)
        b.flat(width)
        if i and width >= 3 and rng.random() < cfg.free_enemies + 0.2:
            b.columns[start + width // 2][base - 1] = "E"
        height = 2 if base - 2 >= HIGHEST_SURFACE and rng.random() < 0.4 else 1
        if height == 2:
            b.column(base - 1)  # a step in front of the tall pipe
        for _ in range(2):
            b.column(base - height)
    b.flat(rng.randint(2, 4))


def _pyramid(b: _Builder, cfg: TierConfig) -> None:
    """Phase 9 (v10), Mario-inspired: a block staircase up and down again, often with a pit at the top."""

    rng = b.rng
    base = b.surface
    n = rng.randint(2, min(4, base - HIGHEST_SURFACE))
    b.flat(2)
    for k in range(1, n + 1):
        b.column(base - k)
    b.column(base - n)
    if rng.random() < 0.7:
        b.gap(rng.randint(1, 2))
    for k in range(n, 0, -1):
        b.column(base - k)
    b.flat(rng.randint(2, 4), enemy=rng.random() < cfg.free_enemies)


def _bridge(b: _Builder, cfg: TierConfig) -> None:
    """Phase 9 (v10), Mario-inspired: floating bricks up to a bridge over a wide pit, enemies on the bridge."""

    rng = b.rng
    base = b.surface
    b.flat(2)
    row = base
    for _ in range(3):  # floating steps, one row up per hop
        row -= 1
        b.gap(1)
        b.column(None, {row: "B"})
    length = rng.randint(6, 12)
    start = len(b.columns)
    for _ in range(length):
        b.column(None, {row: "B"})
    for offset in rng.sample(range(2, length - 1), k=rng.randint(1, 2)):
        b.columns[start + offset][row - 1] = "E"
    b.waypoints.append((len(b.columns) - 1, row))
    b.gap(1)
    b.surface = min(GROUND, row + rng.randint(1, 3))
    b.flat(rng.randint(3, 5))


def _enemy_ramp(b: _Builder, cfg: TierConfig) -> None:
    """A solid staircase up to a plateau; enemies on the top walk down towards the player.

    The bot has to shoot them or time its climb (test series level "festung" showed this gap).
    """

    rng = b.rng
    b.flat(rng.randint(2, 4), enemy=rng.random() < 0.5)
    steps = 0
    for _ in range(rng.randint(3, 5)):
        if not b.rise():
            break
        steps += 1
        first = len(b.columns)
        width = rng.randint(2, 4)
        b.flat(width)
        if steps >= 2 and rng.random() < 0.25:
            b.columns[first + width - 1][b.surface - 1] = "E"  # an enemy already on the way down
    top = rng.randint(5, 9)
    first = len(b.columns)
    b.flat(top)
    for offset in rng.sample(range(1, top), k=min(top - 1, rng.randint(1, 3))):
        b.columns[first + offset][b.surface - 1] = "E"
    if rng.random() < cfg.rain:
        b.columns[first + rng.randrange(top)][rng.randint(0, 1)] = "E"  # one more drops from the sky
    b.waypoints.append((len(b.columns) - 1, b.surface))


def _chain(b: _Builder, cfg: TierConfig) -> None:
    """A long chain of 1-2 wide stones over the void, drifting up and down.

    Rising needs a short gap, same height or falling allows a longer one;
    single stones after a fall need braking in mid-air.
    """

    rng = b.rng
    row = b.surface
    b.flat(1)
    trend = rng.choice((-1, 0, 1))
    for _ in range(rng.randint(6, 14)):
        if rng.random() < 0.3:
            trend = rng.choice((-1, 0, 1))
        change = trend if rng.random() < 0.7 else 0
        new_row = max(TOP_ROW, min(GROUND - 1, row + change))
        change = new_row - row
        gap = rng.randint(1, 2) if change < 0 else rng.randint(1, 3)
        if change < 0 and rng.random() < 0.3:
            gap = 3  # far jump up onto the next stone (the exam's diagonals need it)
        width = rng.choice((1, 2, 2)) if gap < 3 else 2
        b.gap(gap)
        row = new_row
        _floating(b, row, width)
    b.waypoints.append((len(b.columns) - 1, row))
    if row <= 6 and rng.random() < 0.4:
        # a leap into the depth: wide gap, landing far below (like the end of the exam level)
        landing = rng.randint(max(row + 5, GROUND - 2), GROUND)
        b.gap(rng.randint(3, 4) if landing - row >= 7 else 3)
        b.surface = landing
    else:
        b.gap(rng.randint(1, 2))
        b.surface = max(row, min(GROUND, row + rng.randint(0, 2)))
    b.flat(rng.randint(2, 4))
    b.waypoints.append((len(b.columns) - 1, b.surface))


def _trench(b: _Builder, cfg: TierConfig) -> None:
    """Hop up to a floating plateau with a trench of enemies between two low walls."""

    rng = b.rng
    b.flat(1)
    row = b.surface
    plateau = rng.randint(TOP_ROW + 1, 5)
    while row > plateau:
        row -= 1
        b.gap(1)
        _floating(b, row, rng.randint(1, 2))
    b.gap(rng.randint(1, 2))
    _floating(b, row, rng.randint(2, 3))
    b.column(None, {row: "B", row - 1: "B"})  # left wall
    width = rng.randint(5, 8)
    first = len(b.columns)
    _floating(b, row, width)
    for offset in rng.sample(range(1, width - 1), k=rng.randint(2, 3)):
        b.columns[first + offset][row - 1] = "E"
    b.column(None, {row: "B", row - 1: "B"})  # right wall
    _floating(b, row, rng.randint(2, 3))
    b.waypoints.append((len(b.columns) - 1, row))
    b.gap(rng.randint(1, 2))
    b.surface = min(GROUND, row + rng.randint(1, 4))
    b.flat(rng.randint(2, 4))
    b.waypoints.append((len(b.columns) - 1, b.surface))


_CATALOG = None
_TIGHT = {(4, 0), (5, 2)}  # borderline jumps; the solver cannot build them into chains reliably


def _widest_gaps() -> dict:
    """Widest robust gap per height change (the hardest jump of each height)."""

    widest = {}
    for e in _jump_catalog():
        if (e["gap"], e["drop"]) not in _TIGHT:
            widest[e["drop"]] = max(widest.get(e["drop"], 0), e["gap"])
    return widest


def _jump_catalog() -> list:
    global _CATALOG
    if _CATALOG is None:
        from jumpnrun.levelgen.jump_catalog import load_catalog

        _CATALOG = load_catalog()
    return _CATALOG


def _jump_sequence(b: _Builder, cfg: TierConfig) -> None:
    """4-10 single jumps between floating platforms, each drawn evenly from the jump catalogue.

    The height drifts up and down; the next takeoff platform is the previous landing platform.
    """

    rng = b.rng
    row, width = b.surface, 3
    b.flat(2)
    for _ in range(rng.randint(4, 10)):
        options, weights = [], []
        for e in _jump_catalog():
            land = row + e["drop"]
            if e["takeoff"] > width or not TOP_ROW <= land <= GROUND:
                continue
            if (e["gap"], e["drop"]) in _TIGHT:
                continue  # the widest jump for its height: only works from some sub-tile positions
            w = cfg.hard_jumps if e["gap"] == _widest_gaps()[e["drop"]] else 1.0
            if e["drop"] > 0 and land >= 9:
                w = 0.3  # do not sink to the bottom too fast
            options.append(e)
            weights.append(w)
        e = rng.choices(options, weights=weights)[0]
        b.gap(e["gap"])
        row += e["drop"]
        width = e["landing"]
        first = len(b.columns)
        for _ in range(width):
            b.column(None, {row: "B"})
        if cfg.platform_enemies and width == 3 and rng.random() < 0.15:
            b.columns[first + 1][row - 1] = "E"
        b.waypoints.append((len(b.columns) - 1, row))
    b.gap(rng.randint(1, 2))
    b.surface = max(row, min(GROUND, row + rng.randint(0, 2)))
    b.flat(rng.randint(2, 4))
    b.waypoints.append((len(b.columns) - 1, b.surface))


EXAM_SKILL_BLOCKS = ("stones", "chain", "rain_stairs", "jump_seq", "enemy_ramp")
EXAM_SKILL_BOOST = 3.0


def generate(tier: int, seed: int, variant: str = "v9") -> Level:
    """Build a level of the given difficulty tier (0 .. NUM_TIERS-1).

    variant (phase 9): "v9" = the phase-8 generator (default, unchanged); "gabel" = v9 with the repaired fork;
    "pruefung" (phase 12) = v9 with stones, chains, rain stairs, jump sequences and enemy ramps x3 and enemies
    dropping right after the start (never built from exam geometry);
    "v10" = repaired fork + channels + Mario-inspired blocks in tiers 10-12. Tier 13 is always v10.
    Tiers 0-9 are the same in every variant.
    """

    exam_skills = variant == "pruefung"  # phase 12: v9 with the exam skills (stones, chains, rain) weighted up
    if exam_skills:
        variant = "v9"
    cfg = TIERS[max(0, min(tier, NUM_TIERS - 1))]
    if tier >= 13:
        variant = "v10"
    elif tier < 10:
        variant = "v9"
    elif variant == "v10":
        from dataclasses import replace

        cfg = replace(cfg, **V10_EXTRA)
    rng = random.Random(f"{tier}:{seed}")
    b = _Builder(rng)
    b.variant = variant
    b.style = _style(rng, cfg, variant)
    if exam_skills:
        for kind in EXAM_SKILL_BLOCKS:
            if kind in b.style:
                b.style[kind] *= EXAM_SKILL_BOOST
    b.flat(5)
    b.columns[1][b.surface - 1] = "P"
    if exam_skills and rng.random() < 0.6:
        # enemies dropping from the sky right after the start; the player has to time the first steps
        for _ in range(rng.randint(2, 3)):
            b.flat(rng.randint(2, 4))
            b.columns[-1][rng.choice((0, 1, 2))] = "E"
    if cfg.start_enemies and rng.random() < 0.4:
        # an enemy right at the start: walking towards the player, or dropping from the sky
        b.flat(3)
        b.columns[-1][rng.choice((b.surface - 1, 0, 1))] = "E"
    while len(b.columns) < cfg.length:
        _segment(b, cfg)
        top = b.columns[-1]
        if top[b.surface] == "B" and b.surface > 0 and top[b.surface - 1] == " ":
            b.waypoints.append((len(b.columns) - 1, b.surface))
    if variant == "v10" and rng.random() < cfg.channel_end:
        # v10: the level ends in a channel - along the floor to the right, stairs up, back left to the chest
        if b.surface != GROUND:
            b.drop(GROUND - b.surface)
            b.flat(3)
        _channel(b, cfg, final=True)
    else:
        b.flat(4)
        b.columns[-2][b.surface - 1] = "C"
        if cfg.hard >= 3 and rng.random() < 0.5:
            # v3: no wall behind the chest - jumping over it means falling off the level
            if rng.random() < 0.6:
                # v6/v7: chest on the very last floor tile, the void right behind it (as in the exam)
                b.columns[-2][b.surface - 1] = " "
                b.columns[-1][b.surface - 1] = "C"
        else:
            b.column(b.surface - 3)  # wall behind the chest

    lines = ["".join(col[r] for col in b.columns).rstrip() for r in range(ROWS)]
    level = Level(lines, name=f"gen_t{tier}_s{seed}")
    level.building_blocks = dict(b.stats)  # which blocks this level contains (for statistics)
    level.waypoints = sorted(set(b.waypoints))
    level.tier = tier
    level.variant = "pruefung" if exam_skills else variant
    level.needs_path = b.needs_path
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
