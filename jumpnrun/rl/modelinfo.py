"""Which action repeat does a saved model use?

Models up to phase 3 decide every 4 frames, newer ones every 2. The value is
stored next to the model (`<model>.json`) or in the run directory
(`<run>/config.json`); without either, the legacy value 4 applies.
"""

from __future__ import annotations

import json
from pathlib import Path

from jumpnrun.core.actions import ACTION_REPEAT


def model_config(model_path) -> dict:
    path = Path(model_path)
    for candidate in (path.with_suffix(".json"), path.parent / "config.json", path.parent.parent / "config.json"):
        if candidate.exists():
            return json.loads(candidate.read_text())
    return {}


def action_repeat_for(model_path) -> int:
    return int(model_config(model_path).get("action_repeat", ACTION_REPEAT))


def write_model_config(model_path, **values) -> None:
    Path(model_path).with_suffix(".json").write_text(json.dumps(values, indent=2) + "\n")


def env_kwargs(model) -> dict:
    """JumpNRunEnv arguments that match a loaded model (decision rate, overview map yes/no)."""

    return dict(action_repeat=getattr(model, "action_repeat", ACTION_REPEAT),
                overview="overview" in model.observation_space.spaces,
                obs_v2=model.observation_space["vec"].shape[0] > 15,
                obs_v3=model.observation_space["vec"].shape[0] > 21,
                progress="path")  # phase 10: measurement counts "stuck" along the way, not along x


# Phase 12 (Leon, 10.10.): the bot plays with sharpened action probabilities p^(1/T), T = 0.3 - the trained policy
# is often unsure between near-equal actions; sampling at T = 1 then costs single precise jumps (exam 57 % -> 98 %).
PLAY_TEMPERATURE = 0.3


def choose_actions(model, batch: dict, deterministic: bool = False, temperature: float = 1.0):
    """Actions for a batch of observations: deterministic, sampled (T = 1, = model.predict) or sharpened (T < 1)."""

    if deterministic or temperature <= 0:
        return model.predict(batch, deterministic=True)[0]
    if temperature == 1.0:
        return model.predict(batch, deterministic=False)[0]
    import torch

    with torch.no_grad():
        obs, _ = model.policy.obs_to_tensor(batch)
        probs = model.policy.get_distribution(obs).distribution.probs
        p = probs.clamp_min(1e-12) ** (1.0 / temperature)
        return torch.multinomial(p / p.sum(1, keepdim=True), 1).squeeze(1).cpu().numpy()


def load_model(model_path):
    """Load a PPO model and attach its `action_repeat` (used by evaluation and ghost view)."""

    from stable_baselines3 import PPO

    model = PPO.load(str(model_path), device="cpu")
    model.action_repeat = action_repeat_for(model_path)
    return model


def grow_overview(old_model_path, env, algo=None, **kwargs):
    """Network surgery: a new model for `env` (with overview map) that starts with the old weights.

    All old layers are copied; the new overview branch is added with a zero output layer,
    so at first the new model acts exactly like the old one.
    """

    from stable_baselines3 import PPO

    old = PPO.load(str(old_model_path), device="cpu")
    algo = algo or PPO
    params = dict(policy_kwargs=old.policy_kwargs, n_steps=old.n_steps, batch_size=old.batch_size,
                  n_epochs=old.n_epochs, gamma=old.gamma, gae_lambda=old.gae_lambda, vf_coef=old.vf_coef,
                  ent_coef=old.ent_coef, device="cpu", verbose=0)
    params.update(kwargs)
    model = algo("MultiInputPolicy", env, **params)
    missing, unexpected = model.policy.load_state_dict(old.policy.state_dict(), strict=False)
    assert not unexpected and all(".ov_" in k for k in missing), (missing, unexpected)
    for extractor in {model.policy.features_extractor, model.policy.pi_features_extractor,
                      model.policy.vf_features_extractor}:
        extractor.zero_overview_output()
    model.action_repeat = action_repeat_for(old_model_path)
    return model


def grow_vec(old_model_path, env, algo=None, **kwargs):
    """Network surgery for phase 8 (--obs-v2): the vector input grows from 15 to 21 values.

    Every weight is copied; the new input columns of the first vector layer start at zero, so at first the
    new model acts exactly like the old one.
    """

    import torch
    from stable_baselines3 import PPO

    old = (algo or PPO).load(str(old_model_path), device="cpu")
    params = dict(policy_kwargs=old.policy_kwargs, n_steps=old.n_steps, batch_size=old.batch_size,
                  n_epochs=old.n_epochs, gamma=old.gamma, gae_lambda=old.gae_lambda, vf_coef=old.vf_coef,
                  ent_coef=old.ent_coef, device="cpu", verbose=0)
    params.update(kwargs)
    model = (algo or PPO)("MultiInputPolicy", env, **params)
    new_state = model.policy.state_dict()
    old_state = old.policy.state_dict()
    with torch.no_grad():
        for key, value in new_state.items():
            src = old_state[key]
            if src.shape == value.shape:
                value.copy_(src)
            else:
                assert key.endswith("vec_mlp.0.weight"), key
                value.zero_()
                value[:, :src.shape[1]] = src
    model.policy.load_state_dict(new_state)
    model.num_timesteps = old.num_timesteps
    model._num_timesteps_at_start = old.num_timesteps
    if hasattr(old, "bc_updates"):
        model.bc_updates = old.bc_updates
    model.action_repeat = action_repeat_for(old_model_path)
    return model


