"""Phase 12: where do exam attempts end - per exam section and cause, for several models (the exam is never
trained; this only reads results).

    OMP_NUM_THREADS=1 taskset -c 3 python3 scripts/pruefung_diagnose12.py --attempts 128 \
        P8=models/phase8_final.zip P12_22=runs/phase12_schueler/checkpoints/ema_step_0022000000.zip
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

from jumpnrun.core.level import Level  # noqa: E402
from jumpnrun.rl.evaluate import evaluate_levels  # noqa: E402
from jumpnrun.rl.milestones import EXAMS, section_of  # noqa: E402
from jumpnrun.rl.modelinfo import load_model  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+", help="NAME=path")
    parser.add_argument("--attempts", type=int, default=128)
    parser.add_argument("--out", default="runs/phase12/pruefung_diagnose.json")
    args = parser.parse_args()
    torch.set_num_threads(1)
    level = Level.from_file(ROOT / EXAMS["original"])
    out = {}
    for spec in args.models:
        name, path = spec.split("=", 1)
        results = evaluate_levels(load_model(Path(path)), [level] * args.attempts, deterministic=False)
        ends = collections.Counter()
        for r in results:
            if not r["won"]:
                ends[(section_of(int(r["progress"] * level.goal_x) // 60), r.get("outcome", "?"))] += 1
        out[name] = dict(won=sum(r["won"] for r in results), of=args.attempts,
                         mean=round(sum(r["progress"] for r in results) / len(results), 3),
                         ends={f"{s} / {o}": n for (s, o), n in ends.most_common()})
        print(name, json.dumps(out[name], ensure_ascii=False), flush=True)
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
