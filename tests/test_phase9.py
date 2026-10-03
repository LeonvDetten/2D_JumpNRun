"""Phase 9: distance map + way reward, left+jump, view v3, generator v10, augmentation v2, measurement."""

import hashlib
import json
import random
from dataclasses import replace
from pathlib import Path

import numpy as np

from jumpnrun.core import Level
from jumpnrun.core.actions import BOT_ACTIONS, BOT_ACTIONS_V3
from jumpnrun.core.sim import Status
from jumpnrun.levelgen.augment import DEFAULT, AugmentConfig, augment
from jumpnrun.levelgen.distmap import DistanceMap
from jumpnrun.levelgen.generator import generate
from jumpnrun.levelgen.solver import replay, solve
from jumpnrun.rl.env import JumpNRunEnv, fixed_levels

ROOT = Path(__file__).resolve().parent.parent
OFF = AugmentConfig(void=0, raise_rows=0, ceiling=0, air_start=0, enemies=0)


def test_distance_grows_on_a_dead_end_road():
    dm = DistanceMap(Level.from_file(ROOT / "levels/handmade8/doppelgabel.txt"))
    road = [dm.dist[(c, 7)] for c in range(21, 44) if (c, 7) in dm.dist]
    assert len(road) > 15 and all(b > a for a, b in zip(road, road[1:]))  # walking on = further from the chest


def test_distance_falls_along_solver_solutions():
    lines = [line for line in (ROOT / "runs/demos4/demos_v2.jsonl").open() if '"level"' in line][:5] \
        if (ROOT / "runs/demos4/demos_v2.jsonl").exists() else []
    levels = [(Level.from_text(json.loads(x)["level"]), json.loads(x)["actions"]) for x in lines]
    if not levels:
        lv = generate(8, 3)
        levels = [(lv, solve(lv, 100_000, action_repeat=2).actions)]
    for lv, actions in levels:
        dm = DistanceMap(lv)
        from jumpnrun.core import Simulation

        sim, best, unknown = Simulation(lv), dm.start, 0
        for a in actions:
            sim.step(BOT_ACTIONS_V3[a], frames=2)
            d = dm.at_player(sim.player)
            if sim.player.on_ground and d is None:
                unknown += 1
            if d is not None:
                assert d <= best + 3
                best = min(best, d)
        assert unknown == 0


def test_path_reward_pays_progress_not_backtracking():
    lv = Level(["", "", "", "", "", "", "", "", "", "", "", " P              C", "B" * 18])
    env = JumpNRunEnv(fixed_levels([lv]), action_repeat=2, path_reward=True)
    env.reset(seed=0)
    total = sum(env.step(2)[1] for _ in range(30))  # right: 30 steps * 16 px = 8 tiles
    assert 0.6 < total < 0.9
    back = sum(env.step(1)[1] for _ in range(10))
    assert back == 0.0


def test_left_jump_makes_mirrored_levels_solvable():
    lv = generate(8, 4)
    rows = [list(line[::-1]) for line in lv._lines]
    rows[1][lv.cols - 1 - lv.spawn[0] // 60] = "P"
    m = Level(["".join(r) for r in rows])
    r = solve(m, 60_000, action_repeat=2, weight=1.2, dm=DistanceMap(m), actions=BOT_ACTIONS_V3)
    assert r.solved and 6 in r.actions and replay(m, r.actions, 2).status == Status.WON
    assert BOT_ACTIONS_V3[:6] == BOT_ACTIONS


def test_obs_v3_spaces_and_surgery():
    import torch
    from stable_baselines3.common.vec_env import DummyVecEnv

    from jumpnrun.rl.modelinfo import grow_v3, load_model

    level = Level.from_file(ROOT / "levels/handmade8/abgrund.txt")
    env = JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True, obs_v3=True)
    assert env.observation_space["grid"].shape == (4, 13, 33) and env.observation_space["overview"].shape == (4, 13, 40)
    assert env.observation_space["vec"].shape == (23,) and env.action_space.n == 7
    old = load_model(ROOT / "models/phase8_final.zip")
    new = grow_v3(ROOT / "models/phase8_final.zip", DummyVecEnv([lambda: JumpNRunEnv(
        fixed_levels([level]), action_repeat=2, overview=True, obs_v3=True)]))
    eo = JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True)
    oo, _ = eo.reset(seed=1)
    on, _ = env.reset(seed=1)
    diffs = []
    for _ in range(60):
        with torch.no_grad():
            po = old.policy.get_distribution({k: torch.as_tensor(v[None]) for k, v in oo.items()}).distribution.probs
            pn = new.policy.get_distribution({k: torch.as_tensor(v[None]) for k, v in on.items()}).distribution.probs
        diffs.append(float((po - pn[:, :6]).abs().max()))
        a = int(po.argmax())
        oo, *_ = eo.step(a)
        on, *_ = env.step(a)
    assert np.mean(diffs) < 0.06 and float(pn[0, 6]) < 0.05


def test_generator_variants_keep_old_tiers():
    for tier in (0, 5, 9):
        assert generate(tier, 11).to_text() == generate(tier, 11, "v10").to_text()
    for tier in (10, 11, 12):
        assert generate(tier, 11).to_text() == generate(tier, 11, "v9").to_text()


def test_generator_v10_builds_new_blocks():
    seen = set()
    for s in range(30):
        seen |= set(generate(13, 500 + s).building_blocks)
    assert {"channel", "channel_end", "pipes", "pyramid", "bridge", "group"} <= seen
    assert any(k.startswith("gabel_") for k in seen)
    gabel = [generate(10, 600 + s, "gabel") for s in range(60)]
    assert any(lv.building_blocks.get("bait_fork") for lv in gabel)
    assert all(lv.needs_path for lv in gabel if lv.building_blocks.get("bait_fork"))


