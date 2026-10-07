"""Phase 11 final comparison (after the verdict): the best checkpoint of the window against the phase-10 teacher
candidate and P8, paired (same seeds), allowed levels only.

    OMP_NUM_THREADS=1 python3 scripts/vergleich11.py [procs]     # -> runs/phase11/vergleich.json

Candidate: from the verdict arm (runs/phase11/urteil.json), the window measurement (EMA/EMA2 at +6/+7/+8 M) with the
highest G among those passing the hold gate (dev_alt >= P8 - 3 Pp). Every model is measured with milestones11 at
seeds 1 and 2 (seed 0 is the window / baseline) and on the exam with 128 extra attempts (seeds 0..127).
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SEEDS = (1, 2)
EXAM_N = 128


def candidate():
    from jumpnrun.rl import autopilot11 as A

    verdict = json.loads((ROOT / "runs/phase11/urteil.json").read_text())
    arm = verdict["kandidat"]
    p = A.prereg()
    run = A.arms()[arm]
    p8 = A.baseline("p8")
    best = None
    s0 = A.start_steps() + p["lr_plan"]["critic_warmup"]
    for key, r in A.milestones(run).items():
        steps, kind = key.split(":")
        steps = int(steps)
        if kind not in ("ema", "ema2") or r.get("size") != "voll" or steps < s0 + 5_500_000:
            continue
        if r["dev_alt"] < p8["dev_alt"] - 0.03:
            continue
        if best is None or r["G"] > best[2]["G"]:
            best = (f"{run}/checkpoints/{r['checkpoint']}", key, r)
    return arm, best


def job(args):
    import numpy as np
    import torch

    tag, path, seed = args
    torch.set_num_threads(1)
    if seed == "exam":
        from jumpnrun.core.level import Level
        from jumpnrun.rl.evaluate import evaluate_levels
        from jumpnrun.rl.modelinfo import load_model

        np.random.seed(0)
        torch.manual_seed(0)
        lv = Level.from_file(ROOT / "levels/exam/level.txt")
        res = evaluate_levels(load_model(ROOT / path), [lv] * EXAM_N, deterministic=False)
        return tag, seed, {"won": sum(int(r["won"]) for r in res), "of": EXAM_N}
    from jumpnrun.rl import milestones11 as m11

    r = m11.evaluate(ROOT / path, full=True, seed=seed)
    keys = ("dev_alt", "dev_neu", "F", "alt", "spiegel_rate", "spiegel_alt_rate", "spiegel_lang_rate",
            "waechter_plus_rate", "sackgasse_rate", "doppelgabel_rate", "G")
    out = {k: r[k] for k in keys}
    out["pruefung"] = r["dev"]["pruefung"]
    out["schutz"] = r["schutz"]
    out["test_summen"] = r["test_summen"]
    return tag, seed, out


def main():
    arm, best = candidate()
    if best is None:
        print("kein Kandidat besteht das Halte-Tor")
        return
    models = {"kandidat": best[0], "lehrer": "models/phase10_kandidat_lehrer.zip", "p8": "models/phase8_final.zip"}
    jobs = [(t, m, s) for t, m in models.items() for s in (*SEEDS, "exam")]
    out = {"kandidat": {"arm": arm, "messung": best[1], "pfad": best[0]}, "ergebnisse": {}}
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as pool:
        for tag, seed, r in pool.imap_unordered(job, jobs):
            out["ergebnisse"].setdefault(tag, {})[str(seed)] = r
            print(tag, seed, json.dumps(r)[:300], flush=True)
            (ROOT / "runs/phase11/vergleich.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
