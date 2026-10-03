"""Jump catalogue: which single jumps can the bot actually make? Measured once with the solver.

    python -m jumpnrun.levelgen.jump_catalog     # writes jumpnrun/levelgen/jump_catalog.json

A jump is (takeoff width, gap, height change, landing width): the player stands on a floating
platform `takeoff` tiles wide, has to cross `gap` empty columns and land on a floating platform
`landing` tiles wide that lies `drop` rows lower (negative = higher). Below everything is the void.
The solver (same action set and action repeat as the bot) decides whether the landing platform can
be reached. Generator tier 12 builds jump sequences drawn evenly from the feasible entries, so no
kind of jump stays unseen in training - in phase 6 all three big jumps in exam results came from
jump kinds the generator did not build yet.
"""

from __future__ import annotations

import itertools
import json
from multiprocessing import Pool
from pathlib import Path

from jumpnrun.core.constants import ROWS
from jumpnrun.core.level import Level

CATALOG_PATH = Path(__file__).with_name("jump_catalog.json")
TAKEOFF_WIDTHS = (1, 2, 3)
GAPS = (1, 2, 3, 4, 5)
DROPS = tuple(range(-1, 9))  # -1 = one row up ... 8 rows down
LANDING_WIDTHS = (1, 2, 3)
REPEAT = 2


def takeoff_row(drop: int) -> int:
    return 11 - drop if drop >= 3 else 8


def jump_level(takeoff: int, gap: int, drop: int, landing: int) -> Level:
    row = takeoff_row(drop)
    land_row = row + drop
    cols = 1 + takeoff + gap + landing + 8
    grid = [[" "] * cols for _ in range(ROWS)]
    for c in range(1, 1 + takeoff):
        grid[row][c] = "B"
    grid[row - 1][1] = "P"
    first = 1 + takeoff + gap
    for c in range(first, first + landing):
        grid[land_row][c] = "B"
    grid[ROWS - 1][cols - 2] = "B"  # far away chest (the solver aims for the landing platform instead)
    grid[ROWS - 2][cols - 2] = "C"
    return Level(["".join(r).rstrip() for r in grid], name=f"jump_{takeoff}_{gap}_{drop}_{landing}")


def feasible(spec) -> bool:
    """Robustly feasible: reachable from every sub-tile start offset.

    The player moves 8 px per frame, so the positions it can take off from form a lattice whose
    offset depends on how it arrived. The tightest jumps only work for some offsets - in a chain of
    jumps they can become impossible, so they are left out.
    """

    from jumpnrun.core.sim import Simulation
    from jumpnrun.levelgen.solver import solve

    takeoff, gap, drop, landing = spec
    level = jump_level(takeoff, gap, drop, landing)
    first = 1 + takeoff + gap
    goals = [(c, takeoff_row(drop) + drop) for c in range(first, first + landing)]
    for offset in range(8):
        sim = Simulation(level)
        sim.player.x += offset
        if not any(solve(level, 20_000, action_repeat=REPEAT, weight=1.2, start=sim, goal=g).solved for g in goals):
            return False
    return True


def build(procs: int = 4) -> list:
    specs = list(itertools.product(TAKEOFF_WIDTHS, GAPS, DROPS, LANDING_WIDTHS))
    with Pool(procs) as workers:
        ok = workers.map(feasible, specs)
    return [dict(takeoff=t, gap=g, drop=d, landing=l) for (t, g, d, l), good in zip(specs, ok) if good]


def load_catalog() -> list:
    return json.loads(CATALOG_PATH.read_text())


def main() -> None:
    entries = build()
    CATALOG_PATH.write_text(json.dumps(entries, indent=0) + "\n")
    print(f"{len(entries)} feasible jumps -> {CATALOG_PATH}")
    by = {}
    for e in entries:
        by.setdefault((e["gap"], e["drop"]), 0)
        by[(e["gap"], e["drop"])] += 1
    print("gap \\ drop " + " ".join(f"{d:>3}" for d in DROPS))
    for g in GAPS:
        print(f"{g:>10} " + " ".join(f"{by.get((g, d), 0):>3}" for d in DROPS))


if __name__ == "__main__":
    main()
