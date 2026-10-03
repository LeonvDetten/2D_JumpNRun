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
from jumpnrun.levelgen.generator import GENERATOR_VERSION, generate
from jumpnrun.levelgen.solver import solve_auto

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
    result = solve_auto(level, SOLVER_BUDGET, action_repeat=repeat, weight=SOLVER_WEIGHT)
    if not result.solved:
        return None
    rng = random.Random(f"noise:{tier}:{seed}")
    plan = list(result.actions)
    actions: List[int] = []
    mask: List[int] = []
    # re-planning a long level is expensive: there a nudge is only kept if the plan still wins after it
    long_level = level.cols > 150
    nudges_left = 15 if long_level else 10**9  # every check replays the rest of the plan
    while plan and sim.status == Status.RUNNING and len(actions) < 5000:
        if noise and nudges_left and rng.random() < noise and len(plan) > 10:
            nudges_left -= 1
            backup = (sim.clone(), list(plan), len(actions))
            for _ in range(rng.randint(1, 2)):
                nudge = rng.randrange(len(BOT_ACTIONS))
                sim.step(BOT_ACTIONS[nudge], frames=repeat)
                actions.append(nudge)
                mask.append(0)
                plan.pop(0)
                if sim.status != Status.RUNNING:
                    break
            if long_level and (sim.status != Status.RUNNING or not _plan_still_wins(sim, plan, repeat)):
                sim, plan, n = backup
                del actions[n:], mask[n:]
            elif sim.status != Status.RUNNING:
                break
            elif not _plan_still_wins(sim, plan, repeat):
                replan = solve_auto(level, SOLVER_BUDGET // 2, action_repeat=repeat, weight=SOLVER_WEIGHT,
                                    start=sim)
                if not replan.solved:
                    break
                plan = list(replan.actions)
            if not long_level or len(actions) > backup[2]:
                continue
        action = plan.pop(0)
        sim.step(BOT_ACTIONS[action], frames=repeat)
        actions.append(action)
        mask.append(1)
    return dict(tier=tier, seed=seed, repeat=repeat, actions=actions, mask=mask,
                won=sim.status == Status.WON, solver_steps=len(result.actions), solved=True,
                generator=GENERATOR_VERSION, level=level.to_text())


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


def load_dataset(paths, max_samples: int = 800_000, thin_flat: float = 2 / 3, seed: int = 0,
                 overview: bool = False, shuffle: bool = False):
    """Rebuild (observation, label-set) samples from demo files.

    Returns dict with grid (int8, N x 4 x 13 x 25), vec (float32, N x 15),
    action (int64) and allowed (uint8 bit mask of equivalent actions).
    Long stretches where only "right" makes sense are thinned out.
    With overview=True also `overview` (uint8 quarters, N x 4 x 13 x 32).
    shuffle=True mixes the demos of all files first, so max_samples does not cut off the last file.
    """

    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels

    rng = random.Random(seed)
    grids, vecs, overviews, acts, allowed = [], [], [], [], []
    right_only = 1 << 2
    demos = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            demos += [json.loads(line) for line in f if line.strip()]
    if shuffle:
        rng.shuffle(demos)
    for demo in demos:
        level = generate(demo["tier"], demo["seed"]) if "level" not in demo else Level.from_text(demo["level"])
        repeat = demo["repeat"]
        env = JumpNRunEnv(fixed_levels([level]), action_repeat=repeat, overview=overview)
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
                    if overview:
                        overviews.append(np.rint(obs["overview"] * 4).astype(np.uint8))
                    acts.append(action)
                    allowed.append(eq)
            sim.step(BOT_ACTIONS[action], frames=repeat)
            if sim.status != Status.RUNNING:
                break
        if len(acts) >= max_samples:
            break
    data = dict(grid=np.stack(grids), vec=np.stack(vecs).astype(np.float32),
                action=np.array(acts, np.int64), allowed=np.array(allowed, np.uint8))
    if overview:
        data["overview"] = np.stack(overviews)
    return data


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
    parser.add_argument("--tiers", type=int, nargs="*", help="only these tiers ...")
    parser.add_argument("--counts", type=int, nargs="*", help="... with this many levels each")
    parser.add_argument("--resume", action="store_true", help="keep the demos already in --out")
    parser.add_argument("--merge-pool", help="pool.json whose entries are kept (e.g. the v2 pool)")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    per_tier = dict(zip(args.tiers, args.counts)) if args.tiers else dict(enumerate(LEVELS_PER_TIER))
    jobs = [(tier, seed, args.repeat) for tier, n in per_tier.items() for seed in range(int(n * args.scale))]
    random.Random(0).shuffle(jobs)  # mix easy and hard levels across processes
    demo_file = out / "demos.jsonl"
    done_before = []
    if args.resume and demo_file.exists():  # continue after an interruption: keep finished demos
        with open(demo_file, encoding="utf-8") as f:
            for line in f:
                try:
                    done_before.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # a line cut off by the interruption
        finished = {(d["tier"], d["seed"]) for d in done_before}
        jobs = [j for j in jobs if (j[0], j[1]) not in finished]
        print(f"resume: {len(done_before)} demos kept, {len(jobs)} levels to go", flush=True)
    pool: Dict[int, List[int]] = {}
    if args.merge_pool:
        pool = {int(t): list(v) for t, v in json.loads(Path(args.merge_pool).read_text()).items()
                if int(t) not in per_tier}
    for demo in done_before:
        pool.setdefault(demo["tier"], []).append(demo["seed"])
    solved = len(done_before)
    with Pool(args.procs) as workers, open(demo_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(d) + "\n" for d in done_before)
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
