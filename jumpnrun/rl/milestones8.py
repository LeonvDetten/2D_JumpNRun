"""Phase 8 milestone evaluation with an honest measurement protocol.

    OMP_NUM_THREADS=1 python3 -m jumpnrun.rl.milestones8 --run runs/phase8_r1_neu --run runs/phase8_r1_kontrolle

Groups (levels/handmade8/split.json):
    dev      exam (original), test series (6), handmade8 dev (4)   failure analysis + model selection allowed
    test     handmade8 test (4)                                    only total wins, no analysis
    sealed   exam2 + handmade8 sealed (4)                          NEVER here: only once at the end (final8.py)
    schutz   frozen validation v3 + v4 (80 generated levels)       alarm against forgetting
    proben   capability probes levels/probes/v9.json               deterministic, one attempt per level

Main value: dev_mean = mean success rate over the 11 dev levels (each level counts the same), with a 95 %
interval from the per-level rates. EMA checkpoints get the full measurement; raw and ema2 checkpoints only
the dev group (that is all the judging rule needs and keeps the evaluator in step with two runs).
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from jumpnrun.core.level import Level
from jumpnrun.rl.evaluate import evaluate_levels
from jumpnrun.rl.milestones import EXAMS, frozen_levels
from jumpnrun.rl.modelinfo import load_model

ROOT = Path(__file__).resolve().parent.parent.parent
SPLIT = ROOT / "levels/handmade8/split.json"
PROBES = ROOT / "levels/probes/v9.json"
EXAM_ATTEMPTS = 64
LEVEL_ATTEMPTS = 16


def wilson(won: int, n: int, z: float = 1.96):
    """95 % Wilson interval for a success rate."""

    if n == 0:
        return 0.0, 1.0
    p = won / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def split():
    return json.loads(SPLIT.read_text())


def dev_levels():
    """[(name, Level, attempts)] of the dev group."""

    items = [("pruefung", Level.from_file(ROOT / EXAMS["original"]), EXAM_ATTEMPTS)]
    items += [(f"serie_{p.stem}", Level.from_file(p), LEVEL_ATTEMPTS)
              for p in sorted((ROOT / "levels/test_serie").glob("*.txt"))]
    items += [(f"hand_{n}", Level.from_file(ROOT / "levels/handmade8" / f"{n}.txt"), LEVEL_ATTEMPTS)
              for n in split()["dev"]]
    return items


def test_levels():
    return [(f"hand_{n}", Level.from_file(ROOT / "levels/handmade8" / f"{n}.txt"), LEVEL_ATTEMPTS)
            for n in split()["test"]]


def probe_levels():
    data = json.loads(PROBES.read_text())["levels"]
    out = []
    for item in data:
        lv = Level.from_text(item["text"], name=item["name"])
        if item.get("enemy_directions"):
            lv.enemy_directions = item["enemy_directions"]
            lv.enemy_wakes = item["enemy_wakes"]
        out.append((item["skill"], lv))
    return out


def play_group(model, items):
    levels, names = [], []
    for name, level, n in items:
        levels += [level] * n
        names += [name] * n
    results = evaluate_levels(model, levels, deterministic=False)
    out = {}
    for name, r in zip(names, results):
        o = out.setdefault(name, {"won": 0, "of": 0})
        o["won"] += int(r["won"])
        o["of"] += 1
    return out


def dev_mean(result: dict):
    """(mean, low, high): mean per-level success rate of the dev group, 95 % interval over levels."""

    rates = [v["won"] / v["of"] for v in result["dev"].values()]
    m = float(np.mean(rates))
    se = float(np.std(rates, ddof=1) / math.sqrt(len(rates))) if len(rates) > 1 else 0.0
    return m, max(0.0, m - 1.96 * se), min(1.0, m + 1.96 * se)


def evaluate_checkpoint(path: Path, full: bool) -> dict:
    model = load_model(path)
    out = {"dev": play_group(model, dev_levels())}
    if full:
        out["test"] = {"won": sum(v["won"] for v in play_group(model, test_levels()).values()),
                       "of": len(split()["test"]) * LEVEL_ATTEMPTS}
        schutz = 0
        total = 0
        for name in ("v3", "v4"):
            lv = frozen_levels(name)
            schutz += sum(r["won"] for r in evaluate_levels(model, [l for _, l in lv]))
            total += len(lv)
        out["schutz"] = {"won": schutz, "of": total}
        probes = probe_levels()
        res = evaluate_levels(model, [lv for _, lv in probes])
        per = {}
        for (skill, _), r in zip(probes, res):
            o = per.setdefault(skill, {"won": 0, "of": 0})
            o["won"] += int(r["won"])
            o["of"] += 1
        out["proben"] = per
    m, lo, hi = dev_mean(out)
    out["dev_mean"] = [round(m, 4), round(lo, 4), round(hi, 4)]
    return out


def pending(run: Path, done: dict, every: int):
    """(steps, kind, checkpoint) still to evaluate: first raw checkpoint per block, plus ema/ema2 copies."""

    cdir = run / "checkpoints"
    todo = []
    raws = sorted(cdir.glob("step_*.zip"))[:-1]  # the newest may still be written
    seen = set()
    for c in raws:
        steps = int(c.stem[5:])
        block = steps // every
        if block in seen:
            continue
        seen.add(block)
        if f"{steps}:raw" not in done and not any(k.endswith(":raw") and int(k.split(":")[0]) // every == block
                                                  for k in done):
            todo.append((steps, "raw", c))
    for prefix in ("ema", "ema2"):
        for c in sorted(cdir.glob(f"{prefix}_step_*.zip")):
            steps = int(c.stem[len(prefix) + 6:])
            if f"{steps}:{prefix}" not in done:
                todo.append((steps, prefix, c))
    return todo


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 8 milestone evaluation.")
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--every", type=int, default=1_000_000)
    parser.add_argument("--seconds", type=float, default=520)
    args = parser.parse_args()
    torch.set_num_threads(1)
    start = time.time()
    while time.time() - start < args.seconds:
        jobs = []
        for r in args.run:
            run = Path(r)
            path = run / "milestones8.json"
            done = json.loads(path.read_text()) if path.exists() else {}
            for steps, kind, ckpt in pending(run, done, args.every):
                # EMA first (the judging rule needs it), then older before newer
                jobs.append(((0 if kind == "ema" else 1), steps, run, kind, ckpt))
        if not jobs:
            time.sleep(15)
            continue
        _, steps, run, kind, ckpt = min(jobs, key=lambda j: (j[0], j[1]))
        t0 = time.time()
        result = evaluate_checkpoint(ckpt, full=(kind == "ema"))
        result["seconds"] = round(time.time() - t0)
        result["checkpoint"] = ckpt.name
        path = run / "milestones8.json"
        done = json.loads(path.read_text()) if path.exists() else {}
        done[f"{steps}:{kind}"] = result
        path.write_text(json.dumps(done, indent=1))
        extra = ""
        if kind == "ema":
            extra = (f", test {result['test']['won']}/{result['test']['of']}, schutz {result['schutz']['won']}/"
                     f"{result['schutz']['of']}, proben " + " ".join(f"{k[:6]} {v['won']}/{v['of']}"
                                                                    for k, v in result["proben"].items()))
        d = result["dev"]
        print(f"{run.name} {steps:,} {kind}: dev {result['dev_mean'][0]:.1%} "
              f"[{result['dev_mean'][1]:.0%}-{result['dev_mean'][2]:.0%}], pruefung {d['pruefung']['won']}/"
              f"{d['pruefung']['of']}{extra} [{result['seconds']}s]", flush=True)


if __name__ == "__main__":
    main()
