"""Export the bot's policy network for the phone: weights as one float32 file plus a manifest.

    .venv/bin/python mobile/tools/export_bot.py [--fixtures]
writes mobile/public/bot/{weights.bin,bot.json}; with --fixtures also mobile/tests/fixtures/bot.json
(observation hashes and logits of recorded bot runs, for the TypeScript parity test).

Only the parts needed to act are exported: the shared feature extractor, the policy MLP and the action head
(no value head, no optimizer state).
"""

from __future__ import annotations

import argparse
import hashlib
import json

import numpy as np

from _common import FIXTURES, PUBLIC, write_json

from jumpnrun.core.actions import BOT_ACTIONS_V3
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Status
from jumpnrun.levelgen.generator import generate
from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
from jumpnrun.rl.modelinfo import BEST_MODEL, PLAY_TEMPERATURE, env_kwargs, load_model

PREFIXES = ("features_extractor.", "mlp_extractor.policy_net.", "action_net.")


def export(model) -> dict:
    state = model.policy.state_dict()
    names = [k for k in state if k.startswith(PREFIXES)]
    blobs, layers, offset = [], {}, 0
    for name in names:
        arr = state[name].detach().cpu().numpy().astype("<f4")
        layers[name] = {"offset": offset, "shape": list(arr.shape)}
        blobs.append(arr.tobytes())
        offset += arr.size
    out = PUBLIC / "bot"
    out.mkdir(parents=True, exist_ok=True)
    (out / "weights.bin").write_bytes(b"".join(blobs))
    space = model.observation_space
    manifest = {
        "name": "Space Pirate Bot",
        "source": BEST_MODEL.name,
        "action_repeat": int(getattr(model, "action_repeat", 2)),
        "temperature": PLAY_TEMPERATURE,
        "actions": int(model.action_space.n),
        "grid": list(space["grid"].shape),
        "vec": list(space["vec"].shape),
        "overview": list(space["overview"].shape),
        "floats": offset,
        "layers": layers,
    }
    write_json(out / "bot.json", manifest, compact=False)
    print(f"weights.bin: {offset} floats ({offset * 4 / 1e6:.2f} MB)")
    return manifest


def obs_hash(arr: np.ndarray) -> str:
    return hashlib.sha1(np.ascontiguousarray(arr, dtype="<f4").tobytes()).hexdigest()[:16]


def fixtures(model) -> None:
    import torch

    kwargs = env_kwargs(model)
    texts = [("exam", (Level.from_file("levels/exam/level.txt")).to_text()),
             ("serpentine", Level.from_file("levels/handmade9/serpentine.txt").to_text()),
             ("gen_t13_s5", generate(13, 5).to_text())]
    runs = []
    for name, text in texts:
        level = Level.from_text(text, name=name)
        env = JumpNRunEnv(fixed_levels([level]), **kwargs)
        obs, _ = env.reset(seed=0)
        steps = []
        rng = np.random.default_rng(1)
        for i in range(400):
            batch = {k: np.expand_dims(v, 0) for k, v in obs.items()}
            with torch.no_grad():
                t, _ = model.policy.obs_to_tensor(batch)
                logits = model.policy.get_distribution(t).distribution.logits[0].cpu().numpy()
            # follow the sharpened policy with a fixed random stream; the TS test replays the recorded actions
            p = np.exp((logits - logits.max()) / PLAY_TEMPERATURE)
            action = int(rng.choice(len(p), p=p / p.sum()))
            step = {"grid": obs_hash(obs["grid"]), "overview": obs_hash(obs["overview"]),
                    "vec": [float(v) for v in obs["vec"]], "logits": [float(v) for v in logits], "action": action}
            if i < 2:
                step["grid_full"] = [float(v) for v in obs["grid"].ravel()]
                step["overview_full"] = [float(v) for v in obs["overview"].ravel()]
            steps.append(step)
            obs, _, terminated, truncated, _ = env.step(action)
            if terminated or truncated:
                break
        runs.append({"name": name, "text": text, "steps": steps, "status": env.sim.status.value,
                     "frame": env.sim.frame})
        print(f"{name}: {len(steps)} decisions, {env.sim.status.value}")
    write_json(FIXTURES / "bot.json", {"runs": runs})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true")
    args = parser.parse_args()
    model = load_model(BEST_MODEL)
    export(model)
    if args.fixtures:
        fixtures(model)


if __name__ == "__main__":
    main()
