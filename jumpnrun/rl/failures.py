"""Failure catalogue: where and why does a bot fail? Groups deaths into kinds of situations.

    python -m jumpnrun.rl.failures --model runs/phase7a/best_model.zip --sets v3 v4 test_serie exam

For every failed attempt the last place the bot stood on is kept. Deaths in a pit are described as
the jump it tried: gap (empty columns to the next standable tile to the right) and height change
(rows down, negative = up) - the same terms as the jump catalogue (jumpnrun/levelgen/jump_catalog.py),
so a frequent failing jump kind can be compared with what the generator builds. Deaths by enemies are
split by the terrain around them (tunnel/low ceiling, raining enemy, open ground).
The sealed second exam is never played here.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from jumpnrun.core.constants import TILE
from jumpnrun.core.level import Level
from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
from jumpnrun.rl.modelinfo import env_kwargs, load_model

ROOT = Path(__file__).resolve().parent.parent.parent


def level_sets(names):
    from jumpnrun.rl.milestones import EXAMS, frozen_levels

    out = []
    for name in names:
        if name.startswith("v"):
            out += [(name, lv, 1, True) for _, lv in frozen_levels(name)]
        elif name == "test_serie":
            out += [(name, Level.from_file(p), 16, False) for p in sorted((ROOT / "levels/test_serie").glob("*.txt"))]
        elif name == "exam":
            out += [(name, Level.from_file(ROOT / EXAMS["original"]), 64, False)]
    return out


def standable(level: Level, col: int, row: int) -> bool:
    return 0 <= col < level.cols and 0 <= row < level.rows and level.solid[row][col] and (
        row == 0 or not level.solid[row - 1][col])


def describe(level: Level, end: dict, last_ground) -> str:
    if end["outcome"] == "timeout":
        return "Zeit abgelaufen"
    if last_ground is None:
        return "gestorben vor dem ersten Bodenkontakt"
    col, row = last_ground  # row = the block row the bot stood on
    if end["outcome"] == "died_enemy":
        ceiling = any(level.solid[r][col] for r in range(max(0, row - 3), row - 1)) if row >= 2 else False
        return "Gegner unter niedriger Decke / im Tunnel" if ceiling else "Gegner auf offener Strecke"
    for c in range(col + 1, min(level.cols, col + 8)):
        rows = [r for r in range(level.rows) if standable(level, c, r) and r >= row - 2]
        if rows:
            target = min(rows, key=lambda r: abs(r - row))
            gap = c - col - 1
            if gap == 0 and target == row:
                return "Grube direkt vor flachem Boden (Timing)"
            return f"Sprung: Lücke {gap}, Höhe {target - row:+d}"
    return "Sprung ohne erreichbares Ziel in 8 Kacheln"


def run(model, items, repeat_seed: int = 7000) -> Counter:
    envs, labels = [], []
    for set_name, level, n, deterministic in items:
        for _ in range(n):
            envs.append(JumpNRunEnv(fixed_levels([level]), **env_kwargs(model)))
            labels.append((set_name, level, deterministic))
    obs = [e.reset(seed=repeat_seed + i)[0] for i, e in enumerate(envs)]
    ground = [None] * len(envs)
    kinds = Counter()
    by_set = Counter()
    active = list(range(len(envs)))
    while active:
        for det in (True, False):
            group = [i for i in active if labels[i][2] == det]
            if not group:
                continue
            batch = {k: np.stack([obs[i][k] for i in group]) for k in obs[group[0]]}
            actions, _ = model.predict(batch, deterministic=det)
            for i, a in zip(group, actions):
                obs[i], _, term, trunc, info = envs[i].step(int(a))
                p = envs[i].sim.player
                if p.on_ground:
                    ground[i] = ((p.x + p.w // 2) // TILE, (p.y + p.h) // TILE)
                if term or trunc:
                    end = info["episode_end"]
                    if not end["won"]:
                        kind = describe(labels[i][1], end, ground[i])
                        kinds[kind] += 1
                        by_set[(labels[i][0], kind)] += 1
                    active.remove(i)
    return kinds, by_set


def main() -> None:
    parser = argparse.ArgumentParser(description="Group the failures of a bot into kinds of situations.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--sets", nargs="*", default=["v3", "v4", "test_serie", "exam"])
    parser.add_argument("--json", help="also write the catalogue to this file")
    args = parser.parse_args()
    import torch

    torch.set_num_threads(1)
    model = load_model(args.model)
    kinds, by_set = run(model, level_sets(args.sets))
    total = sum(kinds.values())
    print(f"{total} gescheiterte Versuche")
    for kind, n in kinds.most_common(15):
        sets = ", ".join(f"{s} {m}" for (s, k), m in sorted(by_set.items()) if k == kind)
        print(f"{n:5d}  {n / max(1, total):5.1%}  {kind}   ({sets})")
    if args.json:
        Path(args.json).write_text(json.dumps({"total": total, "kinds": kinds.most_common(),
                                               "by_set": [[s, k, n] for (s, k), n in by_set.items()]}, indent=1))


if __name__ == "__main__":
    main()
