"""Phase 7 autopilot: runs the whole phase without questions, by fixed rules. Safe to call at any time.

    python3 -m jumpnrun.rl.autopilot tick      # one step of the state machine (idempotent)
    python3 -m jumpnrun.rl.autopilot status    # print the state

State lives in runs/phase7/state.json. Order of work:
    1 teacher demos (runs/demos4)                       scripts/demos_phase7.sh
    2 start model for run B (behaviour cloning)         models/phase7b_start.zip
    3 smoke tests passed                                runs/phase7/smoke_ok (written after the test runs)
    4 training runs A and B (idempotent launch)          runs/phase7a, runs/phase7b
    5 rules after every milestone round:
        - CANDIDATE (stop rule at two milestones) -> final evaluation (128 exam / 192 test series);
          confirmed -> SUCCESS, otherwise continue training
        - after 12 h and 24 h: a run that is clearly behind (>= 10 points in exam AND test series) pauses,
          the other one gets all 4 cores
        - plateau ladder per run: 1st -> NEEDS_PATTERNS (failure catalogue -> generator, done in the session),
          2nd -> calm fine-tune fork, 3rd -> stop the run
        - both runs finished -> final evaluation of the best model -> DONE
"""

from __future__ import annotations

import json
import shutil
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = ROOT / "runs/phase7"
STATE = STATE_DIR / "state.json"
RUNS = {"A": ROOT / "runs/phase7a", "B": ROOT / "runs/phase7b", "C": ROOT / "runs/phase7c",
        "D": ROOT / "runs/phase7d"}
START_MODELS = {"A": ROOT / "models/phase6_durchbruch.zip", "B": ROOT / "models/phase7b_start.zip",
                # C (Leon's decision 02.10.): fork of A from its best exam milestone (EMA 34M), generator v7
                "C": ROOT / "runs/phase7a/checkpoints/ema_step_0034000000.zip",
                # D (Leon's decision 02.10.): fork of C from EMA 36M, generator v8 (enemy ramps, more upper roads)
                "D": ROOT / "runs/phase7c/checkpoints/ema_step_0036000004.zip"}
# A used 24.4 h before C forked off, C used 3.9 h before D: the A-C-D line stays within 48 h
FORK_HOURS_LIMIT = {"C": 23.5, "D": 19.6}
GOAL_EXAM, GOAL_SERIES = 64 / 128, 144 / 192
HOURS_LIMIT = 48
COMPARE_AT = (12, 24)


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"alloc": {"A": [0, 1], "B": [2, 3]}, "envs": {"A": 8, "B": 8}, "paused": [], "plateaus": {"A": 0, "B": 0},
            "last_intervention": {"A": 0, "B": 0}, "compared": [], "log": [], "calm": {}, "bc_attempts": 0}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1))


