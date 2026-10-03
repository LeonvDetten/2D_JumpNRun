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


DEFAULT = AugmentConfig()


def _grid(level: Level) -> List[List[str]]:
    return [list(line.ljust(level.cols)) for line in level._lines]


def _void_behind_chest(g: List[List[str]], rng: random.Random) -> bool:
    chests = [(r, c) for r, row in enumerate(g) for c, ch in enumerate(row) if ch == "C"]
    if not chests:
        return False
    r, c = max(chests, key=lambda rc: rc[1])  # the last chest
    if r + 1 >= ROWS or g[r + 1][c] != "B":
        return False  # chest not standing on a block: leave the level alone
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


def augment(level: Level, rng: random.Random, cfg: AugmentConfig = DEFAULT) -> Tuple[Level, List[str]]:
    """A randomly augmented copy of `level` and the list of applied augmentations."""

    g = _grid(level)
    tags: List[str] = []
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
    out = Level(["".join(row) for row in g], name=level.name + ("+" + "+".join(tags) if tags else ""))
    if rng.random() < cfg.enemies and out.enemy_spawns:
        lo, hi = cfg.wake_tiles
        out.enemy_directions = [rng.choice((-1, 1)) for _ in out.enemy_spawns]
        out.enemy_wakes = [rng.randint(lo, hi) * TILE for _ in out.enemy_spawns]
        tags.append("enemies")
    if hasattr(level, "building_blocks"):
        out.building_blocks = level.building_blocks
    if hasattr(level, "waypoints"):  # route hints for the solver, moved with the terrain
        out.waypoints = [(c, r - raised) for c, r in level.waypoints if c < out.cols]
    out.augmentations = tags
    return out, tags
