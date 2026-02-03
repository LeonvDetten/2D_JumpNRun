import csv
from collections import deque
from pathlib import Path

from stable_baselines3.common.callbacks import BaseCallback


class EpisodeMetricsCallback(BaseCallback):
    def __init__(self, metrics_dir: str, filename: str = "episodes.csv", window_size: int = 100, verbose: int = 0):
        super().__init__(verbose)
        self.metrics_dir = Path(metrics_dir)
        self.filename = filename
        self.window_size = window_size
        self._rows = []
        self._recent_wins = deque(maxlen=window_size)

    def _on_training_start(self) -> None:
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.metrics_dir / self.filename
        if not self.metrics_file.exists():
            self._write_header()

    def _write_header(self):
        with open(self.metrics_file, "w", newline="", encoding="utf-8") as file_obj:
            writer = csv.writer(file_obj)
            writer.writerow(
                [
                    "num_timesteps",
                    "episode_reward",
                    "episode_length",
                    "is_win",
                    "is_dead",
                    "max_progress_x",
                    "goal_distance",
                    "checkpoint_index",
                ]
            )

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        for info in infos:
            episode_info = info.get("episode")
            if episode_info is None:
                continue

            is_win = int(bool(info.get("is_win", False)))
            is_dead = int(bool(info.get("is_dead", False)))
            max_progress_x = float(info.get("max_progress_x", 0.0))
            goal_distance = float(info.get("goal_distance", 0.0))
            checkpoint_index = int(info.get("checkpoint_index", 0))
            reward = float(episode_info.get("r", 0.0))
            length = int(episode_info.get("l", 0))

            row = [
                int(self.num_timesteps),
                reward,
                length,
                is_win,
                is_dead,
                max_progress_x,
                goal_distance,
                checkpoint_index,
            ]
            self._rows.append(row)
            self._recent_wins.append(is_win)

            self.logger.record("rollout/episode_reward", reward)
            self.logger.record("rollout/episode_length", length)
            self.logger.record("rollout/max_progress_x", max_progress_x)
            self.logger.record("rollout/goal_distance", goal_distance)
            self.logger.record("rollout/checkpoint_index", checkpoint_index)
            self.logger.record("rollout/win_rate_100", sum(self._recent_wins) / len(self._recent_wins))

        if self._rows:
            with open(self.metrics_file, "a", newline="", encoding="utf-8") as file_obj:
                writer = csv.writer(file_obj)
                writer.writerows(self._rows)
            self._rows.clear()

        return True
