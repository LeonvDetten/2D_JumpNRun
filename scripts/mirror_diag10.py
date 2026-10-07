"""Phase 10 D: mirror measurement + failure diagnosis (allowed levels only: dev group + guard val).

    OMP_NUM_THREADS=1 nice taskset -c 2,3 python3 scripts/mirror_diag10.py      # -> runs/phase10/mirror_diag.json

Each level normal and mirrored (chest on the left; mirrored levels only count if the distance map finds a way).
Models: P8 and the best phase-10 candidate, 16 stochastic attempts per level, repaired measurement, same seeds.
Per group: win rate and how the lost attempts end (pit, enemy, stuck, time) plus mean progress of the lost ones.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODELS = {"p8": "models/phase8_final.zip", "kandidat": "models/phase10_kandidat_alt.zip", "lehrer": "models/phase10_kandidat_lehrer.zip"}
N = 16


def mirror(level):
    from jumpnrun.core.level import Level

    lines = level.to_text().splitlines()
    w = max(len(l) for l in lines)
    return Level.from_text("\n".join(l.ljust(w)[::-1].rstrip() for l in lines), name=level.name + "_spiegel")


def levels():
    from jumpnrun.core.level import Level
    from jumpnrun.levelgen.distmap import DistanceMap
    from jumpnrun.rl import milestones8 as m8

    groups = {"dev_alt": [(n, lv) for n, lv, _ in m8.dev_levels()]}
    split = json.loads((ROOT / "levels/handmade10/split.json").read_text())
    groups["waechter_val"] = [(n, Level.from_file(ROOT / "levels/handmade10" / f"{n}.txt")) for n in split["val"]]
    for g in list(groups):
        mirrored = []
        for n, lv in groups[g]:
            m = mirror(lv)
            m.needs_path = True
            if DistanceMap(m).reachable:
                mirrored.append((n + "_spiegel", m))
        groups[g + "_gespiegelt"] = mirrored
    return groups


def work(args):
    import numpy as np
    import torch

    from jumpnrun.rl.evaluate import evaluate_levels
    from jumpnrun.rl.modelinfo import load_model

    tag, group, name, text, needs_path = args
    from jumpnrun.core.level import Level

    lv = Level.from_text(text, name=name)
    lv.needs_path = needs_path
    torch.set_num_threads(1)
    np.random.seed(0)
    torch.manual_seed(0)
    res = evaluate_levels(load_model(ROOT / MODELS[tag]), [lv] * N, deterministic=False)
    return tag, group, name, [(r["outcome"], round(r["progress"], 3)) for r in res]


def main():
    groups = levels()
    tags = sys.argv[1:] or list(MODELS)
    jobs = [(t, g, n, lv.to_text(), getattr(lv, "needs_path", False)) for t in tags for g, items in groups.items()
            for n, lv in items]
    path = ROOT / "runs/phase10/mirror_diag.json"
    out = json.loads(path.read_text()) if path.exists() else {}
    out.update({"n_je_level": N, "levels_je_gruppe": {g: len(v) for g, v in groups.items()}})
    out.setdefault("ergebnis", {})
    for t in tags:
        out["ergebnis"].pop(t, None)
    with Pool(2) as p:
        for tag, group, name, res in p.imap_unordered(work, jobs):
            o = out["ergebnis"].setdefault(tag, {}).setdefault(group, {"per_level": {}})
            o["per_level"][name] = res
            print(tag, group, name, sum(r[0] == "won" for r in res), "/", N, flush=True)
    for tag, gs in out["ergebnis"].items():
        for g, o in gs.items():
            allr = [r for v in o["per_level"].values() for r in v]
            lost = [r for r in allr if r[0] != "won"]
            o["siege"] = f"{sum(r[0] == 'won' for r in allr)}/{len(allr)}"
            o["rate"] = round(sum(r[0] == "won" for r in allr) / max(1, len(allr)), 4)
            o["verloren_wie"] = dict(Counter(r[0] for r in lost))
            o["fortschritt_verloren"] = round(sum(r[1] for r in lost) / max(1, len(lost)), 3)
    (ROOT / "runs/phase10/mirror_diag.json").write_text(json.dumps(out, indent=1))
    for tag, gs in out["ergebnis"].items():
        for g, o in sorted(gs.items()):
            print(f"{tag:9s} {g:24s} {o['siege']:>8s}  verloren: {o['verloren_wie']}  Fortschritt {o['fortschritt_verloren']}")


if __name__ == "__main__":
    main()
