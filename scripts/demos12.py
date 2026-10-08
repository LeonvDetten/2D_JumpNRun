"""Phase 12: solver demos on generator v11 levels (BC start and BC2 stream).

    OMP_NUM_THREADS=1 nice python3 scripts/demos12.py 1500 [procs]     # -> runs/demos12/demos.jsonl

Own seed space "demo12:" (training "hard12:", probes "probe12:"); families spruenge / strukturen / gemischt (40/40/20),
solved leg-wise along the distance-map way (7 actions). The stored level text holds the level; enemies keep the
level default direction (enemy_dir 1).
"""

from __future__ import annotations

import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "runs/demos12"


def demo(i: int):
    from jumpnrun.levelgen.hard import make_hard_level
    from jumpnrun.levelgen.solver import solve_path_legs

    rng = random.Random(f"demo12:{i}")
    fam = rng.choices(("spruenge", "strukturen", "gemischt"), weights=(0.4, 0.4, 0.2))[0]
    try:
        lv = make_hard_level(fam, f"demo12:{fam}:{i}")
    except RuntimeError:
        return None
    r = solve_path_legs(lv, action_repeat=2, leg_budget=30_000, total_budget=250_000)
    if not r.solved:
        return None
    actions = list(r.actions)
    return dict(tier=14, seed=i, repeat=2, actions=actions, mask=[1] * len(actions), won=True, solved=True,
                generator="v11", kind="hart", family=fam, enemy_dir=1, a6=actions.count(6),
                level="\n".join(lv._lines) + "\n")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    procs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    OUT.mkdir(parents=True, exist_ok=True)
    have = set()
    if (OUT / "demos.jsonl").exists():  # resumable
        have = {json.loads(l)["seed"] for l in (OUT / "demos.jsonl").read_text().splitlines() if l.strip()}
    todo = [i for i in range(int(n * 1.5)) if i not in have]
    done = len(have)
    with Pool(procs) as p, open(OUT / "demos.jsonl", "a") as f:
        for d in p.imap_unordered(demo, todo, chunksize=1):
            if d:
                f.write(json.dumps(d) + "\n")
                f.flush()
                done += 1
                if done >= n:
                    p.terminate()
                    break
    print("demos:", done)


if __name__ == "__main__":
    main()
