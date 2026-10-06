"""Phase 10 D: architecture test by imitation - does the network or the view limit the generalist?

    OMP_NUM_THREADS=1 nice taskset -c 2,3 python3 scripts/arch_test10.py data      # teacher data (~1 h on 2 cores)
    OMP_NUM_THREADS=1 nice taskset -c 2,3 python3 scripts/arch_test10.py train     # 4 variants (~40 min)
    OMP_NUM_THREADS=1 nice taskset -c 2,3 python3 scripts/arch_test10.py play      # closed loop (~1 h)
    -> runs/arch10/result.json

Teachers (one data set, the same for every variant):
    alt      P8 playing generated v9 levels (tiers 6-12, seed space "arch10"), soft labels = P8's probabilities
    neu      the solver's actions of the phase-10 teacher demos (practice levels, runs/demos10)
    spiegel  the solver on MIRRORED generated levels (tiers 4-9, chest on the left)
Variants (same training budget):
    heute       today's view (grid 13 behind / 19 ahead) and network
    symm        symmetric view (19 behind / 19 ahead)
    gedaechtnis today's view + the grid of 6 decisions earlier as extra channels (where did I come from?)
    gross       today's view, network twice as wide
Measured: held-out imitation agreement per teacher (split by episode) and closed-loop wins on dev_alt (11 levels),
v11 practice probes, mirrored dev_alt and mirrored held-out generator levels. Only allowed levels are played.
"""

from __future__ import annotations

import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "runs/arch10"
HIST = 6  # decisions back for the memory variant
VIEW_SYM = 19
KEEP_EVERY = 2
VARIANTS = ("heute", "symm", "gedaechtnis", "gross")


# ----------------------------------------------------------------------------------------------- helpers
def mirror(level, name=None):
    from jumpnrun.core.level import Level

    lines = level.to_text().splitlines()
    w = max(len(l) for l in lines)
    lv = Level.from_text("\n".join(l.ljust(w)[::-1].rstrip() for l in lines), name=name or level.name + "_spiegel")
    lv.needs_path = True
    return lv


def make_env(level):
    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels

    env = JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True, obs_v3=True, progress="path")
    env.view_behind = VIEW_SYM  # wide symmetric view; today's view is the slice [..., 6:]
    env.view_cols = VIEW_SYM + 1 + 19
    return env


def pack(obs):
    return (obs["grid"].astype(np.int8), np.rint(obs["overview"] * 4).astype(np.uint8), obs["vec"].astype(np.float32))


# ----------------------------------------------------------------------------------------------- data
def episode_alt(i):
    from jumpnrun.levelgen.generator import generate
    from jumpnrun.rl.drift import old_view
    from jumpnrun.rl.modelinfo import load_model

    torch.set_num_threads(1)
    rng = random.Random(f"arch10:{i}")
    level = generate(rng.randint(6, 12), 9_700_000 + i)
    model = load_model(ROOT / "models/phase8_final.zip")
    env = make_env(level)
    obs, _ = env.reset(seed=i)
    torch.manual_seed(i)
    frames, labels = [], []
    while True:
        o = {k: torch.as_tensor(v[None]) for k, v in obs.items()}
        o["grid"] = o["grid"][..., VIEW_SYM - 13:]  # today's view for P8 (it saw 13 behind after surgery: slice 8:)
        with torch.no_grad():
            p = model.policy.get_distribution(old_view(o)).distribution.probs[0].numpy()
        frames.append(pack(obs))
        labels.append(np.concatenate([p, [0.0]]).astype(np.float32))
        obs, _, term, trunc, _ = env.step(int(np.random.default_rng(i * 100003 + len(frames)).choice(6, p=p / p.sum())))
        if term or trunc:
            break
    return "alt", i, frames, labels


def _replay(group, i, level, actions):
    env = make_env(level)
    obs, _ = env.reset(seed=0)
    frames, labels = [], []
    for a in actions:
        frames.append(pack(obs))
        lab = np.zeros(7, np.float32)
        lab[a] = 1.0
        labels.append(lab)
        obs, _, term, trunc, _ = env.step(int(a))
        if term or trunc:
            break
    return group, i, frames, labels


def episode_neu(args):
    from jumpnrun.core.level import Level

    i, demo = args
    return _replay("neu", i, Level.from_text(demo["level"]), demo["actions"])


