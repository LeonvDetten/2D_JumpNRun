"""Phase 12 autopilot: one idempotent tick (called by scripts/phase12.sh) - BC start, training, evaluator, decision
points, scorecard picture.

    python3 -m jumpnrun.rl.autopilot12            # tick
    python3 -m jumpnrun.rl.autopilot12 bild       # scorecard picture only

Training waits for runs/phase12/E0_FREIGABE (Leon's acceptance of the generator, decision point E0).
All thresholds come from docs/lernen/daten/phase12_vorregistrierung.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from jumpnrun.rl import autopilot10 as A10
from jumpnrun.rl import scorecard12 as S

ROOT = A10.ROOT
PREREG = ROOT / "docs/lernen/daten/phase12_vorregistrierung.json"
STATE_DIR = ROOT / "runs/phase12"
STATE = STATE_DIR / "state.json"
FREIGABE = STATE_DIR / "E0_FREIGABE"
PY = sys.executable

PPO_FLAGS = ["--overview", "--obs-v3", "--path-delta", "--pool", "runs/demos4", "--demos", "runs/demos4",
             "--demo-progress", "path", "--bc2-a6-share", "0.05",
             "--start-prob", "0.2", "--start-dirs", "runs/demos4", "--rewind-prob", "0.4",
             "--ema-every", "1000000", "--ema2-decay", "0.998", "--envs", "8", "--n-steps", "512", "--batch", "1024",
             "--clip", "0.1", "--ent", "0.003", "--target-kl", "0.02", "--bc-coef", "0.3", "--bc-decay", "0.995",
             "--bc-min", "0.02", "--checkpoint-every", "100000", "--keep-every", "250000",
             "--eval-every", "1000000000", "--handmade", "levels/phase1/*.txt", "levels/phase2/*.txt",
             "--handmade-prob", "0.05", "--max-tier", "12", "--pool-share", "0.4", "--augment", "0.7",
             "--plr", "0.3", "--seed", "12", "--phase11", "--phase12", "--channels-last", "--mirror-long-share", "0.0"]


def prereg() -> dict:
    return json.loads(PREREG.read_text())


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {"started": time.time(), "log": [], "entscheidungen": {}}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False))


def note(state: dict, text: str) -> None:
    line = time.strftime("%H:%M ") + text
    state["log"].append(line)
    print(line, flush=True)


def run_dir() -> str:
    return prereg()["run"]


def milestones() -> dict:
    p = ROOT / run_dir() / "milestones12.json"
    return json.loads(p.read_text()) if p.exists() else {}


def ema_at(m: int):
    return milestones().get(f"{m * 1_000_000}:ema")


def neustart_at(m: float):
    pts = json.loads((STATE_DIR / "neustart_kurve.json").read_text())["punkte"]
    best = min(pts, key=lambda p: abs(p[0] - m))
    return {"dev_alt": best[1], "F": best[2]} if abs(best[0] - m) < 0.6 else None


def train_cmd() -> list:
    p = prereg()
    routing = json.loads((STATE_DIR / "lehrer_routing.json").read_text())
    (STATE_DIR / "lehrer_routing_nur.json").write_text(json.dumps(routing["routing"]))
    return [PY, "-m", "jumpnrun.rl.train", "--run", run_dir(), "--target", str(p["ziel_schritte"]),
            "--resume", p["start"], "--threads", "3", *PPO_FLAGS,
            "--lr-plan", json.dumps(p["lernrate"]), "--mix-schedule", json.dumps([[0, p["mischung"]]]),
            "--mix-gates", json.dumps(p["mischung_sperre"]), "--demos2", *p["bc2_dirs"],
            "--bc2-plan", json.dumps(p["bc2_plan"]), "--teachers", *routing["teachers"],
            "--routing", str(STATE_DIR / "lehrer_routing_nur.json"), "--teacher-plan", json.dumps(p["lehrer_plan"]),
            "--time-limit-hours", str(p["zeit_stunden"])]


def decide(state: dict) -> None:
    p = prereg()["entscheidungspunkte"]
    refs = S.references()
    neustart_card = refs.get("neustart", {}).get("kategorien")
    best_g = max((r["generalist"] for r in refs.values()), default=0.0)
    for name, rule in p.items():
        if name in state["entscheidungen"]:
            continue
        m = rule["mio"]
        cur = ema_at(m)
        if cur is None:
            continue
        ns = neustart_at(m) or {}
        cats = cur["kategorien"]
        if name == "E1":
            ok = cur["dev_alt"] >= ns.get("dev_alt", 0) and all(c > 0 for c in cats[3:6])
        elif name == "E2":
            early = ema_at(2)
            rising = early is not None and cats[6] > early["kategorien"][6] and cats[7] > early["kategorien"][7]
            ok = (cur["dev_alt"] >= ns.get("dev_alt", 0) + 0.05 or cur["F"] >= ns.get("F", 0) + 0.05) and rising
        elif name == "E3":
            above = sum(c > n for c, n in zip(cats, neustart_card)) if neustart_card else 0
            ok = cur["dev_alt"] >= 0.55 and above >= 5
        else:
            ok = cur["generalist"] >= best_g - 0.05
        state["entscheidungen"][name] = {"ok": bool(ok), "mio": m, "generalist": cur["generalist"],
                                         "dev_alt": cur["dev_alt"], "F": cur["F"], "neustart": ns,
                                         "kategorien": cats}
        note(state, f"ENTSCHEIDUNGSPUNKT {name} ({m} Mio.): {'erreicht' if ok else 'VERFEHLT'} - "
                    f"Generalist {cur['generalist']:.1%}, dev_alt {cur['dev_alt']:.1%} (Neustart {ns.get('dev_alt', 0):.1%}), "
                    f"F {cur['F']:.1%} (Neustart {ns.get('F', 0):.1%})")
        if not ok and rule.get("stopp"):
            A10.stop(run_dir())
            state["gestoppt"] = name
            note(state, f"Stopp nach {name} (vorregistriert) - Rückfrage an Leon")


def picture(state: dict):
    ms = milestones()
    emas = sorted((int(k.split(":")[0]), v) for k, v in ms.items() if k.endswith(":ema"))
    if not emas:
        return None
    hist = [(s / 1e6, v["generalist"], v["dev_alt"]) for s, v in emas]
    shadow = [(a, b) for a, b, _ in json.loads((STATE_DIR / "neustart_kurve.json").read_text())["punkte"]
              if a <= max(h[0] for h in hist) + 2]
    steps, cur = emas[-1]
    lines = [f"Stand {steps / 1e6:.0f} Mio. Schritte (EMA)", f"dev_alt {cur['dev_alt']:.1%}  ·  F {cur['F']:.1%}  ·  "
             f"Prüfung (32) {cur['pruefung32']}"]
    for name, d in state.get("entscheidungen", {}).items():
        lines.append(f"{name} ({d['mio']} Mio.): {'erreicht' if d['ok'] else 'verfehlt'}")
    lines += [""] + [l[:80] for l in state.get("log", [])[-5:]]
    return S.picture(cur, f"Phase 12 · frischer Schüler · {steps / 1e6:.0f} Mio.", history=hist, shadow=shadow,
                     note="\n".join(lines))


def tick() -> None:
    state = load_state()
    p = prereg()
    run = run_dir()
    if not FREIGABE.exists():
        note(state, "warte auf E0-Freigabe (runs/phase12/E0_FREIGABE)")
        save_state(state)
        return
    if not (ROOT / p["start"]).exists():
        if not A10.running("jumpnrun.rl.bc12 train"):
            A10.spawn([PY, "-m", "jumpnrun.rl.bc12", "train", "--out", p["start"], "--threads", "4"],
                      STATE_DIR / "bc.log", [0, 1, 2, 3])
            note(state, "BC-Start gestartet (4 Kerne)")
        save_state(state)
        return
    if not state.get("gestoppt") and A10.last_step(run) < p["ziel_schritte"] and not A10.train_running(run):
        (ROOT / run).mkdir(parents=True, exist_ok=True)
        A10.spawn(train_cmd(), ROOT / f"{run}.log", p["kerne_training"])
        note(state, f"Training gestartet/fortgesetzt (Kerne {p['kerne_training']})")
    if not A10.running(f"jumpnrun.rl.milestones12 --run {run}"):
        A10.spawn([PY, "-m", "jumpnrun.rl.milestones12", "--run", run], STATE_DIR / "milestones12.log",
                  [p["kern_messung"]])
    decide(state)
    picture(state)
    save_state(state)


if __name__ == "__main__":
    if sys.argv[1:] == ["bild"]:
        print(picture(load_state()))
    else:
        tick()
