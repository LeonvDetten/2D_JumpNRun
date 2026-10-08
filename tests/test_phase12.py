"""Phase 12: generator v11, leg-wise path solver, teacher routing, multi-teacher KL, strict demo replay, mix gates."""

import hashlib
import json
import random
from pathlib import Path

import numpy as np
import pytest

from jumpnrun.core import Level
from jumpnrun.levelgen.distmap import DistanceMap
from jumpnrun.levelgen.hard import FAMILIES, HardSource, LongMixSource, make_hard_level
from jumpnrun.rl.curriculum import MixSource

ROOT = Path(__file__).resolve().parent.parent


def _hash(level: Level) -> str:
    return hashlib.sha256(level.to_text().encode()).hexdigest()


@pytest.mark.parametrize("family", FAMILIES)
def test_v11_levels_are_reachable(family):
    for i in range(3 if family != "lang" else 1):
        lv = make_hard_level(family, f"t12:{family}:{i}")
        assert DistanceMap(lv).reachable and lv.family == f"v11_{family}"
        assert lv.to_text().count("P") == 1 and lv.to_text().count("C") == 1


def test_leg_solver_solves_a_jump_level():
    from jumpnrun.levelgen.solver import solve_path_legs

    lv = make_hard_level("spruenge", "s:spruenge:0")
    assert solve_path_legs(lv, action_repeat=2, leg_budget=30_000, total_budget=150_000).solved


def test_sources_and_families():
    rng = random.Random(1)
    lv, tier = HardSource()(rng)
    assert lv.source == "hart" and lv.family.startswith("v11_")
    lv, tier = LongMixSource()(rng)
    assert lv.cols > 250 and lv.family in ("lang", "v11_lang")


class _Fixed:
    def __init__(self, level, tier=5):
        self.level, self.tier, self.weights = level, tier, [1.0] * 14

    def __call__(self, rng):
        lv = Level.from_text(self.level.to_text())
        for k in ("skill_kind", "family", "augmentations", "building_blocks"):
            if hasattr(self.level, k):
                setattr(lv, k, getattr(self.level, k))
        return lv, self.tier

    def feedback(self, *a, **k):
        pass


def test_routing_sets_the_teacher_and_skips_p8_at_forks():
    plain = Level.from_text("P   C\nBBBBB\n")
    fork = Level.from_text("P   C\nBBBBB\n")
    fork.building_blocks = {"bait_fork": 1}
    hard = Level.from_text("P   C\nBBBBB\n")
    hard.family = "v11_spruenge"
    routing = {"v9_t5": 0, "_p8": 0, "v11_spruenge": -1}
    for level, name, want in ((plain, "p8", 0), (fork, "p8", -1), (hard, "hart", -1)):
        mix = MixSource({name: _Fixed(level)} if name == "p8" else {"p8": _Fixed(plain), name: _Fixed(level)},
                        [[0, {name: 1.0}]], routing=routing)
        lv, _ = mix(random.Random(0))
        assert lv.teacher_id == want


def test_gates_hold_a_source_back_until_its_tier():
    plain = Level.from_text("P   C\nBBBBB\n")
    mix = MixSource({"p8": _Fixed(plain), "hart": _Fixed(plain)}, [[0, {"p8": 0.5, "hart": 0.5}]], gates={"hart": 10})
    mix.weights = [1.0] * 5 + [0.0] * 9
    assert set(mix.shares()) == {"p8"}
    mix.weights = [1.0] * 11 + [0.0] * 3
    assert set(mix.shares()) == {"p8", "hart"}


def test_multi_teacher_kl_is_zero_for_the_student_itself():
    import torch

    from jumpnrun.rl.modelinfo import load_model

    path = ROOT / "models/phase11_kandidat.zip"
    if not path.exists():
        pytest.skip("model not in this checkout")
    model = load_model(path)
    rng = np.random.default_rng(0)
    obs = {k: rng.random((32, *s.shape)).astype(np.float32) for k, s in model.observation_space.spaces.items()}
    t = model.policy.get_distribution({k: torch.as_tensor(v) for k, v in obs.items()}).distribution.probs
    s = torch.log_softmax(model.policy.get_distribution({k: torch.as_tensor(v) for k, v in obs.items()})
                          .distribution.logits, dim=1)
    assert float((t * (t.clamp_min(1e-8).log() - s)).sum(1).mean()) < 1e-5


def test_strict_replay_drops_a_demo_that_does_not_win():
    from jumpnrun.imitation.demos import load_dataset

    demos = [json.loads(l) for l in open(ROOT / "runs/demos_spiegel/demos.jsonl")][:3] \
        if (ROOT / "runs/demos_spiegel/demos.jsonl").exists() else []
    if not demos:
        pytest.skip("demo data not in this checkout")
    broken = dict(demos[0], actions=[0] * 20, mask=[1] * 20)
    tmp = ROOT / "runs/phase12/_test_demos.jsonl"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text("".join(json.dumps(d) + "\n" for d in [broken, demos[1]]))
    strict = load_dataset([tmp], overview=True, obs_v3=True, progress="path", thin_flat=0.0)
    loose = load_dataset([tmp], overview=True, obs_v3=True, thin_flat=0.0)
    tmp.unlink()
    assert len(strict["action"]) < len(loose["action"])
    assert strict["vec"][:, 17].min() < 1.0  # time left changes along the run (strict bookkeeping)


def test_no_v11_level_is_a_measurement_level():
    evaluation = {_hash(Level.from_file(p)) for p in [ROOT / "levels/exam/level.txt",
                                                      *sorted((ROOT / "levels/test_serie").glob("*.txt"))]}
    for folder in ("handmade8", "handmade9"):
        split = json.loads((ROOT / "levels" / folder / "split.json").read_text())
        evaluation |= {_hash(Level.from_file(ROOT / "levels" / folder / f"{n}.txt")) for n in split["dev"]}
    g = json.loads((ROOT / "levels/handmade10/split.json").read_text())
    evaluation |= {_hash(Level.from_file(ROOT / "levels/handmade10" / f"{n}.txt")) for n in g["val"] + g["val_plus"]}
    for probes in ("v10.json", "v11_skills.json", "v12_lange_sackgasse.json", "v13_hard.json"):
        path = ROOT / "levels/probes" / probes
        if path.exists():
            evaluation |= {_hash(Level.from_text(i["text"])) for i in json.loads(path.read_text())["levels"]}
    rng = random.Random(7)
    src = HardSource()
    assert not any(_hash(src(rng)[0]) in evaluation for _ in range(40))
