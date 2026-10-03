"""Milestone evaluation for long runs, as a separate process.

    OMP_NUM_THREADS=1 python3 -m jumpnrun.rl.milestones --run runs/phase7a --run runs/phase7b --seconds 540

For the first checkpoint after every `--every` steps (and its EMA copy, if the run saves one):
    validation v2/v3/v4   frozen generated levels (levels/validierung/*.json), deterministic, never trained
    test series           hand-made levels (levels/test_serie), 16 attempts each, normal random policy
    exam                  both versions, `--exam-attempts` each; where the attempts ended, per section
    exam2 (sealed)        the secret second exam: only the win count, written to milestones_exam2.json,
                          never used for model selection, stopping or analysis

Model selection (best_model.zip) uses only validation - never the test series or the exams.
Several runs are served in turn, oldest pending milestone first.
The run gets a STOP file once the stop rule holds at two milestones in a row (see stop_rule()).
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import numpy as np
import torch

from jumpnrun.core.level import Level
from jumpnrun.rl.evaluate import evaluate_levels
from jumpnrun.rl.modelinfo import load_model

ROOT = Path(__file__).resolve().parent.parent.parent
EXAMS = {"original": "levels/exam/level.txt", "entschaerft": "levels/exam/level_entschaerft.txt"}
EXAM2 = "levels/exam2/level.txt"
# sections of the exam level (tile columns) for the "where do attempts end" statistics
EXAM_SECTIONS = ((0, 36, "start_gegnerregen"), (36, 98, "gabelung_oben"), (98, 160, "trittsteine"),
                 (160, 250, "diagonalen"), (250, 10**6, "ziel"))
STOP_WINS = 16  # phase 6 rule (32 attempts)


def frozen_levels(name: str):
    items = json.loads((ROOT / "levels/validierung" / f"{name}.json").read_text())
    return [(f"stufe_{item['tier']}", Level.from_text(item["text"], name=f"{name}_{i}")) for i, item in enumerate(items)]


def section_of(col: int) -> str:
    return next(name for lo, hi, name in EXAM_SECTIONS if lo <= col < hi)


def evaluate_checkpoint(path: Path, exam_attempts: int = 32, validations=("v2", "v3")) -> dict:
    model = load_model(path)
    out = {}
    for name in validations:
        if not (ROOT / "levels/validierung" / f"{name}.json").exists():
            continue
        levels = frozen_levels(name)
        results = evaluate_levels(model, [lv for _, lv in levels])
        per = {}
        for (group, _), r in zip(levels, results):
            per.setdefault(group, []).append(int(r["won"]))
        out[f"validierung_{name}"] = dict(won=sum(map(sum, per.values())), of=len(levels),
                                          tiers={g: sum(v) for g, v in per.items()})
    series = {}
    for p in sorted((ROOT / "levels/test_serie").glob("*.txt")):
        results = evaluate_levels(model, [Level.from_file(p)] * 16, deterministic=False)
        series[p.stem] = dict(won=sum(r["won"] for r in results), of=16,
                              progress=round(float(np.mean([r["progress"] for r in results])), 3))
    out["test_serie"] = series
    exam = {}
    for name, rel in EXAMS.items():
        level = Level.from_file(ROOT / rel)
        results = evaluate_levels(model, [level] * exam_attempts, deterministic=False)
        ends = {}
        for r in results:
            if not r["won"]:
                col = int(r["progress"] * level.goal_x) // 60
                ends[section_of(col)] = ends.get(section_of(col), 0) + 1
        exam[name] = dict(won=sum(r["won"] for r in results), of=exam_attempts, ends=ends,
                          best=round(max(r["progress"] for r in results), 3),
                          mean=round(float(np.mean([r["progress"] for r in results])), 3))
    out["pruefung"] = exam
    return out


def sealed_exam2(path: Path, attempts: int = 32) -> int:
    """Wins on the secret exam - nothing else about it is kept or shown."""

    model = load_model(path)
    results = evaluate_levels(model, [Level.from_file(ROOT / EXAM2)] * attempts, deterministic=False)
    return int(sum(r["won"] for r in results))


def validation_score(result: dict) -> int:
    return sum(v["won"] for k, v in result.items() if k.startswith("validierung_"))


def selection_score(result: dict) -> float:
    """Fixed before phase 7: exam (original, share) + test series (share)."""

    exam = result["pruefung"]["original"]
    series = result["test_serie"]
    return exam["won"] / exam["of"] + sum(s["won"] for s in series.values()) / sum(s["of"] for s in series.values())


def stop_rule(done: dict, exam_share: float, series_share: float) -> bool:
    """Both conditions at the two newest milestones (raw or EMA, whichever is better at each)."""

    keys = sorted({int(k.split(":")[0]) for k in done})[-2:]
    if len(keys) < 2:
        return False
    for step in keys:
        ok = False
        for kind in ("raw", "ema"):
            r = done.get(f"{step}:{kind}") or (done.get(str(step)) if kind == "raw" else None)
            if not r:
                continue
            exam = r["pruefung"]["original"]
            series = r["test_serie"]
            s_won, s_of = sum(s["won"] for s in series.values()), sum(s["of"] for s in series.values())
            ok = ok or (exam["won"] >= exam_share * exam["of"] and s_won >= series_share * s_of)
        if not ok:
            return False
    return True


def pending(run: Path, done: dict, every: int):
    """(key, kind, checkpoint) still to evaluate: the first checkpoint of each `every` block + its EMA copy."""

    ckpts = sorted((run / "checkpoints").glob("step_*.zip"))[:-1]  # newest may still be written
    emas = {int(e.stem[9:]) // every: e for e in sorted((run / "checkpoints").glob("ema_step_*.zip"), reverse=True)}
    keys = {int(k.split(":")[0]) // every: int(k.split(":")[0]) for k in done}
    todo = []
    for c in ckpts:
        steps = int(c.stem[5:])
        block = steps // every
        if block not in keys:
            keys[block] = steps
            todo.append((steps, "raw", c))
    for block, steps in keys.items():
        if block in emas and f"{steps}:ema" not in done:
            todo.append((steps, "ema", emas[block]))
    return todo


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate milestone checkpoints of long runs.")
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--every", type=int, default=1_000_000)
    parser.add_argument("--seconds", type=float, default=560, help="stop looking for new checkpoints after this")
    parser.add_argument("--exam-attempts", type=int, default=32)
    parser.add_argument("--validations", nargs="*", default=["v2", "v3"])
    parser.add_argument("--exam2", action="store_true", help="also play the sealed second exam")
    parser.add_argument("--stop-exam", type=float, default=0.5, help="stop rule: share of exam wins")
    parser.add_argument("--stop-series", type=float, default=0.0, help="stop rule: share of test series wins")
    parser.add_argument("--stop-file", default="STOP", help="file written when the stop rule holds (phase 7: CANDIDATE)")
    args = parser.parse_args()

    torch.set_num_threads(1)
    start = time.time()
    while time.time() - start < args.seconds:
        jobs = []
        for r in args.run:
            run = Path(r)
            path = run / "milestones.json"
            done = json.loads(path.read_text()) if path.exists() else {}
            if done and not any(":" in k for k in done):  # phase 6 format: plain step keys
                done = {f"{k}:raw": v for k, v in done.items()}
            for steps, kind, ckpt in pending(run, done, args.every):
                if f"{steps}:{kind}" not in done:
                    jobs.append((steps, run, kind, ckpt))
        if not jobs:
            time.sleep(15)
            continue
        steps, run, kind, ckpt = min(jobs, key=lambda j: j[0])
        path = run / "milestones.json"
        done = json.loads(path.read_text()) if path.exists() else {}
        t0 = time.time()
        result = evaluate_checkpoint(ckpt, args.exam_attempts, args.validations)
        result["seconds"] = round(time.time() - t0)
        result["checkpoint"] = ckpt.name
        done[f"{steps}:{kind}"] = result
        path.write_text(json.dumps(done, indent=1))
        if args.exam2:
            sealed = run / "milestones_exam2.json"
            sealed_done = json.loads(sealed.read_text()) if sealed.exists() else {}
            sealed_done[f"{steps}:{kind}"] = sealed_exam2(ckpt)
            sealed.write_text(json.dumps(sealed_done))
        score = validation_score(result)
        if score >= max(validation_score(v) for v in done.values()):
            shutil.copy(ckpt, run / "best_model.zip")
        exam = result["pruefung"]
        series = sum(s["won"] for s in result["test_serie"].values())
        print(f"{run.name} {steps:,} {kind}: validation {score}, test series {series}/96, "
              f"exam {exam['original']['won']}/{exam['original']['of']} + {exam['entschaerft']['won']}"
              f" (ends {exam['original']['ends']}) [{result['seconds']}s]", flush=True)
        if stop_rule(done, args.stop_exam, args.stop_series) and not (run / args.stop_file).exists():
            (run / args.stop_file).write_text(f"stop rule met at two milestones in a row ({steps})\n")
            print(f"STOP {run.name}: stop rule met", flush=True)


if __name__ == "__main__":
    main()
