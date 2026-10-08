"""Phase 12: frozen probes of generator v11 (levels/probes/v13_hard.json).

    OMP_NUM_THREADS=1 python3 scripts/build_probes12.py [procs]

Per family 24 levels (lang: 12), own seed space "probe12:", every level proven by the solver (leg-wise along the
distance-map way, 7 actions). Training uses "hard12:", demos "demo12:" - never shared.
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PLAN = {"spruenge": 24, "strukturen": 24, "gemischt": 24, "lang": 12}
OUT = ROOT / "levels/probes/v13_hard.json"


def candidate(args):
    from jumpnrun.levelgen.hard import make_hard_level
    from jumpnrun.levelgen.solver import solve_path_legs

    fam, i = args
    try:
        lv = make_hard_level(fam, f"probe12:{fam}:{i}")
    except RuntimeError:
        return None
    r = solve_path_legs(lv, action_repeat=2, leg_budget=30_000, total_budget=600_000 if fam == "lang" else 250_000)
    if not r.solved:
        return {"skill": fam, "solved": False}
    return dict(skill=fam, tier=14, name=f"probe12_{fam}_{i}", text="\n".join(lv._lines) + "\n",
                blocks=lv.blocks, actions=list(r.actions), solved=True)


def main():
    jobs = [(f, i) for f, n in PLAN.items() for i in range(int(n * 1.6))]
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as p:
        found = [r for r in p.map(candidate, jobs, chunksize=1) if r]
    out, stats = [], {}
    for f, n in PLAN.items():
        tried = [r for r in found if r["skill"] == f]
        got = [r for r in tried if r["solved"]][:n]
        stats[f] = {"versucht": len(tried), "geloest": sum(r["solved"] for r in tried), "genommen": len(got)}
        print(f, stats[f], flush=True)
        out += got
    OUT.write_text(json.dumps({"generator": "v11", "stats": stats, "levels": out}))


if __name__ == "__main__":
    main()
