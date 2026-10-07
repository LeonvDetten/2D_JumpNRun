"""Phase 11: lange_sackgasse, long and mirrored long levels, demo enemy direction, central practice state,
teacher floor, channels_last, mix shares, no training level is an evaluation level."""

import hashlib
import json
import random
from pathlib import Path

import numpy as np
import pytest

from jumpnrun.core import Level
from jumpnrun.levelgen.distmap import DistanceMap
from jumpnrun.levelgen.skills import (KINDS11, LongSource, MirrorSource, SkillSource, SkillTracker, concat_levels,
                                      make_skill_level)
from jumpnrun.levelgen import generator as G
from jumpnrun.rl.curriculum import MixSource

ROOT = Path(__file__).resolve().parent.parent


def _hash(level: Level) -> str:
    return hashlib.sha256(level.to_text().encode()).hexdigest()


@pytest.mark.parametrize("d", [0, 1, 2])
def test_lange_sackgasse_is_reachable_and_long(d):
    for i in range(4):
        lv = make_skill_level("lange_sackgasse", d, f"t11:{d}:{i}")
        dm = DistanceMap(lv)
        assert dm.reachable and dm.start is not None
        assert lv.skill_kind == "lange_sackgasse" and lv.difficulty == d
        if d < 2:  # spawn on the road: the way first leads back (to the left) before it goes right
            assert dm.start > lv.cols - lv.spawn[0] // 40


def test_long_levels_join_two_generator_levels():
    rng = random.Random(1)
    src = LongSource()
    for _ in range(5):
        lv, tier = src(rng)
        assert tier == LongSource.LONG_TIER and lv.cols > 250
        assert lv.to_text().count("C") == 1 and lv.to_text().count("P") == 1
        assert DistanceMap(lv).reachable


def test_concat_keeps_the_way():
    a, b = G.generate(8, 11), G.generate(9, 12)
    lv = concat_levels(a, b)
    assert lv is not None and lv.cols == a.cols - 1 + 4 + b.cols


def test_mirrored_long_levels_have_the_chest_on_the_left():
    rng = random.Random(4)
    src = MirrorSource(long_share=1.0)
    lv, _ = src(rng)
    assert "lang" in lv.augmentations and lv.goal_x < lv.spawn[0] and lv.cols > 250


def test_mirrored_phase9_demos_replay_with_their_enemy_direction():
    from jumpnrun.core.actions import BOT_ACTIONS_V3
    from jumpnrun.core.sim import Simulation, Status
    from jumpnrun.imitation.demos import demo_enemy_dir

    def wins(path, limit):
        demos = [json.loads(l) for l in open(path) if l.strip()]
        demos = [d for d in demos if d.get("kind") == "spiegel" and d.get("won")][:limit]
        n = 0
        for d in demos:
            lv = Level.from_text(d["level"])
            if demo_enemy_dir(d) and lv.enemy_spawns:
                lv.enemy_directions = [demo_enemy_dir(d)] * len(lv.enemy_spawns)
            sim = Simulation(lv)
            for a in d["actions"]:
                sim.step(BOT_ACTIONS_V3[a], frames=d["repeat"])
                if sim.status != Status.RUNNING:
                    break
            n += sim.status == Status.WON
        return n, len(demos)

    p9 = ROOT / "runs/demos9/demos.jsonl"
    own = ROOT / "runs/demos_spiegel/demos.jsonl"
    if not p9.exists() or not own.exists():
        pytest.skip("demo data not in this checkout")
    won, n = wins(p9, 51)
    assert won >= 48 and n >= 48
    won, n = wins(own, 40)
    assert won == n


def test_central_practice_state_survives_a_restart():
    t = SkillTracker()
    for _ in range(100):
        t.record("lange_sackgasse", 0, True)
    assert t.level["lange_sackgasse"] == 1
    t2 = SkillTracker()
    t2.load(json.loads(json.dumps(t.state())))
    assert t2.level == t.level and t2.p() == t.p()
    src = SkillSource(kinds=KINDS11)
    src.set_state(t2.level, t2.p())
    src.feedback(make_skill_level("kanal2", 0, "t11:x"), True)  # central: no local bookkeeping
    assert src.level["lange_sackgasse"] == 1 and all(not h for h in src.hist.values())