def episode_spiegel(i):
    from jumpnrun.levelgen.generator import generate
    from jumpnrun.levelgen.solver import solve_auto

    rng = random.Random(f"arch10m:{i}")
    level = mirror(generate(rng.randint(4, 9), 9_800_000 + i))
    r = solve_auto(level, 60_000, action_repeat=2, weight=1.2, path=True)
    if not r.solved:
        return "spiegel", i, [], []
    return _replay("spiegel", i, level, list(r.actions))


def build_data():
    OUT.mkdir(parents=True, exist_ok=True)
    demos = [json.loads(l) for l in open(ROOT / "runs/demos10/demos.jsonl")]
    random.Random(0).shuffle(demos)
    jobs = [(episode_alt, i) for i in range(120)] + [(episode_neu, (i, d)) for i, d in enumerate(demos[:700])]
    jobs += [(episode_spiegel, i) for i in range(260)]
    random.Random(1).shuffle(jobs)
    data = {k: [] for k in ("grid", "hist", "overview", "vec", "label", "group", "episode")}
    groups = {"alt": 0, "neu": 1, "spiegel": 2}
    with Pool(2) as p:
        for n, (group, i, frames, labels) in enumerate(p.imap_unordered(_call, jobs, chunksize=2)):
            for t in range(0, len(frames), KEEP_EVERY):
                g, ov, vec = frames[t]
                data["grid"].append(g)
                data["hist"].append(frames[max(0, t - HIST)][0])
                data["overview"].append(ov)
                data["vec"].append(vec)
                data["label"].append(labels[t])
                data["group"].append(groups[group])
                data["episode"].append(groups[group] * 100000 + i)
            if n % 50 == 0:
                print("episodes", n, "of", len(jobs), "samples", len(data["label"]), flush=True)
    np.savez_compressed(OUT / "data.npz", **{k: np.stack(v) for k, v in data.items()})
    print("samples:", len(data["label"]), {g: int(np.sum(np.array(data["group"]) == c)) for g, c in groups.items()})


def _call(job):
    fn, arg = job
    return fn(arg)


# ----------------------------------------------------------------------------------------------- networks
def make_net(variant):
    import gymnasium as gym

    from jumpnrun.rl.policy import GridFeatures

    cols = VIEW_SYM + 1 + 19 if variant == "symm" else 33
    ch = 8 if variant == "gedaechtnis" else 4
    space = gym.spaces.Dict({"grid": gym.spaces.Box(-1, 1, (ch, 13, cols)), "overview": gym.spaces.Box(0, 1, (4, 13, 40)),
                             "vec": gym.spaces.Box(-10, 10, (23,))})
    width = 512 if variant == "gross" else 256
    feats = GridFeatures(space, features_dim=width)
    nn.init.normal_(feats.ov_head.weight, std=0.01)  # train the overview branch from the start here
    hidden = 256 if variant == "gross" else 128
    return nn.Sequential(Wrap(feats), nn.Linear(width, hidden), nn.ReLU(), nn.Linear(hidden, 7))


class Wrap(nn.Module):
    def __init__(self, feats):
        super().__init__()
        self.feats = feats

    def forward(self, obs):
        return self.feats(obs)


def view(variant, grid, hist):
    grid, hist = grid.float(), hist.float()
    if variant == "symm":
        return grid
    g = grid[:, :, :, VIEW_SYM - 13:]
    if variant == "gedaechtnis":
        return torch.cat([g, hist[:, :, :, VIEW_SYM - 13:]], dim=1)
    return g


