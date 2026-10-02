"""Phase 8: data path, level augmentation, enemy dynamics, generator v9, LR schedule, measurement protocol."""

import hashlib
import json
import random
from pathlib import Path

from jumpnrun.core import Level, Simulation
from jumpnrun.core.constants import ENEMY_ACTIVATION_DIST, TILE
from jumpnrun.core.sim import Status
from jumpnrun.levelgen.augment import AugmentConfig, augment
from jumpnrun.levelgen.generator import generate
from jumpnrun.levelgen.solver import replay
from jumpnrun.rl.curriculum import CurriculumSource

ROOT = Path(__file__).resolve().parent.parent
OFF = AugmentConfig(void=0, raise_rows=0, ceiling=0, air_start=0, enemies=0)


def test_enemies_keep_their_defaults_without_augmentation():
    sim = Simulation(Level.from_file(ROOT / "levels/exam/level.txt"))
    assert sim.enemies and all(e.direction == 1 and e.wake == ENEMY_ACTIVATION_DIST for e in sim.enemies)
    actions = json.loads((ROOT / "levels/exam/level.loesung.json").read_text())  # legacy format: repeat 4
    assert replay(Level.from_file(ROOT / "levels/exam/level.txt"), actions).status == Status.WON


def test_augmentation_is_deterministic_per_seed():
    level = generate(11, 5)
    a, ta = augment(level, random.Random(3))
    b, tb = augment(level, random.Random(3))
    assert ta == tb and a.to_text() == b.to_text()


def test_void_behind_chest_is_real_void():
    level = generate(10, 7)
    lv, tags = augment(level, random.Random(1), AugmentConfig(**{**OFF.__dict__, "void": 1.0}))
    assert tags == ["void"]
    cx = max(c[0] for c in lv.chests) // TILE
    assert lv.cols >= cx + 3  # empty columns behind the chest ...
    assert not any(lv.solid[r][c] for r in range(lv.rows) for c in range(cx + 1, lv.cols))  # ... no wall


def test_raise_and_air_start():
    level = generate(6, 2)
    lv, tags = augment(level, random.Random(2), AugmentConfig(**{**OFF.__dict__, "raise_rows": 1.0}))
    assert "raise" in tags and sum(map(sum, lv.solid)) == sum(map(sum, level.solid))
    lv, tags = augment(level, random.Random(4), AugmentConfig(**{**OFF.__dict__, "air_start": 1.0}))
    assert "air" in tags and lv.spawn[1] < level.spawn[1]


def test_enemy_augmentation_sets_direction_and_wake():
    level = next(generate(10, s) for s in range(50) if generate(10, s).enemy_spawns)
    lv, tags = augment(level, random.Random(5), AugmentConfig(**{**OFF.__dict__, "enemies": 1.0}))
    sim = Simulation(lv)
    assert "enemies" in tags
    assert {e.wake for e in sim.enemies} <= set(range(12 * TILE, 25 * TILE))


def test_pool_share_lets_fresh_levels_through(tmp_path):
    texts = [generate(10, s).to_text() for s in range(100)]
    with open(tmp_path / "demos_x.jsonl", "w") as f:
        for t in texts:
            f.write(json.dumps({"tier": 10, "level": t}) + "\n")
    source = CurriculumSource(10, 10, pool_dir=tmp_path, pool_share=0.4, augment_prob=0.5)
    source.weights = [0.0] * len(source.weights)
    source.weights[10] = 1.0
    rng = random.Random(0)
    sources = [source(rng)[0] for _ in range(400)]
    fresh = sum(lv.source == "fresh" for lv in sources) / 400
    augmented = sum(bool(lv.augmentations) for lv in sources) / 400
    assert 0.5 < fresh < 0.7 and 0.3 < augmented < 0.7


def test_generator_v9_builds_bait_forks():
    assert any(generate(11, 95000 + s).building_blocks.get("bait_fork") for s in range(40))


