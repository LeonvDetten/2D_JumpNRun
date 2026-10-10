"""Phase 12: the sealed test - ONCE, paired, for the best candidate of every line (Leon's release 10.10.:
runs/phase12/FINAL_FREIGABE).

    OMP_NUM_THREADS=1 python3 scripts/versiegelt12.py      # -> runs/phase12/versiegelt.json (never overwritten)

Groups (as in final8 / final9): secret exam2 (128 attempts) + the 4 sealed handmade8 levels + the 4 sealed
handmade9 levels (32 attempts each), sampled actions (the scorecard rule), seeded after loading the model.
Only group sums are stored and printed - no per-level result, the levels themselves are never looked at here.
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "runs/phase12/versiegelt.json"
FREIGABE = ROOT / "runs/phase12/FINAL_FREIGABE"
MODELS = {"p8": "models/phase8_final.zip", "phase11": "models/phase11_kandidat.zip",
          "neustart": "models/neustart_kandidat_pruefung.zip", "phase12": "models/phase12_kandidat.zip"}
SEED = 20261010


def job(tag: str) -> tuple:
    import numpy as np
    import torch

    from jumpnrun.core.level import Level
    from jumpnrun.rl.evaluate import evaluate_levels
    from jumpnrun.rl.milestones8 import split as split8
    from jumpnrun.rl.milestones9 import split9, wilson
    from jumpnrun.rl.modelinfo import load_model

    torch.set_num_threads(1)
    model = load_model(ROOT / MODELS[tag])
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    def play(levels, n):
        won = 0
        for level in levels:
            won += int(sum(r["won"] for r in evaluate_levels(model, [level] * n, deterministic=False)))
        of = n * len(levels)
        lo, hi = wilson(won, of)
        return {"won": won, "of": of, "rate": round(won / of, 4), "low95": round(lo, 4), "high95": round(hi, 4)}

    groups = {
        "exam2": play([Level.from_file(ROOT / "levels" / "exam2" / "level.txt")], 128),
        "handmade8_versiegelt": play([Level.from_file(ROOT / "levels/handmade8" / f"{n}.txt")
                                     for n in split8()["sealed"]], 32),
        "handmade9_versiegelt": play([Level.from_file(ROOT / "levels/handmade9" / f"{n}.txt")
                                     for n in split9()["sealed"]], 32),
    }
    won = sum(g["won"] for g in groups.values())
    of = sum(g["of"] for g in groups.values())
    lo, hi = wilson(won, of)
    groups["gesamt"] = {"won": won, "of": of, "rate": round(won / of, 4), "low95": round(lo, 4), "high95": round(hi, 4)}
    return tag, groups


def main() -> None:
    if OUT.exists():
        print("sealed test already done:", OUT.read_text())
        return
    if not FREIGABE.exists():
        print("no release (runs/phase12/FINAL_FREIGABE) - the sealed test is not played")
        return
    res = {"freigabe": FREIGABE.read_text().strip(), "seed": SEED, "modelle": MODELS, "ergebnisse": {}}
    with Pool(4) as pool:
        for tag, groups in pool.imap_unordered(job, list(MODELS)):
            res["ergebnisse"][tag] = groups
            print(tag, json.dumps(groups), flush=True)
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
