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
                obs_v2=model.observation_space["vec"].shape[0] > 15)


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
