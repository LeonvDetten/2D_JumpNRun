"""Phase 8 final evaluation of the model chosen by the fixed rule (autopilot8.finish).

    python3 -m jumpnrun.rl.final8 --checkpoint runs/phase8_r3_neu/checkpoints/ema_step_0053000000.zip

1. re-measure on the dev group with more attempts (exam 256, every other dev level 32)
2. test group H (32 per level, totals only)
3. ONCE: the sealed group - secret exam2 (128) + the 4 sealed hand-made levels (32 each). Only win counts.
Merge criterion (Leon, 02.10.): the lower 95 % Wilson bound of the pooled sealed success rate >= 50 %.
Result: runs/phase8/final.json (never overwritten: the sealed group is played only once).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from jumpnrun.core.level import Level
from jumpnrun.rl.evaluate import evaluate_levels
from jumpnrun.rl.milestones8 import ROOT, dev_levels, split, test_levels, wilson
from jumpnrun.rl.modelinfo import load_model

OUT = ROOT / "runs/phase8/final.json"


def wins(model, level, n):
    return int(sum(r["won"] for r in evaluate_levels(model, [level] * n, deterministic=False)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    if OUT.exists():
        print("final evaluation already done:", OUT.read_text())
        return
    torch.set_num_threads(4)
    np.random.seed(20261003)
    torch.manual_seed(20261003)
    model = load_model(ROOT / args.checkpoint)
    res = {"checkpoint": args.checkpoint, "dev": {}, "test": {}, "sealed": {}}
    for name, level, n in dev_levels():
        res["dev"][name] = {"won": wins(model, level, 256 if name == "pruefung" else 32),
                            "of": 256 if name == "pruefung" else 32}
    res["dev_mean"] = round(float(np.mean([v["won"] / v["of"] for v in res["dev"].values()])), 4)
    for name, level, _ in test_levels():
        res["test"][name] = {"won": wins(model, level, 32), "of": 32}
    sealed = [("exam2", Level.from_file(ROOT / "levels" / "exam2" / "level.txt"), 128)]
    sealed += [(n, Level.from_file(ROOT / "levels/handmade8" / f"{n}.txt"), 32) for n in split()["sealed"]]
    for name, level, n in sealed:
        res["sealed"][name] = {"won": wins(model, level, n), "of": n}
    won = sum(v["won"] for v in res["sealed"].values())
    of = sum(v["of"] for v in res["sealed"].values())
    lo, hi = wilson(won, of)
    res["sealed_total"] = {"won": won, "of": of, "rate": round(won / of, 4), "low95": round(lo, 4), "high95": round(hi, 4)}
    res["goal_met"] = lo >= 0.5
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
