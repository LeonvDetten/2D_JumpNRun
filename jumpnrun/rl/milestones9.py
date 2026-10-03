"""Phase 9 milestone evaluation: the phase-8 protocol plus the new hand-made levels and probes.

    OMP_NUM_THREADS=1 python3 -m jumpnrun.rl.milestones9 --run runs/phase9_r1_neu --run runs/phase9_r1_kontrolle
    python3 -m jumpnrun.rl.milestones9 --once models/phase8_final.zip       # one checkpoint (baseline)

Groups (levels/handmade8/split.json + levels/handmade9/split.json):
    dev      exam, test series (6), handmade8 dev (4)  = "alt"   failure analysis + model selection allowed
             handmade9 dev (4)                          = "neu"
    test     handmade8 test (4) + handmade9 test (4)             only total wins, no analysis
    sealed   exam2 + handmade8 sealed + handmade9 sealed         NEVER here: only once at the end (final9.py)
    schutz   frozen validation v3 + v4 (80 generated levels)     alarm against forgetting
    proben   levels/probes/v10.json (7 old + 6 new skills)       one attempt per level

dev_mean over all 15 dev levels (each counts the same) is the main value; dev_alt / dev_neu are reported next to
it so it stays visible whether new skills push out old ones.
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
from jumpnrun.rl import milestones8 as m8
from jumpnrun.rl.evaluate import evaluate_levels
from jumpnrun.rl.milestones import frozen_levels
from jumpnrun.rl.modelinfo import load_model

ROOT = m8.ROOT
SPLIT9 = ROOT / "levels/handmade9/split.json"
PROBES = ROOT / "levels/probes/v10.json"
LEVEL_ATTEMPTS = m8.LEVEL_ATTEMPTS
wilson = m8.wilson


def split9():
    return json.loads(SPLIT9.read_text())


def dev_levels():
    items = m8.dev_levels()
    items += [(f"hand9_{n}", Level.from_file(ROOT / "levels/handmade9" / f"{n}.txt"), LEVEL_ATTEMPTS)
              for n in split9()["dev"]]
    return items


def test_levels():
    return m8.test_levels() + [(f"hand9_{n}", Level.from_file(ROOT / "levels/handmade9" / f"{n}.txt"), LEVEL_ATTEMPTS)
                               for n in split9()["test"]]


def probe_levels():
    data = json.loads(PROBES.read_text())["levels"]
    out = []
    for item in data:
        lv = Level.from_text(item["text"], name=item["name"])
        if item.get("enemy_directions"):
            lv.enemy_directions = item["enemy_directions"]
        if item.get("enemy_wakes"):
            lv.enemy_wakes = item["enemy_wakes"]
        out.append((item["skill"], lv))
    return out


def _mean(rates):
    m = float(np.mean(rates))
    se = float(np.std(rates, ddof=1) / math.sqrt(len(rates))) if len(rates) > 1 else 0.0
    return [round(m, 4), round(max(0.0, m - 1.96 * se), 4), round(min(1.0, m + 1.96 * se), 4)]


def evaluate_checkpoint(path: Path, full: bool) -> dict:
    model = load_model(path)
    out = {"dev": m8.play_group(model, dev_levels())}
    if full:
        test = m8.play_group(model, test_levels())
        out["test"] = {"won": sum(v["won"] for v in test.values()), "of": sum(v["of"] for v in test.values()),
                       "won_neu": sum(v["won"] for k, v in test.items() if k.startswith("hand9_"))}
        schutz = total = 0
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
    rates = {k: v["won"] / v["of"] for k, v in out["dev"].items()}
    out["dev_mean"] = _mean(list(rates.values()))
    out["dev_alt"] = _mean([r for k, r in rates.items() if not k.startswith("hand9_")])
    out["dev_neu"] = _mean([r for k, r in rates.items() if k.startswith("hand9_")])
    return out


def describe(result: dict) -> str:
    d = result["dev"]
    text = (f"dev {result['dev_mean'][0]:.1%} [{result['dev_mean'][1]:.0%}-{result['dev_mean'][2]:.0%}] "
            f"(alt {result['dev_alt'][0]:.1%}, neu {result['dev_neu'][0]:.1%}), pruefung {d['pruefung']['won']}/"
            f"{d['pruefung']['of']}")
    if "test" in result:
        text += (f", test {result['test']['won']}/{result['test']['of']}, schutz {result['schutz']['won']}/"
                 f"{result['schutz']['of']}, proben " + " ".join(f"{k[:6]} {v['won']}/{v['of']}"
                                                                for k, v in result["proben"].items()))
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 9 milestone evaluation.")
    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--once", help="evaluate one checkpoint fully and print/store the result")
    parser.add_argument("--every", type=int, default=1_000_000)
    parser.add_argument("--seconds", type=float, default=520)
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.once:
        np.random.seed(0)
        torch.manual_seed(0)
        result = evaluate_checkpoint(ROOT / args.once, full=True)
        out = ROOT / "runs/phase9/baseline.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(out.read_text()) if out.exists() else {}
        data[args.once] = result
        out.write_text(json.dumps(data, indent=1))
        print(args.once, describe(result))
        return
    start = time.time()
    while time.time() - start < args.seconds:
        jobs = []
        for r in args.run:
            run = Path(r)
            path = run / "milestones9.json"
            done = json.loads(path.read_text()) if path.exists() else {}
            for steps, kind, ckpt in m8.pending(run, done, args.every):
                jobs.append(((0 if kind == "ema" else 1), steps, run, kind, ckpt))
        if not jobs:
            time.sleep(15)
            continue
        _, steps, run, kind, ckpt = min(jobs, key=lambda j: (j[0], j[1]))
        t0 = time.time()
        result = evaluate_checkpoint(ckpt, full=(kind == "ema"))
        result["seconds"] = round(time.time() - t0)
        result["checkpoint"] = ckpt.name
        path = run / "milestones9.json"
        done = json.loads(path.read_text()) if path.exists() else {}
        done[f"{steps}:{kind}"] = result
        path.write_text(json.dumps(done, indent=1))
        print(f"{run.name} {steps:,} {kind}: {describe(result)} [{result['seconds']}s]", flush=True)


if __name__ == "__main__":
    main()
