"""Phase 13 autopilot: one idempotent tick (scripts/phase13.sh) - training on cores 0-2, evaluator on core 3,
the pre-registered protection rules (applied without Leon: he is away ~15 h), scorecard picture.

    python3 -m jumpnrun.rl.autopilot13          # tick
    python3 -m jumpnrun.rl.autopilot13 bild     # picture only

Rules (docs/lernen/daten/phase13_vorregistrierung.json):
- protection: generalist at T = 0.3 WITHOUT the links category twice in a row > 3 Pp below stand 0 ->
  left share down to 10 % (links 5 %, spiegel 5 %, the rest to p8); after that again twice -> stop.
- E1 (2 M): left jumps or category links/spiegel up over stand 0 - otherwise only noted.
- E2 (5 M): links/spiegel (T = 0.3) at least +5 Pp over stand 0 - otherwise left share 30 -> 15 %.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from jumpnrun.rl import autopilot10 as A10
from jumpnrun.rl import scorecard12 as S

ROOT = A10.ROOT
PREREG = ROOT / "docs/lernen/daten/phase13_vorregistrierung.json"
STATE_DIR = ROOT / "runs/phase13"
STATE = STATE_DIR / "state.json"
PY = sys.executable

PPO_FLAGS = ["--overview", "--obs-v3", "--path-delta", "--pool", "runs/demos4", "--demos", "runs/demos4",
             "--demo-progress", "path", "--bc2-a6-share", "0.05",
             "--start-prob", "0.2", "--start-dirs", "runs/demos4", "--rewind-prob", "0.4",
             "--ema-every", "1000000", "--ema2-decay", "0.998", "--envs", "8", "--n-steps", "512", "--batch", "1024",
             "--clip", "0.1", "--ent", "0.001", "--target-kl", "0.02", "--bc-coef", "0.3", "--bc-decay", "0.995",
             "--bc-min", "0.02", "--checkpoint-every", "100000", "--keep-every", "250000",
             "--eval-every", "1000000000", "--handmade", "levels/phase1/*.txt", "levels/phase2/*.txt",
             "--handmade-prob", "0.05", "--max-tier", "12", "--pool-share", "0.4", "--augment", "0.7",
             "--plr", "0.3", "--seed", "13", "--phase11", "--phase12", "--channels-last", "--mirror-long-share", "0.0",
             "--mirror-adaptive"]


def prereg() -> dict:
    return json.loads(PREREG.read_text())


def save_prereg(p: dict) -> None:
    PREREG.write_text(json.dumps(p, indent=1, ensure_ascii=False) + "\n")


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {"log": [], "entscheidungen": {}, "schutz": []}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False))


def note(state: dict, text: str) -> None:
    line = time.strftime("%d.%m. %H:%M ") + text
    state["log"].append(line)
    print(line, flush=True)


def milestones() -> dict:
    p = ROOT / prereg()["run"] / "milestones13.json"
    return json.loads(p.read_text()) if p.exists() else {}


def stand0() -> dict:
    return json.loads((STATE_DIR / "stand_stand0.json").read_text())


def emas():
    start = prereg()["start_schritte"]
    return sorted(((int(k.split(":")[0]) - start) / 1e6, v) for k, v in milestones().items() if k.endswith(":ema"))


def train_cmd() -> list:
    p = prereg()
    return [PY, "-m", "jumpnrun.rl.train", "--run", p["run"], "--target", str(p["start_schritte"] + p["ziel_schritte"]),
            "--resume", p["start"], "--threads", "3", *PPO_FLAGS,
            "--lr-plan", json.dumps(p["lernrate"]), "--mix-schedule", json.dumps([[0, p["mischung"]]]),
            "--mix-gates", json.dumps(p["mischung_sperre"]), "--demos2", *p["bc2_dirs"],
            "--bc2-plan", json.dumps(p["bc2_plan"]), "--time-limit-hours", str(p["zeit_stunden"])]


def set_mix(state: dict, mix: dict, why: str) -> None:
    p = prereg()
    p["mischung"] = mix
    p.setdefault("aenderungen_autopilot", []).append({"zeit": time.strftime("%Y-%m-%d %H:%M"), "mischung": mix,
                                                       "grund": why})
    save_prereg(p)
    A10.stop(p["run"])
    note(state, f"Mischung geändert ({why}): {mix} - Neustart vom Checkpoint")


def decide(state: dict) -> None:
    pts = emas()
    if not pts:
        return
    s0 = stand0()
    base_ohne, base_links = s0["ohne_links_t03"], s0["t03"]["kategorien"][5]
    base_ls = s0["links_spruenge"]["won"] / s0["links_spruenge"]["of"]
    # protection: the last two points (since the last mix change) below stand 0 - 3 Pp
    seen = state.setdefault("geprueft", [])
    for m, v in pts:
        key = f"{m:.0f}"
        if key in seen:
            continue
        seen.append(key)
        low = v["ohne_links_t03"] < base_ohne - 0.03
        state["schutz"].append(bool(low))
        note(state, f"{m:.0f} Mio.: Generalist T0.3 {v['t03']['generalist']:.1%}, ohne Links {v['ohne_links_t03']:.1%} "
                    f"(Stand 0 {base_ohne:.1%}){' - UNTER der Schutzgrenze' if low else ''}, Links/Spiegel "
                    f"{v['t03']['kategorien'][5]:.0%} (Stand 0 {base_links:.0%})")
        if len(state["schutz"]) >= 2 and state["schutz"][-1] and state["schutz"][-2]:
            stage = state.get("schutz_stufe", 0)
            state["schutz"] = []
            if stage == 0:
                state["schutz_stufe"] = 1
                set_mix(state, {"p8": 0.40, "skill": 0.05, "v10": 0.05, "hart": 0.15, "lang": 0.10, "pruefung": 0.15,
                                "links": 0.05, "spiegel": 0.05}, "Schutzregel: Links-Anteil 30 -> 10 %")
            else:
                A10.stop(prereg()["run"])
                state["gestoppt"] = "Schutzregel zweimal"
                note(state, "STOPP: Schutzregel ein zweites Mal verletzt")
        if m >= 2 and "E1" not in state["entscheidungen"]:
            ls = v["links_spruenge"]["won"] / v["links_spruenge"]["of"]
            ok = ls > base_ls or v["t03"]["kategorien"][5] > base_links
            state["entscheidungen"]["E1"] = {"ok": ok, "mio": m, "links_spruenge": ls}
            note(state, f"E1 (2 Mio.): {'erreicht' if ok else 'verfehlt (nur notiert)'} - Links-Sprünge {ls:.0%} "
                        f"(Stand 0 {base_ls:.0%})")
        if m >= 5 and "E2" not in state["entscheidungen"]:
            ok = v["t03"]["kategorien"][5] >= base_links + 0.05
            state["entscheidungen"]["E2"] = {"ok": ok, "mio": m, "links": v["t03"]["kategorien"][5]}
            note(state, f"E2 (5 Mio.): {'erreicht' if ok else 'verfehlt'} - Links/Spiegel {v['t03']['kategorien'][5]:.0%}")
            if not ok and state.get("schutz_stufe", 0) == 0:
                set_mix(state, {"p8": 0.35, "skill": 0.05, "v10": 0.05, "hart": 0.15, "lang": 0.10, "pruefung": 0.15,
                                "links": 0.10, "spiegel": 0.05}, "E2 verfehlt: Links-Anteil 30 -> 15 %")


def picture(state: dict):
    pts = emas()
    if not pts:
        return None
    s0 = stand0()
    hist = [(0.0, s0["t03"]["generalist"], s0["t1"]["generalist"])] + [(m, v["t03"]["generalist"], v["t1"]["generalist"])
                                                                       for m, v in pts]
    m, cur = pts[-1]
    lines = [f"Stand +{m:.0f} Mio. (EMA), Bot-Spielweise T = 0,3",
             f"Generalist T0,3 {cur['t03']['generalist']:.1%} (Stand 0 {s0['t03']['generalist']:.1%})  ·  "
             f"T1 {cur['t1']['generalist']:.1%} (Stand 0 {s0['t1']['generalist']:.1%})",
             f"ohne Links: {cur['ohne_links_t03']:.1%} (Stand 0 {s0['ohne_links_t03']:.1%}, Schutzgrenze "
             f"{s0['ohne_links_t03'] - 0.03:.1%})",
             f"Links-Sprünge (gespiegelt, nie trainiert): {cur['links_spruenge']['won']}/{cur['links_spruenge']['of']} "
             f"(Stand 0 {s0['links_spruenge']['won']})",
             f"spiegelweg: {cur['spiegelweg']['won']}/16 (Stand 0 {s0['spiegelweg']['won']})"]
    for name, d in state.get("entscheidungen", {}).items():
        lines.append(f"{name}: {'erreicht' if d['ok'] else 'verfehlt'}")
    lines += [""] + [l[:85] for l in state.get("log", [])[-4:]]
    return S.picture({"kategorien": cur["t03"]["kategorien"], "generalist": cur["t03"]["generalist"]},
                     f"Phase 13 · Links-Präzision · +{m:.0f} Mio. · Spielweise T = 0,3", history=hist, shadow=None,
                     out=STATE_DIR / "scorecard.png", note="\n".join(lines),
                     line_labels=("Generalist bei T = 0,3 (Spielweise)", "Generalist bei T = 1 (wie bisher gemessen)"))


def tick() -> None:
    state = load_state()
    p = prereg()
    run = p["run"]
    target = p["start_schritte"] + p["ziel_schritte"]
    decide(state)  # may change the mix and stop the training - it is restarted right below
    if not state.get("gestoppt") and A10.last_step(run) < target and not A10.train_running(run):
        (ROOT / run).mkdir(parents=True, exist_ok=True)
        A10.spawn(train_cmd(), ROOT / f"{run}.log", p["kerne_training"])
        note(state, f"Training gestartet/fortgesetzt (Kerne {p['kerne_training']})")
    if not A10.running(f"jumpnrun.rl.milestones13 --run {run}"):
        A10.spawn([PY, "-m", "jumpnrun.rl.milestones13", "--run", run], STATE_DIR / "milestones13.log",
                  [p["kern_messung"]])
    picture(state)
    save_state(state)


if __name__ == "__main__":
    if sys.argv[1:] == ["bild"]:
        print(picture(load_state()))
    else:
        tick()
