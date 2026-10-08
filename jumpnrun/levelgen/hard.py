"""Phase 12: generator v11 "schwer" - harder and more varied levels than v9/v10 (all models win 83-100 % there).

    from jumpnrun.levelgen.hard import make_hard_level, HardSource, FAMILIES
    level = make_hard_level("spruenge", seed="hard12:...")

Every level is a sequence of building blocks with its own random mix (Dirichlet-like weights per level), so two
levels rarely share a recipe. The blocks come from ideas and the jump catalogue, never from dev/test/exam geometry.

Families (each a training source and a probe group):
    spruenge    precise jump chains (always the widest robust jump for the height change, 1-tile landings),
                landings next to enemies, stone chains with enemies dropping from above, low ceilings,
                plus the hardest existing jump blocks (catalogue sequences, chains, shafts)
    strukturen  new structures - triple fork (floor / middle / top, only one leads on), detour (upper floor ends at
                a wall: back through the hole you jumped over, on below), crossing (channel straight into a fork) -
                plus the existing structural blocks (climbs, high roads, two routes, bait forks, channels, trenches)
    gemischt    both pools
    lang        long levels (550-900 tiles) from both pools
(The old blocks rain_stairs and high_road are left out: the solver never proved them in this setting.)
Rises are at most one row per hop (the bot's jumps, see distmap.JUMPS). Every level is checked with the distance
map; levels the solver cannot prove are filtered by the probe / demo builders.
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import List

from jumpnrun.core.level import Level
from jumpnrun.levelgen import generator as G

ROWS, GROUND, TOP = G.ROWS, G.GROUND, G.TOP_ROW
FAMILIES = ("spruenge", "strukturen", "gemischt", "lang")
LENGTH = {"spruenge": (160, 240), "strukturen": (160, 240), "gemischt": (180, 260), "lang": (550, 900)}
CFG = replace(G.TIERS[12], hard=3, hard_jumps=8.0, platform_enemies=True, free_enemies=0.5, enemy_groups=True,
              rain=0.6, max_gap=3, max_drop=4)


# ----------------------------------------------------------------------------------------------- new jump blocks
def _precise_chain(b: G._Builder) -> None:
    """10-18 jumps, each the widest (or one shorter) jump for its height change - with share 0.3 also the "tight"
    widest jumps that only work from some sub-tile positions -, landings as small as the catalogue allows; enemies on
    half of the wider landings, sometimes enemies dropping onto the chain from above."""

    rng = b.rng
    widest = G._widest_gaps()
    row, width = b.surface, 2
    b.flat(2)
    first_col = len(b.columns)
    for _ in range(rng.randint(10, 18)):
        tight = rng.random() < 0.3
        options = [e for e in G._jump_catalog()
                   if e["takeoff"] <= width and TOP <= row + e["drop"] <= GROUND - 1 and -1 <= e["drop"] <= 3
                   and ((e["gap"], e["drop"]) in G._TIGHT if tight else
                        ((e["gap"], e["drop"]) not in G._TIGHT and e["gap"] >= widest[e["drop"]] - 1))]
        if not options:
            options = [e for e in G._jump_catalog()
                       if e["takeoff"] <= width and TOP <= row + e["drop"] <= GROUND - 1 and -1 <= e["drop"] <= 3
                       and (e["gap"], e["drop"]) not in G._TIGHT and e["gap"] >= widest[e["drop"]] - 1]
        if row >= GROUND - 2:  # low: prefer rising
            options = [e for e in options if e["drop"] <= 0] or options
        e = rng.choice(options)
        land = min(x["landing"] for x in options if (x["gap"], x["drop"]) == (e["gap"], e["drop"]))
        b.gap(e["gap"])
        row += e["drop"]
        width = max(land, 1 if rng.random() < 0.6 else 2)
        first = len(b.columns)
        for _ in range(width):
            b.column(None, {row: "B"})
        if width >= 2 and rng.random() < 0.5:
            b.columns[first + width - 1][row - 1] = "E"
    for c in range(first_col, len(b.columns)):  # enemies waiting above some stones drop onto the chain
        top = next((r for r in range(ROWS) if b.columns[c][r] == "B"), None)
        if top is not None and top >= 5 and rng.random() < 0.12 and all(b.columns[c][r] == " " for r in range(top)):
            b.columns[c][rng.randint(0, 1)] = "E"
    b.gap(rng.randint(1, 2))
    b.surface = max(row, min(GROUND, row + rng.randint(0, 2)))
    b.flat(rng.randint(2, 4))


def _enemy_landings(b: G._Builder) -> None:
    """2-3 wide gaps, each landing on a short floor with 1-2 enemies right there."""

    rng = b.rng
    b.flat(2)
    for _ in range(rng.randint(3, 5)):
        if b.surface >= GROUND - 1 and rng.random() < 0.6:
            b.rise()
            b.flat(1)
        drop = rng.randint(1, 2) if b.surface < GROUND - 1 else 0
        gap = 3
        b.gap(gap)
        b.drop(drop)
        start = len(b.columns)
        width = rng.randint(3, 5)
        b.flat(width)
        for off in rng.sample(range(1, width), k=min(width - 1, rng.randint(1, 3))):
            b.columns[start + off][b.surface - 1] = "E"
    b.flat(2)


def _rain_chain(b: G._Builder) -> None:
    """A stone chain (generator._chain) with enemies waiting high above some stones - they drop onto the way."""

    start = len(b.columns)
    G._chain(b, CFG)
    rng = b.rng
    stones = [c for c in range(start, len(b.columns))
              if any(ch == "B" for ch in b.columns[c][TOP:GROUND]) and b.columns[c][0] == " "]
    for c in rng.sample(stones, k=min(len(stones), rng.randint(1, 3))):
        top = next(r for r in range(ROWS) if b.columns[c][r] == "B")
        if top >= 4 and all(b.columns[c][r] == " " for r in range(0, top)):
            b.columns[c][rng.randint(0, 1)] = "E"


# ----------------------------------------------------------------------------------------------- new structures
def _triple_fork(b: G._Builder) -> None:
    """Floor, middle road (row 9) and top road (row 6) side by side; only one leads on (random). The floor ends in
    a pit that cannot be crossed unless it is the way; a wrong road ends at a wall."""

    rng = b.rng
    if b.surface != GROUND:
        b.drop(GROUND - b.surface)
        b.flat(2)
    right = rng.choice(("boden", "mitte", "oben"))
    mid_len, top_len = rng.randint(22, 34), rng.randint(14, 24)
    w = 9 + mid_len + 2
    cols = [[" "] * ROWS for _ in range(w + 6)]
    for c in range(w + 6):
        cols[c][GROUND] = "B"
    cols[1][11] = cols[2][11] = "B"            # stairs: one row per hop
    cols[4][10] = cols[5][10] = "B"
    for c in range(7, 7 + mid_len):            # middle road (blocks in row 9)
        cols[c][9] = "B"
    cols[10][8] = cols[11][8] = "B"            # stairs from the middle road to the top road
    cols[13][7] = cols[14][7] = "B"
    t0 = 16
    for c in range(t0, min(t0 + top_len, w + 4)):
        cols[c][6] = "B"
    end_mid, end_top = 7 + mid_len - 1, min(t0 + top_len, w + 4) - 1
    if right != "boden":                       # the floor ends in a wide pit
        for c in range(w - 1, w + 6):
            cols[c][GROUND] = " "
    if right != "mitte":
        for r in (7, 8):
            cols[end_mid][r] = "B"
    else:
        for c in range(end_mid + 1, w + 6):
            cols[c][9] = "B"
    if right != "oben":
        for r in (3, 4, 5):
            cols[end_top][r] = "B"
    else:
        for c in range(end_top + 1, w + 6):
            cols[c][6] = "B"
    if rng.random() < 0.6:
        cols[rng.randint(18, w - 3)][GROUND - 1] = "E"
    if rng.random() < 0.4:
        cols[rng.randint(18, end_mid - 1)][8] = "E"
    b.columns += cols
    b.needs_path = True
    b.stats["dreifach_gabel_" + right] = 1
    b.surface = GROUND
    b.flat(rng.randint(3, 5))


def _detour(b: G._Builder) -> None:
    """Up a solid ramp to an upper floor (row 8); it ends at a wall that reaches the top. The way on is the low
    corridor below: back to the hole in the upper floor (jumped over on the way in), down, on to the right."""

    rng = b.rng
    if b.surface != GROUND:
        b.drop(GROUND - b.surface)
        b.flat(2)
    upper = 8
    ramp = list(range(GROUND - 1, upper - 1, -1))  # solid columns 11, 10, 9, 8: one row per step
    for top in ramp:
        b.column(top)
    floor_len = rng.randint(10, 16)
    hole_at, hole_w = rng.randint(2, 4), rng.randint(1, 3)
    for i in range(floor_len):
        col = [" "] * ROWS
        col[GROUND] = "B"
        if not hole_at <= i < hole_at + hole_w:
            col[upper] = "B"
        b.columns.append(col)
    wall = [" "] * ROWS
    for r in range(0, upper + 1):
        wall[r] = "B"
    wall[GROUND] = "B"
    b.columns.append(wall)                     # the corridor (rows 9-11) passes below the wall
    for _ in range(rng.randint(3, 6)):
        col = [" "] * ROWS
        col[GROUND] = "B"
        col[upper] = "B"                       # corridor roof continues a bit
        b.columns.append(col)
    if rng.random() < 0.5:
        b.columns[-rng.randint(2, 4)][GROUND - 1] = "E"
    b.needs_path = True
    b.stats["umweg"] = 1
    b.surface = GROUND
    b.flat(rng.randint(3, 5))


def _crossing(b: G._Builder) -> None:
    """A channel straight into a fork (back left, up, right - then decide floor or road)."""

    from jumpnrun.levelgen import skills

    if b.surface != GROUND:
        b.drop(GROUND - b.surface)
        b.flat(2)
    skills._channel(b, CFG, final=False, wide=b.rng.random() < 0.5)
    if b.surface != GROUND:
        b.drop(GROUND - b.surface)
        b.flat(2)
    G._fork_v10(b, CFG, b.rng.choice(("umkehren", "oben", "unten")), length=b.rng.randint(18, 32))
    b.stats["kreuzung"] = 1


# ----------------------------------------------------------------------------------------------- block pools
def _wrap(fn):
    def run(b):
        fn(b, CFG)
    return run


JUMP_BLOCKS = {
    "praezise_kette": (_precise_chain, lambda b: True),
    "landung_gegner": (_enemy_landings, lambda b: True),
    "regen_kette": (_rain_chain, lambda b: True),
    "sprung_katalog": (_wrap(G._jump_sequence), lambda b: True),
    "decke": (_wrap(G._ceiling), lambda b: b.surface >= 5),
    "schacht": (_wrap(G._shaft), lambda b: b.surface >= G.HIGHEST_SURFACE + 3),
    "rampe_gegner": (_wrap(G._enemy_ramp), lambda b: b.surface >= G.HIGHEST_SURFACE + 3),
}
STRUCT_BLOCKS = {
    "dreifach_gabel": (_triple_fork, lambda b: True),
    "umweg": (_detour, lambda b: True),
    "kreuzung": (_crossing, lambda b: True),
    "klettern": (_wrap(G._climb), lambda b: True),
    "zwei_wege": (_wrap(G._two_routes), lambda b: b.surface == GROUND),
    "koeder_gabel": (_wrap(G._bait_fork), lambda b: b.surface == GROUND),
    "kanal": (_wrap(G._channel), lambda b: b.surface == GROUND),
    "graben": (_wrap(G._trench), lambda b: b.surface >= 6),
}


CORE_JUMPS = ("praezise_kette", "landung_gegner", "regen_kette")


def _pool(family: str) -> dict:
    if family == "spruenge":
        return dict(JUMP_BLOCKS)
    if family == "strukturen":
        return dict(STRUCT_BLOCKS)
    return {**JUMP_BLOCKS, **STRUCT_BLOCKS}


def _build(family: str, rng: random.Random):
    b = G._Builder(rng)
    b.variant = "v10"
    b.style = {}
    pool = _pool(family)
    weights = {k: rng.gammavariate(0.7, 1.0) + 0.05 for k in pool}  # a different recipe in every level
    for k in CORE_JUMPS:  # the sharpened jump blocks carry the "spruenge" family
        if k in weights and family == "spruenge":
            weights[k] += 1.0
    b.flat(5)
    b.columns[1][b.surface - 1] = "P"
    if rng.random() < 0.3:
        b.flat(3)
        b.columns[-1][b.surface - 1] = "E"
    lo, hi = LENGTH[family]
    target = rng.randint(lo, hi)
    used = []
    while len(b.columns) < target:
        options = [k for k, (_, ok) in pool.items() if ok(b)]
        kind = rng.choices(options, weights=[weights[k] for k in options])[0]
        pool[kind][0](b)
        used.append(kind)
        if rng.random() < (0.15 if family == "spruenge" else 0.4):  # a short breather with an enemy now and then
            b.flat(rng.randint(2, 3), enemy=rng.random() < 0.5)
    if b.surface != GROUND and rng.random() < 0.5:
        b.drop(GROUND - b.surface)
    b.flat(4)
    b.columns[-2][b.surface - 1] = "C"
    b.column(b.surface - 3)
    lines = ["".join(col[r] for col in b.columns).rstrip() for r in range(ROWS)]
    return lines, used


def make_hard_level(family: str, seed: str, max_tries: int = 20) -> Level:
    from jumpnrun.levelgen.distmap import DistanceMap

    for t in range(max_tries):
        rng = random.Random(f"{seed}:{t}")
        lines, used = _build(family, rng)
        try:
            level = Level(lines, name=f"hard_{family}")
        except ValueError:
            continue
        dm = DistanceMap(level)
        if dm.reachable and dm.start is not None:
            level.needs_path = True
            level.family = f"v11_{family}"
            level.blocks = used
            level.building_blocks = {f"v11_{k}": 1 for k in used}
            return level
    raise RuntimeError(f"no valid {family} level for seed {seed}")


class HardSource:
    """Training source for generator v11 (MixSource name "hart"): families by weight, long levels separately."""

    HARD_TIER = -7

    def __init__(self, weights=None, seed_space: str = "hard12"):
        self.weights = dict(weights or {"spruenge": 0.4, "strukturen": 0.4, "gemischt": 0.2})
        self.seed_space = seed_space

    def __call__(self, rng: random.Random):
        fam = rng.choices(list(self.weights), weights=list(self.weights.values()))[0]
        for _ in range(5):
            try:
                level = make_hard_level(fam, f"{self.seed_space}:{fam}:{rng.randrange(10**9)}")
                break
            except RuntimeError:
                continue
        level.source = "hart"
        level.augmentations = []
        return level, self.HARD_TIER

    def feedback(self, *args, **kwargs) -> None:
        pass


class LongMixSource:
    """Phase 12 "lang": half two joined generator levels (skills.LongSource), half long v11 levels (550-900 tiles)."""

    LONG_TIER = -6

    def __init__(self, v11_share: float = 0.5):
        from jumpnrun.levelgen.skills import LongSource

        self.concat = LongSource()
        self.v11 = HardSource({"lang": 1.0})
        self.v11_share = v11_share

    def __call__(self, rng: random.Random):
        if rng.random() < self.v11_share:
            level, _ = self.v11(rng)
        else:
            level, _ = self.concat(rng)
            level.family = "lang"
        level.source = "lang"
        return level, self.LONG_TIER

    def feedback(self, *args, **kwargs) -> None:
        pass
