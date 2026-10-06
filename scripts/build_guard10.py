"""Phase 10: guard levels (levels/handmade10) - long levels in the phase-8 style, to catch forgetting.

    python3 scripts/build_guard10.py        # -> levels/handmade10/g0..g7.txt + split.json (4 val, 4 test)

Each is two phase-8 generator levels (v9, tiers 11-12, own seed range 9_100_000+) after each other (~300 tiles, like
the exam), proven solvable by the solver. Val is used for monitoring and selection; test only gives sums.
They only count once runs/phase10/guard_valid.json says valid (val separates P8 from the known dip, R1 control
EMA 54M, by >= 8 Pp at 64 attempts per level) - scripts/calibrate_guard10.py.
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

OUT = ROOT / "levels/handmade10"
OFF = AugmentConfig(void=0, raise_rows=0, ceiling=0, air_start=0, enemies=0)


def candidate(i: int):
    from jumpnrun.levelgen.solver import solve_auto

    rng = random.Random(f"guard10:{i}")
    a = G.generate(rng.choice((11, 12)), 9_100_000 + 2 * i)
    b = G.generate(rng.choice((11, 12)), 9_100_001 + 2 * i)
    lv, tags = augment(a, rng, replace(OFF, concat=1.0), partner=b)
    if "concat" not in tags:
        return None
    lv.needs_path = False  # both parts lead to the right
    lv.waypoints = []
    r = solve_auto(lv, 150_000, action_repeat=2, weight=1.2, path=False)
    if not r.solved:
        return None
    return i, "\n".join(lv._lines) + "\n", list(r.actions)


def main_plus():
    """Phase 10 D: 8 more guard levels (g8..g15, candidates 20..39) as split key "val_plus" - only for the sharper
    guard measurement (scripts/guard_plus10.py); milestones10 keeps its 4 val levels for comparability."""

    with Pool(2) as p:
        found = [r for r in p.map(candidate, range(20, 40), chunksize=1) if r][:8]
    names = []
    for k, (i, text, actions) in enumerate(found):
        name = f"g{8 + k}"
        (OUT / f"{name}.txt").write_text(text)
        (OUT / f"{name}.loesung.json").write_text(json.dumps({"action_repeat": 2, "actions": actions}))
        names.append(name)
    split = json.loads((OUT / "split.json").read_text())
    split["val_plus"] = names
    (OUT / "split.json").write_text(json.dumps(split, indent=1))
    print("extra guard levels:", names)


def main():
    if sys.argv[1:] == ["plus"]:
        return main_plus()
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as p:
        found = [r for r in p.map(candidate, range(14), chunksize=1) if r][:8]
    OUT.mkdir(parents=True, exist_ok=True)
    names = []
    for k, (i, text, actions) in enumerate(found):
        name = f"g{k}"
        (OUT / f"{name}.txt").write_text(text)
        (OUT / f"{name}.loesung.json").write_text(json.dumps({"action_repeat": 2, "actions": actions}))
        names.append(name)
    rng = random.Random("guard10:split")
    rng.shuffle(names)
    (OUT / "split.json").write_text(json.dumps({"val": sorted(names[:4]), "test": sorted(names[4:8])}, indent=1))
    print("guard levels:", len(names))


if __name__ == "__main__":
    main()
