"""Phase 11: frozen probes for the new practice kind lange_sackgasse (levels/probes/v12_lange_sackgasse.json).

    python3 scripts/build_probes11.py [procs]

40 levels (13 d0, 13 d1, 14 d2), own seed space "probe11:" (training uses "skill10:" / SkillSource seeds), every
level proven solvable by the solver (distance map, 7 actions).
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jumpnrun.levelgen import generator as G  # noqa: E402
from jumpnrun.levelgen.skills import make_skill_level  # noqa: E402

KIND = "lange_sackgasse"
PLAN = {0: 13, 1: 13, 2: 14}
OUT = ROOT / "levels/probes/v12_lange_sackgasse.json"


def candidate(args):
    from jumpnrun.levelgen.solver import solve_auto

    d, i = args
    try:
        lv = make_skill_level(KIND, d, f"probe11:{KIND}:{d}:{i}")
    except RuntimeError:
        return None
    r = solve_auto(lv, 150_000, action_repeat=2, weight=1.2, path=True)
    if not r.solved:
        return None
    return dict(skill=f"{KIND}_d{d}", tier=13, name=f"probe11_{KIND}_d{d}_{i}", text="\n".join(lv._lines) + "\n",
                actions=list(r.actions))


def main():
    jobs = [(d, i) for d, n in PLAN.items() for i in range(n + 10)]
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 2) as p:
        found = [r for r in p.map(candidate, jobs, chunksize=1) if r]
    out = []
    for d, n in PLAN.items():
        got = [r for r in found if r["skill"] == f"{KIND}_d{d}"][:n]
        print(d, len(got), flush=True)
        out += got
    OUT.write_text(json.dumps({"generator": G.GENERATOR_VERSION, "levels": out}))


if __name__ == "__main__":
    main()
