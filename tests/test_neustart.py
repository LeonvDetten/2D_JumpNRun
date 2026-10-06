"""Neustart arm: strict demo rendering, kickstarting mask, v10 gate, pooled practice state, abort rule, LR plan."""

import json
import random
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from jumpnrun.core import Level
from jumpnrun.levelgen.generator import NUM_TIERS
from jumpnrun.levelgen.skills import KINDS, SkillSource, SkillTracker
from jumpnrun.rl.curriculum import MixSource

ROOT = Path(__file__).resolve().parent.parent


def test_path_rendering_changes_only_the_step_bookkeeping(tmp_path):
    from jumpnrun.imitation.demos import load_dataset, make_demo

    demos = [d for d in (make_demo(t, s) for t, s in ((3, 1), (5, 2))) if d]
    path = tmp_path / "demos.jsonl"
    path.write_text("".join(json.dumps(d) + "\n" for d in demos))
    x = load_dataset([path], thin_flat=0.0, overview=True, obs_v3=True)
    p = load_dataset([path], thin_flat=0.0, overview=True, obs_v3=True, progress="path")
    for k in ("grid", "overview", "action", "allowed"):
        assert np.array_equal(x[k], p[k]), k
    keep = np.ones(23, bool)
    keep[16:18] = False
    assert np.array_equal(x["vec"][:, keep], p["vec"][:, keep])
    assert (x["vec"][:, 17] == 1.0).all() and p["vec"][:, 17].min() < 1.0  # time left now runs down


@pytest.mark.skipif(not (ROOT / "runs/demos9/demos.jsonl").exists(), reason="phase-9 demos not unpacked")
def test_mirrored_demos_replay_to_a_win():
    from jumpnrun.imitation.demos import _render_demo

    demos = [json.loads(l) for l in open(ROOT / "runs/demos9/demos.jsonl") if '"spiegel"' in l][:12]
    assert demos
    out = {k: [] for k in ("grid", "vec", "overview", "action", "allowed")}
    rng = random.Random(0)
    assert all(_render_demo(d, rng, out, True, True, 2 / 3, "path") for d in demos)


def test_mix_gate_keeps_v10_closed_until_tier_10_and_renormalises():
    calls = []

    def src(name):
        def call(rng):
            calls.append(name)
            return Level.from_text("\n".join([""] * 11 + [" P   C", "BBBBBBB"])), 0
        call.feedback = lambda *a, **k: None
        return call

    p8 = src("p8")
    p8.weights = None
    mix = MixSource({"p8": p8, "skill": src("skill"), "v10": src("v10")},
                    [[0, {"p8": 0.6, "skill": 0.2, "v10": 0.2}]], gates={"v10": 10})
    mix.weights = [1.0] * 4 + [0.0] * (NUM_TIERS - 4)
    assert mix.shares() == pytest.approx({"p8": 0.75, "skill": 0.25})
    rng = random.Random(0)
    for _ in range(400):
        level, _ = mix(rng)
        mix.feedback(level, 0, False, steps=10)
    assert "v10" not in calls
    assert mix.steps["p8"] / (mix.steps["p8"] + mix.steps["skill"]) == pytest.approx(0.75, abs=0.02)
    mix.weights = [1.0] * 11 + [0.0] * (NUM_TIERS - 11)  # tier 10 unlocked: v10 opens, counters start again
    assert sum(mix.steps.values()) == 0
    assert mix.shares() == pytest.approx({"p8": 0.6, "skill": 0.2, "v10": 0.2})


def test_skill_tracker_pools_saves_and_steers_the_envs():
    t = SkillTracker()
    for i in range(SkillTracker.WINDOW):
        t.record("kanal2", 0, i % 10 != 0)  # 90 % fresh wins
    assert t.level["kanal2"] == 1 and t.level["kanal_ende"] == 0
    t2 = SkillTracker()
    t2.load(json.loads(json.dumps(t.state())))
    assert t2.level == t.level and t2.hist == t.hist
    s = SkillSource()
    s.set_state(t.level, t.p())
    assert s.level["kanal2"] == 1
    level = Level.from_text("\n".join([""] * 11 + [" P   C", "BBBBBBB"]))
    level.skill_kind, level.difficulty = "kanal_ende", 0
    for _ in range(200):
        s.feedback(level, True)
    assert s.level["kanal_ende"] == 0  # central state: the env does not open difficulties on its own
    assert set(t.p()) == set(KINDS)


def test_kickstart_weight_is_linear_in_steps_since_the_phase_start():
    from jumpnrun.rl.ppo_demos import PPOWithDemos

    m = SimpleNamespace(kickstart_plan=[[0, 1.0], [15_000_000, 0.0]], kickstart_path="p8.zip", phase10_start=0)
    for steps, want in ((0, 1.0), (7_500_000, 0.5), (15_000_000, 0.0), (40_000_000, 0.0)):
        m.num_timesteps = steps
        assert PPOWithDemos.kickstart_coef(m) == pytest.approx(want)
    m.kickstart_path = None
    assert PPOWithDemos.kickstart_coef(m) == 0.0


