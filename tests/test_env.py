"""Gymnasium environment and curriculum."""

import numpy as np
from gymnasium.utils.env_checker import check_env

from jumpnrun.core import Level
from jumpnrun.core.actions import BOT_ACTION_NAMES
from jumpnrun.rl.curriculum import CurriculumSource, CurriculumTracker
from jumpnrun.rl.env import NO_PROGRESS_STEPS, REWARD_DEATH, REWARD_WIN, JumpNRunEnv, fixed_levels

RIGHT = BOT_ACTION_NAMES.index("right")
NOOP = BOT_ACTION_NAMES.index("noop")


def level(*rows):
    return Level.from_text("\n".join([""] * (13 - len(rows)) + list(rows)))


def test_env_passes_gymnasium_checks():
    check_env(JumpNRunEnv(CurriculumSource(0, 3), seed=0), skip_render_check=True)


def test_observation_shows_blocks_chest_enemy_and_player():
    env = JumpNRunEnv(fixed_levels([level(" P   E    C", "BBBBBBBBBBBBBB")]))
    obs, _ = env.reset(seed=0)
    grid = obs["grid"]
    assert grid.shape == (4, 13, 25) and obs["vec"].shape == (15,)
    assert grid[0, 12, 5:19].all()  # floor under and ahead of the player
    assert grid[0, :, :4].all()  # left level border is a wall
    assert grid[1].sum() == 1 and grid[2].sum() == 1 and grid[3].sum() == 1
    assert grid[3, 11, 5] == 1  # player cell: row 11, fixed column 5
    assert -1 <= obs["vec"].min() and obs["vec"].max() <= 1


def test_walking_to_the_chest_gives_progress_reward_and_win_bonus():
    env = JumpNRunEnv(fixed_levels([level(" P        C", "BBBBBBBBBBBBBB")]))
    env.reset(seed=0)
    total, terminated, info = 0.0, False, {}
    while not terminated:
        _, reward, terminated, truncated, info = env.step(RIGHT)
        total += reward
    assert info["episode_end"]["won"]
    assert REWARD_WIN < total < REWARD_WIN + 1.5


def test_falling_into_a_pit_ends_the_episode_with_a_penalty():
    env = JumpNRunEnv(fixed_levels([level(" P         C", "BBBB    BBBBBBB")]))
    env.reset(seed=0)
    rewards, terminated, info = [], False, {}
    while not terminated:
        _, reward, terminated, _, info = env.step(RIGHT)
        rewards.append(reward)
    assert info["episode_end"]["outcome"] == "died_pit"
    assert rewards[-1] < REWARD_DEATH + 0.2


def test_standing_still_is_truncated_not_terminated():
    env = JumpNRunEnv(fixed_levels([level(" P         C", "BBBBBBBBBBBBBB")]))
    env.reset(seed=0)
    for step in range(NO_PROGRESS_STEPS + 5):
        _, _, terminated, truncated, info = env.step(NOOP)
        if terminated or truncated:
            break
    assert truncated and not terminated
    assert info["episode_end"]["outcome"] == "timeout"


def test_curriculum_unlocks_next_tier_and_prefers_the_frontier():
    tracker = CurriculumTracker(0, 3)
    for _ in range(60):
        tracker.record(0, True)
    assert tracker.unlocked == 1
    for i in range(60):
        tracker.record(1, i % 2 == 0)
    weights = tracker.weights()
    assert weights[1] > weights[0] > 0  # 50 % success beats 100 % success
    assert weights[2] == 0 and tracker.unlocked == 1


def test_curriculum_source_follows_weights():
    import random

    source = CurriculumSource(0, 3)
    from jumpnrun.levelgen.generator import NUM_TIERS

    source.weights = [0.0] * NUM_TIERS
    source.weights[2] = 1.0
    tiers = {source(random.Random(i))[1] for i in range(20)}
    assert tiers == {2}
