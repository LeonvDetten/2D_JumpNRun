"""Behaviour cloning: the student network learns to copy the solver.

    python -m jumpnrun.imitation.bc --demos runs/demos --init models/phase3.zip --out models/phase5_bc.zip

Steps:
    1. imitate the teacher's demos (cross-entropy over the *set* of equivalent actions)
    2. DAgger "rewind on failure": the student plays, and wherever it dies the
       teacher shows how to get out of that situation; imitate those as well
    3. value warm-up: fit only the value head on the student's own returns
       (the teacher's returns would be far too optimistic for the student)
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import torch

from jumpnrun.core.actions import BOT_ACTIONS, DEFAULT_REPEAT
from jumpnrun.core.sim import Simulation, Status
from jumpnrun.imitation.demos import SOLVER_WEIGHT, cached_dataset, load_dataset
from jumpnrun.levelgen.generator import NUM_TIERS, generate
from jumpnrun.levelgen.solver import solve
from jumpnrun.rl.curriculum import load_pool
from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
from jumpnrun.rl.evaluate import eval_level_set, evaluate_levels


# --------------------------------------------------------------------- model
def build_student(init_model: str, repeat: int):
    """Student with the usual PPO network; starts from `init_model`'s weights (its features transfer)."""

    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from jumpnrun.rl.curriculum import CurriculumSource

    env = DummyVecEnv([lambda: JumpNRunEnv(CurriculumSource(0, NUM_TIERS - 1), action_repeat=repeat)])
    model = PPO.load(init_model, env=env, device="cpu")
    model.action_repeat = repeat
    return model


def _obs_tensors(data: Dict[str, np.ndarray], idx: np.ndarray):
    return {"grid": torch.as_tensor(data["grid"][idx], dtype=torch.float32),
            "vec": torch.as_tensor(data["vec"][idx], dtype=torch.float32)}


def bc_loss(policy, obs, allowed: torch.Tensor):
    """-log P(any of the equivalent teacher actions) and accuracy (argmax inside the set)."""

    logits = policy.get_distribution(obs).distribution.logits
    mask = torch.stack([(allowed >> a) & 1 for a in range(logits.shape[1])], dim=1).bool()
    loss = torch.logsumexp(logits, 1) - torch.logsumexp(logits.masked_fill(~mask, -1e9), 1)
    accuracy = mask.gather(1, logits.argmax(1, keepdim=True)).float().mean()
    return loss.mean(), accuracy


def validation_levels(per_tier: int = 8):
    return [level for _, level in eval_level_set(range(4, NUM_TIERS), per_tier)]


def win_rate(model, levels) -> float:
    return float(np.mean([r["won"] for r in evaluate_levels(model, levels)]))


def train_bc(model, data, epochs: int = 5, lr: float = 1e-3, lr_end: float = 1e-4, batch: int = 256,
             val_levels=None, log=print) -> float:
    """Imitation with cosine learning-rate decay; keeps the weights with the best validation win rate."""

    policy = model.policy
    params = list(policy.features_extractor.parameters()) + list(policy.mlp_extractor.policy_net.parameters()) \
        + list(policy.action_net.parameters())
    optimizer = torch.optim.Adam(params, lr=lr)
    n = len(data["action"])
    steps_total = epochs * math.ceil(n / batch)
    step = 0
    best, best_state = -1.0, None
    allowed_all = torch.as_tensor(data["allowed"].astype(np.int64))
    for epoch in range(epochs):
        order = np.random.permutation(n)
        losses, accs = [], []
        start = time.time()
        for i in range(0, n, batch):
            idx = order[i:i + batch]
            for group in optimizer.param_groups:
                group["lr"] = lr_end + 0.5 * (lr - lr_end) * (1 + math.cos(math.pi * step / steps_total))
            loss, acc = bc_loss(policy, _obs_tensors(data, idx), allowed_all[idx])
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 0.5)
            optimizer.step()
            losses.append(loss.item())
            accs.append(acc.item())
            step += 1
        score = win_rate(model, val_levels) if val_levels else float("nan")
        log(f"  BC epoch {epoch + 1}/{epochs}: loss {np.mean(losses):.3f}, accuracy {np.mean(accs):.1%}, "
            f"validation win rate {score:.1%} ({time.time() - start:.0f}s)")
        if val_levels is None or score >= best:
            best = score
            best_state = {k: v.clone() for k, v in policy.state_dict().items()}
    policy.load_state_dict(best_state)
    return best


