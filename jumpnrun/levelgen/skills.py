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
# Phase 11: + lange_sackgasse (the doppelgabel failure: the phase-10 bot walks back along a long dead-end road but
# climbs the stairs up again instead of dropping to the floor and going on under the road)
# The fork is built by _long_fork, not generator._fork_v10: there the road always continues the top stair step,
# while in doppelgabel a 2-tile gap (with floor below) separates them - the phase-10 bot walks back to that gap and
# turns around as if it were a pit. _long_fork varies the gaps between the steps (1-3), the gap between the top
# step and the road (0-3) and the road height (level with or one row above the top step).
#   d0  spawn at the wall of a 20-28 tiles road without gaps, no enemies
#   d1  road 30-40 tiles, an enemy on the floor under the road
#   d2  two such forks in a row (25-40 tiles each), normal start before the first, enemies
KINDS11 = KINDS + ("lange_sackgasse",)
MAX_WIDTH = {"lange_sackgasse": 170}  # practice levels are kept short (120 tiles), the long dead end needs more
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


def _long_fork(b: G._Builder, length: int) -> int:
    """Stairs (3 steps, varied gaps) up to a gap-less dead-end road over a floor; returns the wall column."""

    rng = b.rng
    b.flat(2)
    row = GROUND
    for i in range(3):
        for _ in range(rng.randint(1, 3) if i else rng.randint(0, 1)):  # floor only (the "gap" has floor below)
            b.column(GROUND)
        row -= 1
        for _ in range(rng.randint(1, 3)):
            b.column(GROUND, {row: "B"})
    for _ in range(rng.randint(0, 3)):
        b.column(GROUND)
    road = row - (1 if rng.random() < 0.5 else 0)
    for _ in range(length):
        b.column(GROUND, {road: "B"})
    wall = len(b.columns) - 1
    for r in range(max(0, road - 3), road):
        b.columns[wall][r] = "B"
    b.needs_path = True
    b.stats["lange_sackgasse"] = b.stats.get("lange_sackgasse", 0) + 1
    b.surface = GROUND
    b.flat(rng.randint(3, 5))
    return wall


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
    elif kind == "lange_sackgasse":
        if difficulty < 2:
            start = len(b.columns)
            wall = _long_fork(b, rng.randint(20, 28) if difficulty == 0 else rng.randint(30, 40))
            if difficulty == 1:  # an enemy on the floor under the road
                b.columns[rng.randint(start + 12, wall - 4)][GROUND - 1] = "E"
            key, high = wall - 1, True
        else:
            for _ in range(2):
                wall = _long_fork(b, rng.randint(25, 40))
                if rng.random() < 0.5:
                    b.columns[wall - rng.randint(4, 12)][GROUND - 1] = "E"
            key = None
        G._segment(b, cfg)
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
    if key is None:  # lange_sackgasse d2: the normal start
        pass
    elif kind == "lange_sackgasse":  # d0/d1: at the dead-end wall, on the road
        lines = _place_spawn(lines, key, True)
    elif difficulty == 0:
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
        if width > MAX_WIDTH.get(kind, 120):  # long random segments: keep practice levels short
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

    def __init__(self, seed_space: str = "skill10", kinds=KINDS, boost=None):
        self.seed_space = seed_space
        self.kinds = tuple(kinds)
        self.boost = dict(boost or {})  # phase 11: {kind: factor} on the frontier weight (lange_sackgasse x2)
        self.level = {k: 0 for k in self.kinds}
        self.hist = {(k, d): [] for k in self.kinds for d in range(3)}
        self.central = None  # phase 11: {kind: p} from the SkillTracker of the training process

    def set_state(self, levels: dict, p: dict) -> None:
        """Phase 11: difficulty and frontier estimate per kind pooled over all envs (SkillTracker)."""

        self.level = {k: int(levels.get(k, 0)) for k in self.kinds}
        self.central = dict(p)

    def _p(self, kind: str) -> float:
        if self.central is not None:
            return self.central.get(kind, 0.5)
        h = self.hist[(kind, self.level[kind])]
        return sum(h) / len(h) if h else 0.5

    def __call__(self, rng: random.Random):
        kinds = list(self.kinds)
        weights = [(self._p(k) * (1 - self._p(k)) + 0.05) * self.boost.get(k, 1.0) for k in kinds]
        kind = rng.choices(kinds, weights=weights)[0]
        top = self.level[kind]
        d = top if top == 0 or rng.random() < 0.7 else rng.randrange(top)
        level = make_skill_level(kind, d, f"{self.seed_space}:{kind}:{d}:{rng.randrange(10**9)}")
        level.source = "skill"
        level.augmentations = []
        return level, -4

    def feedback(self, level: Level, won: bool, fresh: bool = True) -> None:
        kind, d = getattr(level, "skill_kind", None), getattr(level, "difficulty", None)
        if kind is None or not fresh or self.central is not None:  # central: the training process decides
            return
        h = self.hist[(kind, d)]
        h.append(int(won))
        del h[:-self.WINDOW]
        if d == self.level[kind] and d < 2 and len(h) >= self.WINDOW and sum(h) / len(h) >= self.OPEN_AT:
            self.level[kind] = d + 1


