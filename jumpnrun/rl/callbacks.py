"""Training callbacks: curriculum updates, metrics, checkpoints, evaluation."""

from __future__ import annotations

import json
import time
from collections import Counter, deque
from pathlib import Path
from typing import List, Tuple

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from jumpnrun.core.level import Level
from jumpnrun.levelgen.generator import NUM_TIERS
from jumpnrun.rl.curriculum import CurriculumTracker


class TrainingMonitor(BaseCallback):
    """Collects episode results from the envs, drives the curriculum, logs metrics.

    TensorBoard names (German explanations in docs/lernen):
        episoden/erfolgsrate        share of won episodes (last 200)
        episoden/fortschritt        how far the bot got (0..1 of the level)
        episoden/tod_grube|tod_gegner|zeit_abgelaufen   how episodes ended
        curriculum/stufe            highest unlocked tier
        curriculum/erfolg_stufe_N   success estimate per tier
    """

    def __init__(self, tracker: CurriculumTracker, run_dir: Path, verbose: int = 0):
        super().__init__(verbose)
        self.tracker = tracker
        self.run_dir = run_dir
        self.recent: deque = deque(maxlen=200)
        self.start_time = time.time()
        self.history_path = run_dir / "episodes.jsonl"
        self._history = None

    def _on_training_start(self) -> None:
        self._history = open(self.history_path, "a", encoding="utf-8")
        self.training_env.env_method("set_tier_weights", self.tracker.weights())

    def _on_step(self) -> bool:
        for info in self.locals["infos"]:
            end = info.get("episode_end")
            if end is None:
                continue
            self.tracker.record(end["tier"], end["won"])
            self.recent.append(end)
            end = dict(end, timesteps=self.num_timesteps)
            self._history.write(json.dumps(end) + "\n")
        return True

    def _on_rollout_end(self) -> None:
        self.training_env.env_method("set_tier_weights", self.tracker.weights())
        if not self.recent:
            return
        outcomes = Counter(e["outcome"] for e in self.recent)
        n = len(self.recent)
        self.logger.record("episoden/erfolgsrate", outcomes["won"] / n)
        self.logger.record("episoden/fortschritt", float(np.mean([e["progress"] for e in self.recent])))
        self.logger.record("episoden/tod_grube", outcomes["died_pit"] / n)
        self.logger.record("episoden/tod_gegner", outcomes["died_enemy"] / n)
        self.logger.record("episoden/zeit_abgelaufen", outcomes["timeout"] / n)
        self.logger.record("curriculum/stufe", self.tracker.unlocked)
        for tier in range(self.tracker.min_tier, self.tracker.unlocked + 1):
            self.logger.record(f"curriculum/erfolg_stufe_{tier}", self.tracker.success[tier])
        self.logger.record("zeit/minuten", (time.time() - self.start_time) / 60)
        self._history.flush()

    def _on_training_end(self) -> None:
        if self._history:
            self._history.close()


class CheckpointSaver(BaseCallback):
    """Saves the model every `every` steps - these checkpoints feed the ghost view and timelapse."""

    def __init__(self, run_dir: Path, every: int, tracker: CurriculumTracker):
        super().__init__()
        self.dir = run_dir / "checkpoints"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.every = every
        self.tracker = tracker
        self._next = 0

    def _on_step(self) -> bool:
        if self.num_timesteps >= self._next:
            self.save()
            self._next = self.num_timesteps + self.every
        return True

    def save(self) -> None:
        path = self.dir / f"step_{self.num_timesteps:010d}.zip"
        self.model.save(str(path))
        state = {"timesteps": self.num_timesteps, "success": self.tracker.success,
                 "episodes": self.tracker.episodes, "unlocked": self.tracker.unlocked}
        (self.dir.parent / "curriculum.json").write_text(json.dumps(state))

    def _on_training_end(self) -> None:
        self.save()


class Evaluator(BaseCallback):
    """Plays fixed, never-trained levels without randomness and logs the success rate."""

    def __init__(self, eval_levels: List[Tuple[str, Level]], every: int, run_dir: Path):
        super().__init__()
        self.eval_levels = eval_levels
        self.every = every
        self.run_dir = run_dir
        self._next = every
        self.best = -1.0

    def _on_step(self) -> bool:
        if self.num_timesteps >= self._next:
            self._next = self.num_timesteps + self.every
            self.evaluate()
        return True

    def evaluate(self) -> float:
        from jumpnrun.rl.evaluate import evaluate_levels

        results = evaluate_levels(self.model, [level for _, level in self.eval_levels])
        groups = {}
        for (group, _), result in zip(self.eval_levels, results):
            groups.setdefault(group, []).append(result)
        for group, items in groups.items():
            self.logger.record(f"eval/erfolg_{group}", float(np.mean([r["won"] for r in items])))
            self.logger.record(f"eval/fortschritt_{group}", float(np.mean([r["progress"] for r in items])))
        overall = float(np.mean([r["won"] for r in results]))
        self.logger.record("eval/erfolg_gesamt", overall)
        if overall >= self.best:
            self.best = overall
            self.model.save(str(self.run_dir / "best_model.zip"))
        return overall
