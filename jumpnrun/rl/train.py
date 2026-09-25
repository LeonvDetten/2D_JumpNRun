"""Train the bot with PPO.

    # phase 1: tiers 0-2, ~2M steps
    python -m jumpnrun.rl.train --run runs/phase1 --max-tier 2 --steps 2000000

    # continue training a model on harder tiers
    python -m jumpnrun.rl.train --run runs/phase2 --resume models/phase1.zip --max-tier 5 --steps 10000000

    # watch live while training (needs a screen)
    python -m jumpnrun.rl.train --run runs/phase1 --max-tier 2 --watch

Outputs in the run directory:
    checkpoints/step_*.zip   snapshots for ghost view and timelapse
    best_model.zip           best model on the evaluation levels
    tb/                      TensorBoard logs  (tensorboard --logdir runs)
    episodes.jsonl           one line per finished training episode
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecMonitor

from jumpnrun.core.level import Level
from jumpnrun.levelgen.generator import NUM_TIERS
from jumpnrun.rl.callbacks import CheckpointSaver, Evaluator, TrainingMonitor
from jumpnrun.rl.curriculum import CurriculumSource, CurriculumTracker
from jumpnrun.rl.env import JumpNRunEnv
from jumpnrun.rl.evaluate import eval_level_set
from jumpnrun.rl.policy import GridFeatures


def make_env(rank: int, seed: int, min_tier: int, max_tier: int, handmade_paths, handmade_prob: float):
    def _init():
        handmade = [Level.from_file(p) for p in handmade_paths]
        source = CurriculumSource(min_tier, max_tier, handmade, handmade_prob)
        return JumpNRunEnv(source, seed=seed * 1000 + rank)

    return _init


def linear_schedule(start: float, end_fraction: float = 0.1):
    return lambda progress_remaining: start * (end_fraction + (1 - end_fraction) * progress_remaining)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the Jump'n'Run bot with PPO.")
    parser.add_argument("--run", required=True, help="output directory, e.g. runs/phase1")
    parser.add_argument("--steps", type=int, default=2_000_000)
    parser.add_argument("--envs", type=int, default=8)
    parser.add_argument("--subproc", action="store_true",
                        help="run envs in separate processes (only worth it on machines with many cores)")
    parser.add_argument("--threads", type=int, default=0, help="torch threads (0 = all cores)")
    parser.add_argument("--min-tier", type=int, default=0)
    parser.add_argument("--max-tier", type=int, default=NUM_TIERS - 1)
    parser.add_argument("--handmade", nargs="*", default=[], help="glob(s) of hand-made training levels")
    parser.add_argument("--handmade-prob", type=float, default=0.25)
    parser.add_argument("--resume", help="continue from this model .zip")
    parser.add_argument("--checkpoint-every", type=int, default=50_000)
    parser.add_argument("--eval-every", type=int, default=100_000)
    parser.add_argument("--eval-per-tier", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--watch", action="store_true", help="open the live ghost view next to training")
    parser.add_argument("--watch-level", help="level for --watch (default: a generated one)")
    args = parser.parse_args()

    run_dir = Path(args.run)
    run_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(args.threads or os.cpu_count() or 1)

    handmade_paths = sorted(p for pattern in args.handmade for p in glob.glob(pattern))
    env_fns = [
        make_env(i, args.seed, args.min_tier, args.max_tier, handmade_paths, args.handmade_prob)
        for i in range(args.envs)
    ]
    # the game is so fast that the network update dominates; one process is usually best
    vec_env = SubprocVecEnv(env_fns) if args.subproc else DummyVecEnv(env_fns)
    vec_env = VecMonitor(vec_env)

    tracker = CurriculumTracker(args.min_tier, args.max_tier)
    eval_levels = eval_level_set(range(args.min_tier, args.max_tier + 1), args.eval_per_tier)
    eval_levels += [(f"handgebaut", Level.from_file(p)) for p in handmade_paths]

    if args.resume:
        model = PPO.load(args.resume, env=vec_env, device="cpu", tensorboard_log=str(run_dir / "tb"))
        model.learning_rate = linear_schedule(args.lr)
        model._setup_lr_schedule()
    else:
        model = PPO(
            "MultiInputPolicy",
            vec_env,
            learning_rate=linear_schedule(args.lr),
            n_steps=256,
            batch_size=512,
            n_epochs=4,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            vf_coef=0.5,
            policy_kwargs=dict(features_extractor_class=GridFeatures, net_arch=dict(pi=[128], vf=[128])),
            tensorboard_log=str(run_dir / "tb"),
            seed=args.seed,
            device="cpu",
            verbose=0,
        )

    watcher = None
    if args.watch:
        cmd = [sys.executable, "-m", "jumpnrun.rl.watch", "--run", str(run_dir), "--live", "--follow"]
        if args.watch_level:
            cmd += ["--level", args.watch_level]
        else:
            cmd += ["--tier", str(args.max_tier)]
        watcher = subprocess.Popen(cmd)

    callbacks = [
        TrainingMonitor(tracker, run_dir),
        CheckpointSaver(run_dir, args.checkpoint_every, tracker),
        Evaluator(eval_levels, args.eval_every, run_dir),
    ]
    print(f"Training {args.steps:,} steps, tiers {args.min_tier}-{args.max_tier}, "
          f"{args.envs} envs, {len(handmade_paths)} hand-made levels -> {run_dir}")
    try:
        model.learn(total_timesteps=args.steps, callback=callbacks, progress_bar=False,
                    reset_num_timesteps=not args.resume, tb_log_name="ppo")
    except KeyboardInterrupt:
        print("Interrupted - saving checkpoint.")
        callbacks[1].save()
    finally:
        model.save(str(run_dir / "final_model.zip"))
        vec_env.close()
        if watcher:
            watcher.terminate()
    print(f"Done. Unlocked tier: {tracker.unlocked}, success per tier: "
          + ", ".join(f"{t}: {tracker.success[t]:.0%}" for t in range(args.min_tier, tracker.unlocked + 1)))


if __name__ == "__main__":
    main()
