"""Paired comparison of all models on allowed levels + a profile per level type (basis for teacher routing).

    OMP_NUM_THREADS=1 python3 scripts/endvergleich12.py [procs]     # -> runs/phase12/endvergleich.json

Models: P8, phase-10 teacher candidate, phase-11 candidate, the three Neustart candidates.
1. milestones11 full measurement at seeds 1 and 2 (P8 / phase 10 / phase 11 reused from runs/phase11/vergleich.json,
   same code and seeds) and the exam with 128 attempts.
2. Level-type profile ("Familien"): fresh generator levels from a validation seed space never used in training -
   v9 tiers 4-12, v10 tiers 10-13, the 8 practice kinds at d2, mirrored v9, long (two levels joined), mirrored long.
   Routing decisions for teachers may only use this profile and the validation groups, never test levels.
Sealed and test levels are never opened here (test groups only as sums inside milestones11).
"""

from __future__ import annotations

import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "runs/phase12/endvergleich.json"
MODELS = {"p8": "models/phase8_final.zip", "lehrer10": "models/phase10_kandidat_lehrer.zip",
          "kandidat11": "models/phase11_kandidat.zip", "neustart_f": "models/neustart_kandidat_f.zip",
          "neustart_waechter": "models/neustart_kandidat_waechter.zip",
          "neustart_pruefung": "models/neustart_kandidat_pruefung.zip"}
REUSE = {"p8": "p8", "lehrer10": "lehrer", "kandidat11": "kandidat"}  # tags in runs/phase11/vergleich.json
N_FAM = 24
VAL_SEED = 3_000_000_000  # validation seed space (training draws seeds < 10**8 / 10**9)


def families():
    from jumpnrun.levelgen import generator as G
    from jumpnrun.levelgen.skills import KINDS11, LongSource, make_skill_level, mirror_level
    from jumpnrun.levelgen.distmap import DistanceMap

    fam = {}
    for t in range(4, 13):
        fam[f"v9_t{t}"] = [G.generate(t, VAL_SEED + 1000 * t + i) for i in range(N_FAM)]
    for t in range(10, 14):
        fam[f"v10_t{t}"] = [G.generate(t, VAL_SEED + 50_000 + 1000 * t + i, "v10") for i in range(N_FAM)]
    for k in KINDS11:
        fam[f"uebung_{k}"] = [make_skill_level(k, 2, f"val12:{k}:{i}") for i in range(N_FAM)]
    for name, tiers in (("spiegel_t4-7", range(4, 8)), ("spiegel_t8-12", range(8, 13))):
        lv, i = [], 0
        while len(lv) < N_FAM:
            t = list(tiers)[i % len(tiers)]
            m = mirror_level(G.generate(t, VAL_SEED + 90_000 + i))
            i += 1
            if DistanceMap(m).reachable:
                lv.append(m)
        fam[name] = lv
    rng = random.Random("val12:lang")
    longs = [LongSource().make(rng) for _ in range(16)]
    fam["lang"] = longs
    fam["spiegel_lang"] = [m for m in (mirror_level(l) for l in longs) if DistanceMap(m).reachable]
    return fam


def job(args):
    import numpy as np
    import torch

    kind, tag, seed = args
    torch.set_num_threads(1)
    path = ROOT / MODELS[tag]
    if kind == "exam":
        from jumpnrun.core.level import Level
        from jumpnrun.rl.evaluate import evaluate_levels
        from jumpnrun.rl.modelinfo import load_model

        np.random.seed(0)
        torch.manual_seed(0)
        res = evaluate_levels(load_model(path), [Level.from_file(ROOT / "levels/exam/level.txt")] * 128,
                              deterministic=False)
        return kind, tag, seed, {"won": sum(int(r["won"]) for r in res), "of": 128}
    if kind == "familien":
        from jumpnrun.rl.evaluate import evaluate_levels
        from jumpnrun.rl.modelinfo import load_model

        model = load_model(path)
        out = {}
        for name, levels in families().items():
            np.random.seed(0)
            torch.manual_seed(0)
            res = evaluate_levels(model, levels, deterministic=False)
            out[name] = {"won": sum(int(r["won"]) for r in res), "of": len(res),
                         "fortschritt": round(float(np.mean([r["progress"] for r in res])), 3)}
        return kind, tag, seed, out
    from jumpnrun.rl import milestones11 as m11

    r = m11.evaluate(path, full=True, seed=seed)
    keys = ("dev_alt", "dev_neu", "F", "alt", "spiegel_rate", "spiegel_alt_rate", "spiegel_lang_rate",
            "waechter_plus_rate", "sackgasse_rate", "doppelgabel_rate", "G")
    out = {k: r[k] for k in keys}
    out.update(pruefung=r["dev"]["pruefung"], schutz=r["schutz"], test_summen=r["test_summen"],
               dev={k: v for k, v in r["dev"].items()}, waechter_plus=r["waechter_plus"])
    return kind, tag, seed, out


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = json.loads(OUT.read_text()) if OUT.exists() else {"mess": {}, "pruefung128": {}, "familien": {}}
    old = json.loads((ROOT / "runs/phase11/vergleich.json").read_text())["ergebnisse"]
    jobs = []
    for tag in MODELS:
        if tag in REUSE:
            r = old[REUSE[tag]]
            out["mess"].setdefault(tag, {"1": r["1"], "2": r["2"]})
            out["pruefung128"].setdefault(tag, r["exam"])
        else:
            jobs += [("mess", tag, s) for s in (1, 2) if str(s) not in out["mess"].get(tag, {})]
            if tag not in out["pruefung128"]:
                jobs.append(("exam", tag, 0))
        if tag not in out["familien"]:
            jobs.append(("familien", tag, 0))
    jobs.sort(key=lambda j: j[0] != "familien")  # the long jobs first
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as pool:
        for kind, tag, seed, r in pool.imap_unordered(job, jobs):
            if kind == "mess":
                out["mess"].setdefault(tag, {})[str(seed)] = r
            elif kind == "exam":
                out["pruefung128"][tag] = r
            else:
                out["familien"][tag] = r
            OUT.write_text(json.dumps(out, indent=1))
            print(kind, tag, seed, json.dumps(r)[:200], flush=True)


if __name__ == "__main__":
    main()
