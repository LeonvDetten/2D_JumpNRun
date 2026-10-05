"""Phase 10: drift of the policy away from the frozen phase-8 model (early warning, never a judging criterion).

    python3 -m jumpnrun.rl.drift build                      # -> runs/phase10/kl_states.npz (~6k states)
    python3 -m jumpnrun.rl.drift measure CKPT [CKPT ...]    # mean KL(P8 || model) and P(left+jump) on old states

States come from stochastic phase-8 runs on generated v9 levels (tiers 6-12, own seed space "drift10") and the six
test-series levels - never the exam. They are stored in the v3 observation format; the phase-8 view is an exact
slice of it (grid columns 8.., overview columns 8.., vec[:15]).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent.parent
STATES = ROOT / "runs/phase10/kl_states.npz"
P8 = ROOT / "models/phase8_final.zip"


def old_view(obs: dict) -> dict:
    """The phase-8 observation inside a v3 observation (batched tensors or arrays)."""

    return {"grid": obs["grid"][..., 8:], "overview": obs["overview"][..., 8:], "vec": obs["vec"][..., :15]}


def build(n_states: int = 6000, every: int = 6) -> None:
    from jumpnrun.core.level import Level
    from jumpnrun.levelgen.generator import generate
    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
    from jumpnrun.rl.modelinfo import load_model

    torch.set_num_threads(1)
    model = load_model(P8)
    rng = random.Random("drift10")
    levels = [Level.from_file(p) for p in sorted((ROOT / "levels/test_serie").glob("*.txt"))]
    levels += [generate(rng.randint(6, 12), 700000 + i) for i in range(60)]
    keep = {"grid": [], "overview": [], "vec": []}
    torch.manual_seed(10)
    k = 0
    while len(keep["vec"]) < n_states:
        level = levels[k % len(levels)]
        k += 1
        env = JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True, obs_v3=True, progress="path")
        obs, _ = env.reset(seed=k)
        t = 0
        while True:
            if t % every == 0:
                for key in keep:
                    keep[key].append(obs[key].copy())
            o = {key: torch.as_tensor(v[None]) for key, v in old_view(obs).items()}
            with torch.no_grad():
                a = int(model.policy.get_distribution(o).distribution.sample()[0])
            obs, _, term, trunc, _ = env.step(a)
            t += 1
            if term or trunc:
                break
    STATES.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(STATES, grid=np.stack(keep["grid"]).astype(np.int8), vec=np.stack(keep["vec"]),
                        overview=np.rint(np.stack(keep["overview"]) * 4).astype(np.uint8))
    print("states:", len(keep["vec"]), "from", k, "episodes")


def _load_states():
    d = np.load(STATES)
    return {"grid": torch.as_tensor(d["grid"], dtype=torch.float32), "vec": torch.as_tensor(d["vec"]),
            "overview": torch.as_tensor(d["overview"], dtype=torch.float32) / 4.0}


_P8_PROBS = {}


def measure(model, states=None, batch: int = 1000) -> dict:
    """{'kl': mean KL(P8 || model) on old states, 'p_a6': mean P(left+jump) there} (model: v3 policy)."""

    from jumpnrun.rl.modelinfo import load_model

    states = states or _load_states()
    n = len(states["vec"])
    if "p" not in _P8_PROBS:
        p8 = load_model(P8)
        with torch.no_grad():
            _P8_PROBS["p"] = torch.cat([p8.policy.get_distribution(
                old_view({k: v[i:i + batch] for k, v in states.items()})).distribution.probs for i in range(0, n, batch)])
    p_old = _P8_PROBS["p"]
    view = old_view if model.observation_space["vec"].shape[0] <= 15 else (lambda o: o)  # old-view models too
    with torch.no_grad():
        p_new = torch.cat([model.policy.get_distribution(view({k: v[i:i + batch] for k, v in states.items()}))
                           .distribution.probs for i in range(0, n, batch)])
    q = p_new[:, :6].clamp_min(1e-8)
    kl = (p_old * (p_old.clamp_min(1e-8).log() - q.log())).sum(1)
    out = {"kl": round(float(kl.mean()), 5), "p_a6": round(float(p_new[:, 6].mean()), 5) if p_new.shape[1] > 6 else 0.0}
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=("build", "measure"))
    parser.add_argument("ckpts", nargs="*")
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.cmd == "build":
        build()
        return
    from jumpnrun.rl.modelinfo import load_model

    states = _load_states()
    for c in args.ckpts:
        print(c, json.dumps(measure(load_model(ROOT / c if not Path(c).is_absolute() else c), states)))


if __name__ == "__main__":
    sys.exit(main())
