"""Phase 11 autopilot: two arms (A with mirrored levels, B without), brakes, catastrophe stop, verdict.

    python3 -m jumpnrun.rl.autopilot11          # one idempotent tick (called by scripts/phase11.sh)

All thresholds come from docs/lernen/daten/phase11_vorregistrierung.json (committed before the first step).
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import numpy as np

from jumpnrun.rl import autopilot10 as A10

ROOT = A10.ROOT
PREREG = ROOT / "docs/lernen/daten/phase11_vorregistrierung.json"
STATE_DIR = ROOT / "runs/phase11"
STATE = STATE_DIR / "state.json"
MILLION = 1_000_000


def prereg() -> dict:
    return json.loads(PREREG.read_text())


def prereg_committed() -> bool:
    rel = str(PREREG.relative_to(ROOT))
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True).returncode == 0
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT).returncode == 0
    return tracked and clean


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"started": time.time(), "log": [], "brakes": [], "stopped": [], "rueckfrage": False}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1))


def note(state: dict, text: str) -> None:
    line = time.strftime("%H:%M ") + text
    state["log"].append(line)
    print(line, flush=True)


def arms() -> dict:
    return {k: v["run"] for k, v in prereg()["arme"].items()}


def start_steps() -> int:
    return int(prereg()["start_steps"])


def target() -> int:
    p = prereg()
    return start_steps() + p["lr_plan"]["critic_warmup"] + p["schritte"]


def milestones(run: str) -> dict:
    path = ROOT / run / "milestones11.json"
    return json.loads(path.read_text()) if path.exists() else {}


def baseline(tag: str):
    path = STATE_DIR / f"baseline_{tag}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return next(iter(data.values())) if data else None


def exam_rate(r: dict) -> float:
    p = r["dev"]["pruefung"]
    return p["won"] / p["of"]


def train_cmd(name: str) -> list:
    p = prereg()
    arm = p["arme"][name]
    extra = ["--phase11", "--channels-last", "--mix-schedule", arm["mix"], "--demos2", *arm["demos2"],
             "--bc2-plan", json.dumps(p["bc2_plan"]), "--bc2-a6-share", str(p["bc2_a6_anteil"]),
             "--teacher", p["lehrer"]["modell"], "--teacher-plan", json.dumps(p["lehrer"]["plan"]),
             "--mirror-long-share", str(p["spiegel_lang_anteil"]), "--time-limit-hours", str(p["zeitlimit_h"])]
    return A10.train_cmd(arm["run"], p["lr_plan"], target(), extra, start=p["start"])


def ema_series(run: str):
    ms = milestones(run)
    return sorted(((int(k.split(":")[0]), v) for k, v in ms.items() if k.endswith(":ema")), key=lambda x: x[0])


def tick() -> dict:
    state = load_state()
    p = prereg()
    if not prereg_committed():
        note(state, "Vorregistrierung nicht committet - kein Start")
        save_state(state)
        return state
    for name, arm in p["arme"].items():
        run = arm["run"]
        if name in state["stopped"] or A10.last_step(run) >= target() or A10.train_running(run):
            continue
        (ROOT / run).mkdir(parents=True, exist_ok=True)
        A10.spawn(train_cmd(name), ROOT / f"{run}.log", arm["kerne"])
        note(state, f"Arm {name}: Training gestartet/fortgesetzt (Kerne {arm['kerne']})")
    start = baseline("lehrer")
    if start is not None:
        b = p["bremse"]
        for name, run in arms().items():
            seq = ema_series(run)
            if name in state["stopped"] or len(seq) < 2:
                continue
            last2 = [r for _, r in seq[-2:]]
            if all(r["dev_alt"] <= start["dev_alt"] - 0.01 * p["katastrophe"]["unter_start_pp"] for r in last2):
                state["stopped"].append(name)
                A10.stop(run)
                note(state, f"Arm {name}: Katastrophen-Stopp (2 Messungen >= 15 Pp unter dem Start)")
                continue
            low = lambda r: (r["dev_alt"] <= start["dev_alt"] - 0.01 * b["unter_start_pp"]  # noqa: E731
                             or exam_rate(r) <= exam_rate(start) - 0.01 * b["unter_start_pp"])
            key = f"{seq[-1][0]}"
            if all(low(r) for r in last2) and key not in [k for _, k in state["brakes"]]:
                scale = max(b["lr_min"] / p["lr_plan"]["stages"][0][1],
                            min([json.loads((ROOT / r / "lr_scale.json").read_text())["scale"]
                                 if (ROOT / r / "lr_scale.json").exists() else 1.0 for r in arms().values()])
                            * b["faktor"])
                for r in arms().values():  # always both arms
                    (ROOT / r / "lr_scale.json").write_text(json.dumps({"scale": scale}))
                state["brakes"].append([name, key])
                note(state, f"Bremse (ausgelöst von Arm {name} bei {key}): LR-Faktor {scale:g} in beiden Armen")
    # question to Leon: A's mirror rate still 0 after +4 M
    a_run = arms().get("a")
    if a_run and not state["rueckfrage"]:
        full = [v for k, v in milestones(a_run).items() if v.get("size") == "voll"
                and int(k.split(":")[0]) >= start_steps() + 4 * MILLION]
        if full and max(v["spiegel_rate"] for v in full) == 0:
            state["rueckfrage"] = True
            note(state, "RÜCKFRAGE: Arm A hat nach +4 Mio. auf gespiegelten Leveln weiterhin 0 % - Leon fragen")
    verdict = judge(p)
    if verdict and not state.get("urteil"):
        state["urteil"] = verdict
        (STATE_DIR / "urteil.json").write_text(json.dumps(verdict, indent=1, ensure_ascii=False))
        note(state, "Urteil: " + verdict["text"])
    save_state(state)
    return state


def window(run: str, p: dict):
    ms = milestones(run)
    s0 = start_steps() + p["lr_plan"]["critic_warmup"]
    out = []
    for m in p["urteil"]["fenster_mio"]:
        for kind in ("ema", "ema2"):
            hit = next((v for k, v in ms.items() if k.endswith(f":{kind}") and v.get("size") == "voll"
                        and abs(int(k.split(":")[0]) - (s0 + m * MILLION)) < 600_000), None)
            if hit is None:
                return None
            out.append(hit)
    return out


def pooled(results, key):
    return float(np.mean([r[key] for r in results]))


def judge(p: dict):
    wins = {name: window(run, p) for name, run in arms().items()}
    if any(w is None for name, w in wins.items() if name not in load_state()["stopped"]):
        return None
    p8, lehrer = baseline("p8"), baseline("lehrer")
    if p8 is None or lehrer is None:
        return None
    vals = {}
    for name, w in wins.items():
        if w is None:
            continue
        v = dict(G=pooled(w, "G"), dev_alt=pooled(w, "dev_alt"), pruefung=float(np.mean([exam_rate(r) for r in w])),
                 spiegel=pooled(w, "spiegel_rate"), waechter_plus=pooled(w, "waechter_plus_rate"), F=pooled(w, "F"),
                 doppelgabel=pooled(w, "doppelgabel_rate"), sackgasse=pooled(w, "sackgasse_rate"))
        v["tor"] = v["dev_alt"] >= p8["dev_alt"] - 0.03 and v["pruefung"] >= exam_rate(p8) - 0.03
        vals[name] = {k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items()}
    a, b = vals.get("a"), vals.get("b")
    if a and b and a["G"] - b["G"] >= 0.05 and a["tor"]:
        pick, why = "a", "A gewinnt (G >= +5 Pp, Halte-Tor bestanden)"
    else:
        ok = [n for n in vals if vals[n]["tor"]]
        pick = max(ok, key=lambda n: vals[n]["G"]) if ok else None
        why = f"kein Unterschied; Kandidat = Arm mit höherem G und bestandenem Tor: {pick}" if pick else \
            "kein Arm besteht das Halte-Tor"
    better = pick is not None and vals[pick]["G"] >= lehrer["G"] + 0.05
    text = (f"{why}. " + " | ".join(f"{n}: G {v['G']:.1%}, dev_alt {v['dev_alt']:.1%}, Prüfung {v['pruefung']:.1%}, "
                                     f"Spiegel {v['spiegel']:.1%}, Tor {'ja' if v['tor'] else 'nein'}"
                                     for n, v in vals.items())
            + f" | Phase-10-Lehrer G {lehrer['G']:.1%} -> "
            + ("Phase-11-Kandidat ist besser (>= +5 Pp)" if better else "Phase-10-Lehrer bleibt das beste Modell"))
    return {"arme": vals, "kandidat": pick, "besser_als_phase10": better, "lehrer_G": lehrer["G"],
            "p8": {"dev_alt": p8["dev_alt"], "pruefung": exam_rate(p8), "G": p8["G"]}, "text": text}


if __name__ == "__main__":
    tick()
