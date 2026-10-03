"""CLI entrypoint for PPO training, fine-tuning, and curriculum runs."""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from loguru import logger
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import get_schedule_fn, set_random_seed
from stable_baselines3.common.vec_env import DummyVecEnv

from rl.pirate_game_env import PirateGameEnv
from rl.training_metrics import EpisodeMetricsCallback


def detect_device():
    """Pick the fastest available backend on the current machine."""

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def make_env(
    level_path: str,
    headless: bool,
    max_episode_steps: int,
    frame_skip: int,
    action_preset: str,
    obs_profile: str,
):
    """Create one monitored environment factory for SB3 vectorized wrappers."""

    def _factory():
        env = PirateGameEnv(
            level_path=level_path,
            headless=headless,
            render_mode="none",
            max_episode_steps=max_episode_steps,
            frame_skip=frame_skip,
            action_preset=action_preset,
            obs_profile=obs_profile,
        )
        return Monitor(env)

    return _factory


def build_vec_env(args, level_path: str, num_envs: int, seed: int):
    factories = [
        make_env(
            level_path,
            True,
            args.max_episode_steps,
            args.frame_skip,
            args.action_preset,
            args.obs_profile,
        )
        for _ in range(max(1, int(num_envs)))
    ]
    vec_env = DummyVecEnv(factories)
    vec_env.seed(int(seed))
    return vec_env


def parse_optional_float(value: Optional[str]):
    if value is None:
        return None
    return float(value)


