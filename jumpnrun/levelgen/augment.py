"""Level augmentation (phase 8): carry situations of hand-made levels into every training level.

The reflection after phase 7 found situations in hand-made levels that training never showed:
    - the chest stands on the last floor tile with a real void behind it (generated levels end right
      after the chest, and the level edge clamps the player like an invisible wall),
    - terrain and stones in the top rows (generated terrain never goes above row 3),
    - a solid ceiling (as in the test series level "hoehle"),
    - the player starting in the air,
    - enemies walking towards the player and waking up at different distances.
Each augmentation keeps the game physics untouched; it only rewrites the tile map (or sets the optional
per-enemy start direction / wake distance that Simulation reads from the level).

    level, tags = augment(level, rng)       # tags: list of applied augmentations, for the episode log

Phase 9 adds (config V2, all off in DEFAULT so phase 8 runs stay as they were):
    - mirror: the level reversed - the chest on the left, the way leads left (needs the path reward),
    - density: 0.5x - 2x enemies on free floor tiles,
    - noise: pits one tile narrower, floating platforms one row up or down,
    - concat: two levels after each other (longer levels; the caller passes the second one).
Mirror, noise and density are checked with the distance map: if the chest became unreachable, they are dropped.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Tuple

from jumpnrun.core.constants import ROWS, TILE
from jumpnrun.core.level import Level


@dataclass(frozen=True)
class AugmentConfig:
    void: float = 0.5  # chest on the last floor tile, void behind it
    raise_rows: float = 0.3  # move the whole level up by 1 (sometimes 2) rows
    ceiling: float = 0.15  # solid ceiling in rows 0-1 where there is headroom
    air_start: float = 0.25  # spawn 1-4 rows higher (falls at the start)
    enemies: float = 0.5  # random start direction and wake distance per enemy
    wake_tiles: Tuple[int, int] = (12, 24)
    mirror: float = 0.0  # phase 9
    density: float = 0.0  # phase 9
    noise: float = 0.0  # phase 9
    concat: float = 0.0  # phase 9 (only applied when augment() gets a partner level)


DEFAULT = AugmentConfig()
V2 = AugmentConfig(mirror=0.3, density=0.3, noise=0.3, concat=0.15)


def _grid(level: Level) -> List[List[str]]:
    return [list(line.ljust(level.cols)) for line in level._lines]


def _void_behind_chest(g: List[List[str]], rng: random.Random) -> bool:
    chests = [(r, c) for r, row in enumerate(g) for c, ch in enumerate(row) if ch == "C"]
    if not chests:
        return False
    r, c = max(chests, key=lambda rc: rc[1])  # the last chest
    if r + 1 >= ROWS or g[r + 1][c] != "B":
        return False  # chest not standing on a block: leave the level alone
    if any(ch == "B" for row in g for ch in row[c + 3:]):
        return False  # phase 9: the chest is not at the end (e.g. inside a channel)
    extra = rng.randint(2, 40) if rng.random() < 0.5 else rng.randint(120, 240)
    for row in g:
        del row[c + 1:]
        row.extend(" " * extra)
    return True


def _raise(g: List[List[str]], rng: random.Random) -> int:
    n = 2 if rng.random() < 0.25 else 1
    # rows 0..n+1 must be empty: after the shift two free rows stay above the highest terrain, else jumps
    # onto the top stones hit the upper border (solver sample: 25 % unsolvable without this rule)
    while n and any(ch != " " for r in range(n + 2) for ch in g[r]):
        n -= 1
    for _ in range(n):
        g.pop(0)
        g.append([" "] * len(g[0]))
    return n


def _ceiling(g: List[List[str]]) -> bool:
    cols = len(g[0])
    done = False
    free = [all(g[r][c] == " " for r in range(5)) for c in range(cols)]
    for c in range(cols):
        # three free rows below the ceiling - also in the neighbouring columns a jump passes through
        if all(free[max(0, c - 4):c + 5]):
            g[0][c] = g[1][c] = "B"
            done = True
    return done


def _air_start(g: List[List[str]], rng: random.Random) -> bool:
    spawn = [(r, c) for r, row in enumerate(g) for c, ch in enumerate(row) if ch == "P"]
    if not spawn:
        return False
    r, c = spawn[0]
    up = rng.randint(1, 4)
    target = r - up
    if target < 0 or any(g[rr][c] != " " for rr in range(target, r)):
        return False
    g[r][c] = " "
    g[target][c] = "P"
    return True


def _concat(g: List[List[str]], other: Level) -> bool:
    """Append `other` behind this level: the first chest (and a wall right behind it) go, other's spawn goes."""

    chests = [(r, c) for r, row in enumerate(g) for c, ch in enumerate(row) if ch == "C"]
    if not chests:
        return False
    r, c = max(chests, key=lambda rc: rc[1])
    g[r][c] = " "
    for row in g:
        del row[c + 2:]  # keep the floor tile behind the chest, drop the wall / void behind it
    h = _grid(other)
    for rr, row in enumerate(h):
        g[rr].extend(" " if ch == "P" else ch for ch in row)
    return True


