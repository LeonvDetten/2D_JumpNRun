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


def load_model(model_path):
    """Load a PPO model and attach its `action_repeat` (used by evaluation and ghost view)."""

    from stable_baselines3 import PPO

    model = PPO.load(str(model_path), device="cpu")
    model.action_repeat = action_repeat_for(model_path)
    return model