def parse_args():
    parser = argparse.ArgumentParser(description="Train PPO agent for the 2D Jump'n'Run game.")
    parser.add_argument("--level-path", default="level.txt")
    parser.add_argument("--easy-level-path", default="level_easy.txt")
    parser.add_argument("--medium-level-path", default="level_medium.txt")
    parser.add_argument("--timesteps", type=int, default=500_000)
    parser.add_argument("--run-name", default=f"ppo_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    parser.add_argument("--log-dir", default="runs")
    parser.add_argument("--frame-skip", type=int, default=2)
    parser.add_argument(
        "--action-preset",
        default="simple",
        choices=["forward", "simple", "full"],
        help="Action set for training. 'simple' is faster to learn on this level.",
    )
    parser.add_argument(
        "--obs-profile",
        default="balanced",
        choices=["balanced", "legacy"],
        help="Observation semantics for slots 10-13.",
    )
    parser.add_argument("--max-episode-steps", type=int, default=1800)
    parser.add_argument("--eval-freq", type=int, default=10_000)
    parser.add_argument("--eval-episodes", type=int, default=10)
    parser.add_argument("--checkpoint-freq", type=int, default=50_000)
    parser.add_argument("--learning-rate", type=float, default=2.5e-4)
    parser.add_argument("--n-steps", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--num-envs", type=int, default=1, help="Number of parallel environments for training.")
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--ent-coef", type=float, default=0.005)
    parser.add_argument(
        "--ent-coef-easy",
        type=parse_optional_float,
        default=None,
        help="Optional entropy coefficient override for easy curriculum stage.",
    )
    parser.add_argument(
        "--ent-coef-medium",
        type=parse_optional_float,
        default=None,
        help="Optional entropy coefficient override for medium curriculum stage.",
    )
    parser.add_argument(
        "--ent-coef-full",
        type=parse_optional_float,
        default=None,
        help="Optional entropy coefficient override for full curriculum stage.",
    )
    parser.add_argument("--clip-range", type=parse_optional_float, default=0.2)
    parser.add_argument(
        "--game-log-level",
        default="WARNING",
        choices=["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"],
        help="Log level for game-side Loguru logs during training.",
    )
    parser.add_argument(
        "--progress-bar",
        action="store_true",
        help="Show SB3 progress bar (small overhead).",
    )
    parser.add_argument(
        "--curriculum",
        action="store_true",
        help="Train first on easy level, then fine-tune on full level.",
    )
    parser.add_argument(
        "--curriculum-easy-steps",
        type=int,
        default=120_000,
        help="Number of timesteps on easy level before full level.",
    )
    parser.add_argument(
        "--curriculum-medium-steps",
        type=int,
        default=120_000,
        help="Number of timesteps on medium level before full level.",
    )
    parser.add_argument(
        "--load-model",
        default=None,
        help="Optional model path for resume/fine-tuning (e.g. runs/<run>/models/final_model.zip).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Global random seed for reproducible training/evaluation behavior.",
    )
    return parser.parse_args()


def configure_game_logging(level: str):
    logger.remove()
    logger.add(sys.stderr, level=level)


def warn_if_loading_model(args):
    if not args.load_model:
        return
    logger.warning(
        "Loading a saved model: policy weights are reused, and selected PPO hyperparameters "
        "(learning rate / entropy / clip-range / gamma / gae-lambda) are re-applied from CLI."
    )


def seed_everything(seed: int):
    seed = int(seed)
    random.seed(seed)
    np.random.seed(seed)
    set_random_seed(seed, using_cuda=torch.cuda.is_available())


def write_run_config(args, run_dir: Path, device: str):
    """Persist all resolved CLI settings for reproducible reruns and debugging."""

    config_path = run_dir / "config.json"
    config_data = vars(args).copy()
    config_data["device"] = device
    config_data["created_at"] = datetime.now().isoformat(timespec="seconds")
    with open(config_path, "w", encoding="utf-8") as file_obj:
        json.dump(config_data, file_obj, indent=2, sort_keys=True)


def build_callbacks(run_dir: Path, eval_env, eval_freq: int, eval_episodes: int, checkpoint_freq: int):
    """Create eval/checkpoint/custom-metrics callbacks for one stage."""

    checkpoints_dir = run_dir / "checkpoints"
    eval_dir = run_dir / "eval"
    metrics_dir = run_dir / "metrics"
    for path in [checkpoints_dir, eval_dir, metrics_dir]:
        path.mkdir(parents=True, exist_ok=True)

    return CallbackList(
        [
            EvalCallback(
                eval_env,
                best_model_save_path=str(checkpoints_dir),
                log_path=str(eval_dir),
                eval_freq=eval_freq,
                n_eval_episodes=eval_episodes,
                deterministic=True,
                render=False,
            ),
            CheckpointCallback(
                save_freq=checkpoint_freq,
                save_path=str(checkpoints_dir),
                name_prefix="ppo_checkpoint",
                save_replay_buffer=False,
                save_vecnormalize=False,
            ),
            EpisodeMetricsCallback(metrics_dir=str(metrics_dir), filename="episodes.csv", window_size=100),
        ]
    )


def build_model(args, train_env, device: str, tensorboard_dir: Path):
    if args.load_model:
        model = PPO.load(
            args.load_model,
            env=train_env,
            device=device,
            tensorboard_log=str(tensorboard_dir),
        )
        apply_loaded_model_overrides(model, args)
        return model

    return PPO(
        "MlpPolicy",
        train_env,
        verbose=1,
        learning_rate=args.learning_rate,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        ent_coef=args.ent_coef,
        clip_range=args.clip_range,
        device=device,
        tensorboard_log=str(tensorboard_dir),
        seed=args.seed,
    )


def apply_loaded_model_overrides(model: PPO, args):
    """Re-apply selected CLI hyperparameters after loading a checkpoint."""

    lr = float(args.learning_rate)
    model.learning_rate = lr
    model.lr_schedule = get_schedule_fn(lr)
    if getattr(model.policy, "optimizer", None) is not None:
        for group in model.policy.optimizer.param_groups:
            group["lr"] = lr

    model.ent_coef = float(args.ent_coef)
    if args.clip_range is not None:
        model.clip_range = get_schedule_fn(float(args.clip_range))
    model.gamma = float(args.gamma)
    model.gae_lambda = float(args.gae_lambda)

    if int(args.n_steps) != int(model.n_steps):
        logger.warning(
            f"Loaded model keeps n_steps={model.n_steps} (requested {args.n_steps}). "
            "Use matching n_steps when fine-tuning from checkpoints."
        )
    if int(args.batch_size) != int(model.batch_size):
        logger.warning(
            f"Loaded model keeps batch_size={model.batch_size} (requested {args.batch_size}). "
            "Use matching batch_size when fine-tuning from checkpoints."
        )


def apply_stage_entropy(model: PPO, value: Optional[float], stage_name: str):
    if value is None:
        return
    model.ent_coef = float(value)
    logger.info(f"Set ent_coef for stage '{stage_name}' to {model.ent_coef}")


def apply_stage_learning_rate(model: PPO, value: float, stage_name: str):
    lr = float(value)
    model.learning_rate = lr
    model.lr_schedule = get_schedule_fn(lr)
    if getattr(model.policy, "optimizer", None) is not None:
        for group in model.policy.optimizer.param_groups:
            group["lr"] = lr
    logger.info(f"Set learning_rate for stage '{stage_name}' to {lr}")


def train_stage(model: PPO, timesteps: int, callbacks, progress_bar: bool, reset_num_timesteps: bool):
    if timesteps <= 0:
        return
    model.learn(
        total_timesteps=timesteps,
        callback=callbacks,
        progress_bar=progress_bar,
        reset_num_timesteps=reset_num_timesteps,
    )


def main():
    args = parse_args()
    configure_game_logging(args.game_log_level)
    warn_if_loading_model(args)
    run_dir = Path(args.log_dir) / args.run_name
    tensorboard_dir = run_dir / "tb"
    plots_dir = run_dir / "plots"
    models_dir = run_dir / "models"

    for path in [run_dir, tensorboard_dir, plots_dir, models_dir]:
        path.mkdir(parents=True, exist_ok=True)

    device = detect_device()
    seed_everything(args.seed)
    write_run_config(args, run_dir, device)
    model = None
    interrupted = False

    try:
        if args.curriculum:
            # Stage schedule: easy -> medium -> full.
            easy_steps = min(args.curriculum_easy_steps, args.timesteps)
            remaining_after_easy = max(0, args.timesteps - easy_steps)
            medium_steps = min(args.curriculum_medium_steps, remaining_after_easy)
            full_steps = max(0, remaining_after_easy - medium_steps)

            easy_train_env = build_vec_env(args, args.easy_level_path, args.num_envs, args.seed)
            easy_eval_env = build_vec_env(args, args.easy_level_path, 1, args.seed + 1_000)
            easy_callbacks = build_callbacks(
                run_dir / "curriculum_easy",
                easy_eval_env,
                args.eval_freq,
                args.eval_episodes,
                args.checkpoint_freq,
            )
            model = build_model(args, easy_train_env, device, tensorboard_dir / "easy")
            apply_stage_learning_rate(model, args.learning_rate, "easy")
            apply_stage_entropy(
                model,
                args.ent_coef if args.ent_coef_easy is None else args.ent_coef_easy,
                "easy",
            )
            train_stage(model, easy_steps, easy_callbacks, args.progress_bar, reset_num_timesteps=True)
            model.save(str(models_dir / "curriculum_easy_model"))

            if medium_steps > 0:
                medium_train_env = build_vec_env(args, args.medium_level_path, args.num_envs, args.seed + 2_000)
                medium_eval_env = build_vec_env(args, args.medium_level_path, 1, args.seed + 3_000)
                model.set_env(medium_train_env)
                medium_callbacks = build_callbacks(
                    run_dir / "curriculum_medium",
                    medium_eval_env,
                    args.eval_freq,
                    args.eval_episodes,
                    args.checkpoint_freq,
                )
                apply_stage_learning_rate(model, args.learning_rate, "medium")
                apply_stage_entropy(
                    model,
                    args.ent_coef if args.ent_coef_medium is None else args.ent_coef_medium,
                    "medium",
                )
                train_stage(model, medium_steps, medium_callbacks, args.progress_bar, reset_num_timesteps=False)
                model.save(str(models_dir / "curriculum_medium_model"))

            if full_steps > 0:
                full_train_env = build_vec_env(args, args.level_path, args.num_envs, args.seed + 4_000)
                full_eval_env = build_vec_env(args, args.level_path, 1, args.seed + 5_000)
                model.set_env(full_train_env)
                full_callbacks = build_callbacks(
                    run_dir / "curriculum_full",
                    full_eval_env,
                    args.eval_freq,
                    args.eval_episodes,
                    args.checkpoint_freq,
                )
                apply_stage_learning_rate(model, args.learning_rate, "full")
                apply_stage_entropy(
                    model,
                    args.ent_coef if args.ent_coef_full is None else args.ent_coef_full,
                    "full",
                )
                train_stage(model, full_steps, full_callbacks, args.progress_bar, reset_num_timesteps=False)
        else:
            train_env = build_vec_env(args, args.level_path, args.num_envs, args.seed)
            eval_env = build_vec_env(args, args.level_path, 1, args.seed + 1_000)
            callbacks = build_callbacks(run_dir, eval_env, args.eval_freq, args.eval_episodes, args.checkpoint_freq)
            model = build_model(args, train_env, device, tensorboard_dir / "main")
            apply_stage_learning_rate(model, args.learning_rate, "main")
            apply_stage_entropy(model, args.ent_coef, "main")
            train_stage(model, args.timesteps, callbacks, args.progress_bar, reset_num_timesteps=True)
    except KeyboardInterrupt:
        interrupted = True
        print("Training interrupted by user.")

    if model is not None:
        if interrupted:
            interrupted_path = models_dir / "interrupted_model"
            model.save(str(interrupted_path))
            print(f"Interrupted model saved to: {interrupted_path}.zip")
        else:
            model.save(str(models_dir / "final_model"))
            print(f"Training complete. Artifacts in: {run_dir}")

    print(f"Selected device: {device}")
    print(f"TensorBoard log dir: {tensorboard_dir}")


if __name__ == "__main__":
    main()
