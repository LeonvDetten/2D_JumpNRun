"""Physics, rules and determinism of the game core."""

import random

import pytest

from jumpnrun.core import NOOP, Action, Level, Simulation, Status
from jumpnrun.core.actions import BOT_ACTIONS
from jumpnrun.core.constants import PLAYER_H, TILE

RIGHT = Action(right=True)
JUMP = Action(jump=True)
RIGHT_JUMP = Action(right=True, jump=True)


def make_level(*rows: str) -> Level:
    """Build a level from rows given top-down; missing top rows are left empty."""

    rows = list(rows)
    return Level.from_text("\n".join([""] * (13 - len(rows)) + rows))


def run(sim: Simulation, action: Action, frames: int) -> Status:
    return sim.step(action, frames=frames)


def settle(sim: Simulation) -> None:
    run(sim, NOOP, 60)
    assert sim.player.on_ground


# ------------------------------------------------------------------ physics
def test_jump_apex_is_more_than_one_and_less_than_two_tiles():
    sim = Simulation(make_level(" P" + " " * 20 + "C", "B" * 30))
    settle(sim)
    ground_y = sim.player.y
    sim.step(JUMP)
    heights = []
    for _ in range(40):
        sim.step(NOOP)
        heights.append(ground_y - sim.player.y)
    assert TILE < max(heights) < 2 * TILE


def test_player_can_climb_a_one_tile_step():
    sim = Simulation(make_level(
        "            C",
        " P    BBBBBBBB",
        "BBBBBBBBBBBBBB",
    ))
    for _ in range(200):
        on_step = sim.player.on_ground and sim.player.y + sim.player.h == 11 * TILE
        if sim.step(RIGHT if on_step else RIGHT_JUMP) != Status.RUNNING:
            break
    assert sim.status == Status.WON


def test_player_cannot_climb_a_two_tile_wall():
    sim = Simulation(make_level(
        "      B     C",
        "      B      ",
        " P    BBBBBBB",
        "BBBBBBBBBBBBB",
    ))
    # alternate: jump into the wall, walk, jump again - every trick must fail
    for i in range(600):
        sim.step(RIGHT_JUMP if i % 7 else RIGHT)
    assert sim.status == Status.RUNNING
    assert sim.player.x + sim.player.w <= 6 * TILE


def test_head_bumps_against_ceiling():
    sim = Simulation(make_level(
        "BBBBBB     C",
        " P",
        "BBBBBBBBBBBB",
    ))
    settle(sim)
    ground_y = sim.player.y
    sim.step(JUMP)
    ys = [sim.player.y]
    for _ in range(30):
        sim.step(NOOP)
        ys.append(sim.player.y)
    assert min(ys) >= TILE * 10  # never inside the ceiling row (row 10 of 13)
    assert sim.player.y == ground_y


def test_falling_into_a_pit_kills():
    sim = Simulation(make_level(" P" + " " * 20 + "C", "BBBB      BBBBBBBBBBBBB"))
    while sim.status == Status.RUNNING and sim.frame < 1000:
        sim.step(RIGHT)
    assert sim.status == Status.DIED_PIT


def test_jumping_over_a_two_tile_gap_wins():
    sim = Simulation(make_level(" P" + " " * 10 + "C", "BBBBB  BBBBBBBBBB"))
    while sim.status == Status.RUNNING and sim.frame < 1000:
        near_edge = 5 * TILE - 8 <= sim.player.x + sim.player.w <= 5 * TILE
        sim.step(RIGHT_JUMP if near_edge else RIGHT)
    assert sim.status == Status.WON


def test_long_levels_have_solid_floor_everywhere():
    """Regression: the old chunk indexing let the player fall through after ~440 tiles."""

    sim = Simulation(make_level(" P" + " " * 995 + "C", "B" * 1000))
    while sim.status == Status.RUNNING and sim.frame < 10_000:
        sim.step(RIGHT)
    assert sim.status == Status.WON


