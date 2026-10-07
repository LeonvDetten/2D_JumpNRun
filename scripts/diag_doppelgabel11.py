"""Phase 11 step 0: why do the bots get stuck on doppelgabel (allowed handmade8 dev level)?

    OMP_NUM_THREADS=1 nice python3 scripts/diag_doppelgabel11.py      # -> runs/phase11/diag_doppelgabel.json

16 stochastic episodes each for P8 and the phase-10 teacher candidate. Per step: x, way distance, P(left-ish)
(actions with left), P(left+jump). Summary: where they end, how often they turned around (x went back >= 3 tiles),
how long the last stretch without way progress was, and the policy's mean P(left) on that stretch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODELS = {"p8": "models/phase8_final.zip", "lehrer": "models/phase10_kandidat_lehrer.zip"}
N = 16


def run(tag):
    import numpy as np
    import torch

    from jumpnrun.core.actions import BOT_ACTIONS_V3
    from jumpnrun.core.constants import TILE
    from jumpnrun.core.level import Level
    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
    from jumpnrun.rl.modelinfo import env_kwargs, load_model

    torch.set_num_threads(1)
    model = load_model(ROOT / MODELS[tag])
    level = Level.from_file(ROOT / "levels/handmade8/doppelgabel.txt")
    env = JumpNRunEnv(fixed_levels([level]), **env_kwargs(model))
    n_act = model.action_space.n
    left = [i for i in range(n_act) if BOT_ACTIONS_V3[i].left]
    episodes = []
    for ep in range(N):
        obs, _ = env.reset(seed=1000 + ep)
        rows, done = [], False
        info = {}
        while not done:
            o = {k: torch.as_tensor(v[None]) for k, v in obs.items()}
            with torch.no_grad():
                probs = model.policy.get_distribution(o).distribution.probs[0].numpy()
            a = int(np.random.default_rng(ep * 100000 + len(rows)).choice(n_act, p=probs / probs.sum()))
            p = env.sim.player
            here = env.dm.at_player(p) if env.dm is not None and env.dm.reachable else None
            rows.append((p.x / TILE, p.y / TILE, here, float(probs[left].sum()), float(probs[6]) if n_act > 6 else 0.0))
            obs, _, term, trunc, info = env.step(a)
            done = term or trunc
        xs = [r[0] for r in rows]
        best, stall_from = None, 0
        for i, r in enumerate(rows):
            if r[2] is not None and (best is None or r[2] < best - 1e-6):
                best, stall_from = r[2], i
        stall = rows[stall_from:]
        turns, peak = 0, xs[0]
        for x in xs:  # direction changes of >= 3 tiles
            if x < peak - 3:
                turns += 1
                peak = x
            peak = max(peak, x) if x >= peak else peak
        episodes.append(dict(outcome=info.get("outcome"), end_x=round(xs[-1], 1), end_y=round(rows[-1][1], 1),
                             best_dist=best, steps=len(rows), stall_steps=len(stall),
                             stall_x_range=[round(min(r[0] for r in stall), 1), round(max(r[0] for r in stall), 1)],
                             stall_p_left=round(float(np.mean([r[3] for r in stall])), 3),
                             stall_p_a6=round(float(np.mean([r[4] for r in stall])), 3),
                             turnbacks=turns, max_x=round(max(xs), 1)))
    return tag, episodes


def main():
    from multiprocessing import Pool

    out = {}
    with Pool(2) as pool:
        for tag, eps in pool.imap_unordered(run, MODELS):
            out[tag] = eps
            print(tag, flush=True)
            for e in eps:
                print("  ", e, flush=True)
    (ROOT / "runs/phase11").mkdir(parents=True, exist_ok=True)
    (ROOT / "runs/phase11/diag_doppelgabel.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
