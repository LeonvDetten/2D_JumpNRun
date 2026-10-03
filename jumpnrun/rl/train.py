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
import json
import os
import subprocess
import sys
from pathlib import Path

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecMonitor

from jumpnrun.core.actions import DEFAULT_REPEAT
from jumpnrun.core.level import Level
from jumpnrun.levelgen.generator import NUM_TIERS
from jumpnrun.rl.callbacks import CheckpointSaver, EmaWeights, Evaluator, TimeLimit, TrainingMonitor
from jumpnrun.rl.curriculum import CurriculumSource, CurriculumTracker
from jumpnrun.rl.env import JumpNRunEnv
from jumpnrun.rl.evaluate import eval_level_set
from jumpnrun.rl.policy import GridFeatures, ImpalaFeatures


def make_env(rank: int, seed: int, min_tier: int, max_tier: int, handmade_paths, handmade_prob: float,
             action_repeat: int, pool_dir=None, overview: bool = False, start_prob: float = 0.0, start_dirs=(),
             rewind_prob: float = 0.0, pool_share: float = 1.0, augment_prob: float = 0.0, obs_v2: bool = False,
             stuck_death: bool = False, plr: float = 0.0, env_extra=None, source_extra=None):
    def _init():
        handmade = [Level.from_file(p) for p in handmade_paths]
        source = CurriculumSource(min_tier, max_tier, handmade, handmade_prob, pool_dir=pool_dir,
                                  start_prob=start_prob, start_dirs=start_dirs, pool_share=pool_share,
                                  augment_prob=augment_prob, plr=plr, **(source_extra or {}))
        return JumpNRunEnv(source, seed=seed * 1000 + rank, action_repeat=action_repeat, overview=overview,
                           rewind_prob=rewind_prob, obs_v2=obs_v2, stuck_death=stuck_death, **(env_extra or {}))

    return _init


def cosine_schedule(start: float, decay_steps: int, target: int, phase_start: int, end_fraction: float = 0.1):
    """Phase 8: cosine decay from `start` to `end_fraction * start` within `decay_steps` after phase_start.

    Phase 7's linear schedule ran towards the 400M target and was still at 92 % after 34M steps.
    """

    import math

    def schedule(progress_remaining: float) -> float:
        done = (1.0 - progress_remaining) * target - phase_start
        x = min(1.0, max(0.0, done / max(1, decay_steps)))
        return start * (end_fraction + (1 - end_fraction) * 0.5 * (1 + math.cos(math.pi * x)))

    return schedule


