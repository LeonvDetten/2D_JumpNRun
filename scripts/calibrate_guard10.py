"""Phase 10: is the guard valid? Val must separate P8 from the known dip (R1 control EMA 54M) by >= 8 Pp.

    OMP_NUM_THREADS=1 nice taskset -c 3 python3 scripts/calibrate_guard10.py     # -> runs/phase10/guard_valid.json

64 stochastic attempts per val level and model, same seeds for both models (paired). Only val is played.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jumpnrun.core.level import Level  # noqa: E402
from jumpnrun.rl import milestones8 as m8  # noqa: E402
from jumpnrun.rl.modelinfo import load_model  # noqa: E402

MODELS = {"p8": "models/phase8_final.zip", "r1k_ema54": "runs/phase9_r1_kontrolle/checkpoints/ema_step_0054000000.zip"}


def main():
    torch.set_num_threads(1)
    split = json.loads((ROOT / "levels/handmade10/split.json").read_text())
    items = [(f"hand10_{n}", Level.from_file(ROOT / "levels/handmade10" / f"{n}.txt"), 64) for n in split["val"]]
    out = {}
    for tag, path in MODELS.items():
        np.random.seed(0)
        torch.manual_seed(0)
        res = m8.play_group(load_model(ROOT / path), items)
        out[tag] = dict(rate=sum(v["won"] for v in res.values()) / sum(v["of"] for v in res.values()),
                        je_level={k: f"{v['won']}/{v['of']}" for k, v in res.items()})
        print(tag, out[tag], flush=True)
    diff = out["p8"]["rate"] - out["r1k_ema54"]["rate"]
    out.update(diff=round(diff, 4), valid=bool(diff >= 0.08), regel="P8 - R1-K EMA 54M >= 8 Pp (64 je Level)")
    (ROOT / "runs/phase10/guard_valid.json").write_text(json.dumps(out, indent=1))
    print("gültig" if out["valid"] else "ungültig", f"(Abstand {diff:+.1%})")


if __name__ == "__main__":
    main()
