"""Phase 10: repaired measurement, LR stages, practice levels, mix by steps, preregistration."""

import hashlib
import json
import random
import sys
from pathlib import Path

from jumpnrun.core import Level
from jumpnrun.levelgen.distmap import DistanceMap
from jumpnrun.levelgen.skills import KINDS, SkillSource, make_skill_level
from jumpnrun.rl.curriculum import MixSource
from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
from jumpnrun.rl.train import staged_schedule

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _hash(level: Level) -> str:
    return hashlib.sha256(level.to_text().encode()).hexdigest()


def test_dev_solutions_win_with_the_repaired_measurement():
    from check_solutions10 import allowed_solutions, outcome

    for name, path, actions, repeat in allowed_solutions():
        assert outcome(Level.from_file(path), actions, repeat) == "won", name


def test_path_time_limit_follows_the_way_length():
    level = Level.from_file(ROOT / "levels/handmade9/serpentine.txt")
    old = JumpNRunEnv(fixed_levels([level]), action_repeat=2)
    new = JumpNRunEnv(fixed_levels([level]), action_repeat=2, progress="path")
    old.reset(seed=0)
    new.reset(seed=0)
    assert new.max_steps >= old.max_steps and new.start_dist is not None


def test_staged_learning_rate_never_restarts(tmp_path):
    plan = {"stages": [[0, 5e-5], [3_000_000, 3e-5], [6_000_000, 2e-5]], "critic_warmup": 150_000, "ramp": 300_000}
    target, start = 60_450_000, 50_000_000
    f = staged_schedule(plan, target, start, tmp_path)
    lr = lambda steps: f(1 - steps / target)  # noqa: E731
    assert lr(start + 300_000) < 5e-5 and abs(lr(start + 500_000) - 5e-5) < 1e-12
    assert abs(lr(start + 4_000_000) - 3e-5) < 1e-12 and abs(lr(start + 7_000_000) - 2e-5) < 1e-12
    again = staged_schedule(plan, target, start, tmp_path)  # a resume gives the same value
    assert again(1 - (start + 4_000_000) / target) == lr(start + 4_000_000)
    (tmp_path / "lr_scale.json").write_text(json.dumps({"scale": 0.5}))
    braked = staged_schedule(plan, target, start, tmp_path)
    assert abs(braked(1 - (start + 7_000_000) / target) - 1e-5) < 1e-12


class _Fixed:
    def __init__(self, name, steps):
        self.name, self.n = name, steps
        self.weights = []

    def __call__(self, rng):
        lv = Level.from_file(ROOT / "levels/handmade8/abgrund.txt")
        lv.ep_steps = self.n
        return lv, 5

    def feedback(self, *a, **k):
        pass


def test_mix_holds_the_shares_in_steps():
    # practice episodes are 10x shorter: shares must still hold in steps, not episodes
    mix = MixSource({"p8": _Fixed("p8", 1000), "skill": _Fixed("skill", 100), "v10": _Fixed("v10", 1500)},
                    [[0, {"skill": 0.55, "v10": 0.0, "p8": 0.45}], [3_000_000, {"skill": 0.1, "v10": 0.3, "p8": 0.6}]])
    rng = random.Random(0)
    for stage, want in ((0, {"skill": 0.55, "v10": 0.0, "p8": 0.45}), (1, {"skill": 0.1, "v10": 0.3, "p8": 0.6})):
        mix.set_mix_stage(stage)
        for _ in range(3000):
            lv, tier = mix(rng)
            mix.feedback(lv, tier, False, steps=lv.ep_steps, fresh=True)
        total = sum(mix.steps.values())
        for k, v in want.items():
            assert abs(mix.steps[k] / total - v) < 0.01, (stage, k)


def test_practice_levels_are_reachable_and_open_the_next_stage():
    for kind in KINDS:
        lv = make_skill_level(kind, 0, f"test10:{kind}")
        assert DistanceMap(lv).reachable
    src = SkillSource()
    lv, tier = src(random.Random(1))
    for _ in range(100):
        src.feedback(lv, True, fresh=True)
    assert src.level[lv.skill_kind] == 1 and tier == -4


def test_no_training_level_is_an_evaluation_level():
    # only allowed groups are read here (exam, dev, test series, probes, guard) - sealed levels are never opened
    evaluation = {_hash(Level.from_file(p)) for p in [ROOT / "levels/exam/level.txt",
                                                      *sorted((ROOT / "levels/test_serie").glob("*.txt"))]}
    for folder in ("handmade8", "handmade9"):
        split = json.loads((ROOT / "levels" / folder / "split.json").read_text())
        evaluation |= {_hash(Level.from_file(ROOT / "levels" / folder / f"{n}.txt")) for n in split["dev"]}
    for probes in ("v10.json", "v11_skills.json"):
        path = ROOT / "levels/probes" / probes
        if path.exists():
            evaluation |= {_hash(Level.from_text(i["text"])) for i in json.loads(path.read_text())["levels"]}
    rng = random.Random(3)
    src = SkillSource()
    assert not any(_hash(src(rng)[0]) in evaluation for _ in range(200))
    demos = [make_skill_level(KINDS[i % 7], 2, f"demo10:{KINDS[i % 7]}:2:{i}") for i in range(14)]
    assert not any(_hash(lv) in evaluation for lv in demos)


def test_autopilot_refuses_an_uncommitted_preregistration(monkeypatch, capsys):
    from jumpnrun.rl import autopilot10

    monkeypatch.setattr(autopilot10, "prereg_committed", lambda: False)
    monkeypatch.setattr(autopilot10, "save_state", lambda state: None)
    called = []
    monkeypatch.setattr(autopilot10, "tick_a", lambda state: called.append(1))
    autopilot10.tick()
    assert not called and "nicht committet" in capsys.readouterr().out