# -------------------------------------------------------------------- DAgger
def _rescue(job):
    """Rewind a failed student run and let the teacher solve from there."""

    tier, seed, prefix, repeat, show = job
    level = generate(tier, seed)
    sim = Simulation(level)
    for action in prefix:
        sim.step(BOT_ACTIONS[action], frames=repeat)
    if sim.status != Status.RUNNING:
        return None
    result = solve(level, 30_000, action_repeat=repeat, weight=SOLVER_WEIGHT, start=sim)
    if not result.solved:
        return None
    rescue = result.actions[:show]
    return dict(tier=tier, seed=seed, repeat=repeat, actions=list(prefix) + rescue,
                mask=[0] * len(prefix) + [1] * len(rescue), dagger=True)


def dagger_round(model, pool: Dict[int, List[int]], n_levels: int, repeat: int, rng: random.Random,
                 procs: int = 4) -> List[dict]:
    """Student plays pool levels; for each failure the teacher demonstrates a rescue."""

    tiers = [t for t in range(4, NUM_TIERS) if pool.get(t)]
    picks = [(t, rng.choice(pool[t])) for t in rng.choices(tiers, k=n_levels)]
    levels = [generate(t, s) for t, s in picks]
    envs = [JumpNRunEnv(fixed_levels([lv]), action_repeat=repeat) for lv in levels]
    obs = [env.reset(seed=i)[0] for i, env in enumerate(envs)]
    history: List[List[int]] = [[] for _ in envs]
    outcome = [None] * len(envs)
    active = list(range(len(envs)))
    while active:
        batch = {k: np.stack([obs[i][k] for i in active]) for k in ("grid", "vec")}
        actions, _ = model.predict(batch, deterministic=False)
        still = []
        for i, a in zip(active, actions):
            obs[i], _, term, trunc, info = envs[i].step(int(a))
            history[i].append(int(a))
            if term or trunc:
                outcome[i] = info["episode_end"]["outcome"]
            else:
                still.append(i)
        active = still
    jobs = []
    for (tier, seed), hist, out in zip(picks, history, outcome):
        if out != "won":
            back = rng.randint(15, 40)
            jobs.append((tier, seed, hist[:max(0, len(hist) - back)], repeat, 40))
    with Pool(procs) as workers:
        rescues = [r for r in workers.map(_rescue, jobs) if r]
    wins = sum(o == "won" for o in outcome)
    print(f"  DAgger: student won {wins}/{len(envs)}, {len(rescues)} rescues from {len(jobs)} failures", flush=True)
    return rescues


