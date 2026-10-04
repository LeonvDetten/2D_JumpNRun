"""Phase 9: teacher demos for the new skills, with the 7th action (left+jump).

    nice -n 19 python3 scripts/demos_phase9.py 600      # -> runs/demos9/demos.jsonl

Short levels like the probes (two random segments, the skill, two segments, the chest) but other seeds:
channels, channel ends (chest on the left), turn-back forks, mirrored levels, and "sackgasse": the player starts
at the dead end of an upper road, so the teacher shows the way back. Each is solved by the solver
guided by the distance map (7 actions). The phase-8 demos never contain left+jump, so the bot never tried it in
round 2 (0 of ~400 steps on a channel level); these demos give the behaviour-cloning loss an example.
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_probes9 import OFF, short_level  # noqa: E402
from jumpnrun.levelgen import generator as G  # noqa: E402
from jumpnrun.levelgen.augment import augment  # noqa: E402

OUT = ROOT / "runs/demos9"
KINDS = ("kanal", "kanal_ende", "umkehren", "spiegel", "sackgasse", "sackgasse")


def dead_end_start(rng: random.Random, name: str):
    """A turn-back fork whose player starts on the upper road right in front of the dead-end wall."""

    from jumpnrun.core.level import Level

    cfg = G.TIERS[10]
    b = G._Builder(rng)
    b.style = G._style(rng, cfg)
    b.flat(5)
    G._segment(b, cfg)
    if b.surface != G.GROUND:
        b.drop(G.GROUND - b.surface)
        b.flat(3)
    G._fork_v10(b, cfg, rng.choice(("umkehren", "unten")))
    wall = max(c for c, col in enumerate(b.columns) if any(col[r] == "B" for r in range(0, 9)) and col[G.GROUND] == "B"
               and sum(ch == "B" for ch in col[:G.GROUND]) >= 3)
    road = min(r for r in range(G.ROWS) if b.columns[wall - 1][r] == "B")
    b.columns[wall - 1 - rng.randint(0, 3)][road - 1] = "P"
    for _ in range(2):
        G._segment(b, cfg)
    b.flat(4)
    b.columns[-2][b.surface - 1] = "C"
    b.column(b.surface - 3)
    lv = Level(["".join(col[r] for col in b.columns).rstrip() for r in range(G.ROWS)], name=name)
    lv.needs_path = True
    return lv


def demo(i: int):
    from jumpnrun.levelgen.solver import solve_auto

    kind = KINDS[i % len(KINDS)]
    rng = random.Random(f"demo9:{i}")
    name = f"demo9_{kind}_{i}"
    if kind == "kanal":
        lv = short_level(rng, lambda b, c: G._channel(b, replace(c, free_enemies=0.3)), name)
    elif kind == "kanal_ende":
        b = G._Builder(rng)
        b.flat(5)
        b.columns[1][b.surface - 1] = "P"
        G._channel(b, replace(G.TIERS[10], free_enemies=0.3), final=True)
        from jumpnrun.core.level import Level

        lv = Level(["".join(col[r] for col in b.columns).rstrip() for r in range(G.ROWS)], name=name)
        lv.needs_path = True
    elif kind == "umkehren":
        lv = short_level(rng, lambda b, c: G._fork_v10(b, c, rng.choice(("umkehren", "oben"))), name)
    elif kind == "spiegel":
        lv, _ = augment(short_level(rng, None, name), rng, replace(OFF, mirror=1.0))
    else:
        lv = dead_end_start(rng, name)
    r = solve_auto(lv, 100_000, action_repeat=2, weight=1.2, path=True)
    if not r.solved:
        return None
    return dict(tier=13, seed=i, repeat=2, actions=list(r.actions), mask=[1] * len(r.actions), won=True,
                solved=True, generator=G.GENERATOR_VERSION, kind=kind, level="\n".join(lv._lines) + "\n")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    OUT.mkdir(parents=True, exist_ok=True)
    done = 0
    with Pool(4) as p, open(OUT / "demos.jsonl", "a") as f:
        for d in p.imap_unordered(demo, range(start, n), chunksize=1):
            if d:
                f.write(json.dumps(d) + "\n")
                f.flush()
                done += 1
    print("demos:", done, "of", n)


if __name__ == "__main__":
    main()
