"""Phase 12 (taken over from the Neustart branch, jumpnrun/rl/neustart_bc.py): a FRESH network, pre-trained by
behaviour cloning before PPO.

    python3 -m jumpnrun.rl.bc12 train --out runs/phase12/bc.zip
    python3 -m jumpnrun.rl.bc12 check runs/phase12/bc.zip      # start check numbers

Changes against the Neustart version: the "neu" source also holds the mirrored demos (runs/demos_spiegel) and the
generator-v11 demos (runs/demos12); data paths under runs/phase12/data; value warm-up on the phase-12 mix.

One solver-BC network is the start of every Neustart arm (they differ only in what happens during PPO, e.g.
online kickstarting from P8 - an offline P8 distillation was dropped: online kickstarting alone brings the KL
to P8 on the student's own states down within ~30k steps, and identical starts keep the arms comparable).

Network: as P8 / phase 10 (GridFeatures for obs v3 - grid 33 columns, overview 40, vec 23 -, pi/vf [128], one
shared extractor, 7 actions), but ReLU heads: with SB3's default Tanh heads a fresh net collapses to "always right"
under behaviour cloning (measured, docs/lernen/daten/neustart_profiling.json).

Data (all rendered with progress="path", i.e. with the training bookkeeping):
    p8      runs/neustart/data/bc_demos4_600k_path.npz   solver demos on generator levels (phase-8 style)
    neu     BC2 cache of runs/demos10 + runs/demos9       solver demos with left+jump on practice levels
    a6      the left+jump samples of "neu", drawn with their own share
Holdout (never trained): runs/demos10/holdout.jsonl, rendered strictly (runs/neustart/data/holdout10_path.npz).
After imitation: value warm-up on the student's own returns with the --path-delta reward on the training mix.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "runs/phase12/data"
NEU_DIRS = ("runs/demos10", "runs/demos9", "runs/demos_spiegel", "runs/demos12")
P8 = ROOT / "models/phase8_final.zip"
DEMOS4 = DATA / "bc_demos4_600k_path.npz"
HOLDOUT = DATA / "holdout10_path.npz"
SHARES = {"p8": 0.50, "neu": 0.45, "a6": 0.05}  # share of every BC batch (phase-8 style >= 50 %, left+jump 5 %)
P8_FLAGS = dict(handmade=("levels/phase1/*.txt", "levels/phase2/*.txt"), handmade_prob=0.05, pool="runs/demos4",
                pool_share=0.4, augment=0.7, start_prob=0.2, start_dirs=("runs/demos4",))


# ----------------------------------------------------------------------------------------------- model and envs
def make_env(seed: int, mix: dict = None, uniform_tiers: bool = True):
    """One training env exactly as train.py builds it for the Neustart arms (obs v3, overview, --path-delta)."""

    from jumpnrun.rl.train import make_env as train_make_env
    import glob

    handmade = sorted(p for pattern in P8_FLAGS["handmade"] for p in glob.glob(str(ROOT / pattern)))
    schedule = [[0, mix]] if mix else None
    env = train_make_env(0, seed, 0, 12, handmade, P8_FLAGS["handmade_prob"], 2, str(ROOT / P8_FLAGS["pool"]),
                         True, P8_FLAGS["start_prob"], tuple(str(ROOT / d) for d in P8_FLAGS["start_dirs"]), 0.0,
                         P8_FLAGS["pool_share"], P8_FLAGS["augment"], False, False, 0.0,
                         env_extra=dict(obs_v3=True, path_delta=True),
                         source_extra=dict(gen_variant="v9", augment_v2=False, mix=schedule))()
    if uniform_tiers:
        env.set_tier_weights([1.0] * 13 + [0.0] * (14 - 13))
    return env


def build_student(seed: int = 0):
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from jumpnrun.rl.policy import GridFeatures

    env = DummyVecEnv([lambda: make_env(seed)])
    model = PPO("MultiInputPolicy", env, n_steps=512, batch_size=1024, n_epochs=4, gamma=0.995, gae_lambda=0.975,
                vf_coef=0.5, ent_coef=0.003, clip_range=0.1, target_kl=0.02, device="cpu", verbose=0, seed=seed,
                policy_kwargs=dict(features_extractor_class=GridFeatures, net_arch=dict(pi=[128], vf=[128]),
                                   share_features_extractor=True, activation_fn=torch.nn.ReLU))
    model.action_repeat = 2
    return model


def obs_tensors(data: dict, idx) -> dict:
    """Cached samples (overview stored as uint8 quarters) -> float tensors."""

    return {"grid": torch.as_tensor(data["grid"][idx], dtype=torch.float32),
            "vec": torch.as_tensor(data["vec"][idx], dtype=torch.float32),
            "overview": torch.as_tensor(data["overview"][idx], dtype=torch.float32) / 4.0}


# ----------------------------------------------------------------------------------------------- imitation
def load_holdout() -> dict:
    from jumpnrun.imitation.demos import cached_dataset

    return cached_dataset([ROOT / "runs/demos10/holdout.jsonl"], HOLDOUT, max_samples=10**7, overview=True,
                          obs_v3=True, progress="path", thin_flat=0.0)


def load_sources():
    from jumpnrun.rl.ppo_demos import bc2_dataset

    src = {"p8": dict(np.load(DEMOS4)), "neu": bc2_dataset([ROOT / d for d in NEU_DIRS], "path", procs=3)}
    src["a6"] = {k: v[src["neu"]["action"] == 6] for k, v in src["neu"].items()}
    return src, load_holdout()


def holdout_metrics(policy, hold: dict) -> dict:
    """Agreement on the never-trained teacher demos (all, and only where "right" is NOT an equivalent action -
    "always right" already scores ~0.9 on all samples), and P(left+jump) on its left+jump states."""

    from jumpnrun.imitation.bc import bc_loss

    allowed = torch.as_tensor(hold["allowed"].astype(np.int64))
    acc, acc_hard, n_hard, p_a6 = [], [], 0, []
    with torch.no_grad():
        for i in range(0, len(hold["action"]), 2048):
            idx = np.arange(i, min(i + 2048, len(hold["action"])))
            obs = obs_tensors(hold, idx)
            logits = policy.get_distribution(obs).distribution.logits
            mask = torch.stack([(allowed[idx] >> a) & 1 for a in range(7)], dim=1).bool()
            hit = mask.gather(1, logits.argmax(1, keepdim=True)).squeeze(1).float()
            acc.append(hit.sum().item())
            hard = ~mask[:, 2]
            acc_hard.append(hit[hard].sum().item())
            n_hard += int(hard.sum())
            a6 = torch.as_tensor(hold["action"][idx] == 6)
            if a6.any():
                p_a6.append(torch.softmax(logits[a6], 1)[:, 6].sum().item())
    n = len(hold["action"])
    n6 = int((hold["action"] == 6).sum())
    return {"holdout": sum(acc) / n, "holdout_ohne_rechts": sum(acc_hard) / max(1, n_hard),
            "holdout_basis_rechts": float(((hold["allowed"] >> 2) & 1).mean()),
            "p_a6_auf_a6": sum(p_a6) / max(1, n6), "n": n, "n_ohne_rechts": n_hard, "n_a6": n6}


def p_a6_old_states(policy) -> float:
    """Mean P(left+jump) on the phase-10 drift states (P8 rollouts on old levels; check only, never trained)."""

    d = np.load(ROOT / "runs/phase10/kl_states.npz")
    out = []
    with torch.no_grad():
        for i in range(0, len(d["vec"]), 2048):
            idx = np.arange(i, min(i + 2048, len(d["vec"])))
            out.append(policy.get_distribution(obs_tensors(d, idx)).distribution.probs[:, 6].sum().item())
    return sum(out) / len(d["vec"])


def train_bc(model, src: dict, shares: dict, steps: int, lr: float = 1e-3, lr_end: float = 1e-4,
             batch: int = 256, log=print, val_every: int = 0, hold=None, val_levels=None) -> dict:
    """Every step: one batch of `batch` samples, drawn from the sources by `shares`, one forward pass;
    loss -log P(any equivalent teacher action) per source, weighted by its share of the batch."""

    from jumpnrun.imitation.bc import win_rate

    policy = model.policy
    params = list(policy.features_extractor.parameters()) + list(policy.mlp_extractor.policy_net.parameters()) \
        + list(policy.action_net.parameters())
    opt = torch.optim.Adam(params, lr=lr)
    names = list(shares)
    counts = np.random.multinomial(batch, [shares[n] for n in names], size=steps)
    best, best_state, hist, best_entry = -1.0, None, [], None
    t0 = time.time()
    run = {n: [] for n in names}
    for step in range(steps):
        for g in opt.param_groups:
            g["lr"] = lr_end + 0.5 * (lr - lr_end) * (1 + math.cos(math.pi * step / steps))
        parts, rows = [], []
        for n, k in zip(names, counts[step]):
            if k:
                idx = np.random.randint(0, len(src[n]["vec"]), k)
                parts.append((n, idx))
                rows.append(obs_tensors(src[n], idx))
        obs = {key: torch.cat([r[key] for r in rows]) for key in rows[0]}
        logits = policy.get_distribution(obs).distribution.logits
        total, at = 0.0, 0
        for n, idx in parts:
            lg = logits[at:at + len(idx)]
            at += len(idx)
            allowed = torch.as_tensor(src[n]["allowed"][idx].astype(np.int64))
            mask = torch.stack([(allowed >> a) & 1 for a in range(lg.shape[1])], dim=1).bool()
            loss = (torch.logsumexp(lg, 1) - torch.logsumexp(lg.masked_fill(~mask, -1e9), 1)).mean()
            total = total + loss * (len(idx) / batch)
            run[n].append(loss.item())
        opt.zero_grad()
        total.backward()
        torch.nn.utils.clip_grad_norm_(params, 0.5)
        opt.step()
        if val_every and ((step + 1) % val_every == 0 or step + 1 == steps):
            m = holdout_metrics(policy, hold)
            m["siege_val"] = win_rate(model, val_levels) if val_levels else float("nan")
            m["schritt"] = step + 1
            m["verlust"] = {n: float(np.mean(v[-val_every:])) for n, v in run.items() if v}
            m["sekunden"] = round(time.time() - t0)
            hist.append(m)
            log(f"  BC {step + 1}/{steps}: holdout {m['holdout']:.3f} (ohne rechts {m['holdout_ohne_rechts']:.3f}), "
                f"P(a6|a6) {m['p_a6_auf_a6']:.2f}, Validierung {m['siege_val']:.1%}, "
                f"Verluste {json.dumps({k: round(v, 3) for k, v in m['verlust'].items()})} [{m['sekunden']}s]")
            score = m["siege_val"] + m["holdout_ohne_rechts"]  # both: playing well and imitating the hard steps
            if score > best:
                best, best_state = score, {k: v.clone() for k, v in policy.state_dict().items()}
                best_entry = m
    if best_state is not None:
        policy.load_state_dict(best_state)
    return {"verlauf": hist, "bester": best_entry if best_state is not None else None}


# ----------------------------------------------------------------------------------------------- value warm-up
def value_warmup(model, steps: int = 300_000, gamma: float = 0.995, n_envs: int = 16, epochs: int = 3,
                 log=print) -> float:
    """Fit only the value head on discounted returns of the student's own play with the --path-delta reward, on
    the training mix (phase-8 levels tiers 0-12 uniform 60 %, practice 20 %, long v10 20 %)."""

    mix = {"p8": 0.6, "skill": 0.2, "v10": 0.1, "hart": 0.1}
    envs = [make_env(1000 + i, mix) for i in range(n_envs)]
    obs = [e.reset(seed=1000 + i)[0] for i, e in enumerate(envs)]
    buffers = [[] for _ in envs]
    keep = {"grid": [], "vec": [], "overview": [], "ret": []}
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
                    keep["grid"].append(ob["grid"].astype(np.int8))
                    keep["vec"].append(ob["vec"])
                    keep["overview"].append(np.rint(ob["overview"] * 4).astype(np.uint8))
                    keep["ret"].append(g)
                buffers[i] = []
                obs[i] = envs[i].reset()[0]
    data = {k: np.stack(v) if k != "ret" else np.array(v, np.float32) for k, v in keep.items()}
    policy = model.policy
    params = list(policy.mlp_extractor.value_net.parameters()) + list(policy.value_net.parameters())
    opt = torch.optim.Adam(params, lr=1e-3)
    n = len(data["ret"])
    mse = float("nan")
    for epoch in range(epochs):
        order = np.random.permutation(n)
        losses = []
        for i in range(0, n, 1024):
            idx = order[i:i + 1024]
            with torch.no_grad():  # shared extractor: only the value head learns here
                features = policy.extract_features(obs_tensors(data, idx), policy.vf_features_extractor)
            value = policy.value_net(policy.mlp_extractor.forward_critic(features)).squeeze(1)
            loss = torch.nn.functional.mse_loss(value, torch.as_tensor(data["ret"][idx]))
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(loss.item())
        mse = float(np.mean(losses))
        log(f"  value warm-up epoch {epoch + 1}/{epochs}: MSE {mse:.3f} on {n:,} states (returns mean "
            f"{data['ret'].mean():.2f})")
    return mse


# ----------------------------------------------------------------------------------------------- main
def main() -> None:
    parser = argparse.ArgumentParser(description="Neustart arm: fresh network, behaviour cloning, value warm-up.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--out", required=True)
    t.add_argument("--steps", type=int, default=16_000, help="BC gradient steps of 256 samples")
    t.add_argument("--lr", type=float, default=1e-3)
    t.add_argument("--val-every", type=int, default=4000)
    t.add_argument("--value-steps", type=int, default=300_000)
    t.add_argument("--threads", type=int, default=2)
    t.add_argument("--seed", type=int, default=0)
    c = sub.add_parser("check")
    c.add_argument("model")
    args = parser.parse_args()

    if args.cmd == "check":
        from jumpnrun.rl.modelinfo import load_model

        model = load_model(ROOT / args.model)
        out = holdout_metrics(model.policy, load_holdout())
        out["p_a6_alte_zustaende"] = p_a6_old_states(model.policy)
        out["action_repeat"] = model.action_repeat
        print(json.dumps(out, indent=1))
        return

    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = []

    def log(msg):
        print(msg, flush=True)
        lines.append(msg)

    from jumpnrun.imitation.bc import validation_levels
    from jumpnrun.rl.modelinfo import write_model_config

    model = build_student(args.seed)
    model.policy.to(memory_format=torch.channels_last)
    src, hold = load_sources()
    log(f"shares {SHARES}, sizes " + ", ".join(f"{k} {len(v['vec']):,}" for k, v in src.items())
        + f", holdout {len(hold['vec']):,}")
    val = validation_levels(8)[:72]  # tiers 4-12 (eval_level_set(4..13) is ordered by tier, 8 levels each)
    res = train_bc(model, src, SHARES, args.steps, lr=args.lr, log=log, val_every=args.val_every,
                   hold=hold, val_levels=val)
    res["siege_val_start"] = res["bester"]["siege_val"] if res.get("bester") else None
    if args.value_steps:
        res["value_mse"] = value_warmup(model, args.value_steps, log=log)
    res["start"] = holdout_metrics(model.policy, hold)
    res["start"]["p_a6_alte_zustaende"] = p_a6_old_states(model.policy)
    model.save(str(out))
    write_model_config(out, action_repeat=2, overview=True, arch="grid", obs_v3=True,
                       source="neustart: fresh net, solver behaviour cloning (+ value warm-up)")
    res["shares"] = SHARES
    out.with_suffix(".bc.json").write_text(json.dumps(res, indent=1))
    out.with_suffix(".log").write_text("\n".join(lines) + "\n")
    log(f"saved {out}: " + json.dumps(res["start"]))


if __name__ == "__main__":
    main()
