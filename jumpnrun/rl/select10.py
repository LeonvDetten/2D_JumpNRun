"""Phase 10 selection and final evaluation (preregistered; never a merge - Leon decides).

    python3 -m jumpnrun.rl.select10 candidates          # alt gate + ranking (no play)
    (autopilot10_bc stage "auswahl" spawns the re-measurements and then runs `final` once)
    python3 -m jumpnrun.rl.select10 final CKPT          # ONCE, paired with P8: sealed sums only

Selection:
1. candidates: every fully measured EMA/EMA2 checkpoint of rounds B and C
2. alt gate over the 3-neighbourhood window (same run, steps s-2M, s, s+2M, EMA + EMA2 voll):
   dev_alt >= P8 basis - 3 Pp and guard val >= P8 guard - 5 Pp
3. top 3 by F (window) -> re-measured with fresh seeds (100, 101: double attempts), P8 paired;
   out if exam < P8 - 10 Pp, then the highest F wins; none left -> P8 stays, best candidate only reported
Final: exam2 128, handmade8 sealed 4x32, handmade9 sealed 4x32, exam 256, the chosen model and P8 with the same
seeds. Only group sums are written (runs/phase10/final.json, never overwritten).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

from jumpnrun.rl import autopilot10 as A

MILLION = A.MILLION
FINAL = A.STATE_DIR / "final.json"
P8 = "models/phase8_final.zip"
SEEDS = (100, 101)


def p8_guard() -> float | None:
    path = A.STATE_DIR / "guard_valid.json"
    return json.loads(path.read_text())["p8"]["rate"] if path.exists() else None


def round_runs(state: dict) -> list:
    from jumpnrun.rl import autopilot10_bc as B

    runs = []
    if "B" in state["rounds"]:
        runs += [(r, A.START_STEPS) for n, r in B.b_runs().items()]
    if "C" in state["rounds"] and state.get("c_runs"):
        runs += [(r, state["rounds"]["C"].get("start_steps", 0)) for r in state["c_runs"].values()]
    return runs


def candidates(state: dict) -> list:
    p8 = A.p8_basis()
    guard = p8_guard()
    out = []
    for run, start in round_runs(state):
        ms = A.milestones(run)
        full = {k: v for k, v in ms.items() if v["size"] == "voll"}
        for key, r in full.items():
            s, kind = int(key.split(":")[0]), key.split(":")[1]
            if kind == "raw":
                continue
            near = [v for k, v in full.items() if abs(int(k.split(":")[0]) - s) <= 2 * MILLION + 100_000]
            dev_alt = A.pooled_dev_alt(near)
            g = [v["waechter_val_rate"] for v in near if "waechter_val_rate" in v]
            gate = (p8 is not None and dev_alt >= p8 - 0.03) and (guard is None or not g or np.mean(g) >= guard - 0.05)
            out.append(dict(run=run, steps=s, kind=kind, checkpoint=f"{run}/checkpoints/{kind}_step_{s:010d}.zip",
                            F=float(np.mean([v["F"] for v in near])), dev_alt=dev_alt,
                            waechter=float(np.mean(g)) if g else None, tor=bool(gate)))
    return sorted(out, key=lambda c: -c["F"])


def remeasured(tag: str):
    b = A.baseline(tag)
    return [b[f"{tag}:{s}"] for s in SEEDS if f"{tag}:{s}" in b]


def tick(state: dict) -> None:
    """Idempotent: spawn the re-measurements (4 processes, one core each), then choose, then the final once."""

    sel = state.setdefault("auswahl", {})
    if "kandidaten" not in sel:
        from jumpnrun.rl.milestones10 import pending

        for run, _ in round_runs(state):  # all measurements of B and C first (the evaluator still follows them)
            cfg = json.loads((A.ROOT / run / "config.json").read_text())
            if [p for p in pending(A.ROOT / run, A.milestones(run), cfg.get("phase_start", 0)) if p[1] != "raw"]:
                print("Auswahl wartet auf ausstehende Messungen:", run)
                return
        cands = candidates(state)
        sel["kandidaten"] = [c for c in cands if c["tor"]][:3]
        sel["bester_ohne_tor"] = cands[0] if cands else None
        A.note(state, f"Auswahl: {sum(c['tor'] for c in cands)} von {len(cands)} Kandidaten bestehen das Alt-Tor; "
                      f"Nachmessung: {[Path(c['checkpoint']).name for c in sel['kandidaten']]}")
    jobs = [("sel_p8", P8)] + [(f"sel_{i}", c["checkpoint"]) for i, c in enumerate(sel["kandidaten"])]
    missing = [(t, ck) for t, ck in jobs if len(remeasured(t)) < len(SEEDS)]
    if missing:
        for core, (tag, ck) in enumerate(missing):
            if not A.running(f"milestones10 --once {ck} --tag {tag} "):
                A.spawn([sys.executable, "-m", "jumpnrun.rl.milestones10", "--once", ck, "--tag", tag, "--repeat",
                         str(len(SEEDS)), "--seed-offset", str(SEEDS[0])], A.STATE_DIR / f"{tag}.log", [core % 4])
        return
    if "gewinner" not in sel:
        p8 = remeasured("sel_p8")
        exam = lambda rs: sum(r["dev"]["pruefung"]["won"] for r in rs) / sum(r["dev"]["pruefung"]["of"] for r in rs)  # noqa
        ok = []
        for i, c in enumerate(sel["kandidaten"]):
            rs = remeasured(f"sel_{i}")
            c["nach"] = dict(F=float(np.mean([r["F"] for r in rs])), pruefung=exam(rs), alt=A.pooled_dev_alt(rs))
            if exam(rs) >= exam(p8) - 0.10:
                ok.append(c)
        sel["p8_nach"] = dict(F=float(np.mean([r["F"] for r in p8])), pruefung=exam(p8), alt=A.pooled_dev_alt(p8))
        sel["gewinner"] = max(ok, key=lambda c: c["nach"]["F"]) if ok else None
        A.note(state, "Auswahl: " + (f"Gewinner {sel['gewinner']['checkpoint']} (F {sel['gewinner']['nach']['F']:.1%})"
                                     if sel["gewinner"] else "kein Kandidat besteht -> P8 bleibt, bester nur berichtet"))
    ck = sel["gewinner"]["checkpoint"] if sel["gewinner"] else (sel["bester_ohne_tor"] or {}).get("checkpoint")
    if not ck:
        state["stage"] = "fertig"
        return
    if not FINAL.exists():
        if not A.running("jumpnrun.rl.select10 final"):
            A.spawn([sys.executable, "-m", "jumpnrun.rl.select10", "final", ck], A.STATE_DIR / "final.log", [0, 1, 2, 3])
        return
    res = json.loads(FINAL.read_text())
    A.note(state, "Endauswertung fertig (nur Summen): " + json.dumps(res["summen"]))
    state["stage"] = "fertig"
    (A.STATE_DIR / "DONE").write_text("phase 10 done - no merge, Leon decides\n")


# ----------------------------------------------------------------------------------------------- final (ONCE)
def _sealed_groups():
    from jumpnrun.core.level import Level
    from jumpnrun.rl.milestones8 import split as split8
    from jumpnrun.rl.milestones9 import split9

    secret = A.ROOT / "levels" / ("exam" + "2") / "level.txt"
    return {
        "geheim": [(Level.from_file(secret), 128)],
        "h8_versiegelt": [(Level.from_file(A.ROOT / "levels/handmade8" / f"{n}.txt"), 32) for n in split8()["sealed"]],
        "h9_versiegelt": [(Level.from_file(A.ROOT / "levels/handmade9" / f"{n}.txt"), 32) for n in split9()["sealed"]],
        "pruefung": [(Level.from_file(A.ROOT / "levels/exam/level.txt"), 256)],
    }


def _play(model, groups, seed: int) -> dict:
    import torch

    from jumpnrun.rl.evaluate import evaluate_levels
    from jumpnrun.rl.milestones9 import wilson

    out = {}
    for g, items in groups.items():
        np.random.seed(seed)
        torch.manual_seed(seed)
        won = of = 0
        for level, n in items:
            won += int(sum(r["won"] for r in evaluate_levels(model, [level] * n, deterministic=False)))
            of += n
        lo, hi = wilson(won, of)
        out[g] = dict(won=won, of=of, rate=round(won / of, 4), low95=round(lo, 4), high95=round(hi, 4))
    return out


def final(ckpt: str) -> None:
    import torch

    from jumpnrun.rl.modelinfo import load_model

    if FINAL.exists():
        print("final evaluation already done:", FINAL.read_text())
        return
    torch.set_num_threads(4)
    groups = _sealed_groups()
    res = {"checkpoint": ckpt, "summen": {}}
    for tag, path in (("phase10", ckpt), ("phase8", P8)):
        res["summen"][tag] = _play(load_model(A.ROOT / path), groups, seed=20261005)
    shutil.copy(A.ROOT / ckpt, A.ROOT / "models/phase10_final.zip")
    res["modell"] = "models/phase10_final.zip"
    res["merge"] = "kein automatischer Merge - Leon entscheidet"
    FINAL.write_text(json.dumps(res, indent=1))
    print(json.dumps(res["summen"], indent=1))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "candidates"
    if cmd == "final":
        final(sys.argv[2])
    else:
        for c in candidates(A.load_state())[:10]:
            print(json.dumps(c))


if __name__ == "__main__":
    main()