# -------------------------------------------------------------- value warmup
def value_warmup(model, pool, steps: int, gamma: float, repeat: int, epochs: int = 3, log=print) -> None:
    """Fit only the value head on discounted returns of the student's own play."""

    from jumpnrun.rl.curriculum import CurriculumSource

    source = CurriculumSource(0, NUM_TIERS - 1)
    source.weights = [1.0] * NUM_TIERS
    source.pool = pool
    n_envs = 16
    envs = [JumpNRunEnv(source, seed=100 + i, action_repeat=repeat) for i in range(n_envs)]
    obs = [env.reset()[0] for env in envs]
    buffers = [[] for _ in envs]
    grids, vecs, returns = [], [], []
    collected = 0
    while collected < steps:
        batch = {k: np.stack([o[k] for o in obs]) for k in ("grid", "vec")}
        actions, _ = model.predict(batch, deterministic=False)
        for i, a in enumerate(actions):
            o, r, term, trunc, _ = envs[i].step(int(a))
            buffers[i].append((obs[i], r))
            obs[i] = o
            collected += 1
            if term or trunc:
                g = 0.0
                for ob, rew in reversed(buffers[i]):
                    g = rew + gamma * g
                    grids.append(ob["grid"].astype(np.int8))
                    vecs.append(ob["vec"])
                    returns.append(g)
                buffers[i] = []
                obs[i] = envs[i].reset()[0]
    data = dict(grid=np.stack(grids), vec=np.stack(vecs), ret=np.array(returns, np.float32))
    policy = model.policy
    params = list(policy.mlp_extractor.value_net.parameters()) + list(policy.value_net.parameters())
    optimizer = torch.optim.Adam(params, lr=1e-3)
    n = len(data["ret"])
    for epoch in range(epochs):
        order = np.random.permutation(n)
        losses = []
        for i in range(0, n, 1024):
            idx = order[i:i + 1024]
            with torch.no_grad():
                features = policy.extract_features(_obs_tensors(data, idx), policy.vf_features_extractor)
            value = policy.value_net(policy.mlp_extractor.forward_critic(features)).squeeze(1)
            loss = torch.nn.functional.mse_loss(value, torch.as_tensor(data["ret"][idx]))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        log(f"  value warm-up epoch {epoch + 1}/{epochs}: MSE {np.mean(losses):.3f} on {n:,} states")


# ---------------------------------------------------------------------- main
def main() -> None:
    parser = argparse.ArgumentParser(description="Behaviour cloning from solver demos (+ DAgger, value warm-up).")
    parser.add_argument("--demos", default="runs/demos", help="directory with demos.jsonl and pool.json")
    parser.add_argument("--init", default="models/phase3.zip", help="network to start from")
    parser.add_argument("--out", default="models/phase5_bc.zip")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--max-samples", type=int, default=800_000)
    parser.add_argument("--dagger-rounds", type=int, default=1)
    parser.add_argument("--dagger-levels", type=int, default=400)
    parser.add_argument("--value-steps", type=int, default=300_000)
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    demo_dir = Path(args.demos)
    pool = load_pool(demo_dir)
    rng = random.Random(0)
    val = validation_levels()
    log_lines: List[str] = []

    def log(msg):
        print(msg, flush=True)
        log_lines.append(msg)

    model = build_student(args.init, args.repeat)
    log(f"start ({args.init}): validation win rate {win_rate(model, val):.1%} on {len(val)} levels")
    data = cached_dataset([demo_dir / "demos.jsonl"], demo_dir / "dataset.npz", max_samples=args.max_samples)
    log(f"imitation data: {len(data['action']):,} samples")
    train_bc(model, data, epochs=args.epochs, val_levels=val, log=log)

    for round_ in range(args.dagger_rounds):
        rescues = dagger_round(model, pool, args.dagger_levels, args.repeat, rng)
        path = demo_dir / f"dagger_{round_}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r) + "\n" for r in rescues)
        extra = load_dataset([path], max_samples=10**9, thin_flat=0.0)
        log(f"DAgger round {round_ + 1}: {len(extra['action']):,} rescue samples")
        keep = np.random.permutation(len(data["action"]))[:max(1, 4 * len(extra["action"]))]
        mixed = {k: np.concatenate([data[k][keep], extra[k]]) for k in data}
        train_bc(model, mixed, epochs=2, lr=3e-4, lr_end=5e-5, val_levels=val, log=log)

    if args.value_steps:
        value_warmup(model, pool, args.value_steps, args.gamma, args.repeat, log=log)

    model.save(args.out)
    from jumpnrun.rl.modelinfo import write_model_config

    write_model_config(args.out, action_repeat=args.repeat, source="behaviour cloning", init=args.init)
    Path(args.out).with_suffix(".log").write_text("\n".join(log_lines) + "\n")
    log(f"saved {args.out}")


if __name__ == "__main__":
    main()
