"""Phase 6: frozen validation, overview map, network surgery, generator v3, start points, test series."""

import glob
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from jumpnrun.core import Level
from jumpnrun.core.actions import BOT_ACTIONS
from jumpnrun.core.sim import Status
from jumpnrun.levelgen.generator import NUM_TIERS, generate
from jumpnrun.levelgen.solver import replay, solve_auto
from jumpnrun.rl.curriculum import MID_START_TIER
from jumpnrun.rl.env import OV_BEHIND, OV_COLS, OV_SCALE, JumpNRunEnv, fixed_levels

ROOT = Path(__file__).resolve().parent.parent


def test_frozen_validation_v2_is_still_generated_identically():
    frozen = json.loads((ROOT / "levels/validierung/v2.json").read_text())
    assert len(frozen) == 120
    for item in frozen[::7]:
        assert generate(item["tier"], item["seed"]).to_text() == item["text"]


def test_env_without_overview_is_unchanged():
    env = JumpNRunEnv(fixed_levels([generate(3, 1)]), action_repeat=2)
    obs, _ = env.reset(seed=0)
    assert set(obs) == {"grid", "vec"}


def test_overview_shape_range_and_far_dead_end():
    level = Level.from_file(ROOT / "levels/exam/level.txt")
    env = JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True)
    obs, _ = env.reset(seed=0)
    ov = obs["overview"]
    assert ov.shape == (4, 13, OV_COLS) and ov.min() >= 0.0 and ov.max() <= 1.0
    assert set(np.unique(ov[0] * 4)) <= {0, 1, 2, 3, 4}
    # the exam floor ends at tile 97, far beyond the 19-tile view - but visible in the overview
    pcol = (env.sim.player.x + env.sim.player.w // 2) // 60
    floor = ov[0, 12]
    last_floor_tile = (np.nonzero(floor)[0].max() + 1) * OV_SCALE + pcol - OV_BEHIND
    assert 95 <= last_floor_tile <= 102
    assert ov[2].sum() > 0  # enemies


def test_network_surgery_keeps_phase5_behaviour():
    from stable_baselines3.common.vec_env import DummyVecEnv

    from jumpnrun.rl.modelinfo import grow_overview, load_model

    level = generate(8, 5)
    env = DummyVecEnv([lambda: JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True)])
    new = grow_overview(ROOT / "models/phase5.zip", env)
    old = load_model(ROOT / "models/phase5.zip")
    single = JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True)
    obs = [single.reset(seed=0)[0]]
    for i in range(30):
        obs.append(single.step(i % 6)[0])
    batch = {k: np.stack([o[k] for o in obs]) for k in obs[0]}
    t_new, _ = new.policy.obs_to_tensor(batch)
    t_old, _ = old.policy.obs_to_tensor({k: batch[k] for k in ("grid", "vec")})
    with torch.no_grad():
        diff = (new.policy.get_distribution(t_new).distribution.logits
                - old.policy.get_distribution(t_old).distribution.logits).abs().max()
        vdiff = (new.policy.predict_values(t_new) - old.policy.predict_values(t_old)).abs().max()
    assert diff < 1e-5 and vdiff < 1e-5


def test_generator_v3_long_tiers_solvable_with_waypoints():
    assert NUM_TIERS >= 12
    for tier in (10, 11):
        level = generate(tier, 0)
        assert level.cols >= 200 and level.waypoints
        result = solve_auto(level, 60_000, action_repeat=2, weight=1.2)
        assert result.solved and replay(level, result.actions, 2).status == Status.WON


def test_mid_level_start_replays_teacher_prefix():
    level = generate(10, 0)
    result = solve_auto(level, 60_000, action_repeat=2, weight=1.2)
    prefix = result.actions[:300]
    source = lambda rng: (level, MID_START_TIER, (2, prefix))
    env = JumpNRunEnv(source, action_repeat=2, overview=True)
    env.reset(seed=0)
    expected = replay(level, prefix, 2)
    assert env.sim.player.x == expected.player.x and env.sim.player.y == expected.player.y
    assert env.start_col > 20


@pytest.mark.parametrize("path", sorted(glob.glob(str(ROOT / "levels/test_serie/*.txt"))))
def test_test_series_levels_have_verified_solutions(path):
    level = Level.from_file(path)
    solution = json.loads(Path(path).with_suffix(".loesung.json").read_text())
    sim = replay(level, solution["actions"], solution["action_repeat"])
    assert sim.status == Status.WON
