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


TIERS = (
    TierConfig(length=25),                                                              # 0 walk to the chest
    TierConfig(length=35, max_gap=1, steps=True),                                       # 1 small gaps, steps
    TierConfig(length=45, max_gap=2, steps=True, max_drop=2),                           # 2 real gaps
    TierConfig(length=55, max_gap=2, steps=True, max_drop=2, valleys=1.0),              # 3 enemies
    TierConfig(length=65, max_gap=2, steps=True, max_drop=2, valleys=1.0, platforms=1.0),    # 4 platforms
    TierConfig(length=80, max_gap=2, steps=True, max_drop=3, valleys=1.5, platforms=1.5,
               free_enemies=0.15),                                                      # 5 everything
    TierConfig(length=100, max_gap=2, steps=True, max_drop=3, valleys=2.0, platforms=2.0,
               platform_enemies=True, free_enemies=0.25),                               # 6 dense
    TierConfig(length=130, max_gap=3, steps=True, max_drop=4, valleys=2.5, platforms=2.5,
               platform_enemies=True, free_enemies=0.35),                               # 7 expert
    TierConfig(length=150, max_gap=3, steps=True, max_drop=4, valleys=2.5, platforms=2.0,
               platform_enemies=True, free_enemies=0.35, climbs=1.5, enemy_groups=True,
               rain=0.3),                                                               # 8 climbing, groups
    TierConfig(length=200, max_gap=3, steps=True, max_drop=4, valleys=3.0, platforms=2.5,
               platform_enemies=True, free_enemies=0.4, climbs=2.5, enemy_groups=True,
               rain=0.5),                                                               # 9 like the exam
)
NUM_TIERS = len(TIERS)


class _Builder:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.columns: List[List[str]] = []  # each column: ROWS chars, top row first
        self.surface = GROUND  # row of the current ground surface

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


def _segment(b: _Builder, cfg: TierConfig) -> None:
    rng = b.rng
    choices = [("flat", 1.0)]
    if cfg.max_gap:
        choices.append(("gap", 1.2))
    if cfg.steps:
        choices.append(("step", 1.0))
    if cfg.valleys and b.surface <= GROUND - 1:
        choices.append(("valley", cfg.valleys))
    if cfg.platforms:
        choices.append(("platforms", cfg.platforms))
    if cfg.climbs:
        choices.append(("climb", cfg.climbs))
    kind = rng.choices([c[0] for c in choices], weights=[c[1] for c in choices])[0]

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


def generate(tier: int, seed: int) -> Level:
    """Build a level of the given difficulty tier (0 .. NUM_TIERS-1)."""

    cfg = TIERS[max(0, min(tier, NUM_TIERS - 1))]
    rng = random.Random(f"{tier}:{seed}")
    b = _Builder(rng)
    b.flat(5)
    b.columns[1][b.surface - 1] = "P"
    while len(b.columns) < cfg.length:
        _segment(b, cfg)
    b.flat(4)
    b.columns[-2][b.surface - 1] = "C"
    b.column(b.surface - 3)  # wall behind the chest

    lines = ["".join(col[r] for col in b.columns).rstrip() for r in range(ROWS)]
    return Level(lines, name=f"gen_t{tier}_s{seed}")


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
