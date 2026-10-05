"""Phase 10: frozen practice probes (levels/probes/v11_skills.json) - 40 per kind, difficulty d2.

    python3 scripts/build_probes10.py

Own seed space "probe10:" (training uses "skill10:", demos "demo10:"); every level is proven solvable by the solver
(distance map, 7 actions). Only reported (the practice goal), never part of the F value: same generator family as the
training levels.
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

PER_KIND = 40
OUT = ROOT / "levels/probes/v11_skills.json"


def candidate(args):
    from jumpnrun.levelgen.solver import solve_auto

    kind, i = args
    try:
        lv = make_skill_level(kind, 2, f"probe10:{kind}:{i}")
    except RuntimeError:
        return None
    r = solve_auto(lv, 100_000, action_repeat=2, weight=1.2, path=True)
    if not r.solved:
        return None
    return dict(skill=kind, tier=13, name=f"probe10_{kind}_{i}", text="\n".join(lv._lines) + "\n",
                actions=list(r.actions))


def main():
    jobs = [(k, i) for k in KINDS for i in range(PER_KIND + 20)]
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as p:
        found = [r for r in p.map(candidate, jobs, chunksize=1) if r]
    out = []
    for k in KINDS:
        got = [r for r in found if r["skill"] == k][:PER_KIND]
        print(k, len(got), flush=True)
        out += got
    OUT.write_text(json.dumps({"generator": G.GENERATOR_VERSION, "levels": out}))


if __name__ == "__main__":
    main()