def train_all():
    torch.set_num_threads(2)
    d = np.load(OUT / "data.npz")
    n = len(d["label"])
    ep = d["episode"]
    held = (np.array([hash(int(e)) % 10 for e in ep]) == 0)  # 10 % of the episodes held out
    tr, te = np.nonzero(~held)[0], np.nonzero(held)[0]
    grid = torch.as_tensor(d["grid"])  # int8, converted per batch (memory)
    hist = torch.as_tensor(d["hist"])
    ov8 = torch.as_tensor(d["overview"])
    vec = torch.as_tensor(d["vec"])
    lab = torch.as_tensor(d["label"])
    group = d["group"]
    # equal weight per teacher (the groups differ in size)
    w = np.zeros(n, np.float32)
    for gidx in range(3):
        w[group == gidx] = 1.0 / max(1, np.sum(group[tr] == gidx))
    results = json.loads((OUT / "result.json").read_text()) if (OUT / "result.json").exists() else {}
    for variant in VARIANTS:
        torch.manual_seed(0)
        net = make_net(variant)
        opt = torch.optim.Adam(net.parameters(), lr=3e-4)
        steps = 6000
        p = w[tr] / w[tr].sum()
        rng = np.random.default_rng(0)
        for s in range(steps):
            idx = torch.as_tensor(rng.choice(tr, 256, p=p))
            obs = {"grid": view(variant, grid[idx], hist[idx]), "overview": ov8[idx].float() / 4.0, "vec": vec[idx]}
            logp = torch.log_softmax(net(obs), dim=1)
            loss = -(lab[idx] * logp).sum(1).mean()
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            if s % 1000 == 0:
                print(variant, s, round(loss.item(), 4), flush=True)
        net.eval()
        acc = {}
        with torch.no_grad():
            for gname, gidx in (("alt", 0), ("neu", 1), ("spiegel", 2)):
                sel = te[group[te] == gidx]
                out = []
                for k in range(0, len(sel), 2048):
                    idx = torch.as_tensor(sel[k:k + 2048])
                    obs = {"grid": view(variant, grid[idx], hist[idx]), "overview": ov8[idx].float() / 4.0, "vec": vec[idx]}
                    out.append(net(obs).argmax(1) == lab[idx].argmax(1))
                acc[gname] = round(float(torch.cat(out).float().mean()), 4) if out else None
        torch.save(net.state_dict(), OUT / f"net_{variant}.pt")
        results.setdefault(variant, {})["nachahmung_holdout"] = acc
        print(variant, "held-out agreement", acc, flush=True)
        (OUT / "result.json").write_text(json.dumps(results, indent=1))


# ----------------------------------------------------------------------------------------------- closed loop
def play_job(args):
    variant, group, name, text, attempts = args
    from jumpnrun.core.level import Level

    torch.set_num_threads(1)
    net = make_net(variant)
    net.load_state_dict(torch.load(OUT / f"net_{variant}.pt"))
    net.eval()
    level = Level.from_text(text, name=name)
    level.needs_path = True
    won = 0
    for a in range(attempts):
        env = make_env(level)
        obs, _ = env.reset(seed=a)
        torch.manual_seed(1000 * a + 7)
        frames = []
        while True:
            frames.append(obs["grid"])
            g = torch.as_tensor(obs["grid"][None])
            h = torch.as_tensor(frames[max(0, len(frames) - 1 - HIST)][None])
            o = {"grid": view(variant, g, h), "overview": torch.as_tensor(obs["overview"][None]),
                 "vec": torch.as_tensor(obs["vec"][None])}
            with torch.no_grad():
                act = int(torch.distributions.Categorical(logits=net(o)).sample()[0])
            obs, _, term, trunc, info = env.step(act)
            if term or trunc:
                won += int(info["episode_end"]["won"])
                break
    return variant, group, name, won, attempts


def play_all():
    from jumpnrun.levelgen.generator import generate
    from jumpnrun.rl import milestones8 as m8
    from jumpnrun.rl.milestones10 import _probe_levels

    levels = {"dev_alt": [(n, lv, 8) for n, lv, _ in m8.dev_levels()]}
    probes = _probe_levels(ROOT / "levels/probes/v11_skills.json")
    levels["uebung_v11"] = [(lv.name, lv, 1) for k, (s, lv) in enumerate(probes) if k % 40 < 6]
    levels["dev_alt_gespiegelt"] = [(n + "_s", mirror(lv), 4) for n, lv, _ in m8.dev_levels()]
    rng = random.Random("arch10test")
    levels["gen_gespiegelt"] = [(f"gm{i}", mirror(generate(rng.randint(4, 9), 9_900_000 + i)), 1) for i in range(40)]
    jobs = [(v, g, n, lv.to_text(), k) for v in VARIANTS for g, items in levels.items() for n, lv, k in items]
    results = json.loads((OUT / "result.json").read_text())
    tally = {}
    with Pool(2) as p:
        for variant, group, name, won, of in p.imap_unordered(play_job, jobs):
            t = tally.setdefault(variant, {}).setdefault(group, [0, 0])
            t[0] += won
            t[1] += of
    for variant, gs in tally.items():
        results.setdefault(variant, {})["spielen"] = {g: f"{w}/{n} ({w / n:.0%})" for g, (w, n) in gs.items()}
        print(variant, results[variant]["spielen"], flush=True)
    (OUT / "result.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "data"
    {"data": build_data, "train": train_all, "play": play_all}[cmd]()
