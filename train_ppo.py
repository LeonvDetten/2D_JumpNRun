import argparse
from datetime import datetime
from pathlib import Path

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from pirate_game_env import PirateGameEnv
from training_metrics import EpisodeMetricsCallback


def detect_device():
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def make_env(level_path: str, headless: bool, max_episode_steps: int, frame_skip: int):
    def _factory():
        env = PirateGameEnv(
            level_path=level_path,
            headless=headless,
            render_mode="none",
            max_episode_steps=max_episode_steps,
            frame_skip=frame_skip,
        )
        return Monitor(env)

    return _factory


def parse_args():
    parser = argparse.ArgumentParser(description="Train PPO agent for the 2D Jump'n'Run game.")
    parser.add_argument("--level-path", default="level.txt")
    parser.add_argument("--timesteps", type=int, default=500_000)
    parser.add_argument("--run-name", default=f"ppo_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    parser.add_argument("--log-dir", default="runs")
    parser.add_argument("--frame-skip", type=int, default=4)
    parser.add_argument("--max-episode-steps", type=int, default=2500)
    parser.add_argument("--eval-freq", type=int, default=10_000)
    parser.add_argument("--eval-episodes", type=int, default=10)
    parser.add_argument("--checkpoint-freq", type=int, default=50_000)
    return parser.parse_args()


def main():
    args = parse_args()
    run_dir = Path(args.log_dir) / args.run_name
    checkpoints_dir = run_dir / "checkpoints"
    eval_dir = run_dir / "eval"
    tensorboard_dir = run_dir / "tb"
    metrics_dir = run_dir / "metrics"
    plots_dir = run_dir / "plots"
    models_dir = run_dir / "models"

    for path in [run_dir, checkpoints_dir, eval_dir, tensorboard_dir, metrics_dir, plots_dir, models_dir]:
        path.mkdir(parents=True, exist_ok=True)

    train_env = DummyVecEnv(
        [make_env(args.level_path, True, args.max_episode_steps, args.frame_skip)]
    )
    eval_env = DummyVecEnv(
        [make_env(args.level_path, True, args.max_episode_steps, args.frame_skip)]
    )

    device = detect_device()
    model = PPO(
        "MlpPolicy",
        train_env,
        verbose=1,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=256,
        gamma=0.995,
        gae_lambda=0.95,
        ent_coef=0.01,
        device=device,
        tensorboard_log=str(tensorboard_dir),
    )

    callbacks = CallbackList(
        [
            EvalCallback(
                eval_env,
                best_model_save_path=str(checkpoints_dir),
                log_path=str(eval_dir),
                eval_freq=args.eval_freq,
                n_eval_episodes=args.eval_episodes,
                deterministic=True,
                render=False,
            ),
            CheckpointCallback(
                save_freq=args.checkpoint_freq,
                save_path=str(checkpoints_dir),
                name_prefix="ppo_checkpoint",
                save_replay_buffer=False,
                save_vecnormalize=False,
            ),
            EpisodeMetricsCallback(metrics_dir=str(metrics_dir), window_size=100),
        ]
    )

    model.learn(total_timesteps=args.timesteps, callback=callbacks)
    model.save(str(models_dir / "final_model"))

    print(f"Training complete. Artifacts in: {run_dir}")
    print(f"Selected device: {device}")
    print(f"TensorBoard log dir: {tensorboard_dir}")


if __name__ == "__main__":
    main()