def test_kickstart_mask_matches_the_level_of_each_stored_observation():
    """The recorder's mask at rollout position t must describe the observation stored at t (the state BEFORE
    step t) - also across episode ends, where DummyVecEnv already resets inside step."""

    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecMonitor

    from jumpnrun.levelgen.skills import SkillSource
    from jumpnrun.rl.curriculum import CurriculumSource
    from jumpnrun.rl.env import JumpNRunEnv
    from jumpnrun.rl.policy import GridFeatures
    from jumpnrun.rl.ppo_demos import KickstartRecorder

    truth = {}

    class Env(JumpNRunEnv):
        def step(self, action):
            truth.setdefault(self.rank, []).append(getattr(self.level, "mix_source", None) == "p8")
            return super().step(action)

    def make(rank):
        def init():
            p8 = CurriculumSource(0, 1)
            mix = MixSource({"p8": p8, "skill": SkillSource()}, [[0, {"p8": 0.5, "skill": 0.5}]])
            env = Env(mix, seed=rank, overview=True, obs_v3=True, path_delta=True)
            env.rank = rank
            return env
        return init

    venv = VecMonitor(DummyVecEnv([make(i) for i in range(3)]))
    model = PPO("MultiInputPolicy", venv, n_steps=96, batch_size=96, n_epochs=1, device="cpu", seed=0,
                policy_kwargs=dict(features_extractor_class=GridFeatures, net_arch=dict(pi=[16], vf=[16])))
    model.learn(96 * 3, callback=KickstartRecorder.make())
    mask = model.ks_mask
    assert mask.shape == (96, 3)
    for rank in range(3):
        assert list(mask[:, rank]) == truth[rank][-96:]
    assert mask.any() and not mask.all()


def test_abort_rule_pools_blocks_and_waits_for_missing_measurements():
    from jumpnrun.rl.autopilot_neustart import abort_check

    def m(won, F, guard=None):
        r = {"dev": {"pruefung": {"won": won, "of": 32}, "serie_berg": {"won": won, "of": 16},
                     "hand9_x": {"won": 0, "of": 16}}, "F": F}
        if guard is not None:
            r["waechter_val"] = {"g0": {"won": guard, "of": 32}}
        return r

    rule = {"millionen": [4, 5], "messungen": ["ema", "raw"], "abbruch_wenn_unter": {"dev_alt": 0.10, "F": 0.10}}
    ms = {"4000000:ema": m(8, 0.2), "4000008:raw": m(8, 0.2), "5000000:ema": m(8, 0.2)}
    assert abort_check(ms, rule) is None  # raw of block 5 missing
    ms["5012345:raw"] = m(0, 0.0)
    abort, nums = abort_check(ms, rule)
    assert nums["n"] == 4 and not abort  # hand9 levels are not part of dev_alt
    assert nums["dev_alt"] == pytest.approx((24 / 128 + 24 / 64) / 2, abs=1e-4)  # attempts added up per level
    rule30 = {"millionen": [28, 30], "messungen": ["ema", "ema2"],
              "abbruch_wenn_unter": {"dev_alt": 0.5, "waechter_val": 0.5}}
    ms = {f"{s}:{k}": m(30, 0.4, guard=10) for s in (28_000_000, 30_000_000) for k in ("ema", "ema2")}
    abort, nums = abort_check(ms, rule30)
    assert abort and nums["unter"] == ["waechter_val"]


def test_cosine_lr_plan_with_critic_warmup_and_ramp(tmp_path):
    from jumpnrun.rl.train import staged_schedule

    plan = {"cosine": [2e-4, 2e-5, 45_000_000], "ramp": 200_000, "critic_warmup": 150_000}
    target = 45_000_000
    f = staged_schedule(plan, target, 0, tmp_path)
    at = lambda steps: f(1.0 - steps / target)  # noqa: E731
    assert at(100_000) == pytest.approx(2e-4, rel=1e-3)  # critic warm-up: full rate, only the value head learns
    assert at(250_000) == pytest.approx(2e-4 * 0.5, rel=1e-2)
    assert at(22_500_000) == pytest.approx(1.1e-4, rel=1e-2)
    assert at(45_000_000) == pytest.approx(2e-5, rel=1e-3)
    (tmp_path / "lr_scale.json").write_text('{"scale": 0.5}')
    g = staged_schedule(plan, target, 0, tmp_path)
    assert g(1.0 - 45_000_000 / target) == pytest.approx(1e-5, rel=1e-3)


def test_preregistration_is_complete():
    pr = json.loads((ROOT / "docs/lernen/daten/neustart_vorregistrierung.json").read_text())
    for key in ("arme", "ziel_schritte", "zeit_stunden", "bc", "startpruefung", "lernrate", "mischung",
                "mischung_sperre", "bc2_plan", "kickstart_plan", "abbruchregel", "sicherung_millionen"):
        assert key in pr, key
    assert sum(pr["mischung"].values()) == pytest.approx(1.0)
    assert [r["name"] for r in pr["abbruchregel"]] == ["+5M", "+15M", "+30M"]
