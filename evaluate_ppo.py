"""Evaluate one PPO checkpoint on the custom game environment."""

import argparse
from collections import Counter
import statistics

from loguru import logger
from stable_baselines3 import PPO

from rl.pirate_game_env import PirateGameEnv

logger.remove()


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate a PPO model over multiple episodes.")
    parser.add_argument("--model-path", required=True, help="Path to PPO .zip model file.")
    parser.add_argument("--level-path", default="level_medium.txt")
    parser.add_argument("--action-preset", default="simple", choices=["forward", "simple", "full"])
    parser.add_argument("--obs-profile", default="balanced", choices=["balanced", "legacy"])
    parser.add_argument("--frame-skip", type=int, default=2)
    parser.add_argument("--max-episode-steps", type=int, default=1800)
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--seed-start", type=int, default=0, help="First seed; each episode uses seed_start + i.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--deterministic", dest="deterministic", action="store_true")
    mode.add_argument("--stochastic", dest="deterministic", action="store_false")
    parser.set_defaults(deterministic=True)
    return parser.parse_args()


def main():
    args = parse_args()
    model = PPO.load(args.model_path, device="cpu")
    env = PirateGameEnv(
        level_path=args.level_path,
        headless=True,
        render_mode="none",
        max_episode_steps=args.max_episode_steps,
        frame_skip=args.frame_skip,
        action_preset=args.action_preset,
        obs_profile=args.obs_profile,
    )

    wins = 0
    deaths = 0
    truncations = 0
    rewards = []
    progress = []
    episode_lengths = []
    action_hist = Counter()
    death_bins = Counter()

    for episode in range(args.episodes):
        obs, _ = env.reset(seed=args.seed_start + episode)
        done = False
        total_reward = 0.0
        info = {}
        while not done:
            action, _ = model.predict(obs, deterministic=args.deterministic)
            action = int(action)
            action_hist[action] += 1
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += float(reward)
            done = terminated or truncated

        wins += int(bool(info.get("is_win")))
        is_dead = bool(info.get("is_dead"))
        deaths += int(is_dead)
        truncations += int((not bool(info.get("is_win"))) and (not is_dead))
        rewards.append(total_reward)
        final_progress = float(info.get("max_progress_x", 0.0))
        progress.append(final_progress)
        episode_lengths.append(int(info.get("step_count", 0)))
        if is_dead:
            death_bins[int(final_progress // 600)] += 1

    env.close()

    total_actions = sum(action_hist.values())
    max_action_share = max((count / max(1, total_actions) for count in action_hist.values()), default=0.0)

    print(f"Model: {args.model_path}")
    print(f"Episodes: {args.episodes}")
    print(
        f"Win rate: {wins / max(1, args.episodes):.3f} "
        f"(wins={wins}, deaths={deaths}, truncations={truncations})"
    )
    print(
        f"Reward mean: {statistics.fmean(rewards):.2f} | "
        f"Progress mean/max: {statistics.fmean(progress):.1f}/{max(progress):.1f} | "
        f"Episode length mean: {statistics.fmean(episode_lengths):.1f}"
    )
    print(f"Action histogram: {dict(sorted(action_hist.items()))}")
    print(f"Max action share: {max_action_share:.3f}")
    print(f"Top death bins (600px): {death_bins.most_common(10)}")


if __name__ == "__main__":
    main()