def linear_schedule(start: float, end_fraction: float = 0.1, target: int = 0, phase_start: int = 0):
    """Linear decay from `start` to `end_fraction * start`.

    SB3 passes progress_remaining = 1 - num_timesteps / target (absolute step counts, also after a
    resume). With target/phase_start the decay runs over this phase only, so a model that already
    has 28M steps from an earlier phase starts again at the full learning rate.
    """

    def schedule(progress_remaining: float) -> float:
        if target and target > phase_start:
            done = (1.0 - progress_remaining) * target
            progress_remaining = 1.0 - min(1.0, max(0.0, (done - phase_start) / (target - phase_start)))
        return start * (end_fraction + (1 - end_fraction) * progress_remaining)

    return schedule


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
    parser.add_argument("--test-levels", nargs="*", default=["levels/showcase/*.txt"],
                        help="hand-made levels only used for evaluation, never for training")
    parser.add_argument("--resume", help="continue from this model .zip")
    parser.add_argument("--target", type=int, default=0,
                        help="train until this total step count; restarts continue from the newest "
                             "checkpoint in --run (safe to re-run the same command after a crash)")
    parser.add_argument("--checkpoint-every", type=int, default=50_000)
    parser.add_argument("--eval-every", type=int, default=100_000)
    parser.add_argument("--eval-per-tier", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--action-repeat", type=int, default=DEFAULT_REPEAT,
                        help="frames per decision (2 = fine control; models up to phase 3 used 4)")
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--gae", type=float, default=0.975)
    parser.add_argument("--n-steps", type=int, default=512)
    parser.add_argument("--batch", type=int, default=1024)
    parser.add_argument("--clip", type=float, default=0.2)
    parser.add_argument("--ent", type=float, default=0.01)
    parser.add_argument("--target-kl", type=float, default=None)
    parser.add_argument("--unlock-all", action="store_true", help="start with all tiers unlocked")
    parser.add_argument("--pool", help="directory with solver-verified level seeds (see jumpnrun.imitation.demos)")
    parser.add_argument("--demos", help="demo file: adds a decaying behaviour-cloning loss to PPO")
    parser.add_argument("--bc-coef", type=float, default=0.5)
    parser.add_argument("--bc-decay", type=float, default=0.99)
    parser.add_argument("--bc-min", type=float, default=0.02)
    parser.add_argument("--overview", action="store_true", help="observe the coarse overview map (phase 6)")
    parser.add_argument("--start-prob", type=float, default=0.0,
                        help="share of episodes that start in the middle of a teacher's winning run")
    parser.add_argument("--start-dirs", nargs="*", default=[], help="demo directories for --start-prob")
    parser.add_argument("--pool-share", type=float, default=1.0,
                        help="phase 8: probability to draw a stored pool level for tiers with a pool (rest: fresh)")
    parser.add_argument("--obs-v2", action="store_true",
                        help="phase 8: 6 more vector inputs (network surgery on the first start, new inputs at zero)")
    parser.add_argument("--stuck-death", action="store_true", help="phase 8: getting stuck counts as a death (-1)")
    parser.add_argument("--obs-v3", action="store_true",
                        help="phase 9: wider view behind, chest compass, 7th action left+jump (surgery on first start)")
    parser.add_argument("--generator", choices=("v9", "gabel", "v10"), default="v9",
                        help="phase 9: generator variant for fresh levels (gabel = repaired fork; v10 = + channels, Mario)")
    parser.add_argument("--augment-v2", action="store_true",
                        help="phase 9: augmentation V2 (mirror, enemy density, noise, concatenated levels)")
    parser.add_argument("--path-reward", action="store_true",
                        help="phase 9: reward progress along the way to the chest (distance map) instead of new max x")
    parser.add_argument("--plr", type=float, default=0.0,
                        help="phase 8: share of episodes replayed from the Prioritized Level Replay buffer")
    parser.add_argument("--augment", type=float, default=0.0,
                        help="phase 8: share of episodes with an augmented level (jumpnrun/levelgen/augment.py)")
    parser.add_argument("--keep-every", type=int, default=0,
                        help="delete older checkpoints except multiples of this step count (0 = keep all)")
    parser.add_argument("--time-limit-hours", type=float, default=0,
                        help="stop after this much training time, summed over restarts (0 = no limit)")
    parser.add_argument("--rewind-prob", type=float, default=0.0,
                        help="after a failure, restart shortly before it with this probability (phase 7)")
    parser.add_argument("--arch", choices=("grid", "impala"), default="grid", help="network for a new model")
    parser.add_argument("--separate-vf", action="store_true", help="separate feature networks for policy and value")
    parser.add_argument("--ema-every", type=int, default=0, help="save an EMA copy of the weights every N steps")
    parser.add_argument("--ema2-decay", type=float, default=0.0,
                        help="phase 8: a second, slower EMA (e.g. 0.998), saved as ema2_step_*.zip")
    parser.add_argument("--lr-decay-steps", type=int, default=0,
                        help="phase 8: cosine learning rate decay to 10%% over this many steps of the phase")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--watch", action="store_true", help="open the live ghost view next to training")
    parser.add_argument("--watch-level", help="level for --watch (default: a generated one)")
    args = parser.parse_args()

    run_dir = Path(args.run)
    run_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(args.threads or os.cpu_count() or 1)

    handmade_paths = sorted(p for pattern in args.handmade for p in glob.glob(pattern))
    env_fns = [
        make_env(i, args.seed, args.min_tier, args.max_tier, handmade_paths, args.handmade_prob,
                 args.action_repeat, args.pool, args.overview, args.start_prob, tuple(args.start_dirs),
                 args.rewind_prob, args.pool_share, args.augment, args.obs_v2, args.stuck_death, args.plr,
                 env_extra=dict(obs_v3=args.obs_v3, path_reward=args.path_reward),
                 source_extra=dict(gen_variant=args.generator, augment_v2=args.augment_v2))
        for i in range(args.envs)
    ]
    # the game is so fast that the network update dominates; one process is usually best
    vec_env = SubprocVecEnv(env_fns) if args.subproc else DummyVecEnv(env_fns)
    vec_env = VecMonitor(vec_env)

    tracker = CurriculumTracker(args.min_tier, args.max_tier)
    if args.unlock_all:
        tracker.unlocked = args.max_tier
    config_path = run_dir / "config.json"
    old_config = json.loads(config_path.read_text()) if config_path.exists() else {}
    if args.target:
        checkpoints = sorted((run_dir / "checkpoints").glob("step_*.zip"))
        if checkpoints:
            args.resume = str(checkpoints[-1])
            done = int(checkpoints[-1].stem.split("_")[1])
            state_path = run_dir / "curriculum.json"
            if state_path.exists():
                state = json.loads(state_path.read_text())
                n = len(tracker.success)
                tracker.success = (state["success"] + [0.0] * n)[:n]
                tracker.episodes = (state["episodes"] + [0] * n)[:n]
                tracker.unlocked = max(args.min_tier, min(state["unlocked"], args.max_tier))
        else:
            done = int(PPO.load(args.resume, device="cpu").num_timesteps) if args.resume else 0
        args.steps = args.target - done
        # the step count at which this run (phase) began, kept across restarts for the LR schedule
        phase_start = old_config.get("phase_start", done)
        if args.steps <= 0:
            print(f"Target {args.target:,} already reached ({done:,}).")
            return
        print(f"Auto-resume: {done:,} steps done, {args.steps:,} to go (from {args.resume or 'scratch'})")
    else:
        phase_start = 0
    config_path.write_text(json.dumps({"action_repeat": args.action_repeat, "overview": args.overview,
                                       "arch": args.arch, "phase_start": phase_start, "obs_v2": args.obs_v2,
                                       "obs_v3": args.obs_v3, "path_reward": args.path_reward,
                                       "generator": args.generator, "augment_v2": args.augment_v2},
                                      indent=2) + "\n")
    eval_levels = eval_level_set(range(args.min_tier, args.max_tier + 1), args.eval_per_tier)
    # hand-made training levels are "practice grades"; --test-levels are never trained on
    eval_levels += [("training_handgebaut", Level.from_file(p)) for p in handmade_paths]
    eval_levels += [("test_handgebaut", Level.from_file(p))
                    for pattern in args.test_levels for p in sorted(glob.glob(pattern))]

    algo = PPO
    extra = {}
    if args.demos:
        from jumpnrun.rl.ppo_demos import PPOWithDemos

        algo = PPOWithDemos
        extra = dict(demo_path=args.demos, bc_coef=args.bc_coef, bc_decay=args.bc_decay, bc_min=args.bc_min)
    hyper = dict(
        learning_rate=(cosine_schedule(args.lr, args.lr_decay_steps, args.target, phase_start)
                       if args.lr_decay_steps else linear_schedule(args.lr, target=args.target, phase_start=phase_start)),
        n_steps=args.n_steps,
        batch_size=args.batch,
        gamma=args.gamma,
        gae_lambda=args.gae,
        clip_range=args.clip,
        ent_coef=args.ent,
        target_kl=args.target_kl,
    )
    if args.resume and args.obs_v3 and PPO.load(args.resume, device="cpu").observation_space["vec"].shape[0] < 23:
        from jumpnrun.rl.modelinfo import grow_v3

        model = grow_v3(args.resume, vec_env, algo, tensorboard_log=str(run_dir / "tb"), **hyper, **extra)
        print(f"Network surgery v3: wider view behind, compass, 7th action, from {args.resume}")
    elif args.resume and args.obs_v2 and PPO.load(args.resume, device="cpu").observation_space["vec"].shape[0] < 21:
        from jumpnrun.rl.modelinfo import grow_vec

        model = grow_vec(args.resume, vec_env, algo, tensorboard_log=str(run_dir / "tb"), **hyper, **extra)
        print(f"Network surgery: vector input 15 -> 21 (new inputs start at zero), from {args.resume}")
    elif args.resume:
        model = algo.load(args.resume, env=vec_env, device="cpu", tensorboard_log=str(run_dir / "tb"),
                          **hyper, **extra)
    else:
        model = algo(
            "MultiInputPolicy",
            vec_env,
            n_epochs=4,
            vf_coef=0.5,
            **hyper,
            **extra,
            policy_kwargs=dict(features_extractor_class=ImpalaFeatures if args.arch == "impala" else GridFeatures,
                               net_arch=dict(pi=[128], vf=[128]), share_features_extractor=not args.separate_vf,
                               activation_fn=torch.nn.ReLU if args.arch == "impala" else torch.nn.Tanh),
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

    model.action_repeat = args.action_repeat
    callbacks = [
        TrainingMonitor(tracker, run_dir),
        CheckpointSaver(run_dir, args.checkpoint_every, tracker, keep_every=args.keep_every),
        Evaluator(eval_levels, args.eval_every, run_dir),
    ]
    if args.time_limit_hours:
        callbacks.append(TimeLimit(run_dir, args.time_limit_hours))
    if args.ema_every:
        callbacks.append(EmaWeights(run_dir, args.ema_every))
        if args.ema2_decay:
            callbacks.append(EmaWeights(run_dir, args.ema_every, decay=args.ema2_decay, prefix="ema2"))
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