# ------------------------------------------------------------------ enemies
def test_walking_into_an_enemy_kills():
    sim = Simulation(make_level(" P      E" + " " * 10 + "C", "B" * 30))
    while sim.status == Status.RUNNING and sim.frame < 500:
        sim.step(RIGHT)
    assert sim.status == Status.DIED_ENEMY


def test_stomping_an_enemy_kills_it():
    sim = Simulation(make_level(" P  E  B" + " " * 12 + "C", "B" * 30))
    settle(sim)
    # wait until the enemy walked back (it turns at the block), then jump on it
    for _ in range(400):
        enemy = sim.enemies[0] if sim.enemies else None
        if enemy is None:
            break
        dx = enemy.x - sim.player.x
        sim.step(JUMP if 30 < dx < 90 and enemy.direction < 0 else NOOP)
        if sim.status != Status.RUNNING:
            break
    assert sim.status == Status.RUNNING
    assert sim.kills_stomp == 1 and not sim.enemies


def test_shooting_an_enemy_kills_it():
    sim = Simulation(make_level(" P" + " " * 12 + "E   B" + " " * 5 + "C", "B" * 30))
    settle(sim)
    sim.step(Action(shoot=True))
    run(sim, NOOP, 60)
    assert sim.kills_shot == 1 and not sim.enemies
    assert sim.status == Status.RUNNING


def test_shoot_cooldown_is_counted_in_frames():
    sim = Simulation(make_level(" P" + " " * 20 + "C", "B" * 30))
    settle(sim)
    shots = 0
    for _ in range(90):
        before = len(sim.bullets) + sim.kills_shot
        sim.step(Action(shoot=True))
        shots += (len(sim.bullets) + sim.kills_shot) > before
    assert shots == 3  # one shot per 30 frames


def test_enemy_far_away_sleeps_until_player_is_close():
    sim = Simulation(make_level(" P" + " " * 40 + "E  C", "B" * 50))
    start_x = sim.enemies[0].x
    run(sim, NOOP, 60)
    assert sim.enemies[0].x == start_x and not sim.enemies[0].active


# ------------------------------------------------------------- determinism
def _random_trace(level: Level, seed: int, steps: int = 600):
    rng = random.Random(seed)
    sim = Simulation(level)
    trace = []
    for _ in range(steps):
        sim.step(rng.choice(BOT_ACTIONS), frames=4)
        trace.append(sim.state_signature())
    return trace


@pytest.fixture(scope="module")
def exam_level():
    return Level.from_file("levels/exam/level.txt")


def test_same_inputs_give_identical_games(exam_level):
    assert _random_trace(exam_level, 1) == _random_trace(exam_level, 1)


def test_clone_continues_identically(exam_level):
    rng = random.Random(3)
    sim = Simulation(exam_level)
    for _ in range(100):
        sim.step(rng.choice(BOT_ACTIONS), frames=4)
    copy = sim.clone()
    actions = [rng.choice(BOT_ACTIONS) for _ in range(200)]
    for action in actions:
        sim.step(action, frames=4)
        copy.step(action, frames=4)
        assert sim.state_signature() == copy.state_signature()


def test_reset_restores_the_start(exam_level):
    sim = Simulation(exam_level)
    start = sim.state_signature()
    for _ in range(300):
        sim.step(RIGHT_JUMP)
    sim.reset()
    assert sim.state_signature() == start


# -------------------------------------------------------------------- level
def test_level_roundtrip_and_validation():
    level = make_level(" P  E   C", "BBBBBBBBB")
    again = Level.from_text(level.to_text())
    assert again.solid == level.solid and again.chests == level.chests
    assert again.enemy_spawns == level.enemy_spawns and again.spawn == level.spawn
    with pytest.raises(ValueError):
        make_level("   ", "BBB")  # no chest
    with pytest.raises(ValueError):
        Level.from_text("\n".join(["B"] * 14 + ["C"]))  # too many rows


def test_spawn_marker_places_player_on_its_tile():
    level = make_level("", " P   C", "BBBBBBB")
    sim = Simulation(level)
    assert sim.player.x // TILE == 1 and sim.player.y + PLAYER_H == 12 * TILE
