"""Phase 10: teacher demos on the practice levels (second BC stream, "BC2"), with left+jump.

    nice -n 19 python3 scripts/demos_phase10.py 2500        # -> runs/demos10/demos.jsonl + holdout.jsonl

Levels come from jumpnrun.levelgen.skills (all seven kinds, difficulties d0-d2) in the own seed space "demo10:";
each is solved by the solver guided by the distance map (7 actions). Every tenth demo goes to holdout.jsonl (not
read by the BC2 stream, which only globs demos*.jsonl) so the imitation accuracy can be measured on unseen levels.
Runs only in the 4-core window between rounds A and B, never next to training.
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jumpnrun.levelgen import generator as G  # noqa: E402
from jumpnrun.levelgen.skills import KINDS, make_skill_level  # noqa: E402

OUT = ROOT / "runs/demos10"
DIFFICULTY = (0, 1, 1, 2, 2, 2)  # more of the full levels: there the skill sits behind normal segments


def demo(i: int):
    from jumpnrun.levelgen.solver import solve_auto

    kind = KINDS[i % len(KINDS)]
    d = DIFFICULTY[(i // len(KINDS)) % len(DIFFICULTY)]
    try:
        lv = make_skill_level(kind, d, f"demo10:{kind}:{d}:{i}")
    except RuntimeError:
        return None
    r = solve_auto(lv, 100_000, action_repeat=2, weight=1.2, path=True)
    if not r.solved:
        return None
    actions = list(r.actions)
    return dict(tier=13, seed=i, repeat=2, actions=actions, mask=[1] * len(actions), won=True, solved=True,
                generator=G.GENERATOR_VERSION, kind=kind, difficulty=d, a6=actions.count(6),
                level="\n".join(lv._lines) + "\n")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2500
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    OUT.mkdir(parents=True, exist_ok=True)
    done = a6 = 0
    with Pool(4) as p, open(OUT / "demos.jsonl", "a") as f, open(OUT / "holdout.jsonl", "a") as h:
        for d in p.imap_unordered(demo, range(start, n), chunksize=1):
            if d:
                (h if d["seed"] % 10 == 9 else f).write(json.dumps(d) + "\n")
                f.flush()
                h.flush()
                done += 1
                a6 += d["a6"] * (d["seed"] % 10 != 9)
    print("demos:", done, "of", n, "| left+jump steps in training demos:", a6)


if __name__ == "__main__":
    main()
