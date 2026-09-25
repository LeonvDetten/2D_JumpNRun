"""PPO that keeps looking at the teacher: a decaying behaviour-cloning loss on demo samples.

After every normal PPO update, a few extra gradient steps pull the policy towards
the solver's actions. Their weight starts at `bc_coef` and shrinks by `bc_decay`
per update (never below `bc_min`), so the bot may outgrow its teacher but does
not throw away what it imitated in the first minutes of reinforcement learning.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO

from jumpnrun.imitation.bc import _obs_tensors, bc_loss
from jumpnrun.imitation.demos import cached_dataset

BC_BATCH = 256


class PPOWithDemos(PPO):
    def __init__(self, *args, demo_path=None, bc_coef: float = 0.5, bc_decay: float = 0.99,
                 bc_min: float = 0.02, **kwargs):
        self.demo_path = demo_path
        self.bc_coef = bc_coef
        self.bc_decay = bc_decay
        self.bc_min = bc_min
        self.bc_updates = 0
        self._demos = None
        super().__init__(*args, **kwargs)

    def _excluded_save_params(self):
        return super()._excluded_save_params() + ["_demos"]

    def _load_demos(self):
        if self._demos is None and self.demo_path:
            folder = Path(self.demo_path)
            files = [folder / "demos.jsonl"] + sorted(folder.glob("dagger_*.jsonl"))
            self._demos = cached_dataset(files, folder / "dataset_ppo.npz", max_samples=300_000)
            self._demo_allowed = torch.as_tensor(self._demos["allowed"].astype(np.int64))
        return self._demos

    def train(self) -> None:
        super().train()
        demos = self._load_demos()
        if demos is None:
            return
        coef = max(self.bc_min, self.bc_coef * self.bc_decay ** self.bc_updates)
        self.bc_updates += 1
        n = len(demos["action"])
        batches = max(1, self.n_epochs * (self.n_steps * self.n_envs // self.batch_size) // 2)
        losses, accs = [], []
        self.policy.set_training_mode(True)
        for _ in range(batches):
            idx = np.random.randint(0, n, BC_BATCH)
            loss, acc = bc_loss(self.policy, _obs_tensors(demos, idx), self._demo_allowed[idx])
            self.policy.optimizer.zero_grad()
            (coef * loss).backward()
            torch.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
            self.policy.optimizer.step()
            losses.append(loss.item())
            accs.append(acc.item())
        self.logger.record("vorbild/gewicht", coef)
        self.logger.record("vorbild/verlust", float(np.mean(losses)))
        self.logger.record("vorbild/uebereinstimmung", float(np.mean(accs)))
