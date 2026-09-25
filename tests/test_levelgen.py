"""Level generator and solver."""

import pytest

from jumpnrun.core import Level
from jumpnrun.levelgen.generator import NUM_TIERS, TIERS, generate
from jumpnrun.levelgen.solver import replay, solve
from jumpnrun.core.sim import Status


@pytest.mark.parametrize("tier", range(NUM_TIERS))
def test_generated_levels_are_solvable_for_the_bot(tier):
    for seed in range(3):
        level = generate(tier, seed)
        result = solve(level, max_expansions=40_000)
        assert result.solved, f"tier {tier} seed {seed} not solvable"
        # the solution is a real action list: replaying it wins
        assert replay(level, result.actions).status == Status.WON


def test_generation_is_reproducible():
    assert generate(4, 123).to_text() == generate(4, 123).to_text()
    assert generate(4, 123).to_text() != generate(4, 124).to_text()


def test_generated_levels_are_valid_and_grow_with_tier():
    for tier in range(NUM_TIERS):
        level = generate(tier, 0)
        assert Level.from_text(level.to_text()).cols == level.cols
        assert len(level.chests) == 1
        assert level.cols >= TIERS[tier].length
    assert generate(0, 0).enemy_spawns == []
    assert any(generate(5, seed).enemy_spawns for seed in range(5))


def test_solver_rejects_an_impossible_level():
    # a 2-tile high wall cannot be jumped (jump apex 78 px < 120 px)
    level = Level.from_text("\n".join([""] * 9 + ["      B", "      B    C", " P    B", "BBBBBBBBBBBB"]))
    assert not solve(level, max_expansions=20_000).solved


def test_defused_exam_level_is_solvable_with_enemies():
    """levels/exam/level_entschaerft.loesung.json is a solver-found action list (proof of solvability)."""

    import json

    level = Level.from_file("levels/exam/level_entschaerft.txt")
    with open("levels/exam/level_entschaerft.loesung.json") as f:
        actions = json.load(f)
    assert replay(level, actions).status == Status.WON
