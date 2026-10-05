"""Phase 10 milestone evaluation (repaired measurement: "stuck" along the way, time limit from the way length).

    OMP_NUM_THREADS=1 python3 -m jumpnrun.rl.milestones10 --run runs/phase10_a_2e5 --run runs/phase10_a_5e5
    python3 -m jumpnrun.rl.milestones10 --once models/phase8_final.zip --tag p8 --repeat 3     # baselines

Two sizes:
    klein  (EMA every 1 M)      dev 16 attempts per level (exam 32), v10 probes kanal/umkehren/truhe_links stochastic
    voll   (EMA + EMA2 every 2 M) dev 32 (exam 64), guard val (handmade10), all v10 probes deterministic + stochastic,
                                skill probes v11 det + stoch, protection set, test sums (H8, H9, H10 test - report only)
Main values:
    dev_alt  11 old dev levels (exam, test series, handmade8 dev)      dev_neu  4 handmade9 dev levels
    F        = 1/2 dev_neu + 1/2 v10 probes kanal/umkehren/truhe_links (stochastic)   - the skill value
    alt      = mean(dev_alt, guard val) once the guard is valid, else dev_alt        - the keep-the-old value
Every evaluation seeds numpy/torch the same way, so two models measured with the same seed are paired.
Sealed levels are never played here.
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
from jumpnrun.rl.evaluate import evaluate_levels
from jumpnrun.rl.milestones import frozen_levels
from jumpnrun.rl.modelinfo import load_model

ROOT = m8.ROOT
GUARD = ROOT / "levels/handmade10/split.json"
GUARD_VALID = ROOT / "runs/phase10/guard_valid.json"
SKILL_PROBES = ROOT / "levels/probes/v11_skills.json"
F_SKILLS = ("kanal", "umkehren", "truhe_links")


def guard_split():
    return json.loads(GUARD.read_text()) if GUARD.exists() else None


def guard_valid() -> bool:
    return GUARD_VALID.exists() and json.loads(GUARD_VALID.read_text()).get("valid", False)


def dev_items(attempts: int):
    """[(name, Level, n)]: exam with 2x attempts, every other dev level with `attempts`."""

    items = []
    for name, level, _ in m9.dev_levels():
        items.append((name, level, 2 * attempts if name == "pruefung" else attempts))
    return items


def _probe_levels(path: Path):
    data = json.loads(path.read_text())["levels"]
    out = []
    for item in data:
        lv = Level.from_text(item["text"], name=item["name"])
        if item.get("enemy_directions"):
            lv.enemy_directions = item["enemy_directions"]
        if item.get("enemy_wakes"):
            lv.enemy_wakes = item["enemy_wakes"]
        out.append((item["skill"], lv))
    return out


def _probe_rates(model, probes, deterministic: bool, repeat: int = 1):
    levels = [lv for _, lv in probes] * repeat
    res = evaluate_levels(model, levels, deterministic=deterministic)
    per = {}
    for (skill, _), r in zip(probes * repeat, res):
        o = per.setdefault(skill, {"won": 0, "of": 0})
        o["won"] += int(r["won"])
        o["of"] += 1
    return per


def _rate(group: dict) -> float:
    return sum(v["won"] for v in group.values()) / max(1, sum(v["of"] for v in group.values()))


def evaluate(model_or_path, full: bool, seed: int = 0) -> dict:
    model = load_model(model_or_path) if isinstance(model_or_path, (str, Path)) else model_or_path
    np.random.seed(seed)
    torch.manual_seed(seed)
    out = {"size": "voll" if full else "klein", "seed": seed}
    out["dev"] = m8.play_group(model, dev_items(32 if full else 16))
    rates = {k: v["won"] / v["of"] for k, v in out["dev"].items()}
    out["dev_alt"] = round(float(np.mean([r for k, r in rates.items() if not k.startswith("hand9_")])), 4)
    out["dev_neu"] = round(float(np.mean([r for k, r in rates.items() if k.startswith("hand9_")])), 4)
    probes10 = m9.probe_levels()
    f_probes = [(s, lv) for s, lv in probes10 if s in F_SKILLS]
    out["proben_stoch"] = _probe_rates(model, f_probes if not full else probes10, deterministic=False, repeat=2)
    out["f_proben"] = round(float(np.mean([out["proben_stoch"][s]["won"] / out["proben_stoch"][s]["of"]
                                           for s in F_SKILLS])), 4)
    out["F"] = round(0.5 * out["dev_neu"] + 0.5 * out["f_proben"], 4)
    if full:
        out["proben_det"] = _probe_rates(model, probes10, deterministic=True)
        if SKILL_PROBES.exists():
            sp = _probe_levels(SKILL_PROBES)
            out["uebung_stoch"] = _probe_rates(model, sp, deterministic=False)
            out["uebung_det"] = _probe_rates(model, sp, deterministic=True)
        schutz = total = 0
        for name in ("v3", "v4"):
            lv = frozen_levels(name)
            schutz += sum(r["won"] for r in evaluate_levels(model, [l for _, l in lv]))
            total += len(lv)
        out["schutz"] = {"won": schutz, "of": total}
        test = m9.test_levels()
        g = guard_split()
        if g:
            gl = [(f"hand10_{n}", Level.from_file(ROOT / "levels/handmade10" / f"{n}.txt"), 32) for n in g["val"]]
            out["waechter_val"] = m8.play_group(model, gl)
            out["waechter_val_rate"] = round(_rate(out["waechter_val"]), 4)
            test = test + [(f"hand10_{n}", Level.from_file(ROOT / "levels/handmade10" / f"{n}.txt"), 16)
                           for n in g["test"]]
        t = m8.play_group(model, test)
        out["test_summen"] = {grp: {"won": sum(v["won"] for k, v in t.items() if k.startswith(pre)),
                                    "of": sum(v["of"] for k, v in t.items() if k.startswith(pre))}
                              for grp, pre in (("h8", "hand_"), ("h9", "hand9_"), ("h10", "hand10_"))}
    alt = out["dev_alt"]
    if full and guard_valid() and "waechter_val_rate" in out:
        alt = 0.5 * (out["dev_alt"] + out["waechter_val_rate"])
    out["alt"] = round(alt, 4)
    return out


def describe(r: dict) -> str:
    d = r["dev"]
    text = (f"[{r['size']}] alt {r['alt']:.1%} (dev_alt {r['dev_alt']:.1%}), F {r['F']:.1%} (dev_neu {r['dev_neu']:.1%}, "
            f"Proben {r['f_proben']:.1%}), Prüfung {d['pruefung']['won']}/{d['pruefung']['of']}")
    if r["size"] == "voll":
        text += f", Schutz {r['schutz']['won']}/{r['schutz']['of']}"
        if "waechter_val_rate" in r:
            text += f", Wächter-Val {r['waechter_val_rate']:.1%}"
        text += ", Test " + " ".join(f"{k} {v['won']}/{v['of']}" for k, v in r["test_summen"].items())
    return text


def pending(run: Path, done: dict, phase_start: int):
    """(steps, kind, size, checkpoint): EMA every 1 M (klein; voll at even millions after the phase start), EMA2 voll."""

    cdir = run / "checkpoints"
    todo = []
    for prefix in ("ema", "ema2"):
        for c in sorted(cdir.glob(f"{prefix}_step_*.zip")):
            steps = int(c.stem[len(prefix) + 6:])
            rel = round((steps - phase_start) / 1e6)
            full = prefix == "ema2" or rel % 2 == 0
            if prefix == "ema2" and rel % 2:
                continue
            if f"{steps}:{prefix}" not in done:
                todo.append((steps, prefix, full, c))
    seen = set()  # raw: the first checkpoint of every whole million (klein)
    for c in sorted(cdir.glob("step_*.zip"))[:-1]:  # the newest may still be written
        steps = int(c.stem[5:])
        block = steps // 1_000_000
        if block in seen or steps - block * 1_000_000 > 50_000 or steps < phase_start + 1_000_000:
            continue
        seen.add(block)
        if not any(k.endswith(":raw") and int(k.split(":")[0]) // 1_000_000 == block for k in done):
            todo.append((steps, "raw", False, c))
    return todo


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 10 milestone evaluation.")
    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--once", help="evaluate one checkpoint fully (baseline)")
    parser.add_argument("--tag", help="name for --once")
    parser.add_argument("--repeat", type=int, default=1, help="--once: independent repeats (seeds 0, 1, ...)")
    parser.add_argument("--seed-offset", type=int, default=0, help="--once: first seed (selection: fresh seeds)")
    parser.add_argument("--seconds", type=float, default=1e9)
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.once:
        out = ROOT / f"runs/phase10/baseline_{args.tag or Path(args.once).stem}.json"  # one file per tag (parallel)
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
            path = run / "milestones10.json"
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
        path = run / "milestones10.json"
        done = json.loads(path.read_text()) if path.exists() else {}
        done[f"{steps}:{kind}"] = res
        path.write_text(json.dumps(done, indent=1))
        print(f"{run.name} {steps:,} {kind}: {describe(res)} [{res['seconds']}s]", flush=True)


if __name__ == "__main__":
    main()
