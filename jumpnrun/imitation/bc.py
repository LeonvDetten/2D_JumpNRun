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
from jumpnrun.levelgen.solver import solve_auto
from jumpnrun.rl.curriculum import load_pool
from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
from jumpnrun.rl.evaluate import eval_level_set, evaluate_levels
from jumpnrun.rl.modelinfo import env_kwargs


# --------------------------------------------------------------------- model
def build_student(init_model: str, repeat: int, grow: bool = False):
    """Student with the usual PPO network; starts from `init_model`'s weights (its features transfer).

    grow=True: network surgery - the old network plus a new, silent overview-map branch.
    """

    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from jumpnrun.rl.curriculum import CurriculumSource
    from jumpnrun.rl.modelinfo import grow_overview

    overview = grow or "overview" in PPO.load(init_model, device="cpu").observation_space.spaces
    env = DummyVecEnv([lambda: JumpNRunEnv(CurriculumSource(0, NUM_TIERS - 1), action_repeat=repeat,
                                           overview=overview)])
    model = grow_overview(init_model, env) if grow else PPO.load(init_model, env=env, device="cpu")
    model.action_repeat = repeat
    return model


def build_fresh_student(arch: str, repeat: int, separate_vf: bool = True):
    """A new, untrained network with the overview map (phase 7 run B)."""

    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from jumpnrun.rl.curriculum import CurriculumSource
    from jumpnrun.rl.policy import GridFeatures, ImpalaFeatures

    env = DummyVecEnv([lambda: JumpNRunEnv(CurriculumSource(0, NUM_TIERS - 1), action_repeat=repeat, overview=True)])
    extractor = ImpalaFeatures if arch == "impala" else GridFeatures
    model = PPO("MultiInputPolicy", env, n_steps=512, batch_size=1024, n_epochs=4, gamma=0.995, gae_lambda=0.975,
                vf_coef=0.5, ent_coef=0.003, device="cpu", verbose=0,
                policy_kwargs=dict(features_extractor_class=extractor, net_arch=dict(pi=[128], vf=[128]),
                                   share_features_extractor=not separate_vf))
    model.action_repeat = repeat
    return model


def _obs_tensors(data: Dict[str, np.ndarray], idx: np.ndarray):
    obs = {"grid": torch.as_tensor(data["grid"][idx], dtype=torch.float32),
           "vec": torch.as_tensor(data["vec"][idx], dtype=torch.float32)}
    if "overview" in data:  # stored as uint8 in quarters
        obs["overview"] = torch.as_tensor(data["overview"][idx], dtype=torch.float32) / 4.0
    return obs


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
             val_levels=None, log=print, only_overview: bool = False, start_score: float = None) -> float:
    """Imitation with cosine learning-rate decay; keeps the weights with the best validation win rate.

    only_overview=True trains just the new overview branch; everything learned before stays frozen.
    start_score: validation win rate before training - if no epoch beats it, the old weights stay.
    """

    policy = model.policy
    if only_overview:
        params = [p for name, p in policy.features_extractor.named_parameters() if name.startswith("ov_")]
    else:
        params = list(policy.features_extractor.parameters()) \
            + list(policy.mlp_extractor.policy_net.parameters()) + list(policy.action_net.parameters())
    optimizer = torch.optim.Adam(params, lr=lr)
    n = len(data["action"])
    steps_total = epochs * math.ceil(n / batch)
    step = 0
    best, best_state = -1.0, None
    if start_score is not None:
        best, best_state = start_score, {k: v.clone() for k, v in policy.state_dict().items()}
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
        if val_levels is None or score > best or (score == best and start_score is None):
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
    result = solve_auto(level, 30_000, action_repeat=repeat, weight=SOLVER_WEIGHT, start=sim)
    if not result.solved:
        return None
    rescue = result.actions[:show]
    return dict(tier=tier, seed=seed, repeat=repeat, actions=list(prefix) + rescue,
                mask=[0] * len(prefix) + [1] * len(rescue), dagger=True, level=level.to_text())


