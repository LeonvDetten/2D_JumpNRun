"""Phase 10: short practice levels for the new skills ("erst üben, dann mischen").

    from jumpnrun.levelgen.skills import KINDS, make_skill_level, SkillSource
    level = make_skill_level("kanal3", difficulty=1, seed="skill10:...")

Seven kinds, each with three difficulties:
    kanal_ende        a channel that ends with the chest on the left (bottom right, stairs up, back left)
    kanal2            a channel with two turns, out at the top right
    kanal3            like kanal2, but the jump back over the stair opening is 3 tiles wide (as in serpentine)
    sackgasse_runter  start on an upper road in front of its dead-end wall: walk back, drop down, go on below
    gabel_umkehren    a fork whose upper road has no gaps and dead-ends (the floor is right)
    gabel_oben        a fork whose floor ends in a wide pit (the upper road is right)
    truhe_links_kurz  the chest 20-60 tiles to the left, 1-4 gaps / steps that need left+jump
    d0  start ~5 tiles before the key spot, no enemies
    d1  one random segment before, start 10-15 tiles before the key spot
    d2  two random segments before, normal start, enemies (free_enemies 0.3)
Every level is checked with the distance map (chest reachable from the start), else the next seed is tried.
Seed spaces: "skill10:" training, "demo10:" teacher demos, "probe10:" probes - never shared.
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import List, Optional

from jumpnrun.core.level import Level
from jumpnrun.levelgen import generator as G

KINDS = ("kanal_ende", "kanal2", "kanal3", "sackgasse_runter", "gabel_umkehren", "gabel_oben", "truhe_links_kurz")
ROWS, GROUND = G.ROWS, G.GROUND


def _channel(b: G._Builder, cfg: G.TierConfig, final: bool, wide: bool) -> int:
    """Like generator._channel; wide=True makes the stair openings one tile wider (jump back over 3 tiles).

    Returns the column of the key spot (top of the first stairs)."""

    rng = b.rng
    w = rng.randint(20, 30)
    s = len(b.columns)
    o = 1 if wide else 0
    cols = [[" "] * ROWS for _ in range(w)]
    for c in range(w):
        cols[c][GROUND] = "B"
    for r in range(0, 9):
        cols[0][r] = "B"
    for c in range(0, w - 4 - o):
        cols[c][8] = "B"
    for c, top in ((w - 4, 11), (w - 3, 10), (w - 2, 9)):
        for r in range(top, GROUND):
            cols[c][r] = "B"
    for r in range(0 if final else 4, ROWS):
        cols[w - 1][r] = "B"
    if rng.random() < cfg.free_enemies:
        cols[rng.randint(4, w - 8)][GROUND - 1] = "E"
    if final:
        cols[rng.randint(1, 3)][7] = "C"
        if rng.random() < cfg.free_enemies:
            cols[rng.randint(7, w - 7 - o)][7] = "E"
    else:
        for c in range(4 + o, w - 1):
            cols[c][4] = "B"
        for c, top in ((3, 7), (2, 6), (1, 5)):
            for r in range(top, 8):
                cols[c][r] = "B"
        if rng.random() < cfg.free_enemies:
            cols[rng.randint(7, w - 7 - o)][7] = "E"
    b.columns += cols
    if not final:
        b.surface = G.HIGHEST_SURFACE
        b.flat(rng.randint(3, 5))
    return s + w - 2


def _segments(b: G._Builder, cfg: G.TierConfig, n: int) -> None:
    for _ in range(n):
        G._segment(b, cfg)
    if b.surface != GROUND:
        b.drop(GROUND - b.surface)
        b.flat(3)


def _finish(b: G._Builder) -> None:
    b.flat(4)
    b.columns[-2][b.surface - 1] = "C"
    b.column(b.surface - 3)


def _stand_rows(lines: List[str], col: int) -> List[int]:
    return [r for r in range(ROWS - 1) if lines[r][col] == " " and lines[r + 1][col] == "B"]


def _place_spawn(lines: List[str], col: int, high: bool) -> Optional[List[str]]:
    col = max(1, min(col, len(lines[0]) - 2))
    for c in [col] + [col + d for k in range(1, 6) for d in (-k, k)]:
        if not 0 < c < len(lines[0]) - 1:
            continue
        rows = _stand_rows(lines, c)
        if rows:
            r = min(rows) if high else max(rows)
            out = [line.replace("P", " ") for line in lines]
            out[r] = out[r][:c] + "P" + out[r][c + 1:]
            return out
    return None


def _build(kind: str, difficulty: int, rng: random.Random):
    cfg = G.TIERS[10]
    if difficulty < 2:
        cfg = replace(cfg, free_enemies=0.0, platform_enemies=False, rain=0.0, enemy_groups=False)
    else:
        cfg = replace(cfg, free_enemies=0.3)
    b = G._Builder(rng)
    b.variant = "v9"
    b.style = G._style(rng, cfg)
    if difficulty < 2:  # no random blocks with enemies in the easy stages
        b.style = {k: v for k, v in b.style.items() if k in ("flat", "gap", "step", "platforms", "stones")}
    b.flat(5)
    b.columns[1][b.surface - 1] = "P"
    _segments(b, cfg, difficulty)
    high = False
    mirror = False
    if kind in ("kanal_ende", "kanal2", "kanal3"):
        key = _channel(b, cfg, final=kind == "kanal_ende", wide=kind == "kanal3")
        key -= 12  # the key spot is reached along the bottom corridor: start before the stairs
        if kind != "kanal_ende":
            _finish(b)
    elif kind in ("sackgasse_runter", "gabel_umkehren", "gabel_oben"):
        start = len(b.columns)
        G._fork_v10(b, cfg, "umkehren" if kind != "gabel_oben" else "oben")
        if kind == "sackgasse_runter":
            wall = max(c for c in range(start, len(b.columns))
                       if sum(ch == "B" for ch in b.columns[c][:GROUND]) >= 3 and b.columns[c][GROUND] == "B")
            key, high = wall - 1, True
        else:
            key = start + 2
        G._segment(b, cfg)
        _finish(b)
    else:  # truhe_links_kurz: built left to right (start -> chest), then mirrored
        b.flat(3)
        key = len(b.columns)
        for _ in range(rng.randint(1, 4)):
            if rng.random() < 0.65:
                b.gap(rng.randint(2, 3))
                b.flat(rng.randint(2, 5))
            else:
                if not b.rise():
                    b.drop(1)
                b.flat(rng.randint(2, 4))
        _finish(b)
        mirror = True
    lines = ["".join(col[r] for col in b.columns) for r in range(ROWS)]
    width = len(lines[0])
    if difficulty == 0:
        lines = _place_spawn(lines, key if high else key - 5, high)
    elif difficulty == 1:
        lines = _place_spawn(lines, key if high else key - rng.randint(10, 15), high)
    elif high:  # d2 of sackgasse_runter: further back on the road
        lines = _place_spawn(lines, key - rng.randint(8, 14), True)
    if lines is None:
        return None
    if mirror:
        lines = [line[::-1] for line in lines]
    lines = [line.rstrip() for line in lines]
    return lines, width


def make_skill_level(kind: str, difficulty: int, seed: str, max_tries: int = 12) -> Level:
    from jumpnrun.levelgen.distmap import DistanceMap

    for t in range(max_tries):
        rng = random.Random(f"{seed}:{t}")
        built = _build(kind, difficulty, rng)
        if built is None:
            continue
        lines, width = built
        if width > 120:  # long random segments: keep practice levels short
            continue
        try:
            level = Level(lines, name=f"skill_{kind}_d{difficulty}")
        except ValueError:
            continue
        dm = DistanceMap(level)
        if dm.reachable and dm.start is not None:
            level.skill_kind = kind
            level.difficulty = difficulty
            level.needs_path = True
            level.building_blocks = {f"skill_{kind}": 1}
            return level
    raise RuntimeError(f"no valid {kind} d{difficulty} level for seed {seed}")


class SkillSource:
    """Practice levels drawn at the learning frontier (weight p(1-p) + 0.05 per kind); the next difficulty of a
    kind opens at >= 70 % fresh wins over its last 100 episodes."""

    WINDOW = 100
    OPEN_AT = 0.7

    def __init__(self, seed_space: str = "skill10"):
        self.seed_space = seed_space
        self.level = {k: 0 for k in KINDS}
        self.hist = {(k, d): [] for k in KINDS for d in range(3)}

    def _p(self, kind: str) -> float:
        h = self.hist[(kind, self.level[kind])]
        return sum(h) / len(h) if h else 0.5

    def __call__(self, rng: random.Random):
        kinds = list(KINDS)
        weights = [self._p(k) * (1 - self._p(k)) + 0.05 for k in kinds]
        kind = rng.choices(kinds, weights=weights)[0]
        top = self.level[kind]
        d = top if top == 0 or rng.random() < 0.7 else rng.randrange(top)
        level = make_skill_level(kind, d, f"{self.seed_space}:{kind}:{d}:{rng.randrange(10**9)}")
        level.source = "skill"
        level.augmentations = []
        return level, -4

    def feedback(self, level: Level, won: bool, fresh: bool = True) -> None:
        kind, d = getattr(level, "skill_kind", None), getattr(level, "difficulty", None)
        if kind is None or not fresh:
            return
        h = self.hist[(kind, d)]
        h.append(int(won))
        del h[:-self.WINDOW]
        if d == self.level[kind] and d < 2 and len(h) >= self.WINDOW and sum(h) / len(h) >= self.OPEN_AT:
            self.level[kind] = d + 1


def mirror_level(level: Level, name: str = None) -> Level:
    """The level mirrored left-right (chest on the other side); needs the way-distance measurement."""

    lines = level.to_text().splitlines()
    w = max(len(l) for l in lines)
    out = Level("\n".join(l.ljust(w)[::-1].rstrip() for l in lines).splitlines(), name=name or level.name + "_spiegel")
    out.needs_path = True
    return out


class MirrorSource:
    """Phase 10 D: mirrored phase-8 generator levels (v9, tiers 4-12, chest on the left) for the generalist goal
    "both directions"; only levels whose mirror the distance map can solve are used."""

    MIRROR_TIER = -5

    def __init__(self, min_tier: int = 4, max_tier: int = 12):
        self.tiers = list(range(min_tier, max_tier + 1))

    def __call__(self, rng: random.Random):
        from jumpnrun.levelgen.distmap import DistanceMap

        for _ in range(10):
            tier = rng.choice(self.tiers)
            level = mirror_level(G.generate(tier, rng.randrange(10**8)))
            dm = DistanceMap(level)
            if dm.reachable and dm.start is not None:
                break
        level.source = "spiegel"
        level.augmentations = ["mirror"]
        level.mirror_tier = tier
        return level, self.MIRROR_TIER

    def feedback(self, *args, **kwargs) -> None:
        pass
