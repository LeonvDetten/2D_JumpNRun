"""Phase 13: left demos for the BC2 stream -> runs/demos13/demos.jsonl

    OMP_NUM_THREADS=1 python3 scripts/demos13.py [fresh] [procs]

1. The solver demos of the hard v11 levels (runs/demos12) MIRRORED: level text mirrored, actions left <-> right
   (left 1 <-> right 2, left+jump 6 <-> right+jump 4), enemies start walking left (enemy_dir -1). Kept only if the
   mirrored run wins when replayed on a fresh simulation.
2. `fresh` (default 300) new solver demos on links_trittsteine levels (jumpnrun.levelgen.links, own seeds).
"""

from __future__ import annotations

import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "runs/demos13"
SWAP = {1: 2, 2: 1, 4: 6, 6: 4}


def mirrored(d: dict):
    from jumpnrun.core.level import Level
    from jumpnrun.core.sim import Status
    from jumpnrun.levelgen.skills import mirror_level
    from jumpnrun.levelgen.solver import replay

    level = mirror_level(Level.from_text(d["level"], name="m"))
    if level.enemy_spawns:
        level.enemy_directions = [-1] * len(level.enemy_spawns)
    actions = [SWAP.get(a, a) for a in d["actions"]]
    sim = replay(level, actions, action_repeat=d.get("repeat", 2))
    if sim.status != Status.WON:
        return None
    return dict(tier=14, seed=d["seed"], repeat=d.get("repeat", 2), actions=actions, mask=[1] * len(actions),
                won=True, solved=True, generator="v11", kind="links", family=f"links_{d.get('family', 'x')}",
                enemy_dir=-1, a6=actions.count(6), level="\n".join(level._lines) + "\n")


def fresh(i: int):
    from jumpnrun.levelgen import generator as G
    from jumpnrun.levelgen.skills import mirror_level
    from jumpnrun.levelgen.solver import solve_path_legs

    rng = random.Random(f"demos13:{i}")
    tier = rng.randint(8, 12)
    level = mirror_level(G.generate(tier, 90_000_000 + i, "pruefung"), name=f"demos13_{i}")
    r = solve_path_legs(level, action_repeat=2, leg_budget=20_000, total_budget=120_000)
    if not r.solved:
        return None
    actions = list(r.actions)
    return dict(tier=tier, seed=90_000_000 + i, repeat=2, actions=actions, mask=[1] * len(actions), won=True,
                solved=True, generator="v9-pruefung", kind="links", family="links_trittsteine", enemy_dir=1,
                a6=actions.count(6), level="\n".join(level._lines) + "\n")


def main():
    n_fresh = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    procs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    OUT.mkdir(parents=True, exist_ok=True)
    src = [json.loads(l) for l in (ROOT / "runs/demos12/demos.jsonl").read_text().splitlines() if l.strip()]
    stats = {"gespiegelt": 0, "gespiegelt_von": len(src), "frisch": 0, "frisch_von": n_fresh, "a6": 0}
    with Pool(procs) as pool, open(OUT / "demos.jsonl", "w") as f:
        for d in pool.imap_unordered(mirrored, src, chunksize=4):
            if d:
                f.write(json.dumps(d) + "\n")
                stats["gespiegelt"] += 1
                stats["a6"] += d["a6"]
        f.flush()
        for d in pool.imap_unordered(fresh, range(n_fresh), chunksize=1):
            if d:
                f.write(json.dumps(d) + "\n")
                f.flush()
                stats["frisch"] += 1
                stats["a6"] += d["a6"]
    (OUT / "stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
