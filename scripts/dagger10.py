"""Phase 10, round C case 2 only: correction demos (DAgger) - the solver takes over where the bot fails.

    nice python3 scripts/dagger10.py runs/phase10_b_neu/checkpoints/ema2_step_....zip 1500   # -> runs/dagger10

The bot plays generated practice levels (all kinds, d1/d2, own seed space "dagger10:") and long v10 levels
(tier 13), stochastically. On a lost episode the state 20-40 steps before the end is taken; from there the solver
(distance map, 7 actions) finds the way. Demo = the bot's own actions up to that state (mask 0, not imitated)
+ the solver's actions (mask 1). Only generated levels; runs in its own 4-core window, never next to training.
"""

from __future__ import annotations

import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "runs/dagger10"
_MODEL = {}


def _level(i: int):
    from jumpnrun.levelgen.generator import generate
    from jumpnrun.levelgen.skills import KINDS, make_skill_level

    if i % 3 == 2:
        lv = generate(13, 9_500_000 + i)
        lv.needs_path = True
        return lv
    kind = KINDS[i % len(KINDS)]
    return make_skill_level(kind, 1 + (i // len(KINDS)) % 2, f"dagger10:{kind}:{i}")


def work(args):
    import torch

    from jumpnrun.core.actions import BOT_ACTIONS_V3
    from jumpnrun.core.sim import Simulation, Status
    from jumpnrun.levelgen.solver import solve_auto
    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
    from jumpnrun.rl.modelinfo import load_model

    ckpt, i = args
    torch.set_num_threads(1)
    if ckpt not in _MODEL:
        _MODEL[ckpt] = load_model(ROOT / ckpt)
    model = _MODEL[ckpt]
    try:
        level = _level(i)
    except RuntimeError:
        return None
    env = JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True, obs_v3=True, progress="path")
    obs, _ = env.reset(seed=i)
    torch.manual_seed(i)
    actions = []
    while True:
        o = {k: torch.as_tensor(v[None]) for k, v in obs.items()}
        with torch.no_grad():
            a = int(model.policy.get_distribution(o).distribution.sample()[0])
        actions.append(a)
        obs, _, term, trunc, info = env.step(a)
        if term or trunc:
            break
    if info["episode_end"]["won"]:
        return dict(i=i, won=True)
    rng = random.Random(f"dagger10:{i}")
    back = min(len(actions) - 1, rng.randint(20, 40))
    prefix = actions[:len(actions) - back]
    sim = Simulation(level)
    for a in prefix:
        sim.step(BOT_ACTIONS_V3[a], frames=2)
        if sim.status != Status.RUNNING:
            return dict(i=i, won=False)
    r = solve_auto(level, 100_000, action_repeat=2, weight=1.2, path=True, start=sim)
    if not r.solved:
        return dict(i=i, won=False)
    plan = list(r.actions)
    return dict(i=i, won=False, demo=dict(tier=13, seed=i, repeat=2, actions=prefix + plan,
                                          mask=[0] * len(prefix) + [1] * len(plan), won=True, solved=True,
                                          a6=plan.count(6), level="\n".join(level._lines) + "\n"))


def main():
    ckpt = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    OUT.mkdir(parents=True, exist_ok=True)
    stats = {"won": 0, "lost": 0, "demos": 0}
    with Pool(4) as p, open(OUT / "demos_dagger.jsonl", "a") as f:
        for r in p.imap_unordered(work, [(ckpt, i) for i in range(n)], chunksize=2):
            if r is None:
                continue
            stats["won" if r["won"] else "lost"] += 1
            if r.get("demo"):
                f.write(json.dumps(r["demo"]) + "\n")
                f.flush()
                stats["demos"] += 1
    from jumpnrun.rl.ppo_demos import bc2_dataset  # prebuild the BC2 cache of round C (same dir order)

    bc2_dataset(["runs/demos10", "runs/demos9", "runs/dagger10"])
    (OUT / "done.json").write_text(json.dumps(dict(stats, checkpoint=ckpt)))
    print(stats)


if __name__ == "__main__":
    main()
