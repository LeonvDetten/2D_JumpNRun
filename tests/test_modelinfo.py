"""Loading saved models across Python versions (the pickled training schedules)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_load_model_does_not_unpickle_the_training_schedules():
    from jumpnrun.rl.modelinfo import load_model, saved_python

    path = ROOT / "models/phase1.zip"
    assert saved_python(path) == "3.11"
    model = load_model(path)  # a 3.11 lambda run under 3.13 would crash the interpreter here
    assert model.learning_rate == 0.0 and model.lr_schedule(1.0) == 0.0 and model.clip_range(1.0) == 0.0
    assert model.num_timesteps > 0 and model.action_repeat == 4


def test_load_ppo_kwargs_set_the_schedules_for_further_training():
    from jumpnrun.rl.modelinfo import load_ppo

    model = load_ppo(ROOT / "models/phase1.zip", learning_rate=lambda p: 1e-4 * p, clip_range=0.15)
    assert model.lr_schedule(0.5) == 5e-5 and model.clip_range(0.3) == 0.15
