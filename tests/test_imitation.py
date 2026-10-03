"""Finer control (action repeat 2), solver demos, behaviour cloning, PPO with demos."""

import json

import numpy as np
import torch

from jumpnrun.core import Level, Simulation
from jumpnrun.core.actions import BOT_ACTION_NAMES, BOT_ACTIONS
from jumpnrun.core.sim import Status
from jumpnrun.imitation.bc import bc_loss, _obs_tensors
from jumpnrun.imitation.demos import equivalent_actions, load_dataset, make_demo
from jumpnrun.levelgen.generator import NUM_TIERS, generate
from jumpnrun.levelgen.solver import replay, solve
from jumpnrun.rl.env import JumpNRunEnv, fixed_levels

RIGHT = BOT_ACTION_NAMES.index("right")
RIGHT_JUMP = BOT_ACTION_NAMES.index("right+jump")


def small_level():
    return Level.from_text("\n".join([""] * 11 + [" P       E     C", "BBBBB  BBBBBBBBBBB"]))


def test_env_time_limits_scale_with_action_repeat():
    level = small_level()
    fine = JumpNRunEnv(fixed_levels([level]), action_repeat=2)
    coarse = JumpNRunEnv(fixed_levels([level]), action_repeat=4)
    fine.reset(seed=0)
    coarse.reset(seed=0)
    assert fine.no_progress_steps == 2 * coarse.no_progress_steps
    assert fine.max_steps * 2 >= coarse.max_steps * 2 - 4  # same game time, twice the decisions
    fine.step(RIGHT)
    assert fine.sim.frame == 2


def test_solver_with_repeat_two_finds_replayable_solution():
    level = generate(6, 3)
    result = solve(level, 60_000, action_repeat=2, weight=1.2)
    assert result.solved
    assert replay(level, result.actions, action_repeat=2).status == Status.WON


def test_equivalent_actions_in_the_air_and_on_the_ground():
    sim = Simulation(small_level())
    sim.step(BOT_ACTIONS[0], frames=40)  # settle on the ground
    on_ground = equivalent_actions(sim, RIGHT, 2)
    assert not on_ground & (1 << RIGHT_JUMP)  # on the ground, jumping makes a difference
    sim.step(BOT_ACTIONS[RIGHT_JUMP], frames=2)  # now in the air
    in_air = equivalent_actions(sim, RIGHT, 2)
    assert in_air & (1 << RIGHT_JUMP) and in_air & (1 << RIGHT)


def test_demo_labels_rebuild_into_a_dataset(tmp_path):
    demo = make_demo(2, 0, repeat=2)
    assert demo is not None and sum(demo["mask"]) > 20
    path = tmp_path / "demos.jsonl"
    path.write_text(json.dumps(demo) + "\n")
    data = load_dataset([path], thin_flat=0.0)
    n = len(data["action"])
    assert n == sum(demo["mask"])
    assert data["grid"].shape == (n, 4, 13, 25) and data["vec"].shape == (n, 15)
    # the teacher's own action is always part of its equivalence set
    assert all(allowed & (1 << a) for a, allowed in zip(data["action"], data["allowed"]))


def test_bc_loss_is_lower_for_the_imitated_action():
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from jumpnrun.rl.policy import GridFeatures

    env = DummyVecEnv([lambda: JumpNRunEnv(fixed_levels([small_level()]), action_repeat=2)])
    model = PPO("MultiInputPolicy", env, n_steps=64, batch_size=64, device="cpu",
                policy_kwargs=dict(features_extractor_class=GridFeatures))
    obs = env.reset()
    data = {"grid": obs["grid"].astype(np.int8), "vec": obs["vec"]}
    idx = np.array([0])
    tensors = _obs_tensors(data, idx)
    optimizer = torch.optim.Adam(model.policy.parameters(), lr=1e-2)
    target = torch.tensor([1 << RIGHT])
    first, _ = bc_loss(model.policy, tensors, target)
    for _ in range(30):
        loss, _ = bc_loss(model.policy, tensors, target)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    last, acc = bc_loss(model.policy, tensors, target)
    assert last.item() < first.item() * 0.5 and acc.item() == 1.0


def test_generator_v2_uses_the_new_building_blocks():
    seen = set()
    for tier in (5, 6, 7, 8, 9):
        for seed in range(6):
            seen |= set(generate(tier, seed).building_blocks)
    assert {"tunnel", "shaft", "ceiling", "two_routes"} <= seen
    assert not set(generate(3, 0).building_blocks) & {"tunnel", "shaft", "ceiling", "two_routes"}


def test_new_tiers_are_solvable_with_fine_control():
    for tier in range(5, NUM_TIERS):
        for seed in range(2):
            assert solve(generate(tier, seed), 60_000, action_repeat=2, weight=1.2).solved, (tier, seed)
