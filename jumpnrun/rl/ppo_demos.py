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


def bc2_dataset(dirs) -> dict:
    """Phase 10: the BC2 samples of all demos*.jsonl in `dirs`, cached by a hash of the file list and sizes
    (prebuilt in the demo window: `python3 -c "from jumpnrun.rl.ppo_demos import bc2_dataset; bc2_dataset([...])"`)."""

    import hashlib

    files = sorted(f for d in dirs for f in Path(d).glob("demos*.jsonl"))
    key = hashlib.sha256("|".join(f"{f}:{f.stat().st_size}" for f in files).encode()).hexdigest()[:16]
    cache = Path(dirs[0]) / f"bc2_{key}.npz"
    return dict(cached_dataset(files, cache, max_samples=10**7, overview=True, shuffle=True, obs_v3=True))


class PPOWithDemos(PPO):
    def __init__(self, *args, demo_path=None, bc_coef: float = 0.5, bc_decay: float = 0.99,
                 bc_min: float = 0.02, demo2_paths=None, bc2_plan=None, bc2_a6_share: float = 0.05,
                 phase10_start: int = 0, anchor_path=None, anchor_eps: float = 0.02, anchor_coef: float = 0.1,
                 anchor_target_kl: float = 0.02, teacher_path=None, teacher_plan=None, **kwargs):
        self.demo_path = demo_path
        # phase 10: a second demo stream (BC2: teacher demos with left+jump on practice levels) with its own weight
        # by stage ([[steps since phase10_start, coef], ...]); left+jump samples drawn with share bc2_a6_share
        self.demo2_paths = demo2_paths
        self.bc2_plan = bc2_plan
        self.bc2_a6_share = bc2_a6_share
        self.phase10_start = phase10_start
        self._demos2 = None
        # phase 10 anchor (only active by rule): KL(P8 || policy) on states of won phase-8 episodes, over the six
        # old actions with the policy renormalised to them - left+jump is neither forbidden nor pushed (a fixed eps
        # share for it pulled left+jump up wherever the policy had ~0 there); the weight adapts so the measured
        # KL stays near anchor_target_kl. anchor_eps is kept for loading old models and is not used.
        self.anchor_path = anchor_path
        self.anchor_eps = anchor_eps
        self.anchor_coef = anchor_coef
        self.anchor_target_kl = anchor_target_kl
        self._anchor = None
        # phase 10 D: P8 as a teacher on the student's OWN rollout states of phase-8 levels (KL over the six old
        # actions, student renormalised), weight by plan [[steps since phase10_start, coef], ...] linear in between
        self.teacher_path = teacher_path
        self.teacher_plan = teacher_plan
        self._teacher = None
        self.bc_coef = bc_coef
        self.bc_decay = bc_decay
        self.bc_min = bc_min
        self.bc_updates = 0
        self._demos = None
        super().__init__(*args, **kwargs)

    def _excluded_save_params(self):
        return super()._excluded_save_params() + ["_demos", "_demos2", "_anchor", "_teacher", "_p8_mask", "bc_paused"]

    def _load_demos(self):
        if self._demos is None and self.demo_path:
            folder = Path(self.demo_path)
            files = sorted(folder.glob("demos*.jsonl")) + sorted(folder.glob("dagger_*.jsonl"))
            overview = "overview" in self.observation_space.spaces
            v3 = self.observation_space["vec"].shape[0] >= 23  # phase 9: wider view, the demos are re-rendered
            cache = folder / ("dataset_ppo_ov3.npz" if v3 else "dataset_ppo_ov.npz" if overview else "dataset_ppo.npz")
            extra = {"obs_v3": True} if v3 else {}
            self._demos = cached_dataset(files, cache, max_samples=300_000, overview=overview, shuffle=overview,
                                         **extra)
            self._demo_allowed = torch.as_tensor(self._demos["allowed"].astype(np.int64))
            want = self.observation_space["vec"].shape[0]
            have = self._demos["vec"].shape[1]
            if have < want:  # phase 8 --obs-v2: old demos lack the new values; they stay zero
                self._demos = dict(self._demos)
                self._demos["vec"] = np.pad(self._demos["vec"], ((0, 0), (0, want - have)))
        return self._demos

    def _load_demos2(self):
        if getattr(self, "_demos2", None) is None and getattr(self, "demo2_paths", None):
            data = bc2_dataset(self.demo2_paths)
            data["allowed_t"] = torch.as_tensor(data["allowed"].astype(np.int64))
            data["a6_idx"] = np.nonzero(data["action"] == 6)[0]
            self._demos2 = data
        return getattr(self, "_demos2", None)

    def _load_anchor(self):
        if getattr(self, "_anchor", None) is None and getattr(self, "anchor_path", None):
            d = np.load(self.anchor_path)
            teacher = torch.as_tensor(d["p8"])
            self._anchor = {"grid": d["grid"], "vec": d["vec"], "overview": d["overview"], "teacher": teacher}
        return getattr(self, "_anchor", None)

    def _anchor_loss(self, data):
        idx = np.random.randint(0, len(data["vec"]), BC_BATCH)
        obs = _obs_tensors(data, idx)
        logp = torch.log_softmax(self.policy.get_distribution(obs).distribution.logits[:, :6], dim=1)
        t = data["teacher"][idx]
        return (t * (t.clamp_min(1e-8).log() - logp)).sum(1).mean()

    def teacher_coef(self) -> float:
        plan = sorted(getattr(self, "teacher_plan", None) or [])
        if not plan or not getattr(self, "teacher_path", None):
            return 0.0
        rel = self.num_timesteps - getattr(self, "phase10_start", 0)
        if rel <= plan[0][0]:
            return float(plan[0][1])
        for (s0, c0), (s1, c1) in zip(plan, plan[1:]):
            if rel <= s1:
                return float(c0 + (c1 - c0) * (rel - s0) / max(1, s1 - s0))
        return float(plan[-1][1])

    def _teacher_states(self):
        """Indices (into the flattened rollout buffer) of states from phase-8 levels, or None."""

        mask = getattr(self, "_p8_mask", None)
        buf = self.rollout_buffer
        if mask is None or not buf.full:
            return None
        flat = mask.swapaxes(0, 1).reshape(-1) if buf.generator_ready else mask.reshape(-1)
        idx = np.nonzero(flat)[0]
        return idx if len(idx) else None

    def _teacher_loss(self, idx_pool):
        from jumpnrun.rl.drift import old_view

        if getattr(self, "_teacher", None) is None:
            from jumpnrun.rl.modelinfo import load_model

            self._teacher = load_model(self.teacher_path).policy
            self._teacher.set_training_mode(False)
        buf = self.rollout_buffer
        idx = np.random.choice(idx_pool, BC_BATCH)
        obs = {k: torch.as_tensor(v[idx].reshape((BC_BATCH,) + v.shape[2:]) if v.ndim > 2 and not buf.generator_ready
                                  else v[idx], dtype=torch.float32) for k, v in buf.observations.items()}
        with torch.no_grad():
            t = self._teacher.get_distribution(old_view(obs)).distribution.probs
        logp = torch.log_softmax(self.policy.get_distribution(obs).distribution.logits[:, :6], dim=1)
        return (t * (t.clamp_min(1e-8).log() - logp)).sum(1).mean()

    def bc2_coef(self) -> float:
        plan = getattr(self, "bc2_plan", None)
        if not plan:
            return 0.0
        rel = self.num_timesteps - getattr(self, "phase10_start", 0)
        coef = 0.0
        for start, value in sorted(plan):
            if rel >= start:
                coef = value
        return coef

    def _bc2_batch(self, data):
        n = len(data["action"])
        idx = np.random.randint(0, n, BC_BATCH)
        if len(data["a6_idx"]) and self.bc2_a6_share:
            k = np.random.rand(BC_BATCH) < self.bc2_a6_share
            idx[k] = np.random.choice(data["a6_idx"], int(k.sum()))
        return _obs_tensors(data, idx), data["allowed_t"][idx]

    def train(self) -> None:
        super().train()
        demos = self._load_demos()
        if demos is None or getattr(self, "bc_paused", False):  # phase 10: no BC during the critic warm-up
            return
        coef = max(self.bc_min, self.bc_coef * self.bc_decay ** self.bc_updates)
        self.bc_updates += 1
        n = len(demos["action"])
        batches = max(1, self.n_epochs * (self.n_steps * self.n_envs // self.batch_size) // 2)
        losses, accs = [], []
        self.policy.set_training_mode(True)
        coef2 = self.bc2_coef()
        demos2 = self._load_demos2() if coef2 > 0 else None
        losses2, accs2 = [], []
        anchor = self._load_anchor()
        kls = []
        coef_t = self.teacher_coef()
        teacher_idx = self._teacher_states() if coef_t > 0 else None
        tkls = []
        for _ in range(batches):
            idx = np.random.randint(0, n, BC_BATCH)
            loss, acc = bc_loss(self.policy, _obs_tensors(demos, idx), self._demo_allowed[idx])
            total = coef * loss
            if demos2 is not None:
                obs2, allowed2 = self._bc2_batch(demos2)
                loss2, acc2 = bc_loss(self.policy, obs2, allowed2)
                total = total + coef2 * loss2
                losses2.append(loss2.item())
                accs2.append(acc2.item())
            if anchor is not None:
                kl = self._anchor_loss(anchor)
                total = total + self.anchor_coef * kl
                kls.append(kl.item())
            if teacher_idx is not None:
                tkl = self._teacher_loss(teacher_idx)
                total = total + coef_t * tkl
                tkls.append(tkl.item())
            self.policy.optimizer.zero_grad()
            total.backward()
            torch.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
            self.policy.optimizer.step()
            losses.append(loss.item())
            accs.append(acc.item())
        self.logger.record("vorbild/gewicht", coef)
        self.logger.record("vorbild/verlust", float(np.mean(losses)))
        self.logger.record("vorbild/uebereinstimmung", float(np.mean(accs)))
        if kls:  # adaptive weight, as PPO's adaptive KL penalty
            kl = float(np.mean(kls))
            if kl > 1.5 * self.anchor_target_kl:
                self.anchor_coef = min(10.0, self.anchor_coef * 1.5)
            elif kl < self.anchor_target_kl / 1.5:
                self.anchor_coef = max(0.01, self.anchor_coef / 1.5)
            self.logger.record("anker/kl", kl)
            self.logger.record("anker/gewicht", self.anchor_coef)
        if tkls:
            self.logger.record("lehrer/kl", float(np.mean(tkls)))
            self.logger.record("lehrer/gewicht", coef_t)
            self.logger.record("lehrer/anteil_p8", len(teacher_idx) / (self.n_steps * self.n_envs))
        if losses2:
            self.logger.record("vorbild2/gewicht", coef2)
            self.logger.record("vorbild2/verlust", float(np.mean(losses2)))
            self.logger.record("vorbild2/uebereinstimmung", float(np.mean(accs2)))