def grow_v3(old_model_path, env, algo=None, a6_bias_offset: float = -4.0, **kwargs):
    """Network surgery for phase 9 (--obs-v3): wider view behind, longer overview behind, chest compass.

    The grid gains 8 columns on the left (5 -> 13 behind) and the overview 8 columns (32 more tiles behind).
    Both CNNs keep their filters; after the two stride-2 layers the old feature columns sit 2 (grid) or
    4 (overview) places further right, so the first dense layer gets its old weights there and zero weights for
    the new columns. The vector grows to 23 (new inputs start at zero). Apart from the old view's left edge,
    which now sees real tiles instead of padding, the new model starts out acting like the old one.
    The policy gets a 7th action (left+jump), initialised like "left" but about 50 times less likely.
    """

    import torch
    from stable_baselines3 import PPO

    old = (algo or PPO).load(str(old_model_path), device="cpu")
    params = dict(policy_kwargs=old.policy_kwargs, n_steps=old.n_steps, batch_size=old.batch_size,
                  n_epochs=old.n_epochs, gamma=old.gamma, gae_lambda=old.gae_lambda, vf_coef=old.vf_coef,
                  ent_coef=old.ent_coef, device="cpu", verbose=0)
    params.update(kwargs)
    model = (algo or PPO)("MultiInputPolicy", env, **params)
    new_state = model.policy.state_dict()
    old_state = old.policy.state_dict()
    old_ext = old.policy.features_extractor
    new_ext = model.policy.features_extractor

    with torch.no_grad():
        og, oo = (old_ext.cnn[:-1](torch.zeros(1, *old.observation_space["grid"].shape)).shape,
                  old_ext.ov_cnn[:-1](torch.zeros(1, *old.observation_space["overview"].shape)).shape
                  if old_ext.has_overview else None)
        ng, no = (new_ext.cnn[:-1](torch.zeros(1, *model.observation_space["grid"].shape)).shape,
                  new_ext.ov_cnn[:-1](torch.zeros(1, *model.observation_space["overview"].shape)).shape
                  if new_ext.has_overview else None)

    def remap(src, dst, old_shape, new_shape, extra_cols=0):
        """Copy dense weights over flattened (C, H, W) features whose columns moved right by the width growth."""

        _, c, h, w = old_shape
        _, c2, h2, w2 = new_shape
        assert c == c2 and h == h2 and w2 >= w
        n_old, n_new = c * h * w, c2 * h2 * w2
        dst.zero_()
        a = src[:, :n_old].reshape(-1, c, h, w)
        b = dst[:, :n_new].reshape(-1, c, h, w2)
        b[:, :, :, w2 - w:] = a
        dst[:, :n_new] = b.reshape(dst.shape[0], n_new)
        if extra_cols:  # the vector features behind the CNN features
            dst[:, n_new:n_new + extra_cols] = src[:, n_old:n_old + extra_cols]

    with torch.no_grad():
        for key, value in new_state.items():
            src = old_state[key]
            if src.shape == value.shape:
                value.copy_(src)
            elif key.endswith("vec_mlp.0.weight"):
                value.zero_()
                value[:, :src.shape[1]] = src
            elif key.endswith("head.0.weight"):
                remap(src, value, og, ng, extra_cols=64)
            elif key.endswith("ov_mlp.0.weight"):
                remap(src, value, oo, no)
            elif key in ("action_net.weight", "action_net.bias"):  # 7th action left+jump: like "left", but rare
                value[:src.shape[0]] = src
                value[src.shape[0]:] = src[1:2]
                if key.endswith("bias"):
                    value[src.shape[0]:] += a6_bias_offset  # phase 9: -4 (rare); phase 10: 0 (as likely as "left")
            else:
                raise AssertionError(key)
    model.policy.load_state_dict(new_state)
    model.num_timesteps = old.num_timesteps
    model._num_timesteps_at_start = old.num_timesteps
    if hasattr(old, "bc_updates"):
        model.bc_updates = old.bc_updates
    model.action_repeat = action_repeat_for(old_model_path)
    return model