def test_teacher_plan_keeps_its_floor():
    from jumpnrun.rl.ppo_demos import PPOWithDemos

    plan = json.loads((ROOT / "docs/lernen/daten/phase11_vorregistrierung.json").read_text())["lehrer"]["plan"]
    fake = type("F", (), {})()
    fake.teacher_plan, fake.phase10_start, fake.teacher_path = plan, 72_000_000, "p8"
    for rel, want in ((0, 1.0), (6_000_000, 0.3), (8_150_000, 0.3)):
        fake.num_timesteps = 72_000_000 + rel
        assert abs(PPOWithDemos.teacher_coef(fake) - want) < 1e-6


def test_channels_last_keeps_the_outputs():
    import torch

    from jumpnrun.rl.modelinfo import load_model

    path = ROOT / "models/phase10_kandidat_lehrer.zip"
    if not path.exists():
        pytest.skip("model not in this checkout")
    a, b = load_model(path), load_model(path)
    b.policy.to(memory_format=torch.channels_last)
    rng = np.random.default_rng(0)
    obs = {k: torch.as_tensor(rng.random((64, *s.shape)).astype(np.float32)) for k, s in a.observation_space.spaces.items()}
    with torch.no_grad():
        la = a.policy.get_distribution(obs).distribution.logits
        lb = b.policy.get_distribution(obs).distribution.logits
    assert (la - lb).abs().max().item() <= 1e-4


def test_mix_holds_the_phase11_shares_in_steps():
    shares = json.loads((ROOT / "configs/phase11/a.json").read_text())[0][1]

    class Fixed:
        def __init__(self, n, steps):
            self.n, self.s = n, steps

        def __call__(self, rng):
            lv = Level.from_text("P   C\nBBBBB\n")
            return lv, 0

        def feedback(self, *a, **k):
            pass

    lens = {"p8": 300, "skill": 40, "v10": 400, "lang": 900, "spiegel": 350}
    mix = MixSource({n: Fixed(n, s) for n, s in lens.items()}, [[0, shares]])
    rng = random.Random(0)
    for _ in range(6000):
        lv, tier = mix(rng)
        mix.feedback(lv, tier, False, steps=lens[lv.mix_source])
    total = sum(mix.steps.values())
    for n, s in shares.items():
        assert abs(mix.steps[n] / total - s) < 0.03


def test_no_new_training_level_is_an_evaluation_level():
    # only allowed groups are read (exam, test series, dev, probes, guard val/val_plus) - sealed/test never opened
    evaluation = {_hash(Level.from_file(p)) for p in [ROOT / "levels/exam/level.txt",
                                                      *sorted((ROOT / "levels/test_serie").glob("*.txt"))]}
    for folder in ("handmade8", "handmade9"):
        split = json.loads((ROOT / "levels" / folder / "split.json").read_text())
        evaluation |= {_hash(Level.from_file(ROOT / "levels" / folder / f"{n}.txt")) for n in split["dev"]}
    g = json.loads((ROOT / "levels/handmade10/split.json").read_text())
    evaluation |= {_hash(Level.from_file(ROOT / "levels/handmade10" / f"{n}.txt")) for n in g["val"] + g["val_plus"]}
    for probes in ("v10.json", "v11_skills.json", "v12_lange_sackgasse.json"):
        path = ROOT / "levels/probes" / probes
        if path.exists():
            evaluation |= {_hash(Level.from_text(i["text"])) for i in json.loads(path.read_text())["levels"]}
    rng = random.Random(5)
    skill = SkillSource(kinds=KINDS11, boost={"lange_sackgasse": 2.0})
    assert not any(_hash(skill(rng)[0]) in evaluation for _ in range(150))
    long_src, mirror = LongSource(), MirrorSource(long_share=0.3)
    assert not any(_hash(long_src(rng)[0]) in evaluation for _ in range(10))
    assert not any(_hash(mirror(rng)[0]) in evaluation for _ in range(20))
