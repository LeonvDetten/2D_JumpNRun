"""Phase 8: frozen capability probes (levels/probes/v9.json).

    python3 scripts/build_probes8.py

Per skill 20 generated levels (generator v9, tiers 10-12) with exactly the situation of that skill, each
proven solvable by the solver. Measured deterministically at every milestone; they vary less than the exam and
never use it up. Skills: chest before a void, stones in the top rows, enemies coming down a staircase, bait
fork, ceiling, start in the air, enemies walking towards the player.
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jumpnrun.levelgen.augment import AugmentConfig, augment  # noqa: E402
from jumpnrun.levelgen.generator import GENERATOR_VERSION, generate  # noqa: E402

OFF = AugmentConfig(void=0, raise_rows=0, ceiling=0, air_start=0, enemies=0)
SKILLS = {
    "truhe_abgrund": (replace(OFF, void=1), None),
    "hohe_steine": (replace(OFF, raise_rows=1), ("chain", "stones")),
    "gegner_treppe": (OFF, ("enemy_ramp",)),
    "koeder": (OFF, ("bait_fork",)),
    "decke": (replace(OFF, ceiling=1), None),
    "luftstart": (replace(OFF, air_start=1), None),
    "gegner_entgegen": (replace(OFF, enemies=1), None),
}
PER_SKILL = 20
OUT = ROOT / "levels/probes/v9.json"


def candidate(args):
    from jumpnrun.levelgen.solver import solve_auto

    skill, i = args
    cfg, blocks = SKILLS[skill]
    tier = 10 + i % 3
    level = generate(tier, 880000 + 1000 * list(SKILLS).index(skill) + i)
    if blocks and not any(level.building_blocks.get(b) for b in blocks):
        return None
    lv, tags = augment(level, random.Random(i), cfg)
    if cfg != OFF and not tags:
        return None
    if not solve_auto(lv, 80_000, action_repeat=2, weight=1.2).solved:
        return None
    return dict(skill=skill, tier=tier, name=lv.name, text=lv.to_text(),
                enemy_directions=getattr(lv, "enemy_directions", None), enemy_wakes=getattr(lv, "enemy_wakes", None))


def main():
    jobs = [(s, i) for s in SKILLS for i in range(70)]
    with Pool(4) as p:
        found = [r for r in p.map(candidate, jobs, chunksize=1) if r]
    out = []
    for s in SKILLS:
        got = [r for r in found if r["skill"] == s][:PER_SKILL]
        print(s, len(got))
        out += got
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generator": GENERATOR_VERSION, "levels": out}))


if __name__ == "__main__":
    main()
