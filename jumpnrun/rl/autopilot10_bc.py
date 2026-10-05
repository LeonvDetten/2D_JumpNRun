"""Phase 10 autopilot, after round A: teacher-demo window, round B (practise, then mix), round C (rule round).

Called by autopilot10.tick once state["stage"] != "A". Stages:
    demos   teacher demos (runs/demos10) + practice probes (v11) + left+jump-only states, on all 4 cores
    B       two arms from the start model: "neu" (practise first) and "kontrolle" (fixed mix), same LR/BC/brakes
    C       one rule round from the B winner (rules 0-3 of the preregistration)
    auswahl selection + final evaluation (select10 / final10), then "fertig" - never a merge
All thresholds come from the committed preregistration (autopilot10.prereg()).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

import numpy as np

from jumpnrun.rl import autopilot10 as A

MILLION = A.MILLION
WARMUP = {"critic_warmup": 150_000, "ramp": 300_000}
B_TARGET = A.START_STEPS + 10 * MILLION + 450_000
BC2_PLAN = [[0, 0.1], [3 * MILLION, 0.05], [6 * MILLION, 0.03]]
DEMO_DIRS = ["runs/demos10", "runs/demos9"]
A6_STATES = A.STATE_DIR / "a6_states.npz"
DEMO_DONE = A.ROOT / "runs/demos10/done.json"


def b_runs() -> dict:
    return {"neu": "runs/phase10_b_neu", "kontrolle": "runs/phase10_b_kontrolle"}


# ----------------------------------------------------------------------------------------------- demo window
DEMO_SCRIPT = """set -e
cd {root}
nice -n 5 python3 scripts/demos_phase10.py 2500 > runs/demos10/demos.log 2>&1
nice -n 5 python3 scripts/build_probes10.py 4 > runs/demos10/probes.log 2>&1
python3 -m jumpnrun.rl.autopilot10_bc a6states > runs/demos10/a6.log 2>&1
python3 -c "from jumpnrun.rl.ppo_demos import bc2_dataset; d = bc2_dataset({dirs}); print(len(d['action']), int((d['action'] == 6).sum()))" > runs/demos10/bc2.log 2>&1
echo '{{"done": true}}' > runs/demos10/done.json
"""


def build_a6_states() -> None:
    """States of the held-out teacher demos where left+jump is the ONLY right action (start check of round B)."""

    from jumpnrun.imitation.demos import cached_dataset

    data = cached_dataset([A.ROOT / "runs/demos10/holdout.jsonl"], A.STATE_DIR / "holdout10.npz",
                          max_samples=10**6, overview=True, shuffle=False, obs_v3=True)
    keep = np.nonzero(data["allowed"] == (1 << 6))[0]
    np.savez_compressed(A6_STATES, grid=data["grid"][keep], vec=data["vec"][keep], overview=data["overview"][keep])
    print("left+jump-only states:", len(keep))


def p_a6_only(model) -> float:
    import torch

    d = np.load(A6_STATES)
    ov = d["overview"].astype(np.float32)
    if d["overview"].dtype == np.uint8:
        ov = ov / 4.0
    obs = {"grid": torch.as_tensor(d["grid"], dtype=torch.float32), "vec": torch.as_tensor(d["vec"]),
           "overview": torch.as_tensor(ov)}
    with torch.no_grad():
        p = model.policy.get_distribution(obs).distribution.probs
    return float(p[:, 6].mean())


def tick_demos(state: dict) -> None:
    if DEMO_DONE.exists():
        from jumpnrun.rl.modelinfo import load_model

        state["b_start_p_a6_only"] = p_a6_only(load_model(A.ROOT / A.START))
        A.note(state, f"Lehrer-Beispiele fertig ({(A.ROOT / 'runs/demos10/demos.log').read_text().strip()[-120:]}); "
                      f"Startmodell P(links+springen | nur-links+springen) {state['b_start_p_a6_only']:.3f}")
        state["stage"] = "B"
        return
    if A.running("demos_phase10.py") or A.running("build_probes10.py") or A.running("autopilot10_bc a6states"):
        return
    if state.get("demos_started"):
        A.note(state, "Demo-Fenster: Skript beendet ohne done.json -> angehalten (bitte prüfen)")
        state["stage"] = "halt"
        return
    (A.ROOT / "runs/demos10").mkdir(parents=True, exist_ok=True)
    script = A.ROOT / "runs/demos10/run.sh"
    script.write_text(DEMO_SCRIPT.format(root=A.ROOT, dirs=DEMO_DIRS))
    subprocess.Popen(["bash", str(script)], cwd=A.ROOT, start_new_session=True,
                     stdout=open(A.ROOT / "runs/demos10/run.log", "a"), stderr=subprocess.STDOUT)
    state["demos_started"] = time.time()
    A.note(state, "Demo-Fenster gestartet (4 Kerne, kein Training parallel)")


# ----------------------------------------------------------------------------------------------- measurements
def series(run: str, kind: str):
    """[(steps, result)] of one kind (ema / ema2 / raw), sorted."""

    ms = A.milestones(run)
    return sorted(((int(k.split(":")[0]), v) for k, v in ms.items() if k.split(":")[1] == kind), key=lambda x: x[0])


def full_pooled(run: str):
    """[(steps, pooled dev_alt of EMA+EMA2 voll at that step)] - the brake signal."""

    ms = A.milestones(run)
    out = []
    for s, r in series(run, "ema2"):
        both = [r] + ([ms[f"{s}:ema"]] if f"{s}:ema" in ms and ms[f"{s}:ema"]["size"] == "voll" else [])
        out.append((s, A.pooled_dev_alt(both)))
    return out


def window(run: str, start: int, rel_millions, kinds=("ema", "ema2")):
    ms = A.milestones(run)
    got = {k: [ms[f"{start + m * MILLION}:{k}"] for m in rel_millions if f"{start + m * MILLION}:{k}" in ms]
           for k in kinds}
    return got


def mean(xs, key):
    return float(np.mean([x[key] for x in xs])) if xs else float("nan")


# ----------------------------------------------------------------------------------------------- brakes
def brakes(state: dict, rnd: str, runs: dict, stopped: list, start: int) -> None:
    pb = A.prereg()["bremsen_b_c"]
    s_kl = float(pb["S_KL"].split("=")[-1].replace(",", "."))
    basis = A.start_basis()
    info = state["rounds"][rnd]
    for name, run in runs.items():
        if name in stopped:
            continue
        # catastrophe: dev_alt of 2 EMA measurements in a row >= 15 Pp under the start basis
        seq = [r["dev_alt"] for s, r in series(run, "ema") if s > start]
        if basis is not None and len(seq) >= 2 and all(v <= basis - 0.15 for v in seq[-2:]):
            stopped.append(name)
            A.stop(run)
            A.note(state, f"Runde {rnd}, Arm {name}: Katastrophen-Stopp (2 Messungen >= 15 Pp unter der Startbasis)")
    if info.get("braked"):
        return
    reason = None
    for name, run in runs.items():
        if name in stopped:
            continue
        fp = [v for s, v in full_pooled(run) if s > start]
        if basis is not None and len(fp) >= 2 and fp[-2] <= basis - 0.08 and fp[-1] <= basis - 0.06:
            reason = f"Alt-Bremse Arm {name} ({fp[-2]:.1%}, {fp[-1]:.1%} bei Basis {basis:.1%})"
        drift = A.ROOT / run / "drift.json"
        if drift.exists():
            d = sorted(json.loads(drift.read_text()).values(), key=lambda x: x["steps"])
            d = [x for x in d if x["steps"] > start]
            if len(d) >= 2 and d[-1]["kl"] > s_kl and d[-2]["kl"] > s_kl:
                reason = reason or f"KL-Bremse Arm {name} ({d[-2]['kl']:.3f}, {d[-1]['kl']:.3f} > {s_kl:.4f})"
    if reason:
        info["braked"] = reason
        for run in runs.values():
            (A.ROOT / run / "lr_scale.json").write_text(json.dumps({"scale": 0.5, "grund": reason}))
        state["brakes"].append(dict(round=rnd, reason=reason, at=time.time()))
        A.note(state, f"Runde {rnd}: Bremse in beiden Armen (Lernrate halbiert): {reason}")


# ----------------------------------------------------------------------------------------------- round B
def start_checks(state: dict, runs: dict) -> list:
    """Problems of the start checks at +1 M (empty: passed)."""

    from jumpnrun.rl.modelinfo import load_model

    pc = A.prereg()["runde_b"]["startpruefungen_bei_1mio"]
    fps_ref = state.get("fps_a")
    problems = []
    for name, run in runs.items():
        ck = [c for c in sorted((A.ROOT / run / "checkpoints").glob("step_*.zip"))
              if int(c.stem[5:]) >= A.START_STEPS + MILLION]
        if not ck:
            return ["noch nicht"]
        model = load_model(ck[0])
        rise = p_a6_only(model) - state.get("b_start_p_a6_only", 0.0)
        if rise < pc["p_a6_nur_a6_anstieg_min"]:
            problems.append(f"{name}: P(l+s | nur l+s) nur +{rise:.3f}")
        from jumpnrun.rl.drift import measure

        old = measure(model)["p_a6"]
        if old >= pc["p_a6_alte_zustaende_max"]:
            problems.append(f"{name}: P(l+s) auf alten Zuständen {old:.3f}")
        steps = {}
        with open(A.ROOT / run / "episodes.jsonl") as f:
            for line in f:
                e = json.loads(line)
                if A.START_STEPS + 100_000 <= e["timesteps"] <= A.START_STEPS + MILLION:
                    steps[e.get("mix") or "p8"] = steps.get(e.get("mix") or "p8", 0) + e["steps"]
        total = sum(steps.values()) or 1
        plan = A.prereg()["runde_b"][f"mix_{name}"][0][1]
        for src, share in plan.items():
            if abs(steps.get(src, 0) / total - share) * 100 > pc["anteil_abweichung_max_pp"]:
                problems.append(f"{name}: Anteil {src} {steps.get(src, 0) / total:.1%} statt {share:.0%}")
        acc = tb_last(run, "vorbild/uebereinstimmung")
        if acc is not None and acc < pc["bc1_uebereinstimmung_min"]:
            problems.append(f"{name}: BC1-Übereinstimmung {acc:.2f}")
        secs = float((A.ROOT / run / "seconds_used").read_text() or 0) if (A.ROOT / run / "seconds_used").exists() else 0
        fps = (A.last_step(run) - A.START_STEPS) / secs if secs else None
        if fps and fps_ref and fps < pc["fps_min_anteil"] * fps_ref:
            problems.append(f"{name}: {fps:.0f} fps statt >= {pc['fps_min_anteil'] * fps_ref:.0f}")
        state["rounds"]["B"].setdefault("startpruefung", {})[name] = dict(
            p_a6_anstieg=round(rise, 4), p_a6_alt=old, anteile={k: round(v / total, 3) for k, v in steps.items()},
            bc1=acc, fps=fps)
    return problems


def tb_last(run: str, tag: str):
    try:
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    except ImportError:
        return None
    vals = []
    for d in sorted((A.ROOT / run / "tb").glob("*")):
        acc = EventAccumulator(str(d), size_guidance={"scalars": 0})
        acc.Reload()
        if tag in acc.Tags().get("scalars", []):
            vals += [e.value for e in acc.Scalars(tag)]
    return float(np.mean(vals[-20:])) if vals else None


def b_command(state: dict, name: str, run: str) -> list:
    plan = state["b_plan"]
    lr = {"stages": [[0, plan["lr_ueben"]], [3 * MILLION, plan["lr_mischen1"]], [6 * MILLION, plan["lr_mischen2"]]],
          **WARMUP}
    mix = A.prereg()["runde_b"][f"mix_{name}"]
    extra = ["--mix-schedule", json.dumps(mix), "--demos2", *DEMO_DIRS, "--bc2-plan", json.dumps(BC2_PLAN),
             "--bc2-a6-share", "0.05"]
    if plan.get("anker"):
        extra += ["--anchor"]
    return A.train_cmd(run, lr, B_TARGET, extra)


def judge_b(state: dict, runs: dict, stopped: list):
    """None while measurements are missing, else (winner, details)."""

    rel = (8, 9, 10)
    w = {n: window(r, A.START_STEPS, rel) for n, r in runs.items()}
    for n in runs:
        if n not in stopped and (len(w[n]["ema"]) < 3 or len(w[n]["ema2"]) < 2):
            return None
    if len(stopped) == 2:
        return "keiner", {"grund": "beide Arme im Katastrophen-Stopp"}
    if stopped:
        winner = next(n for n in runs if n not in stopped)
        return winner, {"grund": f"{stopped[0]} im Katastrophen-Stopp"}
    d = {}
    for kind in ("ema", "ema2"):
        d[kind] = {key: mean(w["neu"][kind], key) - mean(w["kontrolle"][kind], key) for key in ("F", "alt")}
    pooled = {n: w[n]["ema"] + w[n]["ema2"] for n in runs}
    dF = mean(pooled["neu"], "F") - mean(pooled["kontrolle"], "F")
    dAlt = mean(pooled["neu"], "alt") - mean(pooled["kontrolle"], "alt")
    same = np.sign(d["ema"]["F"]) == np.sign(d["ema2"]["F"])
    details = dict(dF=round(dF, 4), dAlt=round(dAlt, 4), je_art=d, gleiche_richtung=bool(same),
                   F={n: mean(pooled[n], "F") for n in runs}, alt={n: mean(pooled[n], "alt") for n in runs})
    if same and dF >= 0.05 and dAlt >= -0.03:
        return "neu", dict(details, grund="neu gewinnt (F >= +5 Pp, Alt >= -3 Pp)")
    if same and dF <= -0.05 and dAlt <= 0.03:
        return "kontrolle", dict(details, grund="Kontrolle gewinnt (spiegelbildlich)")
    winner = max(runs, key=lambda n: details["alt"][n])
    return winner, dict(details, grund=f"kein Unterschied -> höherer Alt-Wert: {winner}")


def tick_b(state: dict) -> None:
    if state["b_plan"].get("anker") and not anchor_available():
        print("Runde B braucht den Anker (Regel 'keine sicher'), der noch nicht gebaut ist -> wartet.")
        return
    runs = b_runs()
    info = state["rounds"].setdefault("B", {"target": B_TARGET, "stopped": []})
    stopped = info["stopped"]
    for i, (name, run) in enumerate(runs.items()):
        if name in stopped or A.last_step(run) >= B_TARGET or A.train_running(run):
            continue
        (A.ROOT / run).mkdir(parents=True, exist_ok=True)
        A.spawn(b_command(state, name, run), A.ROOT / f"{run}.log", A.CORES[i])
        A.note(state, f"Runde B, Arm {name}: Training gestartet/fortgesetzt (Kerne {A.CORES[i]})")
    for run in runs.values():
        A.update_drift(run)
    if "startpruefung_ok" not in info:
        problems = start_checks(state, runs)
        if problems == ["noch nicht"]:
            pass
        elif problems:
            for run in runs.values():
                A.stop(run)
            info["startpruefung_ok"] = False
            state["stage"] = "halt"
            A.note(state, "Runde B: Startprüfung bei +1 Mio. nicht bestanden -> beide Arme gestoppt: " + "; ".join(problems))
            return
        else:
            info["startpruefung_ok"] = True
            A.note(state, "Runde B: Startprüfungen bei +1 Mio. bestanden")
    brakes(state, "B", runs, stopped, A.START_STEPS)
    res = judge_b(state, runs, stopped)
    if res is None:
        return
    winner, details = res
    info["urteil"] = dict(details, gewinner=winner)
    for run in runs.values():
        A.stop(run)
    A.note(state, f"Runde B entschieden: {details['grund']}"
                  + (f" (ΔF {details['dF']:+.1%}, ΔAlt {details['dAlt']:+.1%})" if "dF" in details else ""))
    state["stage"] = "C" if winner != "keiner" else "halt"
    state["b_winner"] = winner


def anchor_available() -> bool:
    out = subprocess.run([sys.executable, "-m", "jumpnrun.rl.train", "--help"], cwd=A.ROOT, capture_output=True,
                         text=True).stdout
    return "--anchor" in out


# ----------------------------------------------------------------------------------------------- round C (TODO)
def tick_c(state: dict, hours: float) -> None:
    print("Runde C: Regeln werden während Runde B gebaut.")


def tick(state: dict, hours: float) -> None:
    stage = state["stage"]
    if stage == "demos":
        tick_demos(state)
    elif stage == "B":
        tick_b(state)
    elif stage == "C":
        tick_c(state, hours)
    elif stage == "halt":
        print("Autopilot angehalten:", state["log"][-1] if state["log"] else "")


def current_runs(state: dict) -> list:
    stage = state["stage"]
    if stage == "B" or (stage in ("C", "halt") and "B" in state["rounds"]):
        runs = list(b_runs().values())
        if stage == "C":
            runs += [r for r in state.get("c_runs", {}).values()]
        return runs
    return []


def main() -> None:
    if sys.argv[1:] == ["a6states"]:
        build_a6_states()


if __name__ == "__main__":
    main()