def test_channel_block_is_solvable():
    from jumpnrun.levelgen import generator as G

    b = G._Builder(random.Random(3))
    b.flat(5)
    b.columns[1][b.surface - 1] = "P"
    G._channel(b, G.TIERS[0], final=True)
    lv = Level(["".join(c[r] for c in b.columns) for r in range(13)])
    assert lv.goal_x < (len(b.columns) - 10) * 60  # the chest is on the left end of the channel
    r = solve(lv, 100_000, action_repeat=2, weight=1.2, dm=DistanceMap(lv), actions=BOT_ACTIONS_V3)
    assert r.solved


def test_augment_v2_mirror_and_concat():
    lv = generate(8, 2)
    m, tags = augment(lv, random.Random(0), replace(OFF, mirror=1.0))
    assert tags == ["mirror"] and m.goal_x < m.spawn[0] and m.needs_path
    c, tags = augment(lv, random.Random(0), replace(OFF, concat=1.0), partner=generate(8, 3))
    assert tags == ["concat"] and c.cols > lv.cols + 100 and len(c.chests) == 1
    a, ta = augment(lv, random.Random(5), DEFAULT)  # phase 8 default: no new augmentation
    assert not {"mirror", "concat", "density", "noise"} & set(ta)


def test_augment_v2_keeps_levels_reachable():
    from jumpnrun.levelgen.augment import V2

    bad = 0
    for i in range(40):
        rng = random.Random(i)
        out, _ = augment(generate(10 + i % 4, i, "v10"), rng, V2, partner=generate(10, 1000 + i, "v10"))
        dm = DistanceMap(out)
        bad += not (dm.reachable and dm.start is not None)
    assert bad <= 2


def test_handmade9_split_is_locked_and_solvable():
    split = json.loads((ROOT / "levels/handmade9/split.json").read_text())
    names = split["dev"] + split["test"] + split["sealed"]
    assert len(names) == 12 and len(set(names)) == 12
    for name in names:
        path = ROOT / "levels/handmade9" / f"{name}.txt"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == split["sha256"][name]
        solution = json.loads((ROOT / "levels/handmade9" / f"{name}.loesung.json").read_text())
        assert replay(Level.from_file(path), solution["actions"], solution["action_repeat"]).status == Status.WON


def test_probes_v10_cover_every_skill():
    data = json.loads((ROOT / "levels/probes/v10.json").read_text())
    skills = {}
    for item in data["levels"]:
        skills[item["skill"]] = skills.get(item["skill"], 0) + 1
    assert len(skills) == 13 and min(skills.values()) >= 10


def test_sealed_levels_are_not_played_during_training():
    for path in ("jumpnrun/rl/milestones9.py", "jumpnrun/rl/autopilot9.py", "jumpnrun/rl/train.py",
                 "jumpnrun/rl/curriculum.py", "jumpnrun/rl/status9.py"):
        text = (ROOT / path).read_text()
        assert "levels/exam2" not in text and '"sealed"' not in text, path


def _fake_round(tmp_path, monkeypatch, neu, kontrolle, alt=(0.7, 0.7), start=50_000_000):
    import jumpnrun.rl.autopilot9 as ap

    monkeypatch.setattr(ap, "ROOT", tmp_path)
    monkeypatch.setattr(ap, "stop", lambda run: None)
    for arm, values, a in (("neu", neu, alt[0]), ("kontrolle", kontrolle, alt[1])):
        run = tmp_path / f"runs/phase9_r1_{arm}"
        run.mkdir(parents=True)
        ms = {f"{start + (i + 1) * 1_000_000}:ema": {"dev_mean": [v, v - 0.1, v + 0.1], "dev_alt": [a, 0, 1],
                                                     "schutz": {"won": 70}} for i, v in enumerate(values)}
        (run / "milestones9.json").write_text(json.dumps(ms))
    state = {"rounds": {"1": {"start_steps": start, "baseline": 0.6, "stopped": []}}, "log": []}
    return ap, state


def test_judging_new_arm_wins_with_three_points(tmp_path, monkeypatch):
    ap, state = _fake_round(tmp_path, monkeypatch, [0.70] * 6, [0.66] * 6)
    assert ap.judge(state, 1) == "neu"


def test_judging_new_arm_must_not_lose_the_old_levels(tmp_path, monkeypatch):
    ap, state = _fake_round(tmp_path, monkeypatch, [0.75] * 6, [0.66] * 6, alt=(0.60, 0.70))
    assert ap.judge(state, 1) == "kontrolle"


def test_round_two_adds_the_way_reward_if_the_control_won(tmp_path, monkeypatch):
    import jumpnrun.rl.autopilot9 as ap

    monkeypatch.setattr(ap, "note", lambda state, text: None)
    state = {"start": "x_step_0055000000.zip", "base_flags": ["--plr", "0.3"], "rounds": {"2": {"baseline": 0.6}}}
    ap.start_round(state, 2)
    flags = state["rounds"]["2"]["flags"]
    assert "--path-reward" in flags["neu"] and "--obs-v3" in flags["neu"] and "--path-reward" not in flags["kontrolle"]


def test_path_delta_rewards_turning_back():
    lv = Level(["", "", "", "", "", "", "", "", "", "", "", " P              C", "B" * 18])
    env = JumpNRunEnv(fixed_levels([lv]), action_repeat=2, path_delta=True)
    env.reset(seed=0)
    forward = sum(env.step(2)[1] for _ in range(30))
    back = sum(env.step(1)[1] for _ in range(10))
    again = sum(env.step(2)[1] for _ in range(10))
    assert forward > 0.6 and back < -0.1 and abs(back + again) < 1e-9  # loops sum to zero