def _mirror(g: List[List[str]]) -> None:
    for row in g:
        row.reverse()


def _density(g: List[List[str]], rng: random.Random) -> bool:
    enemies = [(r, c) for r, row in enumerate(g) for c, ch in enumerate(row) if ch == "E"]
    spawn = [c for row in g for c, ch in enumerate(row) if ch == "P"]
    sc = spawn[0] if spawn else 2
    factor = rng.choice((0.5, 1.5, 2.0))
    if factor < 1:
        for r, c in rng.sample(enemies, k=len(enemies) // 2):
            g[r][c] = " "
        return bool(enemies)
    free = [(r, c) for r in range(1, ROWS - 1) for c in range(len(g[0]))
            if g[r][c] == " " and g[r + 1][c] == "B" and g[r - 1][c] == " " and abs(c - sc) > 10]
    extra = max(1, round(len(enemies) * (factor - 1)))
    for r, c in rng.sample(free, k=min(extra, len(free))):
        g[r][c] = "E"
    return bool(free)


def _noise(g: List[List[str]], rng: random.Random) -> bool:
    cols = len(g[0])
    empty = [all(g[r][c] == " " for r in range(ROWS)) for c in range(cols)]
    changed = False
    c = 0
    while c < cols:  # pits (fully empty columns) of width >= 2: sometimes one narrower
        if not empty[c]:
            c += 1
            continue
        e = c
        while e < cols and empty[e]:
            e += 1
        if e < cols and c > 0 and e - c >= 2 and rng.random() < 0.3:
            for r in range(ROWS):
                g[r][c] = g[r][c - 1] if g[r][c - 1] == "B" else " "
            changed = True
        c = e
    for r in range(4, ROWS - 2):  # floating platforms (1-4 blocks, free above and below): one row up or down
        c = 0
        while c < cols:
            if g[r][c] != "B":
                c += 1
                continue
            e = c
            while e < cols and g[r][e] == "B":
                e += 1
            run = range(c, e)
            floating = e - c <= 4 and all(g[r - 1][x] == " " and g[r + 1][x] == " " for x in run)
            if floating and rng.random() < 0.3:
                d = rng.choice((-1, 1))
                t = r + d
                if 3 <= t <= ROWS - 2 and all(g[t][x] == " " and g[t - 1][x] == " " and g[t + 1][x] in " B"
                                              for x in run):
                    for x in run:
                        g[r][x], g[t][x] = " ", "B"
                    changed = True
            c = e
    return changed


def _reachable(g: List[List[str]]) -> bool:
    from jumpnrun.levelgen.distmap import DistanceMap

    try:
        lv = Level(["".join(row) for row in g])
    except ValueError:
        return False
    dm = DistanceMap(lv)
    return dm.reachable and dm.start is not None


def augment(level: Level, rng: random.Random, cfg: AugmentConfig = DEFAULT,
            partner: "Level | None" = None) -> Tuple[Level, List[str]]:
    """A randomly augmented copy of `level` and the list of applied augmentations."""

    g = _grid(level)
    tags: List[str] = []
    mirrored = False
    if partner is not None and rng.random() < cfg.concat and _concat(g, partner):
        tags.append("concat")
    for name, prob, fn in (("density", cfg.density, _density), ("noise", cfg.noise, _noise)):
        if prob and rng.random() < prob:
            before = [row[:] for row in g]
            if fn(g, rng) and _reachable(g):
                tags.append(name)
            else:
                g = before
    if rng.random() < cfg.void and _void_behind_chest(g, rng):
        tags.append("void")
    raised = 0
    if rng.random() < cfg.raise_rows:
        raised = _raise(g, rng)
        if raised:
            tags.append("raise")
    if rng.random() < cfg.ceiling and _ceiling(g):
        tags.append("ceiling")
    if rng.random() < cfg.air_start and _air_start(g, rng):
        tags.append("air")
    if cfg.mirror and rng.random() < cfg.mirror:  # last: the void behind the chest ends up on the left
        _mirror(g)
        mirrored = True
        tags.append("mirror")
    out = Level(["".join(row) for row in g], name=level.name + ("+" + "+".join(tags) if tags else ""))
    if rng.random() < cfg.enemies and out.enemy_spawns:
        lo, hi = cfg.wake_tiles
        out.enemy_directions = [rng.choice((-1, 1)) for _ in out.enemy_spawns]
        out.enemy_wakes = [rng.randint(lo, hi) * TILE for _ in out.enemy_spawns]
        tags.append("enemies")
    elif mirrored and out.enemy_spawns:
        out.enemy_directions = [-1] * len(out.enemy_spawns)  # mirrored: enemies walk the mirrored way
    if hasattr(level, "building_blocks"):
        out.building_blocks = level.building_blocks
    if hasattr(level, "waypoints") and not mirrored and "concat" not in tags:
        out.waypoints = [(c, r - raised) for c, r in level.waypoints if c < out.cols]  # moved with the terrain
    out.needs_path = mirrored or "concat" in tags or getattr(level, "needs_path", False)
    out.augmentations = tags
    return out, tags