class SkillTracker:
    """Phase 11 (from the Neustart branch): the SkillSource frontier pooled over all envs, in the training process.
    Phase 10 kept it per env (8 x 100 episodes per kind before the next difficulty opened) and lost it on every
    restart; here it is shared, sent to the envs at every rollout end and saved in curriculum.json."""

    WINDOW = SkillSource.WINDOW
    OPEN_AT = SkillSource.OPEN_AT

    def __init__(self, kinds=KINDS11):
        self.level = {k: 0 for k in kinds}
        self.hist = {f"{k}:{d}": [] for k in kinds for d in range(3)}

    def record(self, kind: str, d: int, won: bool) -> None:
        h = self.hist.get(f"{kind}:{d}")
        if h is None:
            return
        h.append(int(won))
        del h[:-self.WINDOW]
        if d == self.level[kind] and d < 2 and len(h) >= self.WINDOW and sum(h) / len(h) >= self.OPEN_AT:
            self.level[kind] = d + 1

    def p(self) -> dict:
        out = {}
        for k, d in self.level.items():
            h = self.hist[f"{k}:{d}"]
            out[k] = sum(h) / len(h) if h else 0.5
        return out

    def state(self) -> dict:
        return {"level": self.level, "hist": self.hist}

    def load(self, state: dict) -> None:
        self.level.update({k: int(v) for k, v in state.get("level", {}).items() if k in self.level})
        for key, h in state.get("hist", {}).items():
            if key in self.hist:
                self.hist[key] = list(h)[-self.WINDOW:]


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

    def __init__(self, min_tier: int = 4, max_tier: int = 12, long_share: float = 0.0):
        self.tiers = list(range(min_tier, max_tier + 1))
        self.long_share = long_share  # phase 11: share of mirrored long levels (LongSource, chest far left)

    def __call__(self, rng: random.Random):
        from jumpnrun.levelgen.distmap import DistanceMap

        if self.long_share and rng.random() < self.long_share:
            for _ in range(10):
                level = mirror_level(LongSource().make(rng))
                dm = DistanceMap(level)
                if dm.reachable and dm.start is not None:
                    level.source = "spiegel"
                    level.augmentations = ["mirror", "lang"]
                    level.mirror_tier = LongSource.LONG_TIER
                    return level, self.MIRROR_TIER
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


def _top(lines: List[str], col: int) -> Optional[int]:
    return next((r for r in range(len(lines)) if col < len(lines[r]) and lines[r][col] == "B"), None)


def concat_levels(a: Level, b: Level, name: str = None) -> Optional[Level]:
    """Phase 11: one long level from two generator levels - a's chest and end wall removed, b's spawn removed,
    joined by 4 floor columns at the lower of the two surfaces. None if the distance map finds no way."""

    from jumpnrun.levelgen.distmap import DistanceMap

    la, lb = a.to_text().splitlines(), b.to_text().splitlines()
    rows = max(len(la), len(lb))
    la += [""] * (rows - len(la))
    lb += [""] * (rows - len(lb))
    wa = max(len(l) for l in la) - 1  # without a's end wall column
    la = [l.ljust(wa + 1)[:wa].replace("C", " ") for l in la]
    lb = [l.replace("P", " ") for l in lb]
    ta, tb = _top(la, wa - 1), _top(lb, 0)
    if ta is None or tb is None:
        return None
    floor = max(ta, tb)
    bridge = ["B" * 4 if r >= floor else " " * 4 for r in range(rows)]
    lines = [(la[r] + bridge[r] + lb[r]).rstrip() for r in range(rows)]
    try:
        out = Level(lines, name=name or f"{a.name}+{b.name}")
    except ValueError:
        return None
    out.needs_path = True
    dm = DistanceMap(out)
    return out if dm.reachable and dm.start is not None else None


class LongSource:
    """Phase 11: long levels (~300-700 tiles) made of two v9 generator levels of tiers 8-12 (endurance: on the
    long guard levels the deaths spread over the whole length)."""

    LONG_TIER = -6

    def __init__(self, min_tier: int = 8, max_tier: int = 12):
        self.tiers = list(range(min_tier, max_tier + 1))

    def make(self, rng: random.Random) -> Level:
        for _ in range(20):
            ta, tb = rng.choice(self.tiers), rng.choice(self.tiers)
            level = concat_levels(G.generate(ta, rng.randrange(10**8)), G.generate(tb, rng.randrange(10**8)),
                                  name=f"lang_{ta}_{tb}")
            if level is not None:
                level.long_tiers = (ta, tb)
                return level
        raise RuntimeError("no valid long level in 20 tries")

    def __call__(self, rng: random.Random):
        level = self.make(rng)
        level.source = "lang"
        level.augmentations = []
        return level, self.LONG_TIER

    def feedback(self, *args, **kwargs) -> None:
        pass
