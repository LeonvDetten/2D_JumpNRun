"""Measure raw simulation speed (frames per second on one CPU core).

    python -m jumpnrun.core.benchmark [level.txt] [--seconds 5]
"""

from __future__ import annotations

import argparse
import random
import time

from jumpnrun.core.actions import ACTION_REPEAT, BOT_ACTIONS
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status


def benchmark(level: Level, seconds: float = 5.0, seed: int = 0) -> float:
    rng = random.Random(seed)
    sim = Simulation(level)
    frames = 0
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        for _ in range(100):
            # bias towards walking right so the run covers the whole level
            action = BOT_ACTIONS[rng.choice((2, 2, 4, 4, 0, 1, 3, 5))]
            sim.step(action, frames=ACTION_REPEAT)
            frames += ACTION_REPEAT
            if sim.status != Status.RUNNING:
                sim.reset()
    return frames / (time.perf_counter() - start)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("level", nargs="?", default="levels/exam/level.txt")
    parser.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args()
    fps = benchmark(Level.from_file(args.level), args.seconds)
    print(f"{fps:,.0f} frames/s  ({fps / ACTION_REPEAT:,.0f} bot steps/s) on one core")


if __name__ == "__main__":
    main()
