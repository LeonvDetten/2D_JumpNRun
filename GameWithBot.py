import argparse
from pathlib import Path

from stable_baselines3 import PPO

from rl.pirate_game_env import PirateGameEnv


def parse_args():
    parser = argparse.ArgumentParser(description="Play the game with a trained PPO model.")
    parser.add_argument(
        "--model-path",
        default="runs/ppo_easy_proof/checkpoints/best_model.zip",
        help="Path to a PPO .zip checkpoint (best_model.zip, final_model.zip, ...)",
    )
    parser.add_argument("--level-path", default="level_easy.txt", help="Level file to play")
    parser.add_argument("--action-preset", default="simple", choices=["simple", "full"])
    parser.add_argument("--obs-profile", default="balanced", choices=["balanced", "legacy"])
    parser.add_argument("--frame-skip", type=int, default=2)
    parser.add_argument("--max-episode-steps", type=int, default=1800)
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Auto-restart after episode end.",
    )
    parser.add_argument(
        "--deterministic",
        action="store_true",
        default=True,
        help="Use deterministic action selection.",
    )
    return parser.parse_args()


def run_ppo_bot(args):
    model_path = Path(args.model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    env = PirateGameEnv(
        level_path=args.level_path,
        headless=False,
        render_mode="human",
        max_episode_steps=args.max_episode_steps,
        frame_skip=args.frame_skip,
        action_preset=args.action_preset,
        obs_profile=args.obs_profile,
    )

    model = PPO.load(str(model_path), device="cpu")

    try:
        obs, _ = env.reset()
        while True:
            action, _ = model.predict(obs, deterministic=args.deterministic)
            obs, _, terminated, truncated, info = env.step(action)

            if terminated or truncated:
                status = "WIN" if info.get("is_win") else "DEAD/TRUNCATED"
                print(f"Episode finished: {status}, progress_x={info.get('max_progress_x', 0):.0f}")
                if args.loop:
                    obs, _ = env.reset()
                    continue
                break
    finally:
        env.close()


if __name__ == "__main__":
    run_ppo_bot(parse_args())
