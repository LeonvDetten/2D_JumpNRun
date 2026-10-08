"""Phase 12 milestones: the scorecard (8 categories + generalist value) plus milestones10 "klein" (dev_alt, F, exam
32 - the numbers the Neustart curve has, for the comparison at the same step count).

    OMP_NUM_THREADS=1 taskset -c 3 python3 -m jumpnrun.rl.milestones12 --run runs/phase12_schueler

Pace: EMA every 2 M (and at 1 M); EMA2 additionally in the window +40/+42/+44 M. Results in <run>/milestones12.json.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import torch

from jumpnrun.rl import milestones10 as m10
from jumpnrun.rl import scorecard12 as S
from jumpnrun.rl.modelinfo import load_model

WINDOW = (40, 42, 44)


def evaluate(ckpt: Path, seed: int = 0) -> dict:
    model = load_model(ckpt)
    small = m10.evaluate(model, full=False, seed=seed)
    card = S.evaluate(ckpt, seed=seed, procs=1)
    p = small["dev"]["pruefung"]
    return {"dev_alt": small["dev_alt"], "dev_neu": small["dev_neu"], "F": small["F"],
            "pruefung32": f"{p['won']}/{p['of']}", "kategorien": card["kategorien"], "generalist": card["generalist"],
            "komponenten": card["komponenten"]}


def pending(run: Path, done: dict):
    cdir = run / "checkpoints"
    todo = []
    for prefix in ("ema", "ema2"):
        for c in sorted(cdir.glob(f"{prefix}_step_*.zip")):
            steps = int(c.stem[len(prefix) + 6:])
            m = round(steps / 1e6)
            if m == 0 or abs(steps - m * 1_000_000) > 60_000:
                continue
            want = (m == 1 or m % 2 == 0) if prefix == "ema" else m in WINDOW
            if want and f"{steps}:{prefix}" not in done:
                todo.append((steps, prefix, c))
    return todo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--seconds", type=float, default=1e9)
    args = parser.parse_args()
    torch.set_num_threads(1)
    run = Path(args.run)
    path = run / "milestones12.json"
    start = time.time()
    while time.time() - start < args.seconds:
        done = json.loads(path.read_text()) if path.exists() else {}
        jobs = pending(run, done)
        if not jobs:
            time.sleep(20)
            continue
        steps, prefix, ckpt = min(jobs, key=lambda j: (j[0], j[1]))
        t0 = time.time()
        res = evaluate(ckpt)
        res["sekunden"] = round(time.time() - t0)
        res["checkpoint"] = ckpt.name
        done = json.loads(path.read_text()) if path.exists() else {}
        done[f"{steps}:{prefix}"] = res
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(done, indent=1))
        os.replace(tmp, path)
        print(f"{steps:,} {prefix}: Generalist {res['generalist']:.1%}, dev_alt {res['dev_alt']:.1%}, F {res['F']:.1%}, "
              + " | ".join(f"{c.split(' ', 1)[1]} {v:.0%}" for c, v in zip(S.CATS, res["kategorien"]))
              + f" [{res['sekunden']}s]", flush=True)


if __name__ == "__main__":
    main()
