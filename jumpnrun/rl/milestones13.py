"""Phase 13 milestones: every EMA checkpoint (each 1 M) - the scorecard at T = 1 (comparable with all earlier
measurements) and at T = 0.3 (how the bot plays since 10.10.), with a fixed seed, plus two extra values that do
not enter the generalist value:

- links_spruenge: the v13 jump probes mirrored (chest left, enemies walking left), never trained
- spiegelweg: the dev level (start right, chest left; no model has won it so far), 16 attempts at T = 0.3

    OMP_NUM_THREADS=1 taskset -c 3 python3 -m jumpnrun.rl.milestones13 --run runs/phase13
    python3 -m jumpnrun.rl.milestones13 --model models/phase12_kandidat.zip --tag stand0   # one model, once

Results in <run>/milestones13.json (key "<steps>:<ema|ema2>") or runs/phase13/stand_<tag>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import torch

from jumpnrun.rl import scorecard12 as S
from jumpnrun.rl.train import _zip_ok

SEED = 7
T_PLAY = 0.3
ROOT = S.ROOT


def extra_levels():
    from jumpnrun.levelgen.skills import mirror_level
    from jumpnrun.rl import milestones9 as m9

    links = []
    for lv, skill in S._v13():
        if skill == "spruenge":
            m = mirror_level(lv)
            if m.enemy_spawns:
                m.enemy_directions = [-1] * len(m.enemy_spawns)
            links.append(m)
    dev = {n: lv for n, lv, _ in m9.dev_levels()}
    sw = dev["hand9_spiegelweg"]
    sw.needs_path = True
    return links, sw


def _rate(model, levels, temperature, seed):
    from jumpnrun.rl.evaluate import evaluate_levels

    np.random.seed(seed)
    torch.manual_seed(seed)
    res = evaluate_levels(model, levels, deterministic=False, temperature=temperature)
    return {"won": sum(int(r["won"]) for r in res), "of": len(res),
            "fortschritt": round(float(np.mean([r["progress"] for r in res])), 3)}


def evaluate(ckpt: Path, seed: int = SEED) -> dict:
    from jumpnrun.rl.modelinfo import load_model

    out = {}
    for name, temp in (("t1", 1.0), ("t03", T_PLAY)):
        card = S.evaluate(ckpt, seed=seed, procs=1, temperature=temp)
        out[name] = {"kategorien": card["kategorien"], "generalist": card["generalist"],
                     "komponenten": card["komponenten"]}
    model = load_model(ckpt)
    links, sw = extra_levels()
    out["links_spruenge"] = _rate(model, links, T_PLAY, seed)
    out["spiegelweg"] = _rate(model, [sw] * 16, T_PLAY, seed)
    k = out["t03"]["kategorien"]
    out["ohne_links_t03"] = float(np.mean([v for i, v in enumerate(k) if i != 5]))
    return out


def pending(run: Path, done: dict):
    todo = []
    for prefix in ("ema", "ema2"):
        for c in sorted((run / "checkpoints").glob(f"{prefix}_step_*.zip")):
            steps = int(c.stem[len(prefix) + 6:])
            if abs(steps - round(steps / 1e6) * 1e6) > 60_000:
                continue
            if prefix == "ema2" and round(steps / 1e6) % 3:  # EMA2 every 3 M (the window for the verdict)
                continue
            if time.time() - c.stat().st_mtime < 60 or f"{steps}:{prefix}" in done or not _zip_ok(c):
                continue
            todo.append((steps, prefix, c))
    return todo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run")
    parser.add_argument("--model")
    parser.add_argument("--tag")
    parser.add_argument("--seconds", type=float, default=1e9)
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.model:
        res = evaluate(ROOT / args.model)
        res["modell"] = args.model
        (ROOT / "runs/phase13").mkdir(parents=True, exist_ok=True)
        (ROOT / "runs/phase13" / f"stand_{args.tag}.json").write_text(json.dumps(res, indent=1))
        print(args.tag, summary(res))
        return
    run = Path(args.run)
    path = run / "milestones13.json"
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
        print(f"{steps:,} {prefix}: {summary(res)} [{res['sekunden']}s]", flush=True)


def summary(res: dict) -> str:
    cats = " | ".join(f"{c.split(' ', 1)[1]} {v:.0%}" for c, v in zip(S.CATS, res["t03"]["kategorien"]))
    return (f"Generalist T0.3 {res['t03']['generalist']:.1%} (T1 {res['t1']['generalist']:.1%}), ohne Links "
            f"{res['ohne_links_t03']:.1%}, Links-Sprünge {res['links_spruenge']['won']}/{res['links_spruenge']['of']}, "
            f"spiegelweg {res['spiegelweg']['won']}/16 || {cats}")


if __name__ == "__main__":
    main()
