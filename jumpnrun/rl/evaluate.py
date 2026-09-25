"""Evaluate a trained bot on levels (deterministic policy, no learning).

    python -m jumpnrun.rl.evaluate --model models/phase1.zip --tiers 0 1 2 --per-tier 20
    python -m jumpnrun.rl.evaluate --model models/phase1.zip --levels levels/phase1/*.txt
"""

from __future__ import annotations

import argparse
from typing import Dict, List, Sequence

import numpy as np

from jumpnrun.core.actions import ACTION_REPEAT
from jumpnrun.core.level import Level
from jumpnrun.levelgen.generator import generate
from jumpnrun.rl.curriculum import EVAL_SEED_OFFSET
from jumpnrun.rl.env import JumpNRunEnv, fixed_levels


def eval_level_set(tiers: Sequence[int], per_tier: int) -> List[tuple]:
    """Fixed evaluation levels: generated with seeds the training never uses."""

    return [(f"stufe_{t}", generate(t, EVAL_SEED_OFFSET + i)) for t in tiers for i in range(per_tier)]


def evaluate_levels(model, levels: Sequence[Level], deterministic: bool = True) -> List[Dict]:
    """Play every level once; all levels run in lock-step so the network sees one batch."""

    repeat = getattr(model, "action_repeat", ACTION_REPEAT)
    envs = [JumpNRunEnv(fixed_levels([level]), action_repeat=repeat) for level in levels]
    obs = [env.reset(seed=i)[0] for i, env in enumerate(envs)]
    results: List[Dict] = [None] * len(envs)
    active = list(range(len(envs)))
    while active:
        batch = {key: np.stack([obs[i][key] for i in active]) for key in ("grid", "vec")}
        actions, _ = model.predict(batch, deterministic=deterministic)
        still_active = []
        for i, action in zip(active, actions):
            obs[i], _, terminated, truncated, info = envs[i].step(int(action))
            if terminated or truncated:
                results[i] = info["episode_end"]
            else:
                still_active.append(i)
        active = still_active
    return results


def main() -> None:
    from jumpnrun.rl.modelinfo import load_model

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--tiers", type=int, nargs="*", default=[])
    parser.add_argument("--per-tier", type=int, default=20)
    parser.add_argument("--levels", nargs="*", default=[])
    args = parser.parse_args()

    model = load_model(args.model)
    for tier in args.tiers:
        levels = [level for _, level in eval_level_set([tier], args.per_tier)]
        results = evaluate_levels(model, levels)
        wins = sum(r["won"] for r in results)
        print(f"Stufe {tier}: {wins}/{len(results)} gewonnen, "
              f"Fortschritt {np.mean([r['progress'] for r in results]):.0%}")
    for path in args.levels:
        result = evaluate_levels(model, [Level.from_file(path)])[0]
        print(f"{path}: {result['outcome']} (Fortschritt {result['progress']:.0%}, {result['steps']} Schritte)")


if __name__ == "__main__":
    main()
