"""Demonstrations from the solver (the "teacher") for imitation learning.

    python -m jumpnrun.imitation.demos --out runs/demos        # ~2,500 levels, 4 processes

Each demo is stored compactly as (tier, seed, executed actions, label mask):
the simulation is deterministic, so observations are rebuilt when loading.

* label mask 1 = the teacher chose this action (used for training)
* label mask 0 = a random "nudge" (noise) or the student's own action (DAgger);
  these steps are executed but never imitated. They put the teacher into
  slightly unusual situations, so the student also learns how to recover.

The solved levels double as a pool of verified training levels (pool.json).
"""

from __future__ import annotations

import argparse
import json
import random
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from jumpnrun.core.actions import BOT_ACTIONS, DEFAULT_REPEAT
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status
from jumpnrun.levelgen.generator import generate
from jumpnrun.levelgen.solver import solve

LEVELS_PER_TIER = (50, 50, 50, 50, 150, 150, 300, 300, 700, 700)
SOLVER_WEIGHT = 1.2
SOLVER_BUDGET = 60_000
NOISE_PROB = 0.05


def _plan_still_wins(sim: Simulation, plan: List[int], repeat: int) -> bool:
    probe = sim.clone()
    for action in plan:
        if probe.step(BOT_ACTIONS[action], frames=repeat) != Status.RUNNING:
            break
    return probe.status == Status.WON


def make_demo(tier: int, seed: int, repeat: int = DEFAULT_REPEAT, noise: float = NOISE_PROB) -> Optional[Dict]:
    """Solve one generated level; follow the plan, with occasional random nudges and re-planning."""

    level = generate(tier, seed)
    sim = Simulation(level)
    result = solve(level, SOLVER_BUDGET, action_repeat=repeat, weight=SOLVER_WEIGHT)
    if not result.solved:
        return None
    rng = random.Random(f"noise:{tier}:{seed}")
    plan = list(result.actions)
    actions: List[int] = []
    mask: List[int] = []
    while plan and sim.status == Status.RUNNING and len(actions) < 5000:
        if noise and rng.random() < noise and len(plan) > 10:
            for _ in range(rng.randint(1, 2)):
                nudge = rng.randrange(len(BOT_ACTIONS))
                sim.step(BOT_ACTIONS[nudge], frames=repeat)
                actions.append(nudge)
                mask.append(0)
                plan.pop(0)
                if sim.status != Status.RUNNING:
                    break
            if sim.status != Status.RUNNING:
                break
            if not _plan_still_wins(sim, plan, repeat):
                replan = solve(level, SOLVER_BUDGET // 2, action_repeat=repeat, weight=SOLVER_WEIGHT, start=sim)
                if not replan.solved:
                    break
                plan = list(replan.actions)
            continue
        action = plan.pop(0)
        sim.step(BOT_ACTIONS[action], frames=repeat)
        actions.append(action)
        mask.append(1)
    return dict(tier=tier, seed=seed, repeat=repeat, actions=actions, mask=mask,
                won=sim.status == Status.WON, solver_steps=len(result.actions), solved=True)


def _work(args):
    return make_demo(*args)


def equivalent_actions(sim: Simulation, action: int, repeat: int) -> int:
    """Bit mask of all actions that lead to exactly the same next state as `action`."""

    results = []
    for a in range(len(BOT_ACTIONS)):
        probe = sim.clone()
        probe.step(BOT_ACTIONS[a], frames=repeat)
        results.append(probe.state_signature())
    target = results[action]
    return sum(1 << a for a, r in enumerate(results) if r == target)


def load_dataset(paths, max_samples: int = 800_000, thin_flat: float = 2 / 3, seed: int = 0):
    """Rebuild (observation, label-set) samples from demo files.

    Returns dict with grid (int8, N x 4 x 13 x 25), vec (float32, N x 15),
    action (int64) and allowed (uint8 bit mask of equivalent actions).
    Long stretches where only "right" makes sense are thinned out.
    """

    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels

    rng = random.Random(seed)
    grids, vecs, acts, allowed = [], [], [], []
    right_only = 1 << 2
    for path in paths:
        with open(path, encoding="utf-8") as f:
            demos = [json.loads(line) for line in f if line.strip()]
        for demo in demos:
            level = generate(demo["tier"], demo["seed"]) if "level" not in demo else Level.from_text(demo["level"])
            repeat = demo["repeat"]
            env = JumpNRunEnv(fixed_levels([level]), action_repeat=repeat)
            env.reset(seed=0)
            sim = env.sim
            streak = 0
            for action, labelled in zip(demo["actions"], demo["mask"]):
                if labelled:
                    eq = equivalent_actions(sim, action, repeat)
                    streak = streak + 1 if eq == right_only else 0
                    if not (streak > 2 and rng.random() < thin_flat):
                        obs = env.observe()
                        grids.append(obs["grid"].astype(np.int8))
                        vecs.append(obs["vec"])
                        acts.append(action)
                        allowed.append(eq)
                sim.step(BOT_ACTIONS[action], frames=repeat)
                if sim.status != Status.RUNNING:
                    break
            if len(acts) >= max_samples:
                break
        if len(acts) >= max_samples:
            break
    return dict(grid=np.stack(grids), vec=np.stack(vecs).astype(np.float32),
                action=np.array(acts, np.int64), allowed=np.array(allowed, np.uint8))


def cached_dataset(demo_files, cache: Path, **kwargs):
    """load_dataset with an .npz cache (rebuilding ~1M samples takes a few minutes)."""

    if cache.exists():
        data = np.load(cache)
        return {k: data[k] for k in data.files}
    data = load_dataset(demo_files, **kwargs)
    np.savez_compressed(cache, **data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate solver demonstrations and a verified level pool.")
    parser.add_argument("--out", default="runs/demos")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    parser.add_argument("--scale", type=float, default=1.0, help="multiply the number of levels per tier")
    parser.add_argument("--procs", type=int, default=4)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(tier, seed, args.repeat) for tier, n in enumerate(LEVELS_PER_TIER)
            for seed in range(int(n * args.scale))]
    random.Random(0).shuffle(jobs)  # mix easy and hard levels across processes
    pool: Dict[int, List[int]] = {}
    solved = 0
    with Pool(args.procs) as workers, open(out / "demos.jsonl", "w", encoding="utf-8") as f:
        for i, demo in enumerate(workers.imap_unordered(_work, jobs, chunksize=4)):
            if demo is not None:  # the level is solvable; labels before an unlucky nudge stay valid
                f.write(json.dumps(demo) + "\n")
                pool.setdefault(demo["tier"], []).append(demo["seed"])
                solved += 1
            if (i + 1) % 250 == 0:
                print(f"{i + 1}/{len(jobs)} levels, {solved} demos", flush=True)
    (out / "pool.json").write_text(json.dumps({t: sorted(s) for t, s in sorted(pool.items())}))
    print(f"done: {solved}/{len(jobs)} levels solved -> {out}")


if __name__ == "__main__":
    main()