def dagger_round(model, pool: Dict[int, List[int]], n_levels: int, repeat: int, rng: random.Random,
                 procs: int = 4) -> List[dict]:
    """Student plays pool levels; for each failure the teacher demonstrates a rescue."""

    tiers = [t for t in range(4, NUM_TIERS) if pool.get(t)]
    picks = [(t, rng.choice(pool[t])) for t in rng.choices(tiers, k=n_levels)]
    levels = [generate(t, s) for t, s in picks]
    envs = [JumpNRunEnv(fixed_levels([lv]), **env_kwargs(model)) for lv in levels]
    obs = [env.reset(seed=i)[0] for i, env in enumerate(envs)]
    history: List[List[int]] = [[] for _ in envs]
    outcome = [None] * len(envs)
    active = list(range(len(envs)))
    while active:
        batch = {k: np.stack([obs[i][k] for i in active]) for k in obs[active[0]]}
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
    envs = [JumpNRunEnv(source, seed=100 + i, **env_kwargs(model)) for i in range(n_envs)]
    obs = [env.reset()[0] for env in envs]
    buffers = [[] for _ in envs]
    grids, vecs, overviews, returns = [], [], [], []
    collected = 0
    while collected < steps:
        batch = {k: np.stack([o[k] for o in obs]) for k in obs[0]}
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
                    if "overview" in ob:
                        overviews.append(np.rint(ob["overview"] * 4).astype(np.uint8))
                    returns.append(g)
                buffers[i] = []
                obs[i] = envs[i].reset()[0]
    data = dict(grid=np.stack(grids), vec=np.stack(vecs), ret=np.array(returns, np.float32))
    if overviews:
        data["overview"] = np.stack(overviews)
    policy = model.policy
    params = list(policy.mlp_extractor.value_net.parameters()) + list(policy.value_net.parameters())
    separate = not policy.share_features_extractor
    if separate:  # an own value network (phase 7): its feature layers learn here too
        params += list(policy.vf_features_extractor.parameters())
    optimizer = torch.optim.Adam(params, lr=1e-3)
    n = len(data["ret"])
    for epoch in range(epochs):
        order = np.random.permutation(n)
        losses = []
        for i in range(0, n, 1024):
            idx = order[i:i + 1024]
            with torch.set_grad_enabled(separate):
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
    parser.add_argument("--grow", action="store_true", help="add the overview-map branch to --init (phase 6)")
    parser.add_argument("--only-overview", action="store_true", help="imitation trains only the new branch")
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--val-per-tier", type=int, default=8)
    parser.add_argument("--arch", choices=("grid", "impala"), help="start from a fresh network of this kind")
    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    demo_dir = Path(args.demos)
    pool = load_pool(demo_dir)
    rng = random.Random(0)
    val = validation_levels(args.val_per_tier)
    log_lines: List[str] = []

    def log(msg):
        print(msg, flush=True)
        log_lines.append(msg)

    model = build_fresh_student(args.arch, args.repeat) if args.arch else build_student(args.init, args.repeat,
                                                                                      grow=args.grow)
    overview = "overview" in model.observation_space.spaces
    start_score = win_rate(model, val)
    log(f"start ({args.arch or args.init}): validation win rate {start_score:.1%} on {len(val)} levels")
    files = sorted(demo_dir.glob("demos*.jsonl")) + sorted(demo_dir.glob("dagger_*.jsonl"))
    cache = demo_dir / ("dataset_ov.npz" if overview else "dataset.npz")
    data = cached_dataset(files, cache, max_samples=args.max_samples, overview=overview, shuffle=overview)
    log(f"imitation data: {len(data['action']):,} samples from {len(files)} files")
    best = train_bc(model, data, epochs=args.epochs, lr=args.lr, val_levels=val, log=log,
                    only_overview=args.only_overview, start_score=None if args.arch else start_score)
    log(f"after imitation: validation win rate {best:.1%}")

    for round_ in range(args.dagger_rounds):
        rescues = dagger_round(model, pool, args.dagger_levels, args.repeat, rng)
        path = demo_dir / f"dagger_{round_}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r) + "\n" for r in rescues)
        extra = load_dataset([path], max_samples=10**9, thin_flat=0.0, overview=overview)
        log(f"DAgger round {round_ + 1}: {len(extra['action']):,} rescue samples")
        keep = np.random.permutation(len(data["action"]))[:max(1, 4 * len(extra["action"]))]
        mixed = {k: np.concatenate([data[k][keep], extra[k]]) for k in data}
        train_bc(model, mixed, epochs=2, lr=3e-4, lr_end=5e-5, val_levels=val, log=log,
                 only_overview=args.only_overview)

    if args.value_steps:
        value_warmup(model, pool, args.value_steps, args.gamma, args.repeat, log=log)

    model.save(args.out)
    from jumpnrun.rl.modelinfo import write_model_config

    write_model_config(args.out, action_repeat=args.repeat, source="behaviour cloning",
                       init=args.arch or args.init, overview=overview)
    Path(args.out).with_suffix(".log").write_text("\n".join(log_lines) + "\n")
    log(f"saved {args.out}")


if __name__ == "__main__":
    main()
