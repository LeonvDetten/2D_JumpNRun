"""Phase 10 D: sharper guard measurement - 12 val levels (val + val_plus of levels/handmade10), 64 attempts each.

    OMP_NUM_THREADS=1 nice taskset -c 2,3 python3 scripts/guard_plus10.py p8=models/phase8_final.zip ...
    -> runs/phase10/guard_plus.json (merged per tag)

Same seeds for every model (paired). milestones10 keeps its 4-level guard for comparability with earlier runs.
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
N = 64
OUT = ROOT / "runs/phase10/guard_plus.json"


def work(args):
    import numpy as np
    import torch

    from jumpnrun.core.level import Level
    from jumpnrun.rl.evaluate import evaluate_levels
    from jumpnrun.rl.modelinfo import load_model

    tag, path, name = args
    torch.set_num_threads(1)
    np.random.seed(0)
    torch.manual_seed(0)
    lv = Level.from_file(ROOT / "levels/handmade10" / f"{name}.txt")
    res = evaluate_levels(load_model(ROOT / path), [lv] * N, deterministic=False)
    return tag, name, sum(int(r["won"]) for r in res)


def main():
    split = json.loads((ROOT / "levels/handmade10/split.json").read_text())
    names = split["val"] + split["val_plus"]
    models = dict(a.split("=") for a in sys.argv[1:])
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    with Pool(2) as p:
        for tag, name, won in p.imap_unordered(work, [(t, m, n) for t, m in models.items() for n in names]):
            o = out.setdefault(tag, {"modell": models[tag], "je_level": {}})
            o["je_level"][name] = won
            print(tag, name, won, "/", N, flush=True)
    for tag in models:
        o = out[tag]
        won = sum(o["je_level"].values())
        o["summe"] = f"{won}/{N * len(names)}"
        o["rate"] = round(won / (N * len(names)), 4)
    OUT.write_text(json.dumps(out, indent=1))
    for tag in models:
        print(tag, out[tag]["summe"], out[tag]["rate"])


if __name__ == "__main__":
    main()
