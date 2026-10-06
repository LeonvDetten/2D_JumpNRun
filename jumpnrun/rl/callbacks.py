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
from jumpnrun.rl.curriculum import MID_START_TIER, REWIND_TIER, CurriculumTracker


class TrainingMonitor(BaseCallback):
    """Collects episode results from the envs, drives the curriculum, logs metrics.

    TensorBoard names (German explanations in docs/lernen):
        episoden/erfolgsrate        share of won episodes (last 200)
        episoden/fortschritt        how far the bot got (0..1 of the level)
        episoden/tod_grube|tod_gegner|zeit_abgelaufen   how episodes ended
        curriculum/stufe            highest unlocked tier
        curriculum/erfolg_stufe_N   success estimate per tier
    """

    def __init__(self, tracker: CurriculumTracker, run_dir: Path, verbose: int = 0, p8_only: bool = False):
        super().__init__(verbose)
        self.tracker = tracker
        # Neustart arm: only episodes of the phase-8 source steer the tier curriculum (v10 levels report tiers
        # 10-13 as well and would mix into the success estimates of tiers 10-12)
        self.p8_only = p8_only
        self.run_dir = run_dir
        self.recent: deque = deque(maxlen=200)
        self.mid_starts: deque = deque(maxlen=200)  # episodes started in the middle of a level
        self.rewinds: deque = deque(maxlen=200)  # episodes restarted shortly before a failure
        self.start_time = time.time()
        self.history_path = run_dir / "episodes.jsonl"
        self._history = None

    def _on_training_start(self) -> None:
        self._history = open(self.history_path, "a", encoding="utf-8")
        self.training_env.env_method("set_tier_weights", self.tracker.weights())
        self._send_skill_state()

    def _send_skill_state(self) -> None:
        skill = getattr(self.tracker, "skill", None)
        if skill is not None:
            self.training_env.env_method("set_skill_state", skill.level, skill.p())

    def _on_step(self) -> bool:
        for info in self.locals["infos"]:
            end = info.get("episode_end")
            if end is None:
                continue
            if not self.p8_only or end.get("mix") in (None, "p8"):
                self.tracker.record(end["tier"], end["won"])
            skill = getattr(self.tracker, "skill", None)
            if skill is not None and end.get("kind") and end["tier"] == -4 and end.get("rewind_depth", 0) == 0:
                skill.record(end["kind"], end["difficulty"], end["won"])  # fresh practice episodes only
            if end["tier"] == MID_START_TIER:
                self.mid_starts.append(end)
            elif end["tier"] == REWIND_TIER:
                self.rewinds.append(end)
            else:
                self.recent.append(end)
            end = dict(end, timesteps=self.num_timesteps)
            self._history.write(json.dumps(end) + "\n")
        return True

    def _on_rollout_end(self) -> None:
        self.training_env.env_method("set_tier_weights", self.tracker.weights())
        self._send_skill_state()
        skill = getattr(self.tracker, "skill", None)
        if skill is not None:
            for kind, d in skill.level.items():
                self.logger.record(f"uebung/stufe_{kind}", d)
        if not self.recent:
            return
        outcomes = Counter(e["outcome"] for e in self.recent)
        n = len(self.recent)
        self.logger.record("episoden/erfolgsrate", outcomes["won"] / n)
        self.logger.record("episoden/fortschritt", float(np.mean([e["progress"] for e in self.recent])))
        self.logger.record("episoden/tod_grube", outcomes["died_pit"] / n)
        self.logger.record("episoden/tod_gegner", outcomes["died_enemy"] / n)
        self.logger.record("episoden/zeit_abgelaufen", outcomes["timeout"] / n)
        if self.mid_starts:
            self.logger.record("episoden/start_mitte_erfolg",
                               float(np.mean([e["won"] for e in self.mid_starts])))
        if self.rewinds:
            self.logger.record("episoden/rueckspul_erfolg", float(np.mean([e["won"] for e in self.rewinds])))
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

    def __init__(self, run_dir: Path, every: int, tracker: CurriculumTracker, keep_every: int = 0,
                 keep_last: int = 5):
        super().__init__()
        self.dir = run_dir / "checkpoints"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.every = every
        self.keep_every = keep_every
        self.keep_last = keep_last
        self.tracker = tracker
        self._next = 0

    def _on_step(self) -> bool:
        if self.num_timesteps >= self._next:
            self.save()
            # on the grid of `every` (a save at an odd step, e.g. on SIGTERM, must not shift all later
            # checkpoints: the milestone evaluator takes the first one within 50k after each whole million)
            self._next = (self.num_timesteps // self.every + 1) * self.every
        return True

    def save(self) -> None:
        path = self.dir / f"step_{self.num_timesteps:010d}.zip"
        self.model.save(str(path))
        state = {"timesteps": self.num_timesteps, "success": self.tracker.success,
                 "episodes": self.tracker.episodes, "unlocked": self.tracker.unlocked}
        if getattr(self.tracker, "skill", None) is not None:
            state["skill"] = self.tracker.skill.state()
        (self.dir.parent / "curriculum.json").write_text(json.dumps(state))
        if self.keep_every:  # long runs: keep every keep_every-th checkpoint plus the newest few
            checkpoints = sorted(self.dir.glob("step_*.zip"))
            for old in checkpoints[:-self.keep_last]:
                if int(old.stem.split("_")[1]) % self.keep_every >= self.every:
                    old.unlink()

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


class TimeLimit(BaseCallback):
    """Stops training after `hours` of training time, summed over restarts (run_dir/seconds_used)."""

    def __init__(self, run_dir: Path, hours: float):
        super().__init__()
        self.path = run_dir / "seconds_used"
        self.limit = hours * 3600
        self.before = float(self.path.read_text()) if self.path.exists() else 0.0
        self.start = time.time()
        self._last_write = 0.0

    def used(self) -> float:
        return self.before + time.time() - self.start

    def _on_step(self) -> bool:
        now = time.time()
        if now - self._last_write > 30:
            self._last_write = now
            self.path.write_text(f"{self.used():.0f}")
        if self.used() >= self.limit:
            self.path.write_text(f"{self.used():.0f}")
            (self.path.parent / "STOP").write_text(f"time limit of {self.limit / 3600:.0f} h reached\n")
            return False
        return True


class EmaWeights(BaseCallback):
    """Keeps an exponential moving average of the policy weights and saves it next to the checkpoints.

    PPO's policy drifts a little with every update; on long levels that shows as big swings between
    milestones. The average of the recent weights is often steadier. Saved as ema_step_*.zip every
    `every` steps (same format as normal checkpoints, so every tool can load it).
    """

    def __init__(self, run_dir: Path, every: int = 1_000_000, decay: float = 0.99, prefix: str = "ema"):
        super().__init__()
        self.dir = run_dir / "checkpoints"
        self.prefix = prefix
        self.path = run_dir / f"{prefix}_weights.pt"
        self.every = every
        self.decay = decay
        self.ema = None
        self._next = 0

    def _on_training_start(self) -> None:
        import torch

        params = self.model.policy.state_dict()
        if self.path.exists():
            saved = torch.load(self.path, map_location="cpu")
            if saved.keys() == params.keys():
                self.ema = saved
        if self.ema is None:
            self.ema = {k: v.detach().clone().float() for k, v in params.items()}
        # a restart exactly at a multiple (killed between checkpoint and EMA save) still writes that EMA
        self._next = max(self.every, -(-self.num_timesteps // self.every) * self.every)

    def _on_rollout_start(self) -> None:  # called after every PPO update
        import torch

        if self.ema is None:
            return
        with torch.no_grad():
            for k, v in self.model.policy.state_dict().items():
                if v.dtype.is_floating_point:
                    self.ema[k].mul_(self.decay).add_(v.float(), alpha=1 - self.decay)
                else:
                    self.ema[k].copy_(v)

    def _on_step(self) -> bool:
        if self.num_timesteps >= self._next:
            self._next += self.every
            self.save()
        return True

    def save(self) -> None:
        import torch

        policy = self.model.policy
        current = {k: v.detach().clone() for k, v in policy.state_dict().items()}
        policy.load_state_dict(self.ema)
        try:
            self.model.save(str(self.dir / f"{self.prefix}_step_{self.num_timesteps:010d}.zip"))
        finally:  # a SIGTERM in between must not leave the EMA weights in the training policy
            policy.load_state_dict(current)
        torch.save(self.ema, self.path)

    def _on_training_end(self) -> None:
        import torch

        if self.ema is not None:
            torch.save(self.ema, self.path)


class CriticWarmup(BaseCallback):
    """Phase 10: for the first `steps` after the phase start only the value branch learns.

    After the network surgery the optimizer is fresh and the reward (way distance) is new, so the critic's first
    estimates are poor; letting it settle before the policy moves avoids a bad first push. The behaviour-cloning
    steps pause meanwhile (model.bc_paused).
    """

    def __init__(self, phase_start: int, steps: int):
        super().__init__()
        self.until = phase_start + steps
        self.active = None

    def _set(self, frozen: bool) -> None:
        policy = self.model.policy
        for name, p in policy.named_parameters():
            if frozen:
                p.requires_grad_("value_net" in name)
            else:
                p.requires_grad_(True)
        self.model.bc_paused = frozen
        self.active = frozen

    def _on_training_start(self) -> None:
        self._set(self.model.num_timesteps < self.until)

    def _on_step(self) -> bool:
        if self.active and self.num_timesteps >= self.until:
            self._set(False)
        return True


class MixScheduler(BaseCallback):
    """Phase 10: switches the mix stage of every env's MixSource by absolute steps since the phase start."""

    def __init__(self, phase_start: int, stage_starts):
        super().__init__()
        self.phase_start = phase_start
        self.starts = sorted(int(x) for x in stage_starts)
        self.stage = None

    def _current(self) -> int:
        rel = self.model.num_timesteps - self.phase_start
        return max(i for i, s in enumerate(self.starts) if rel >= s) if rel >= self.starts[0] else 0

    def _on_training_start(self) -> None:
        self.stage = self._current()
        self.training_env.env_method("set_mix_stage", self.stage)

    def _on_step(self) -> bool:
        if self.n_calls % 256 == 0:
            idx = self._current()
            if idx != self.stage:
                self.stage = idx
                self.training_env.env_method("set_mix_stage", idx)
        return True
