import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(description="Export training metrics to PNG plots.")
    parser.add_argument("--run-dir", default=None, help="Path to one run directory (e.g. runs/ppo_YYYYMMDD_HHMMSS).")
    parser.add_argument("--window", type=int, default=50, help="Rolling window for smoothed curves.")
    return parser.parse_args()


def resolve_run_dir(run_dir: str | None):
    if run_dir is not None:
        return Path(run_dir)
    runs = sorted(Path("runs").glob("ppo_*"))
    if not runs:
        raise FileNotFoundError("No run directories found in ./runs.")
    return runs[-1]


def plot_curve(df, value_col, out_path: Path, title: str, y_label: str, window: int):
    plt.figure(figsize=(10, 5))
    x = range(1, len(df) + 1)
    plt.plot(x, df[value_col], alpha=0.35, label=value_col)
    plt.plot(x, df[value_col].rolling(window=window, min_periods=1).mean(), label=f"rolling_mean_{window}")
    plt.title(title)
    plt.xlabel("Episode")
    plt.ylabel(y_label)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def main():
    args = parse_args()
    run_dir = resolve_run_dir(args.run_dir)
    metrics_file = run_dir / "metrics" / "episodes.csv"
    plots_dir = run_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    if not metrics_file.exists():
        raise FileNotFoundError(f"Metrics file not found: {metrics_file}")

    df = pd.read_csv(metrics_file)
    if df.empty:
        raise ValueError(f"Metrics file is empty: {metrics_file}")

    plot_curve(
        df,
        value_col="episode_reward",
        out_path=plots_dir / "reward_curve.png",
        title="Episode Reward",
        y_label="Reward",
        window=args.window,
    )
    plot_curve(
        df,
        value_col="episode_length",
        out_path=plots_dir / "episode_length.png",
        title="Episode Length",
        y_label="Steps",
        window=args.window,
    )
    plot_curve(
        df,
        value_col="max_progress_x",
        out_path=plots_dir / "progress_x.png",
        title="Max Progress X",
        y_label="X position",
        window=args.window,
    )

    success = df["is_win"].rolling(window=args.window, min_periods=1).mean()
    plt.figure(figsize=(10, 5))
    plt.plot(range(1, len(df) + 1), success)
    plt.ylim(0.0, 1.0)
    plt.title(f"Success Rate (rolling {args.window})")
    plt.xlabel("Episode")
    plt.ylabel("Success Rate")
    plt.tight_layout()
    plt.savefig(plots_dir / "success_rate.png")
    plt.close()

    summary = run_dir / "metrics" / "metrics_summary.md"
    with open(summary, "w", encoding="utf-8") as file_obj:
        file_obj.write("# Training Metrics Summary\n\n")
        file_obj.write(f"- Episodes: {len(df)}\n")
        file_obj.write(f"- Mean reward: {df['episode_reward'].mean():.2f}\n")
        file_obj.write(f"- Mean episode length: {df['episode_length'].mean():.2f}\n")
        file_obj.write(f"- Mean success rate: {df['is_win'].mean():.2%}\n")
        file_obj.write(f"- Mean max progress x: {df['max_progress_x'].mean():.2f}\n")

    print(f"Plots exported to: {plots_dir}")
    print(f"Summary written to: {summary}")


if __name__ == "__main__":
    main()
