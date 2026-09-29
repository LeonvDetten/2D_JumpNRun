"""Milestone evaluation for long runs, as a separate process (phase 6).

    OMP_NUM_THREADS=1 taskset -c 3 python3 -m jumpnrun.rl.milestones --run runs/phase6 --seconds 560

For the first checkpoint after every `--every` steps:
    validation v2 + v3   frozen generated levels (levels/validierung/*.json), deterministic, never trained
    test series          hand-made levels (levels/test_serie), 16 attempts each with the normal random policy
    exam                 both versions, 32 attempts each; where the attempts ended, per section of the level

Model selection (best_model.zip) uses only validation v2 + v3 - never the test series or the exam.
The run stops (STOP file) once the original exam is won in >= 16/32 attempts at two milestones in a row.
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
# sections of the exam level (tile columns) for the "where do attempts end" statistics
EXAM_SECTIONS = ((0, 36, "start_gegnerregen"), (36, 98, "gabelung_oben"), (98, 160, "trittsteine"),
                 (160, 250, "diagonalen"), (250, 10**6, "ziel"))
STOP_WINS = 16


def frozen_levels(name: str):
    items = json.loads((ROOT / "levels/validierung" / f"{name}.json").read_text())
    return [(f"stufe_{item['tier']}", Level.from_text(item["text"], name=f"{name}_{i}")) for i, item in enumerate(items)]


def section_of(col: int) -> str:
    return next(name for lo, hi, name in EXAM_SECTIONS if lo <= col < hi)


def evaluate_checkpoint(path: Path) -> dict:
    model = load_model(path)
    out = {}
    for name in ("v2", "v3"):
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
        results = evaluate_levels(model, [level] * 32, deterministic=False)
        ends = {}
        for r in results:
            if not r["won"]:
                col = int(r["progress"] * level.goal_x) // 60
                ends[section_of(col)] = ends.get(section_of(col), 0) + 1
        exam[name] = dict(won=sum(r["won"] for r in results), of=32, ends=ends,
                          best=round(max(r["progress"] for r in results), 3),
                          mean=round(float(np.mean([r["progress"] for r in results])), 3))
    out["pruefung"] = exam
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate milestone checkpoints of a long run.")
    parser.add_argument("--run", required=True)
    parser.add_argument("--every", type=int, default=1_000_000)
    parser.add_argument("--seconds", type=float, default=560, help="stop looking for new checkpoints after this")
    args = parser.parse_args()

    torch.set_num_threads(1)
    run = Path(args.run)
    out_path = run / "milestones.json"
    done = json.loads(out_path.read_text()) if out_path.exists() else {}
    start = time.time()
    while time.time() - start < args.seconds:
        checkpoints = sorted((run / "checkpoints").glob("step_*.zip"))[:-1]  # newest may still be written
        seen_blocks = {int(k) // args.every for k in done}
        todo = [c for c in checkpoints if int(c.stem[5:]) // args.every not in seen_blocks]
        if not todo:
            time.sleep(15)
            continue
        ckpt = todo[0]
        steps = int(ckpt.stem[5:])
        t0 = time.time()
        result = evaluate_checkpoint(ckpt)
        result["seconds"] = round(time.time() - t0)
        result["checkpoint"] = ckpt.name
        done[str(steps)] = result
        out_path.write_text(json.dumps(done, indent=1))
        score = result["validierung_v2"]["won"] + result["validierung_v3"]["won"]
        best = max(v["validierung_v2"]["won"] + v["validierung_v3"]["won"] for v in done.values())
        if score >= best:
            shutil.copy(ckpt, run / "best_model.zip")
        exam = result["pruefung"]
        print(f"{steps:,}: validation v2 {result['validierung_v2']['won']}/120, "
              f"v3 {result['validierung_v3']['won']}/{result['validierung_v3']['of']}, "
              f"test series {sum(s['won'] for s in result['test_serie'].values())}/96, "
              f"exam {exam['original']['won']}/32 + {exam['entschaerft']['won']}/32 "
              f"(ends {exam['original']['ends']}) [{result['seconds']}s]", flush=True)
        recent = [done[k]["pruefung"]["original"]["won"] for k in sorted(done, key=int)[-2:]]
        if len(recent) == 2 and min(recent) >= STOP_WINS:
            (run / "STOP").write_text(f"exam passed at two milestones in a row ({recent}) at {steps}\n")
            print("STOP: exam passed twice in a row", flush=True)
            return


if __name__ == "__main__":
    main()
