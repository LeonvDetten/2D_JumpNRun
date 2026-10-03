"""Phase 9 final evaluation of the model chosen by the fixed rule (autopilot9.finish).

    python3 -m jumpnrun.rl.final9 --checkpoint runs/phase9_r3_neu/checkpoints/ema_step_0068000000.zip

1. re-measure on the dev group with more attempts (exam 256, every other dev level 32)
2. test group H (32 per level, totals only)
3. ONCE: the sealed group - secret exam2 (128) + 4 sealed handmade8 + 4 sealed handmade9 levels (32 each),
   and for comparison the phase-8 final model on the 4 sealed handmade9 levels. Only win counts.
Merge criterion (Leon, 03.10.): on the new sealed levels at least +15 points over phase8_final with
non-overlapping 95 % Wilson intervals, AND on the phase-8 sealed group (exam2 + handmade8) still a lower bound
>= 50 %. Result: runs/phase9/final.json (never overwritten: the sealed group is played only once).
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import torch

from jumpnrun.core.level import Level
from jumpnrun.rl.evaluate import evaluate_levels
from jumpnrun.rl.milestones8 import split as split8
from jumpnrun.rl.milestones9 import ROOT, dev_levels, split9, test_levels, wilson
from jumpnrun.rl.modelinfo import load_model

OUT = ROOT / "runs/phase9/final.json"
PHASE8 = ROOT / "models/phase8_final.zip"


def wins(model, level, n):
    return int(sum(r["won"] for r in evaluate_levels(model, [level] * n, deterministic=False)))


def total(group: dict) -> dict:
    won = sum(v["won"] for v in group.values())
    of = sum(v["of"] for v in group.values())
    lo, hi = wilson(won, of)
    return {"won": won, "of": of, "rate": round(won / of, 4), "low95": round(lo, 4), "high95": round(hi, 4)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    if OUT.exists():
        print("final evaluation already done:", OUT.read_text())
        return
    torch.set_num_threads(4)
    np.random.seed(20261004)
    torch.manual_seed(20261004)
    model = load_model(ROOT / args.checkpoint)
    res = {"checkpoint": args.checkpoint, "dev": {}, "test": {}, "sealed8": {}, "sealed9_detail": {}}
    for name, level, _ in dev_levels():
        n = 256 if name == "pruefung" else 32
        res["dev"][name] = {"won": wins(model, level, n), "of": n}
    res["dev_mean"] = round(float(np.mean([v["won"] / v["of"] for v in res["dev"].values()])), 4)
    for name, level, _ in test_levels():
        res["test"][name] = {"won": wins(model, level, 32), "of": 32}
    sealed8 = [("exam2", Level.from_file(ROOT / "levels" / "exam2" / "level.txt"), 128)]
    sealed8 += [(n, Level.from_file(ROOT / "levels/handmade8" / f"{n}.txt"), 32) for n in split8()["sealed"]]
    for name, level, n in sealed8:
        res["sealed8"][name] = {"won": wins(model, level, n), "of": n}
    res["sealed8_total"] = total(res["sealed8"])
    sealed9 = [(n, Level.from_file(ROOT / "levels/handmade9" / f"{n}.txt")) for n in split9()["sealed"]]
    old = load_model(PHASE8)
    new9, old9 = {}, {}
    for name, level in sealed9:
        new9[name] = {"won": wins(model, level, 32), "of": 32}
        old9[name] = {"won": wins(old, level, 32), "of": 32}
    res["sealed9_detail"] = {"neu": new9, "phase8": old9}
    res["sealed9"] = total(new9)
    res["sealed9_phase8"] = total(old9)
    gain = res["sealed9"]["rate"] - res["sealed9_phase8"]["rate"]
    res["sealed9_gain"] = round(gain, 4)
    res["merge"] = bool(gain >= 0.15 and res["sealed9"]["low95"] > res["sealed9_phase8"]["high95"]
                        and res["sealed8_total"]["low95"] >= 0.5)
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k not in ("sealed8", "sealed9_detail")}, indent=1))


if __name__ == "__main__":
    main()
