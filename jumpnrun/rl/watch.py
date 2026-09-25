"""Watch the bot learn: ghost view of many bots on one level.

    # live window, always the newest checkpoint of a running training
    python -m jumpnrun.rl.watch --run runs/phase1 --live --tier 2

    # one video with a specific model
    python -m jumpnrun.rl.watch --model models/phase1.zip --level levels/showcase/gaps.txt --video out.mp4

    # timelapse: the same level played by checkpoints from the whole training
    python -m jumpnrun.rl.watch --run runs/phase1 --timelapse out.mp4 --tier 2
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import List, Optional

import numpy as np

from jumpnrun.core.actions import ACTION_REPEAT, BOT_ACTIONS
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Status
from jumpnrun.levelgen.generator import generate
from jumpnrun.rl.curriculum import EVAL_SEED_OFFSET
from jumpnrun.rl.env import JumpNRunEnv, fixed_levels


class GhostRun:
    """N bots on the same level, advanced frame by frame together."""

    def __init__(self, level: Level, n: int):
        self.level = level
        self.envs = [JumpNRunEnv(fixed_levels([level])) for _ in range(n)]
        self.obs = [env.reset(seed=i)[0] for i, env in enumerate(self.envs)]
        self.running = [True] * n
        self.deaths: List[tuple] = []
        self.results: List[Optional[dict]] = [None] * n

    @property
    def sims(self):
        return [env.sim for env in self.envs]

    def done(self) -> bool:
        return not any(self.running)

    def play_step(self, model, deterministic: bool = False):
        """One bot decision for every running ghost; yields after each of its frames."""

        active = [i for i, r in enumerate(self.running) if r]
        if not active:
            return
        batch = {key: np.stack([self.obs[i][key] for i in active]) for key in ("grid", "vec")}
        actions, _ = model.predict(batch, deterministic=deterministic)
        before = {i: self.envs[i].sim.max_x for i in active}
        for _ in range(ACTION_REPEAT):
            for i, action in zip(active, actions):
                self.envs[i].sim.step(BOT_ACTIONS[int(action)])
            yield
        for i, action in zip(active, actions):
            obs, _, terminated, truncated, info = self.envs[i].finish_step(int(action), before[i])
            self.obs[i] = obs
            if terminated or truncated:
                self.running[i] = False
                self.results[i] = info["episode_end"]
                sim = self.envs[i].sim
                if sim.status in (Status.DIED_PIT, Status.DIED_ENEMY):
                    self.deaths.append((sim.player.x + sim.player.w // 2, sim.player.y + sim.player.h // 2))


def latest_checkpoint(run_dir: Path) -> Optional[Path]:
    checkpoints = sorted((run_dir / "checkpoints").glob("step_*.zip"))
    return checkpoints[-1] if checkpoints else None


def checkpoint_steps(path: Path) -> int:
    return int(path.stem.split("_")[1])


def pick_timelapse(checkpoints: List[Path], count: int) -> List[Path]:
    """Checkpoints spread so the early (fast learning) part gets more clips."""

    if len(checkpoints) <= count:
        return checkpoints
    last = checkpoint_steps(checkpoints[-1])
    fractions = [0.0] + [(i / (count - 1)) ** 2 for i in range(1, count)]
    chosen = []
    for f in fractions:
        target = f * last
        best = min(checkpoints, key=lambda c: abs(checkpoint_steps(c) - target))
        if best not in chosen:
            chosen.append(best)
    return chosen


def run_episode(model, level: Level, ghosts: int, view, surface, title: str, subtitle: str,
                on_frame, speed: int = 2, max_seconds: float = 60.0, deterministic: bool = False):
    """Play one ghost episode, calling on_frame(surface) for every rendered frame."""

    run = GhostRun(level, ghosts)
    frame = 0
    max_frames = int(max_seconds * 30)
    while not run.done() and frame < max_frames:
        for _ in run.play_step(model, deterministic):
            frame += 1
            if frame % speed == 0:
                view.draw(surface, run.sims, run.running, run.deaths, title, subtitle)
                if on_frame(surface) is False:
                    return run
    for _ in range(30):  # hold the final picture for a moment
        view.draw(surface, run.sims, run.running, run.deaths, title, subtitle)
        on_frame(surface)
    return run


def resolve_level(args) -> Level:
    if args.level:
        return Level.from_file(args.level)
    return generate(args.tier, EVAL_SEED_OFFSET + args.seed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ghost view of the bot.")
    parser.add_argument("--run", help="training run directory (uses its checkpoints)")
    parser.add_argument("--model", help="a single model .zip")
    parser.add_argument("--level", help="level file (default: generated level of --tier/--seed)")
    parser.add_argument("--tier", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ghosts", type=int, default=32)
    parser.add_argument("--speed", type=int, default=2, help="render every n-th frame (2 = double speed)")
    parser.add_argument("--live", action="store_true", help="window, newest checkpoint, endless")
    parser.add_argument("--video", help="write one episode to this mp4")
    parser.add_argument("--timelapse", help="write a clip per checkpoint to this mp4")
    parser.add_argument("--clips", type=int, default=8, help="number of checkpoints in the timelapse")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--follow", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")
    import pygame
    from stable_baselines3 import PPO

    from jumpnrun.core.constants import SCREEN_H, SCREEN_W
    from jumpnrun.render.ghosts import GhostView
    from jumpnrun.render.video import VideoWriter, init_headless

    level = resolve_level(args)
    level_label = args.level or f"Stufe {args.tier} (Seed {args.seed})"

    if args.live:
        pygame.init()
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Jump'n'Run - Geister-Ansicht")
        clock = pygame.time.Clock()
        view = GhostView(level)

        def show(surface):
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    raise SystemExit
            screen.blit(surface, (0, 0))
            pygame.display.update()
            clock.tick(30)

        surface = pygame.Surface((SCREEN_W, SCREEN_H))
        while True:
            path = Path(args.model) if args.model else latest_checkpoint(Path(args.run))
            if path is None:
                surface.fill((14, 12, 34))
                show(surface)
                time.sleep(1)
                continue
            model = PPO.load(str(path), device="cpu")
            steps = checkpoint_steps(path) if path.stem.startswith("step_") else 0
            run_episode(model, level, args.ghosts, view, surface,
                        f"Nach {steps:,} Trainingsschritten".replace(",", "."), level_label, show, args.speed)
        return

    surface = init_headless()
    view = GhostView(level)
    if args.video:
        model_path = args.model or str(latest_checkpoint(Path(args.run)))
        model = PPO.load(model_path, device="cpu")
        with VideoWriter(args.video) as video:
            run = run_episode(model, level, args.ghosts, view, surface, Path(model_path).stem, level_label,
                              video.add, args.speed, deterministic=args.deterministic)
        wins = sum(1 for r in run.results if r and r["won"])
        print(f"{args.video}: {wins}/{args.ghosts} im Ziel")

    if args.timelapse:
        checkpoints = pick_timelapse(sorted((Path(args.run) / "checkpoints").glob("step_*.zip")), args.clips)
        with VideoWriter(args.timelapse) as video:
            for path in checkpoints:
                model = PPO.load(str(path), device="cpu")
                steps = checkpoint_steps(path)
                title = "Untrainiert" if steps < 1000 else f"Nach {steps:,} Trainingsschritten".replace(",", ".")
                run = run_episode(model, level, args.ghosts, view, surface, title, level_label,
                                  video.add, args.speed, max_seconds=30)
                wins = sum(1 for r in run.results if r and r["won"])
                print(f"  {path.name}: {wins}/{args.ghosts} im Ziel")
        print(f"timelapse: {args.timelapse}")


if __name__ == "__main__":
    main()
