"""Phase 11 milestone evaluation: everything of milestones10 (comparable) plus the generalist measurements.

    OMP_NUM_THREADS=1 python3 -m jumpnrun.rl.milestones11 --run runs/phase11_a --run runs/phase11_b
    python3 -m jumpnrun.rl.milestones11 --once models/phase10_kandidat_lehrer.zip --tag lehrer   # baselines

Added (allowed levels only):
    doppelgabel     handmade8 dev level, 16 attempts (klein and voll)
    spiegel         voll: mirrored dev_alt levels (8 each) + mirrored guard val/val_plus (8 each), chest on the left;
                    only mirrors the distance map can solve count
    waechter_plus   voll: 12 guard levels (val + val_plus) x 32
    sackgasse       voll: probes levels/probes/v12_lange_sackgasse.json, stochastic
Generalist value G (voll) = mean of: spiegel rate, waechter_plus rate, F, mean(doppelgabel, sackgasse probes).
Seeds as in milestones10: two models measured with the same seed are paired. Sealed levels are never played here.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from jumpnrun.core.level import Level
from jumpnrun.rl import milestones8 as m8
from jumpnrun.rl import milestones9 as m9
from jumpnrun.rl import milestones10 as m10
from jumpnrun.rl.modelinfo import load_model

ROOT = m8.ROOT
SACKGASSE = ROOT / "levels/probes/v12_lange_sackgasse.json"
VOLL_ALSO = (7,)  # judging window +6/+7/+8: +7 voll as well


def _mirror(level: Level, name: str):
    from jumpnrun.levelgen.distmap import DistanceMap
    from jumpnrun.levelgen.skills import mirror_level

    m = mirror_level(level, name)
    return m if DistanceMap(m).reachable else None


def mirror_items(per_level: int = 8):
    split = m10.guard_split() or {"val": [], "val_plus": []}
    items = []
    for name, level, _ in m9.dev_levels():
        if name.startswith("hand9_"):
            continue  # dev_alt only
        m = _mirror(level, name + "_spiegel")
        if m is not None:
            items.append((name + "_spiegel", m, per_level))
    for n in split["val"] + split.get("val_plus", []):
        m = _mirror(Level.from_file(ROOT / "levels/handmade10" / f"{n}.txt"), f"hand10_{n}_spiegel")
        if m is not None:
            items.append((f"hand10_{n}_spiegel", m, per_level))
    return items


def guard_plus_items(per_level: int = 32):
    split = m10.guard_split() or {"val": [], "val_plus": []}
    return [(f"hand10_{n}", Level.from_file(ROOT / "levels/handmade10" / f"{n}.txt"), per_level)
            for n in split["val"] + split.get("val_plus", [])]


def doppelgabel_items(n: int = 16):
    return [("doppelgabel", Level.from_file(ROOT / "levels/handmade8/doppelgabel.txt"), n)]


def generalist(r: dict) -> float:
    parts = [r["spiegel_rate"], r["waechter_plus_rate"], r["F"], 0.5 * (r["doppelgabel_rate"] + r["sackgasse_rate"])]
    return round(float(np.mean(parts)), 4)


def evaluate(model_or_path, full: bool, seed: int = 0) -> dict:
    model = load_model(model_or_path) if isinstance(model_or_path, (str, Path)) else model_or_path
    out = m10.evaluate(model, full=full, seed=seed)
    np.random.seed(seed + 11)
    torch.manual_seed(seed + 11)
    d = m8.play_group(model, doppelgabel_items())["doppelgabel"]
    out["doppelgabel"] = d
    out["doppelgabel_rate"] = round(d["won"] / d["of"], 4)
    if full:
        out["spiegel"] = m8.play_group(model, mirror_items())
        out["spiegel_rate"] = round(m10._rate(out["spiegel"]), 4)
        out["spiegel_alt_rate"] = round(m10._rate({k: v for k, v in out["spiegel"].items()
                                                   if not k.startswith("hand10_")}), 4)
        out["spiegel_lang_rate"] = round(m10._rate({k: v for k, v in out["spiegel"].items()
                                                    if k.startswith("hand10_")}), 4)
        out["waechter_plus"] = m8.play_group(model, guard_plus_items())
        out["waechter_plus_rate"] = round(m10._rate(out["waechter_plus"]), 4)
        if SACKGASSE.exists():
            out["sackgasse"] = m10._probe_rates(model, m10._probe_levels(SACKGASSE), deterministic=False, repeat=2)
            out["sackgasse_rate"] = round(m10._rate(out["sackgasse"]), 4)
        else:
            out["sackgasse_rate"] = 0.0
        out["G"] = generalist(out)
    return out


def describe(r: dict) -> str:
    text = m10.describe(r) + f", doppelgabel {r['doppelgabel']['won']}/{r['doppelgabel']['of']}"
    if r["size"] == "voll":
        text += (f" | G {r['G']:.1%}: Spiegel {r['spiegel_rate']:.1%} (alt {r['spiegel_alt_rate']:.1%}, lang "
                 f"{r['spiegel_lang_rate']:.1%}), Wächter+ {r['waechter_plus_rate']:.1%}, "
                 f"Sackgasse {r['sackgasse_rate']:.1%}")
    return text


def pending(run: Path, done: dict, phase_start: int):
    """(steps, kind, size, checkpoint): like milestones10, plus voll for EMA and EMA2 at +7 M."""

    cdir = run / "checkpoints"
    todo = []
    for prefix in ("ema", "ema2"):
        for c in sorted(cdir.glob(f"{prefix}_step_*.zip")):
            steps = int(c.stem[len(prefix) + 6:])
            rel = round((steps - phase_start) / 1e6)
            full = rel % 2 == 0 or rel in VOLL_ALSO
            if prefix == "ema2" and not full:
                continue
            if f"{steps}:{prefix}" not in done:
                todo.append((steps, prefix, full, c))
    seen = set()
    for c in sorted(cdir.glob("step_*.zip"))[:-1]:
        steps = int(c.stem[5:])
        block = steps // 1_000_000
        if block in seen or steps - block * 1_000_000 > 50_000 or steps < phase_start + 1_000_000:
            continue
        seen.add(block)
        if not any(k.endswith(":raw") and int(k.split(":")[0]) // 1_000_000 == block for k in done):
            todo.append((steps, "raw", False, c))
    return todo


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 11 milestone evaluation.")
    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--once", help="evaluate one checkpoint fully (baseline)")
    parser.add_argument("--tag", help="name for --once")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=1e9)
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.once:
        out = ROOT / f"runs/phase11/baseline_{args.tag or Path(args.once).stem}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        model = load_model(ROOT / args.once)
        for k in range(args.repeat):
            t0 = time.time()
            res = evaluate(model, full=True, seed=args.seed_offset + k)
            res["seconds"] = round(time.time() - t0)
            res["checkpoint"] = args.once
            data = json.loads(out.read_text()) if out.exists() else {}
            data[f"{args.tag or args.once}:{args.seed_offset + k}"] = res
            out.write_text(json.dumps(data, indent=1))
            print(f"{args.tag or args.once} #{k}: {describe(res)} [{res['seconds']}s]", flush=True)
        return
    start = time.time()
    while time.time() - start < args.seconds:
        jobs = []
        for r in args.run:
            run = Path(r)
            cfg = json.loads((run / "config.json").read_text()) if (run / "config.json").exists() else {}
            path = run / "milestones11.json"
            done = json.loads(path.read_text()) if path.exists() else {}
            for steps, kind, full, ckpt in pending(run, done, cfg.get("phase_start", 0)):
                jobs.append((steps, {"ema": 0, "ema2": 1, "raw": 2}[kind], run, kind, full, ckpt))
        if not jobs:
            time.sleep(15)
            continue
        steps, _, run, kind, full, ckpt = min(jobs, key=lambda j: (j[0], j[1]))
        t0 = time.time()
        res = evaluate(ckpt, full=full, seed=0)
        res["seconds"] = round(time.time() - t0)
        res["checkpoint"] = ckpt.name
        path = run / "milestones11.json"
        done = json.loads(path.read_text()) if path.exists() else {}
        done[f"{steps}:{kind}"] = res
        path.write_text(json.dumps(done, indent=1))
        print(f"{run.name} {steps:,} {kind}: {describe(res)} [{res['seconds']}s]", flush=True)


if __name__ == "__main__":
    main()
