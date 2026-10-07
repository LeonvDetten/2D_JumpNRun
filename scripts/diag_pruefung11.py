"""Phase 11: where do the exam attempts end? (exam = levels/exam/level.txt, evaluation only, never trained on)

    OMP_NUM_THREADS=1 nice python3 scripts/diag_pruefung11.py tag=path ...   # -> runs/phase11/diag_pruefung.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
N = 48


def work(args):
    import numpy as np
    import torch

    from jumpnrun.core.level import Level
    from jumpnrun.rl.evaluate import evaluate_levels
    from jumpnrun.rl.modelinfo import load_model

    tag, path = args
    torch.set_num_threads(1)
    np.random.seed(0)
    torch.manual_seed(0)
    lv = Level.from_file(ROOT / "levels/exam/level.txt")
    res = evaluate_levels(load_model(ROOT / path), [lv] * N, deterministic=False)
    ends = Counter()
    for r in res:
        if not r["won"]:
            ends[(r["outcome"], int(r.get("progress", 0) * 10) * 10)] += 1
    return tag, sum(r["won"] for r in res), sorted(((o, p, n) for (o, p), n in ends.items()), key=lambda t: t[1])


def main():
    models = dict(a.split("=") for a in sys.argv[1:])
    out = {}
    with Pool(min(4, len(models))) as p:
        for tag, won, ends in p.imap_unordered(work, list(models.items())):
            out[tag] = {"won": won, "of": N, "enden": ends}
            print(tag, f"{won}/{N}", ends, flush=True)
    (ROOT / "runs/phase11/diag_pruefung.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
