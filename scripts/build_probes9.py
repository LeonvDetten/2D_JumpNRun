"""Phase 9: frozen capability probes (levels/probes/v10.json) - the 7 probes of phase 8 plus 6 new skills.

    python3 scripts/build_probes9.py

New skills, 20 short levels each (two random tier-10 segments, the skill, two more segments, the chest), every
level proven solvable by the solver (distance map, 7 actions):
    umkehren      repaired fork where turning back is needed (upper road without gaps, or the floor ends)
    kanal         a channel: right, stairs up, left, stairs up, out at the top right
    truhe_links   a mirrored level: the chest on the left
    mario         pipes, block pyramids, a brick bridge or an enemy group
    lang          two levels after each other (about 300 tiles)
    gegner_dicht  1.5-2x the enemies
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

from jumpnrun.levelgen import generator as G  # noqa: E402
from jumpnrun.levelgen.augment import AugmentConfig, augment  # noqa: E402

OFF = AugmentConfig(void=0, raise_rows=0, ceiling=0, air_start=0, enemies=0)
SKILLS = ("umkehren", "kanal", "truhe_links", "mario", "lang", "gegner_dicht")
PER_SKILL = 20
OUT = ROOT / "levels/probes/v10.json"
OLD = ROOT / "levels/probes/v9.json"


def short_level(rng: random.Random, block, name: str):
    from jumpnrun.core.level import Level

    cfg = G.TIERS[10]
    b = G._Builder(rng)
    b.variant = "v9"
    b.style = G._style(rng, cfg)
    b.flat(5)
    b.columns[1][b.surface - 1] = "P"
    for _ in range(2):
        G._segment(b, cfg)
    if block is not None:
        if b.surface != G.GROUND:
            b.drop(G.GROUND - b.surface)
            b.flat(3)
        block(b, cfg)
    for _ in range(2):
        G._segment(b, cfg)
    b.flat(4)
    b.columns[-2][b.surface - 1] = "C"
    b.column(b.surface - 3)
    lines = ["".join(col[r] for col in b.columns).rstrip() for r in range(G.ROWS)]
    lv = Level(lines, name=name)
    lv.needs_path = True
    return lv


def candidate(args):
    from jumpnrun.levelgen.solver import solve_auto

    skill, i = args
    rng = random.Random(f"probe9:{skill}:{i}")
    name = f"probe9_{skill}_{i}"
    if skill == "umkehren":
        lv = short_level(rng, lambda b, c: G._fork_v10(b, c, rng.choice(("umkehren", "oben"))), name)
    elif skill == "kanal":
        lv = short_level(rng, lambda b, c: G._channel(b, replace(c, free_enemies=0.3)), name)
    elif skill == "mario":
        block = rng.choice((G._pipes, G._pyramid, G._bridge))
        lv = short_level(rng, block, name)
    elif skill == "truhe_links":
        lv, _ = augment(short_level(rng, None, name), rng, replace(OFF, mirror=1.0))
    elif skill == "lang":
        a, b = G.generate(8, 7700 + i), G.generate(8, 7800 + i)
        lv, _ = augment(a, rng, replace(OFF, concat=1.0), partner=b)
        lv.needs_path = False  # both parts lead to the right: the leg-by-leg search is faster
        lv.waypoints = []
    else:
        lv, tags = augment(short_level(rng, None, name), rng, replace(OFF, density=1.0))
        if "density" not in tags:
            return None
    r = solve_auto(lv, 100_000, action_repeat=2, weight=1.2, path=lv.needs_path)
    if not r.solved:
        return None
    return dict(skill=skill, tier=10, name=name, text="\n".join(lv._lines) + "\n",
                enemy_directions=getattr(lv, "enemy_directions", None), enemy_wakes=getattr(lv, "enemy_wakes", None))


def main():
    jobs = [(s, i) for s in SKILLS for i in range(32)]
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as p:
        found = [r for r in p.map(candidate, jobs, chunksize=1) if r]
    old = json.loads(OLD.read_text())["levels"]
    out = list(old)
    for s in SKILLS:
        got = [r for r in found if r["skill"] == s][:PER_SKILL]
        print(s, len(got), flush=True)
        out += got
    OUT.write_text(json.dumps({"generator": G.GENERATOR_VERSION, "levels": out}))


if __name__ == "__main__":
    main()
