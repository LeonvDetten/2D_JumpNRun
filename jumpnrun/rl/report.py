"""Learning report from a training run (works without TensorBoard).

    python -m jumpnrun.rl.report runs/phase1             # table in the terminal
    python -m jumpnrun.rl.report runs/phase1 --png a.png # charts as image
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


def load_episodes(run_dir: Path) -> List[Dict]:
    path = Path(run_dir) / "episodes.jsonl"
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def windows(episodes: List[Dict], size: int) -> List[Dict]:
    """Aggregate consecutive episodes into windows of `size` timesteps."""

    buckets = defaultdict(list)
    for e in episodes:
        buckets[e["timesteps"] // size].append(e)
    rows = []
    for key in sorted(buckets):
        items = buckets[key]
        n = len(items)
        tiers = defaultdict(list)
        for e in items:
            tiers[e["tier"]].append(e["won"])
        rows.append({
            "timesteps": (key + 1) * size,
            "episodes": n,
            "won": sum(e["won"] for e in items) / n,
            "pit": sum(e["outcome"] == "died_pit" for e in items) / n,
            "enemy": sum(e["outcome"] == "died_enemy" for e in items) / n,
            "timeout": sum(e["outcome"] == "timeout" for e in items) / n,
            "progress": sum(e["progress"] for e in items) / n,
            "max_tier": max(e["tier"] for e in items),
            "tiers": {t: sum(v) / len(v) for t, v in sorted(tiers.items())},
        })
    return rows


def print_table(rows: List[Dict]) -> None:
    print(f"{'Schritte':>10} {'Episoden':>8} {'Erfolg':>7} {'Grube':>6} {'Gegner':>7} {'Zeit':>5} "
          f"{'Fortschr.':>9}  Erfolg je Stufe")
    for r in rows:
        per_tier = "  ".join(f"{'H' if t < 0 else t}:{v:.0%}" for t, v in r["tiers"].items())
        print(f"{r['timesteps']:>10,} {r['episodes']:>8} {r['won']:>7.0%} {r['pit']:>6.0%} {r['enemy']:>7.0%} "
              f"{r['timeout']:>5.0%} {r['progress']:>9.0%}  {per_tier}")


def plot(rows: List[Dict], path: str, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = [r["timesteps"] / 1e6 for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    ax = axes[0]
    ax.plot(x, [r["won"] for r in rows], label="im Ziel", color="#2a9d4a", linewidth=2)
    ax.plot(x, [r["progress"] for r in rows], label="Ø Fortschritt", color="#3366cc", linewidth=2)
    ax.plot(x, [r["pit"] for r in rows], label="Grube", color="#d64545", linestyle="--")
    ax.plot(x, [r["enemy"] for r in rows], label="Gegner", color="#e08a1e", linestyle="--")
    ax.plot(x, [r["timeout"] for r in rows], label="Zeit um", color="#888888", linestyle=":")
    ax.set_ylim(0, 1)
    ax.set_xlabel("Trainingsschritte (Millionen)")
    ax.set_title("Wie enden die Episoden?")
    ax.legend(loc="center right", frameon=False)
    ax.grid(alpha=0.3)

    ax = axes[1]
    tiers = sorted({t for r in rows for t in r["tiers"]})
    for t in tiers:
        pts = [(r["timesteps"] / 1e6, r["tiers"][t]) for r in rows if t in r["tiers"]]
        label = "handgebaut" if t < 0 else f"Stufe {t}"
        ax.plot([p[0] for p in pts], [p[1] for p in pts], label=label, linewidth=2)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Trainingsschritte (Millionen)")
    ax.set_title("Erfolgsrate je Schwierigkeitsstufe")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(alpha=0.3)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=110)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    parser.add_argument("--window", type=int, default=100_000)
    parser.add_argument("--png")
    args = parser.parse_args()
    rows = windows(load_episodes(Path(args.run)), args.window)
    print_table(rows)
    if args.png:
        plot(rows, args.png, Path(args.run).name)
        print(f"chart: {args.png}")


if __name__ == "__main__":
    main()
