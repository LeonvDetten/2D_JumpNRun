"""Phase 10 D: teacher demos on MIRRORED generator levels (v9, tiers 4-10, chest on the left) for the BC2 stream.

    nice python3 scripts/demos_spiegel10.py 400        # -> runs/demos_spiegel/demos.jsonl

Own seed space ("demo10m:", seeds 9_600_000+); solved by the solver with the distance map (7 actions).
"""

from __future__ import annotations

import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jumpnrun.levelgen import generator as G  # noqa: E402
from jumpnrun.levelgen.skills import mirror_level  # noqa: E402

OUT = ROOT / "runs/demos_spiegel"


def demo(i: int):
    from jumpnrun.levelgen.solver import solve_auto

    rng = random.Random(f"demo10m:{i}")
    lv = mirror_level(G.generate(rng.randint(4, 10), 9_600_000 + i), name=f"demo10m_{i}")
    r = solve_auto(lv, 60_000, action_repeat=2, weight=1.2, path=True)
    if not r.solved:
        return None
    actions = list(r.actions)
    return dict(tier=13, seed=i, repeat=2, actions=actions, mask=[1] * len(actions), won=True, solved=True,
                generator=G.GENERATOR_VERSION, kind="spiegel", a6=actions.count(6), level="\n".join(lv._lines) + "\n")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    OUT.mkdir(parents=True, exist_ok=True)
    done = a6 = 0
    with Pool(2) as p, open(OUT / "demos.jsonl", "a") as f:
        for d in p.imap_unordered(demo, range(n), chunksize=1):
            if d:
                f.write(json.dumps(d) + "\n")
                f.flush()
                done += 1
                a6 += d["a6"]
    print("demos:", done, "of", n, "| left+jump steps:", a6)


if __name__ == "__main__":
    main()