def test_cosine_schedule():
    from jumpnrun.rl.train import cosine_schedule

    f = cosine_schedule(1e-4, 8_000_000, target=400_000_000, phase_start=35_000_000)
    at = lambda steps: f(1 - steps / 400_000_000)  # noqa: E731
    assert abs(at(35_000_000) - 1e-4) < 1e-9
    assert abs(at(39_000_000) - 0.55e-4) < 1e-9
    assert abs(at(43_000_000) - 1e-5) < 1e-9 and abs(at(60_000_000) - 1e-5) < 1e-9


def test_wilson_and_dev_mean():
    from jumpnrun.rl.milestones8 import dev_mean, wilson

    lo, hi = wilson(76, 128)
    assert 0.5 <= lo < 0.6 < hi
    assert wilson(75, 128)[0] < 0.5
    m, lo, hi = dev_mean({"dev": {"a": {"won": 8, "of": 16}, "b": {"won": 16, "of": 16}}})
    assert m == 0.75 and lo < m < hi


def test_sealed_levels_are_not_played_during_training():
    for path in ("jumpnrun/rl/milestones8.py", "jumpnrun/rl/train.py", "jumpnrun/rl/curriculum.py"):
        text = (ROOT / path).read_text()
        assert "levels/exam2" not in text and '"sealed"' not in text, path


def test_handmade8_split_is_locked_and_solvable():
    split = json.loads((ROOT / "levels/handmade8/split.json").read_text())
    names = split["dev"] + split["test"] + split["sealed"]
    assert len(names) == 12 and len(set(names)) == 12
    for name in names:
        path = ROOT / "levels/handmade8" / f"{name}.txt"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == split["sha256"][name]
        solution = json.loads((ROOT / "levels/handmade8" / f"{name}.loesung.json").read_text())
        assert replay(Level.from_file(path), solution["actions"], solution["action_repeat"]).status == Status.WON


def test_probes_cover_every_skill():
    data = json.loads((ROOT / "levels/probes/v9.json").read_text())
    skills = {}
    for item in data["levels"]:
        skills[item["skill"]] = skills.get(item["skill"], 0) + 1
    assert len(skills) == 7 and min(skills.values()) >= 10


def test_obs_v2_surgery_keeps_behaviour():
    import numpy as np
    import torch
    from stable_baselines3.common.vec_env import DummyVecEnv

    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
    from jumpnrun.rl.modelinfo import grow_vec, load_model

    path = ROOT / "models/phase7_final.zip"
    old = load_model(path)
    level = Level.from_file(ROOT / "levels/exam/level.txt")
    env = DummyVecEnv([lambda: JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True, obs_v2=True)])
    new = grow_vec(path, env)
    e = JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True, obs_v2=True)
    obs, _ = e.reset(seed=1)
    for _ in range(40):
        obs, *_ = e.step(2)
    o_new = {k: torch.as_tensor(v[None]) for k, v in obs.items()}
    o_old = dict(o_new, vec=o_new["vec"][:, :15])
    with torch.no_grad():
        p_old = old.policy.get_distribution(o_old).distribution.probs
        p_new = new.policy.get_distribution(o_new).distribution.probs
    assert obs["vec"].shape == (21,) and np.abs(obs["vec"][15:]).sum() > 0
    assert torch.allclose(p_old, p_new, atol=1e-6)


def test_stuck_death_ends_the_episode():
    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels

    level = generate(0, 1)
    e = JumpNRunEnv(fixed_levels([level]), action_repeat=2, stuck_death=True)
    e.no_progress_steps = 50  # the short level would hit its time limit first
    e.reset(seed=0)
    for _ in range(2000):
        _, r, term, trunc, info = e.step(0)  # idle: no progress
        if term or trunc:
            break
    assert term and not trunc and info["episode_end"]["outcome"] == "stuck" and r < 0


def test_plr_buffer_fills_and_replays():
    source = CurriculumSource(6, 6, plr=0.5)
    source.weights = [0.0] * len(source.weights)
    source.weights[6] = 1.0
    rng = random.Random(1)
    for i in range(80):
        level, tier = source(rng)
        source.feedback(level, tier, won=i % 3 == 0)
    replayed = sum(source(rng)[0].source == "plr" for _ in range(200))
    assert len(source._plr) >= 50 and 60 < replayed < 140