def note(state: dict, text: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M", time.gmtime())
    state["log"].append(f"{stamp} {text}")
    print(text, flush=True)


def running(pattern: str) -> int | None:
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.split()
    own = {os.getpid(), os.getppid()}
    pids = [int(p) for p in out if int(p) not in own]
    return pids[0] if pids else None


def spawn(cmd: list, log: Path, cores=None) -> None:
    if cores:
        cmd = ["taskset", "-c", ",".join(map(str, cores))] + cmd
    env = dict(os.environ, OMP_NUM_THREADS=str(len(cores) if cores else 4))
    with open(log, "a") as f:
        subprocess.Popen(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env=env, start_new_session=True)


# ----------------------------------------------------------------------------- steps
def demos_done() -> bool:
    pool = ROOT / "runs/demos4/pool.json"
    return pool.exists() and '"12"' in pool.read_text()


def bc_start_model(state: dict) -> bool:
    """Run B's start model: behaviour cloning of a fresh IMPALA network. True when ready."""

    target = START_MODELS["B"]
    if target.exists():
        return True
    if running("jumpnrun.imitation.bc --demos runs/demos4"):
        return False
    log = ROOT / "runs/bc7.log"
    if state["bc_attempts"] >= 2:
        first = ROOT / "models/phase7b_bc_first.zip"
        if first.exists():  # second attempt was killed (container restart): keep the first model
            note(state, "Zweiter Nachahm-Versuch abgebrochen (Container-Neustart): B startet vom ersten BC-Modell")
            for suffix in (".zip", ".json"):
                shutil.copy(first.with_suffix(suffix), target.with_suffix(suffix))
            return True
        state["b_fresh"] = True
        return True
    state["bc_attempts"] += 1
    if state["bc_attempts"] == 1:
        start = ["--arch", "impala", "--lr", "1e-3"]
    else:  # second attempt: continue the first model (its curve was still rising) with a smaller rate
        start = ["--init", "models/phase7b_bc_first.zip", "--lr", "5e-4"]
    note(state, f"Starte Nachahmen für Lauf B (Versuch {state['bc_attempts']}: {' '.join(start)})")
    spawn([sys.executable, "-m", "jumpnrun.imitation.bc", "--demos", "runs/demos4", *start,
           "--dagger-rounds", "0", "--epochs", "3", "--max-samples", "700000", "--value-steps", "300000",
           "--threads", "4", "--out", "models/phase7b_bc_try.zip"], log)
    return False


def check_bc(state: dict) -> None:
    """Accept the BC model if its validation win rate is >= 40 %, else retry once, else start B fresh."""

    trial = ROOT / "models/phase7b_bc_try.zip"
    if START_MODELS["B"].exists() or not trial.exists() or running("jumpnrun.imitation.bc --demos runs/demos4"):
        return
    text = (ROOT / "runs/bc7.log").read_text()
    rates = [float(l.split("validation win rate")[1].split("%")[0]) for l in text.splitlines()
             if l.startswith("after imitation")]
    rate = rates[-1] if rates else 0.0
    if rate >= 40.0 or state["bc_attempts"] >= 2:
        # after the second attempt the better imitation model is used either way (better than none)
        note(state, f"Nachahmen für B angenommen: {rate:.1f} % Validierung (Versuch {state['bc_attempts']})")
        for suffix in (".zip", ".json"):
            os.replace(trial.with_suffix(suffix), START_MODELS["B"].with_suffix(suffix))
    else:
        note(state, f"Nachahmen für B noch zu schwach ({rate:.1f} %), zweiter Versuch: weitertrainieren")
        for suffix in (".zip", ".json"):
            os.replace(trial.with_suffix(suffix), (ROOT / "models/phase7b_bc_first").with_suffix(suffix))
        os.replace(ROOT / "runs/bc7.log", ROOT / "runs/bc7_first.log")


def train_cmd(name: str, state: dict) -> list:
    run = RUNS[name]
    threads = len(state["alloc"][name])
    cmd = [sys.executable, "-m", "jumpnrun.rl.train", "--run", str(run.relative_to(ROOT)), "--target", "400000000",
           "--overview", "--pool", "runs/demos4", "--demos", "runs/demos4", "--start-prob", "0.2",
           "--start-dirs", "runs/demos4", "--rewind-prob", "0.4", "--ema-every", "1000000",
           "--time-limit-hours", str(HOURS_LIMIT), "--unlock-all", "--threads", str(threads),
           "--envs", str(state["envs"][name]), "--lr", "1e-4", "--clip", "0.1", "--ent", "0.003",
           "--target-kl", "0.02", "--bc-coef", "0.3", "--bc-decay", "0.995", "--bc-min", "0.02",
           "--checkpoint-every", "100000", "--keep-every", "1000000", "--eval-every", "1000000000",
           "--handmade", "levels/phase1/*.txt", "levels/phase2/*.txt", "--handmade-prob", "0.05"]
    if state["calm"].get(name):  # second plateau: calm fine-tune
        cmd[cmd.index("--lr") + 1] = "3e-5"
        cmd[cmd.index("--ent") + 1] = "0.0"
    if name in FORK_HOURS_LIMIT:  # forks: calm, but keep the small entropy bonus
        cmd[cmd.index("--lr") + 1] = "3e-5"
        cmd[cmd.index("--time-limit-hours") + 1] = str(FORK_HOURS_LIMIT[name])
    if name == "B" and state.get("b_fresh"):
        cmd += ["--arch", "impala", "--separate-vf"]
    else:
        cmd += ["--resume", str(START_MODELS[name].relative_to(ROOT))]
    return cmd


def ensure_training(state: dict) -> None:
    for name, run in RUNS.items():
        if name in state["paused"] or (run / "STOP").exists():
            continue
        if running(f"jumpnrun.rl.train --run {run.relative_to(ROOT)} "):
            continue
        run.mkdir(parents=True, exist_ok=True)
        spawn(train_cmd(name, state), ROOT / f"runs/phase7{name.lower()}.log", state["alloc"][name])
        note(state, f"Training {name} gestartet/fortgesetzt auf Kernen {state['alloc'][name]}")


def stop_training(run: Path) -> None:
    pid = running(f"jumpnrun.rl.train --run {run.relative_to(ROOT)} ")
    if pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(60):
            if not running(f"jumpnrun.rl.train --run {run.relative_to(ROOT)} "):
                break
            time.sleep(1)


# ----------------------------------------------------------------------------- rules
def milestones(run: Path) -> dict:
    path = run / "milestones.json"
    return json.loads(path.read_text()) if path.exists() else {}


def hours(run: Path) -> float:
    path = run / "seconds_used"
    return float(path.read_text()) / 3600 if path.exists() else 0.0


def shares(result: dict):
    exam = result["pruefung"]["original"]
    series = result["test_serie"]
    return exam["won"] / exam["of"], sum(s["won"] for s in series.values()) / sum(s["of"] for s in series.values())


def recent_average(run: Path, n: int = 3):
    """Mean (exam share, test series share) of the best model kind over the last n milestones."""

    done = milestones(run)
    by_step = {}
    for key, result in done.items():
        step = int(key.split(":")[0])
        e, s = shares(result)
        if step not in by_step or e + s > sum(by_step[step]):
            by_step[step] = (e, s)
    steps = sorted(by_step)[-n:]
    if not steps:
        return None
    return tuple(sum(by_step[s][i] for s in steps) / len(steps) for i in (0, 1))


def best_checkpoint(run: Path):
    """The milestone checkpoint with the best 3-milestone window of the selection score (fixed rule)."""

    done = milestones(run)
    items = []
    for key, result in done.items():
        step, kind = key.split(":")
        e, s = shares(result)
        items.append((int(step), kind, e + s, result["checkpoint"]))
    if not items:
        return None
    steps = sorted({i[0] for i in items})
    best_of = {st: max((i for i in items if i[0] == st), key=lambda i: i[2]) for st in steps}
    window = lambda k: sum(best_of[s][2] for s in steps[max(0, k - 1):k + 2]) / len(steps[max(0, k - 1):k + 2])
    k = max(range(len(steps)), key=window)
    return run / "checkpoints" / best_of[steps[k]][3]


def final_evaluation(checkpoint: Path, label: str) -> dict:
    """128 fresh exam attempts (both versions), 32 per test series level. Written to runs/phase7/final_*.json."""

    out = STATE_DIR / f"final_{label}.json"
    if out.exists():
        return json.loads(out.read_text())
    import numpy as np
    import torch

    from jumpnrun.core.level import Level
    from jumpnrun.rl.evaluate import evaluate_levels
    from jumpnrun.rl.milestones import EXAMS, frozen_levels
    from jumpnrun.rl.modelinfo import load_model

    torch.set_num_threads(2)
    model = load_model(checkpoint)
    np.random.seed(424242)
    torch.manual_seed(424242)
    res = {"checkpoint": str(checkpoint.relative_to(ROOT))}
    for name, rel in EXAMS.items():
        r = evaluate_levels(model, [Level.from_file(ROOT / rel)] * 128, deterministic=False)
        res[f"pruefung_{name}"] = sum(x["won"] for x in r)
    series = {}
    for p in sorted((ROOT / "levels/test_serie").glob("*.txt")):
        r = evaluate_levels(model, [Level.from_file(p)] * 32, deterministic=False)
        series[p.stem] = sum(x["won"] for x in r)
    res["test_serie"] = series
    for v in ("v2", "v3", "v4"):
        lv = frozen_levels(v)
        res[f"validierung_{v}"] = sum(x["won"] for x in evaluate_levels(model, [l for _, l in lv]))
    out.write_text(json.dumps(res, indent=1))
    return res


def goal_met(res: dict) -> bool:
    return res["pruefung_original"] >= GOAL_EXAM * 128 and sum(res["test_serie"].values()) >= GOAL_SERIES * 192


def apply_rules(state: dict) -> None:
    from jumpnrun.rl.status import load as load_status
    from jumpnrun.rl.status import verdict

    # candidates -> final evaluation
    for name, run in RUNS.items():
        cand = run / "CANDIDATE"
        if cand.exists():
            ckpt = best_checkpoint(run)
            label = f"{name}_{ckpt.stem}"
            note(state, f"Lauf {name}: Stopp-Regel erfüllt, Endauswertung von {ckpt.name}")
            res = final_evaluation(ckpt, label)
            if goal_met(res):
                note(state, f"ZIEL ERREICHT mit Lauf {name}: {res['pruefung_original']}/128, "
                            f"Test-Serie {sum(res['test_serie'].values())}/192")
                state["success"] = label
                for other in RUNS.values():
                    (other / "STOP").write_text("phase 7 goal reached\n")
                    stop_training(other)
            else:
                note(state, f"Endauswertung {name} unter dem Ziel ({res['pruefung_original']}/128, "
                            f"{sum(res['test_serie'].values())}/192) – weiter trainieren")
            cand.unlink()

    # A/B comparison after 12 h and 24 h
    for mark in COMPARE_AT:
        if mark in state["compared"] or state["paused"]:
            continue
        if all(hours(run) >= mark for run in RUNS.values()):
            avg = {n: recent_average(r) for n, r in RUNS.items()}
            state["compared"].append(mark)
            if all(avg.values()):
                (ea, sa), (eb, sb) = avg["A"], avg["B"]
                loser = "B" if ea - eb >= 0.10 and sa - sb >= 0.10 else "A" if eb - ea >= 0.10 and sb - sa >= 0.10 else None
                note(state, f"Vergleich nach {mark} h: A Prüfung {ea:.0%} / Test-Serie {sa:.0%}, "
                            f"B {eb:.0%} / {sb:.0%}" + (f" -> {loser} pausiert" if loser else " -> beide laufen weiter"))
                if loser:
                    winner = "A" if loser == "B" else "B"
                    state["paused"].append(loser)
                    stop_training(RUNS[loser])
                    stop_training(RUNS[winner])
                    state["alloc"][winner] = [0, 1, 2, 3]
                    state["envs"][winner] = 12

    # plateau ladder
    for name, run in RUNS.items():
        if name in state["paused"] or (run / "STOP").exists():
            continue
        rows, curve, _ = load_status(run)
        n_milestones = len({r["steps"] for r in rows["raw"]})
        if n_milestones - state["last_intervention"][name] < 6:
            continue
        label, _ = verdict(rows, curve)
        if label != "Plateau":
            continue
        state["plateaus"][name] += 1
        state["last_intervention"][name] = n_milestones
        level = state["plateaus"][name]
        if level == 1:
            (STATE_DIR / f"NEEDS_PATTERNS_{name}").write_text("plateau: run the failure catalogue and extend the generator\n")
            note(state, f"Lauf {name}: Plateau (1.) -> Fehlerkatalog auswerten, fehlende Muster ergänzen")
        elif level == 2:
            note(state, f"Lauf {name}: Plateau (2.) -> ruhiger Feinschliff (lr 3e-5, kein Zufallsbonus)")
            state["calm"][name] = True
            stop_training(run)
        else:
            note(state, f"Lauf {name}: Plateau (3.) -> Lauf beendet")
            (run / "STOP").write_text("third plateau\n")
            stop_training(run)

    # everything finished -> final evaluation of the best model
    finished = all(name in state["paused"] or (run / "STOP").exists() for name, run in RUNS.items())
    if finished and not state.get("done"):
        best = None
        for name, run in RUNS.items():
            ckpt = best_checkpoint(run)
            if ckpt:
                avg = recent_average(run) or (0, 0)
                if best is None or sum(avg) > best[0]:
                    best = (sum(avg), name, ckpt)
        if best:
            res = final_evaluation(best[2], f"{best[1]}_{best[2].stem}")
            state["final"] = {"run": best[1], **res}
            note(state, f"Phase 7 beendet. Bestes Modell {best[1]} {best[2].name}: {res['pruefung_original']}/128, "
                        f"Test-Serie {sum(res['test_serie'].values())}/192")
        state["done"] = True


def tick() -> None:
    state = load_state()
    try:
        if state.get("done"):
            print("Phase 7 abgeschlossen.")
            return
        if not demos_done():
            subprocess.run(["bash", "scripts/demos_phase7.sh"], cwd=ROOT)
            return
        check_bc(state)
        if not state.get("b_fresh") and not bc_start_model(state):
            return
        if not (STATE_DIR / "smoke_ok").exists():
            print("Warte auf Probeläufe (runs/phase7/smoke_ok fehlt).")
            return
        ensure_training(state)
        apply_rules(state)
        ensure_training(state)
    finally:
        save_state(state)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "tick":
        tick()
    else:
        state = load_state()
        print(json.dumps({k: v for k, v in state.items() if k != "log"}, indent=1))
        print("\n".join(state["log"][-15:]))


if __name__ == "__main__":
    main()
