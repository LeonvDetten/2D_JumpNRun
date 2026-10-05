"""Phase 10: paired shift check of the measurement repair.

    python3 scripts/shift_check10.py [--attempts 32] [--procs 4]

The phase-8 model plays the 11 old dev levels with identical seeds (level reset + torch) once under the old rule
("stuck" = no new rightmost x, time limit from the level width) and once under the new one (way-based). Up to the
old cut-off point both runs are identical, so every changed result is caused by the rule, not by chance.
Criterion (plan): at most 3 % of the episodes change their result.
"""

from __future__ import annotations

import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def episode(args):
    import numpy as np
    import torch

    from jumpnrun.core.level import Level
    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
    from jumpnrun.rl.modelinfo import env_kwargs, load_model

    model_path, level_path, k = args
    torch.set_num_threads(1)
    model = load_model(ROOT / model_path)
    level = Level.from_file(level_path)
    out = []
    for rule in ("x", "path"):
        kw = env_kwargs(model)
        kw["progress"] = rule
        env = JumpNRunEnv(fixed_levels([level]), **kw)
        obs, _ = env.reset(seed=k)
        torch.manual_seed(1000 + k)
        np.random.seed(1000 + k)
        while True:
            a, _ = model.predict({key: v[None] for key, v in obs.items()}, deterministic=False)
            obs, _, term, trunc, info = env.step(int(a[0]))
            if term or trunc:
                out.append(info["episode_end"]["outcome"])
                break
    return level_path.stem, out


def main() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_solutions10 import allowed_solutions

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/phase8_final.zip")
    parser.add_argument("--attempts", type=int, default=32)
    parser.add_argument("--procs", type=int, default=4)
    args = parser.parse_args()
    levels = [p for name, p, _, _ in allowed_solutions() if not name.startswith(("handmade9", "handmade10"))]
    jobs = [(args.model, p, k) for p in levels for k in range(args.attempts)]
    with Pool(args.procs) as pool:
        res = pool.map(episode, jobs, chunksize=4)
    changed, won_old, won_new = 0, 0, 0
    per = {}
    for name, (old, new) in res:
        d = per.setdefault(name, [0, 0, 0])
        d[0] += old == "won"
        d[1] += new == "won"
        d[2] += (old == "won") != (new == "won")
        changed += (old == "won") != (new == "won")
        won_old += old == "won"
        won_new += new == "won"
    n = len(res)
    for name, (a, b, c) in per.items():
        print(f"{name:14s} alt {a:2d}  neu {b:2d}  gewechselt {c}")
    result = {"model": args.model, "episodes": n, "won_old_rule": won_old, "won_new_rule": won_new,
              "changed": changed, "changed_share": round(changed / n, 4), "ok": changed / n <= 0.03}
    print(json.dumps(result))
    out = ROOT / "runs/phase10/shift_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(result, per_level=per), indent=1))


if __name__ == "__main__":
    main()
