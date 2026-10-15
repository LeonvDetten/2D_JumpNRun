"""Golden values from the Python code for the TypeScript parity tests (mobile/tests/fixtures/*.json).

    .venv/bin/python mobile/tools/make_fixtures.py [--only random,generator,sim,distmap]
"""

from __future__ import annotations

import argparse
import random

from _common import FIXTURES, write_json

from jumpnrun.app import levels_index
from jumpnrun.app.progress import level_key
from jumpnrun.core.actions import BOT_ACTIONS_V3, Action
from jumpnrun.core.level import Level
from jumpnrun.core.sim import Simulation, Status
from jumpnrun.editor.model import load_solution
from jumpnrun.levelgen.distmap import DistanceMap
from jumpnrun.levelgen.generator import NUM_TIERS, generate


def signature(sim: Simulation) -> list:
    frame, status, p, enemies, bullets = sim.state_signature()
    return [frame, status.value if isinstance(status, Status) else status, list(p),
            [list(e) for e in enemies], [list(b) for b in bullets]]


def random_fixture() -> dict:
    cases = []
    for seed in ["0:0", "3:17", "13:99", "12:4", "x" * 200, 12345]:
        rng = random.Random(seed)
        ops = []
        for i in range(400):
            kind = i % 8
            if kind == 0:
                ops.append(["random", rng.random()])
            elif kind == 1:
                a = i % 7
                ops.append(["randint", a, a + 1 + i % 13, rng.randint(a, a + 1 + i % 13)])
            elif kind == 2:
                ops.append(["randrange", 3, 3 + i % 29 + 1, rng.randrange(3, 3 + i % 29 + 1)])
            elif kind == 3:
                seq = [-1, 0, 0, 1][: 2 + i % 3]
                ops.append(["choice", seq, rng.choice(seq)])
            elif kind == 4:
                pop = list(range(1, 4 + i % 20))
                k = min(len(pop), 1 + i % 3)
                ops.append(["sample", pop, k, rng.sample(range(1, 4 + i % 20), k)])
            elif kind == 5:
                ops.append(["gamma", rng.gammavariate(1.0, 1.0)])
            elif kind == 6:
                pop = ["a", "b", "c", "d"]
                w = [0.5 + (i % 5), 1.3, 0.0 if i % 2 else 2.2, 0.7]
                ops.append(["choices", pop, w, rng.choices(pop, weights=w)[0]])
            else:
                pop = list(range(40))
                ops.append(["sample", pop, 8, rng.sample(range(40), 8)])
        cases.append({"seed": seed, "ops": ops})
    rng = random.Random("gamma")  # many logarithms: the place where libm and JS could differ in the last bit
    cases.append({"seed": "gamma", "ops": [["gamma", rng.gammavariate(1.0, 1.0)] for _ in range(20000)]})
    return {"cases": cases}


def generator_fixture() -> dict:
    out = []
    specs = [(t, s, "v9") for t in range(NUM_TIERS) for s in range(25)]
    specs += [(t, s, v) for t in (10, 11, 12) for s in range(6) for v in ("v10", "gabel", "pruefung")]
    specs += [(t, s, "pruefung") for t in (3, 8) for s in range(4)]
    for tier, seed, variant in specs:
        level = generate(tier, seed, variant)
        out.append({
            "tier": tier, "seed": seed, "variant": variant, "text": level.to_text(),
            "waypoints": [list(w) for w in level.waypoints], "needs_path": level.needs_path,
            "blocks": level.building_blocks, "key": level_key(level.to_text()),
        })
    # many more seeds, only their level keys (keeps the fixture small)
    keys = [[t, s, level_key(generate(t, s).to_text())] for t in range(NUM_TIERS) for s in range(25, 325)]
    return {"levels": out, "keys": keys}


def _bundled():
    for tab, entries in levels_index.scan().items():
        for entry in entries:
            yield entry


def sim_fixture() -> dict:
    replays = []
    for entry in _bundled():
        solution = load_solution(entry.path)
        if not solution:
            continue
        sim = Simulation(Level.from_text(entry.text))
        trace = []
        for i, a in enumerate(solution):
            sim.step(BOT_ACTIONS_V3[a], 2)
            if i % 25 == 0:
                trace.append(signature(sim))
            if sim.status != Status.RUNNING:
                break
        replays.append({"name": f"{entry.folder}/{entry.path.stem}", "text": entry.text, "actions": solution,
                        "trace": trace, "final": signature(sim), "kills": [sim.kills_stomp, sim.kills_shot],
                        "jumps": sim.jumps, "max_x": sim.max_x})
    # random human-like inputs (single frames, all 16 input combinations) on a few levels incl. generated ones
    rng = random.Random(7)
    texts = [e.text for e in list(_bundled())[:12]] + [generate(t, 3).to_text() for t in (3, 6, 9, 11, 13)]
    noise = []
    for text in texts:
        sim = Simulation(Level.from_text(text))
        codes, trace = [], []
        for f in range(1500):
            if f % 6 == 0:
                code = rng.choice([2, 2, 2, 6, 6, 10, 0, 1, 5, 4, 8, 14])
            codes.append(code)
            sim.step(Action(bool(code & 1), bool(code & 2), bool(code & 4), bool(code & 8)))
            if f % 10 == 0:
                trace.append(signature(sim))
            if sim.status != Status.RUNNING:
                break
        noise.append({"text": text, "codes": codes, "trace": trace, "final": signature(sim)})
    return {"replays": replays, "noise": noise}


def distmap_fixture() -> dict:
    out = []
    texts = [(f"{e.folder}/{e.path.stem}", e.text) for e in _bundled()]
    texts += [(f"gen_t{t}_s{s}", generate(t, s).to_text()) for t in range(NUM_TIERS) for s in (1, 2)]
    for name, text in texts:
        level = Level.from_text(text)
        dm = DistanceMap(level)
        cells = [[c, r, round(d, 9)] for (c, r), d in sorted(dm.dist.items())]
        out.append({"name": name, "text": text, "start": dm.start, "reachable": dm.reachable,
                    "dist": cells, "par": levels_index.par_frames(level),
                    "key": level_key(text)})
    return {"levels": out}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="random,generator,sim,distmap")
    args = parser.parse_args()
    parts = set(args.only.split(","))
    if "random" in parts:
        write_json(FIXTURES / "pyrandom.json", random_fixture())
    if "generator" in parts:
        write_json(FIXTURES / "generator.json", generator_fixture())
    if "sim" in parts:
        write_json(FIXTURES / "sim.json", sim_fixture())
    if "distmap" in parts:
        write_json(FIXTURES / "distmap.json", distmap_fixture())


if __name__ == "__main__":
    main()
