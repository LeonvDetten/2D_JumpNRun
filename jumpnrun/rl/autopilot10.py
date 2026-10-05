"""Phase 10 autopilot: rounds A (learning rate), B (practise, then mix), C (rule round), selection, final evaluation.

    python3 -m jumpnrun.rl.autopilot10 tick       # one idempotent step (called by scripts/phase10.sh)
    python3 -m jumpnrun.rl.autopilot10 status
    python3 -m jumpnrun.rl.autopilot10 runs       # runs the milestone evaluator should follow

All thresholds come from docs/lernen/daten/phase10_vorregistrierung.json, which must be committed and unchanged
(its sha256 is stored in the state on the first tick; a later change stops the autopilot). State:
runs/phase10/state.json. Two arms per round on cores [0,1] and [2,3]; teacher demos never run during training.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = ROOT / "runs/phase10"
STATE = STATE_DIR / "state.json"
PREREG = ROOT / "docs/lernen/daten/phase10_vorregistrierung.json"
START = "runs/phase10/start_p8_v3.zip"
START_STEPS = 50_000_000
CORES = {0: [0, 1], 1: [2, 3]}
BUDGET_HOURS = 48.0
MILLION = 1_000_000

P8_FLAGS = ["--overview", "--pool", "runs/demos4", "--demos", "runs/demos4", "--start-prob", "0.2",
            "--start-dirs", "runs/demos4", "--rewind-prob", "0.4", "--ema-every", "1000000", "--ema2-decay", "0.998",
            "--unlock-all", "--threads", "2", "--envs", "8", "--clip", "0.1", "--ent", "0.003", "--target-kl", "0.02",
            "--bc-coef", "0.3", "--bc-decay", "0.995", "--bc-min", "0.02", "--checkpoint-every", "100000",
            "--keep-every", "250000", "--eval-every", "1000000000", "--handmade", "levels/phase1/*.txt",
            "levels/phase2/*.txt", "--handmade-prob", "0.05", "--max-tier", "12", "--pool-share", "0.4",
            "--augment", "0.7", "--plr", "0.3", "--obs-v3", "--path-delta", "--seed", "10",
            "--time-limit-hours", "30"]


# ----------------------------------------------------------------------------------------------- state & helpers
def prereg() -> dict:
    return json.loads(PREREG.read_text())


def prereg_hash() -> str:
    return hashlib.sha256(PREREG.read_bytes()).hexdigest()


def prereg_committed() -> bool:
    out = subprocess.run(["git", "status", "--porcelain", str(PREREG.relative_to(ROOT))], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    tracked = subprocess.run(["git", "ls-files", str(PREREG.relative_to(ROOT))], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    return bool(tracked) and not out


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"stage": "A", "log": [], "started": time.time(), "rounds": {}, "brakes": []}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1))


def note(state: dict, text: str) -> None:
    state["log"].append(time.strftime("%Y-%m-%d %H:%M", time.gmtime()) + " " + text)
    print(text, flush=True)


def running(pattern: str):
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.split()
    own = {os.getpid(), os.getppid()}
    pids = [int(p) for p in out if int(p) not in own]
    return pids[0] if pids else None


def train_running(run: str):
    return running(f"jumpnrun.rl.train --run {run} ")


def spawn(cmd: list, log: Path, cores) -> None:
    cmd = ["taskset", "-c", ",".join(map(str, cores))] + cmd
    env = dict(os.environ, OMP_NUM_THREADS=str(len(cores)))
    with open(log, "a") as f:
        subprocess.Popen(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env=env, start_new_session=True)


def stop(run: str) -> None:
    pid = train_running(run)
    if pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(60):
            if not train_running(run):
                break
            time.sleep(1)


def milestones(run: str) -> dict:
    path = ROOT / run / "milestones10.json"
    return json.loads(path.read_text()) if path.exists() else {}


def last_step(run: str) -> int:
    ck = sorted((ROOT / run / "checkpoints").glob("step_*.zip"))
    return int(ck[-1].stem[5:]) if ck else 0


def baseline(tag: str) -> dict:
    path = STATE_DIR / f"baseline_{tag}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def pooled_dev_alt(results) -> float:
    """dev_alt over several measurements with the attempts added up (each level counts the same)."""

    per = {}
    for r in results:
        for k, v in r["dev"].items():
            if k.startswith("hand9_"):
                continue
            o = per.setdefault(k, [0, 0])
            o[0] += v["won"]
            o[1] += v["of"]
    return sum(w / n for w, n in per.values()) / max(1, len(per))


def start_basis() -> float | None:
    b = baseline("start")
    return pooled_dev_alt(b.values()) if len(b) >= 3 else None


def p8_basis() -> float | None:
    b = baseline("p8")
    return pooled_dev_alt(b.values()) if len(b) >= 3 else None


# ----------------------------------------------------------------------------------------------- drift (KL)
def update_drift(run: str) -> None:
    """KL to phase 8 for raw checkpoints every 0.25 M (cheap, ~10 s each)."""

    from jumpnrun.rl.drift import measure
    from jumpnrun.rl.modelinfo import load_model

    path = ROOT / run / "drift.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    ck = sorted((ROOT / run / "checkpoints").glob("step_*.zip"))[:-1]
    changed = False
    for c in ck:
        steps = int(c.stem[5:])
        bucket = steps // 250_000
        if str(bucket) in done:
            continue
        try:
            done[str(bucket)] = dict(measure(load_model(c)), steps=steps)
        except Exception as exc:  # a checkpoint being deleted by keep-every
            print("drift skipped", c.name, exc)
            continue
        changed = True
    if changed:
        path.write_text(json.dumps(done, indent=1))


# ----------------------------------------------------------------------------------------------- round A
def arm_runs_a() -> dict:
    return {name: f"runs/phase10_{name}" for name in prereg()["runde_a"]["arme"]}


def train_cmd(run: str, lr_plan: dict, target: int, extra=(), start: str = START) -> list:
    return [sys.executable, "-m", "jumpnrun.rl.train", "--run", run, "--target", str(target),
            *P8_FLAGS, "--lr-plan", json.dumps(lr_plan), "--resume", start, *extra]


def tick_a(state: dict) -> None:
    pa = prereg()["runde_a"]
    target = START_STEPS + pa["critic_warmup"] + pa["ramp"] + pa["schritte_nach_warmup"]
    runs = arm_runs_a()
    info = state["rounds"].setdefault("A", {"target": target, "stopped": []})
    for i, (name, run) in enumerate(runs.items()):
        if name in info["stopped"] or last_step(run) >= target or train_running(run):
            continue
        plan = {"stages": [[0, pa["arme"][name]]], "critic_warmup": pa["critic_warmup"], "ramp": pa["ramp"]}
        (ROOT / run).mkdir(parents=True, exist_ok=True)
        spawn(train_cmd(run, plan, target), ROOT / f"{run}.log", CORES[i])
        note(state, f"Runde A, Arm {name}: Training gestartet/fortgesetzt (Kerne {CORES[i]})")
    for name, run in runs.items():
        update_drift(run)
    basis = start_basis()
    # catastrophe stop: dev_alt at 2 measurements in a row >= 15 Pp under the start basis
    for name, run in runs.items():
        if name in info["stopped"] or basis is None:
            continue
        seq = [v for k, v in sorted(milestones(run).items(), key=lambda kv: int(kv[0].split(":")[0]))
               if k.endswith(":ema")]
        if len(seq) >= 2 and all(r["dev_alt"] <= basis - 0.15 for r in seq[-2:]):
            info["stopped"].append(name)
            stop(run)
            note(state, f"Runde A, Arm {name}: Katastrophen-Stopp (2 Messungen >= 15 Pp unter der Startbasis)")
    # judge when all measurements at +2/+3/+4 M (EMA and raw) exist
    need = [START_STEPS + k * MILLION for k in (2, 3, 4)]
    results = {}
    for name, run in runs.items():
        ms = milestones(run)
        got = []
        for s in need:
            ema = ms.get(f"{s}:ema")
            raw = next((v for k, v in ms.items() if k.endswith(":raw") and int(k.split(":")[0]) // MILLION == s // MILLION),
                       None)
            if ema and raw:
                got += [ema, raw]
        if name not in info["stopped"] and len(got) < 6:
            return
        results[name] = got
    if basis is None:
        print("Runde A wartet auf die Startmodell-Basis (3 Messungen).")
        return
    loss = {n: (pooled_dev_alt(r) - basis if r else -1.0) for n, r in results.items()}
    safe = {n: loss[n] > pa["sicher_wenn_verlust_groesser_als"] and n not in info["stopped"] for n in loss}
    if safe.get("a_5e5"):
        key = "5e5_sicher"
    elif safe.get("a_2e5"):
        key = "nur_2e5_sicher"
    else:
        key = "keine_sicher"
    decision = dict(pa["regel"][key], fall=key)
    info["judged"] = {"verlust": loss, "sicher": safe, "basis": basis, "entscheidung": decision}
    state["b_plan"] = decision
    for run in runs.values():
        stop(run)
    note(state, f"Runde A entschieden: Alt-Verlust 2e-5 {loss.get('a_2e5', 0):+.1%}, 5e-5 {loss.get('a_5e5', 0):+.1%} "
                f"(Basis {basis:.1%}) -> {key}: Üben {decision['lr_ueben']}, Mischen {decision['lr_mischen1']} → "
                f"{decision['lr_mischen2']}, Anker {'an' if decision['anker'] else 'aus'}")
    state["stage"] = "demos"


# ----------------------------------------------------------------------------------------------- main tick
def tick() -> None:
    state = load_state()
    try:
        h = prereg_hash()
        if not prereg_committed():
            print("Vorregistrierung nicht committet -> kein Start.")
            return
        if state.setdefault("prereg_sha256", h) != h:
            note(state, "Vorregistrierung wurde nach dem Start geändert -> Autopilot angehalten.")
            return
        hours = (time.time() - state["started"]) / 3600
        stage = state["stage"]
        if stage == "A":
            tick_a(state)
        else:
            from jumpnrun.rl import autopilot10_bc as later  # rounds B/C, selection, final (built during round A)

            later.tick(state, hours)
    finally:
        save_state(state)


def current_runs() -> list:
    state = load_state()
    if state["stage"] == "A":
        return list(arm_runs_a().values())
    try:
        from jumpnrun.rl import autopilot10_bc as later

        return later.current_runs(state)
    except ImportError:
        return []


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "tick":
        tick()
    elif cmd == "runs":
        print(" ".join(current_runs()))
    else:
        state = load_state()
        print(json.dumps({k: v for k, v in state.items() if k != "log"}, indent=1))
        print("\n".join(state["log"][-15:]))


if __name__ == "__main__":
    main()
