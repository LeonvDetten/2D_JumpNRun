"""Phase 7: secret exam, pool from stored text, jump catalogue, rewind starts, EMA, IMPALA, autopilot rules."""

import hashlib
import json
import random
from pathlib import Path

import numpy as np
import torch

from jumpnrun.core import Level, Simulation
from jumpnrun.core.actions import BOT_ACTIONS
from jumpnrun.core.sim import Status
from jumpnrun.levelgen.generator import generate
from jumpnrun.levelgen.jump_catalog import load_catalog
from jumpnrun.levelgen.solver import replay
from jumpnrun.rl.curriculum import REWIND_TIER, CurriculumSource
from jumpnrun.rl.env import JumpNRunEnv, fixed_levels

ROOT = Path(__file__).resolve().parent.parent
EXAM2_SHA = "69e083be5b0d2391fc792791ff52f2a6a4bdff154d38d236539397c087717f12"


def test_exam2_is_locked_and_solvable():
    text = (ROOT / "levels/exam2/level.txt").read_bytes()
    assert hashlib.sha256(text).hexdigest() == EXAM2_SHA
    solution = json.loads((ROOT / "levels/exam2/level.loesung.json").read_text())
    sim = replay(Level.from_file(ROOT / "levels/exam2/level.txt"), solution["actions"], solution["action_repeat"])
    assert sim.status == Status.WON


def test_exam2_is_never_used_for_training():
    training_scripts = list((ROOT / "scripts").glob("train_*.sh")) + list((ROOT / "scripts").glob("demos_*.sh"))
    for path in training_scripts + [ROOT / "jumpnrun/rl/train.py", ROOT / "jumpnrun/rl/curriculum.py",
                                                          ROOT / "jumpnrun/imitation/demos.py", ROOT / "jumpnrun/rl/failures.py"]:
        assert "exam2" not in path.read_text(), path


def test_pool_plays_stored_level_text(tmp_path):
    level = generate(10, 3)
    demo = dict(tier=10, seed=3, repeat=2, actions=[2] * 70, mask=[1] * 70, won=True, level=level.to_text())
    with open(tmp_path / "demos.jsonl", "w") as f:
        for _ in range(100):
            f.write(json.dumps(demo) + "\n")
    source = CurriculumSource(0, 12, pool_dir=tmp_path)
    source.weights = [0.0] * len(source.weights)
    source.weights[10] = 1.0
    played, tier = source(random.Random(0))
    assert tier == 10 and played.to_text() == level.to_text()


def test_jump_catalogue_covers_all_kinds():
    catalog = load_catalog()
    kinds = {(e["gap"], e["drop"]) for e in catalog}
    assert (3, -1) in kinds and (4, 3) in kinds and (3, 8) in kinds and (5, -1) not in kinds
    assert len(catalog) > 350


def test_simulation_clone_is_exact():
    sim = Simulation(generate(8, 2))
    rng = random.Random(1)
    for _ in range(40):
        sim.step(BOT_ACTIONS[rng.randrange(6)], frames=2)
    copy = sim.clone()
    actions = [rng.randrange(6) for _ in range(60)]
    for a in actions:
        sim.step(BOT_ACTIONS[a], frames=2)
        copy.step(BOT_ACTIONS[a], frames=2)
    assert sim.state_signature() == copy.state_signature()


def test_rewind_restarts_before_the_failure():
    level = generate(10, 1)
    env = JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True, rewind_prob=1.0, seed=0)
    env.reset()
    rng = random.Random(0)
    ends = []
    for _ in range(6000):
        _, reward, term, trunc, info = env.step(rng.choice([2, 2, 4, 4, 3, 0]))
        if term or trunc:
            ends.append(info["episode_end"])
            env.reset()
    rewinds = [e for e in ends if e["tier"] == REWIND_TIER]
    assert rewinds and all(1 <= e["rewind_depth"] <= 2 for e in rewinds)
    assert all(e["start_col"] > 0 for e in rewinds)


def test_impala_policy_trains_and_old_models_still_load():
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from jumpnrun.imitation.bc import build_fresh_student
    from jumpnrun.rl.evaluate import evaluate_levels
    from jumpnrun.rl.modelinfo import load_model

    model = build_fresh_student("impala", 2)
    assert not model.policy.share_features_extractor
    level = Level.from_text("\n".join([""] * 11 + [" P      C", "BBBBBBBBBB"]))
    assert evaluate_levels(model, [level])[0]["outcome"] in ("won", "timeout", "died_pit", "died_enemy")
    old = load_model(ROOT / "models/phase6_durchbruch.zip")
    assert evaluate_levels(old, [level])[0]["won"]


def test_phase_local_learning_rate():
    from jumpnrun.rl.train import linear_schedule

    lr = linear_schedule(1e-4, target=100_000_000, phase_start=40_000_000)
    assert abs(lr(1 - 0.4) - 1e-4) < 1e-12
    assert abs(lr(0.0) - 1e-5) < 1e-12


def _fake_result(exam_won, series_won):
    return {"validierung_v2": {"won": 100, "of": 120}, "validierung_v3": {"won": 30, "of": 40},
            "test_serie": {f"l{i}": {"won": series_won // 6, "of": 16} for i in range(6)},
            "pruefung": {"original": {"won": exam_won, "of": 64, "ends": {}},
                         "entschaerft": {"won": exam_won, "of": 64, "ends": {}}},
            "checkpoint": "step_x.zip"}


def test_stop_rule_needs_two_milestones_in_a_row():
    from jumpnrun.rl.milestones import stop_rule

    done = {"1000000:raw": _fake_result(40, 78), "2000000:raw": _fake_result(20, 78)}
    assert not stop_rule(done, 0.5625, 0.75)
    done["3000000:ema"] = _fake_result(40, 78)
    done["3000000:raw"] = _fake_result(10, 30)
    assert not stop_rule(done, 0.5625, 0.75)
    done["2000000:ema"] = _fake_result(37, 72)
    assert stop_rule(done, 0.5625, 0.75)
