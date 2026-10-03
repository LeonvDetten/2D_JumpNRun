"""Phase 8 autopilot: rounds of "new" arm vs control arm with a judging rule fixed in advance.

    python3 -m jumpnrun.rl.autopilot8 tick      # one idempotent step (called by scripts/phase8.sh)
    python3 -m jumpnrun.rl.autopilot8 status

State in runs/phase8/state.json. Per round both arms start from the same checkpoint, get 2 cores each, and
differ in exactly the flags of that round:
    round 1  data:    --pool-share 0.4 --augment 0.7          (control: stored pool only, no augmentation)
    round 2  signal:  + --obs-v2 --stuck-death                (control: winner of round 1 continued)
    round 3  PLR:     + --plr                                 (control: winner of round 2 continued)
Judging (after JUDGE_STEPS steps of both arms): mean dev score over the last 3 EMA milestones. "new" wins
with >= +3 percentage points; otherwise the control wins unless its protection validation (schutz) is
>= 5 levels worse. A real regression (3 EMA milestones in a row >= 8 points below the round's start) stops
an arm early. The loser is paused, checkpoints stay. After round 3 (or the 48 h budget) the final model is
picked by a fixed rule and evaluated once on the sealed group (jumpnrun/rl/final8.py).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = ROOT / "runs/phase8"
STATE = STATE_DIR / "state.json"
JUDGE_STEPS = 6_000_000
WIN_MARGIN = 0.03
SCHUTZ_MARGIN = 5
REGRESSION = 0.08
BUDGET_HOURS = 48.0
START = "runs/phase7c/checkpoints/ema_step_0035000008.zip"  # step 1 probe: best dev mean (0.681)
ROUND_FLAGS = {1: ["--pool-share", "0.4", "--augment", "0.7"], 2: ["--obs-v2", "--stuck-death"], 3: ["--plr", "0.3"]}
ROUND_READY = {1: None, 2: STATE_DIR / "r2_ready", 3: STATE_DIR / "r3_ready"}
CORES = {"neu": [0, 1], "kontrolle": [2, 3]}


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"round": 1, "start": START, "base_flags": [], "rounds": {}, "log": [], "started": time.time()}


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


def run_dir(rnd: int, arm: str) -> Path:
    return ROOT / f"runs/phase8_r{rnd}_{arm}"


def train_cmd(state: dict, rnd: int, arm: str) -> list:
    info = state["rounds"][str(rnd)]
    flags = list(info["flags"][arm])
    return [sys.executable, "-m", "jumpnrun.rl.train", "--run", str(run_dir(rnd, arm).relative_to(ROOT)),
            "--target", "400000000", "--overview", "--pool", "runs/demos4", "--demos", "runs/demos4",
            "--start-prob", "0.2", "--start-dirs", "runs/demos4", "--rewind-prob", "0.4",
            "--ema-every", "1000000", "--ema2-decay", "0.998", "--time-limit-hours", "16", "--unlock-all",
            "--threads", "2", "--envs", "8", "--lr", "1e-4", "--lr-decay-steps", "8000000", "--clip", "0.1",
            "--ent", "0.003", "--target-kl", "0.02", "--bc-coef", "0.3", "--bc-decay", "0.995", "--bc-min", "0.02",
            "--checkpoint-every", "100000", "--keep-every", "1000000", "--eval-every", "1000000000",
            "--handmade", "levels/phase1/*.txt", "levels/phase2/*.txt", "--handmade-prob", "0.05",
            "--resume", info["start"], *flags]


def spawn(cmd: list, log: Path, cores) -> None:
    cmd = ["taskset", "-c", ",".join(map(str, cores))] + cmd
    env = dict(os.environ, OMP_NUM_THREADS=str(len(cores)))
    with open(log, "a") as f:
        subprocess.Popen(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env=env, start_new_session=True)


def stop(run: Path) -> None:
    pid = running(f"jumpnrun.rl.train --run {run.relative_to(ROOT)} ")
    if pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(60):
            if not running(f"jumpnrun.rl.train --run {run.relative_to(ROOT)} "):
                break
            time.sleep(1)


def milestones(run: Path) -> dict:
    path = run / "milestones8.json"
    return json.loads(path.read_text()) if path.exists() else {}


def ema_series(run: Path, kind: str = "ema"):
    """[(steps, dev_mean, schutz_won|None)] sorted by steps."""

    out = []
    for key, r in milestones(run).items():
        steps, k = key.split(":")
        if k == kind:
            out.append((int(steps), r["dev_mean"][0], r.get("schutz", {}).get("won")))
    return sorted(out)


def start_round(state: dict, rnd: int) -> None:
    info = state["rounds"].setdefault(str(rnd), {})
    base = state["base_flags"]
    info.update(start=state["start"], flags={"neu": base + ROUND_FLAGS[rnd], "kontrolle": list(base)},
                started=time.time(), stopped=[], start_steps=int(Path(state["start"]).stem.split("_")[-1]))
    if "baseline" not in info:
        from jumpnrun.rl.milestones8 import evaluate_checkpoint

        info["baseline"] = evaluate_checkpoint(ROOT / state["start"], full=False)["dev_mean"][0]
    note(state, f"Runde {rnd} startet von {state['start']} (Dev-Mittel Start {info['baseline']:.1%}); "
                f"neu: {' '.join(info['flags']['neu']) or '-'}")


def ensure_training(state: dict, rnd: int) -> None:
    info = state["rounds"][str(rnd)]
    for arm in ("neu", "kontrolle"):
        run = run_dir(rnd, arm)
        if arm in info["stopped"] or (run / "STOP").exists():
            continue
        if running(f"jumpnrun.rl.train --run {run.relative_to(ROOT)} "):
            continue
        run.mkdir(parents=True, exist_ok=True)
        spawn(train_cmd(state, rnd, arm), ROOT / f"runs/phase8_r{rnd}_{arm}.log", CORES[arm])
        note(state, f"Runde {rnd}, Arm {arm}: Training gestartet/fortgesetzt auf Kernen {CORES[arm]}")


def judge(state: dict, rnd: int):
    """'neu' / 'kontrolle' when the round can be judged, else None. Also applies the regression stop."""

    info = state["rounds"][str(rnd)]
    end = info["start_steps"] + JUDGE_STEPS - 50_000  # EMA copies land at whole millions (+ a few steps)
    series = {arm: ema_series(run_dir(rnd, arm)) for arm in ("neu", "kontrolle")}
    for arm, s in series.items():
        if arm in info["stopped"]:
            continue
        last = [d for _, d, _ in s[-3:]]
        if len(last) == 3 and all(d <= info["baseline"] - REGRESSION for d in last):
            info["stopped"].append(arm)
            (run_dir(rnd, arm) / "STOP").write_text("regression\n")
            stop(run_dir(rnd, arm))
            note(state, f"Runde {rnd}, Arm {arm}: Rückschritt (3 Meilensteine ≥ 8 Pp unter dem Start) -> gestoppt")
    alive = [a for a in ("neu", "kontrolle") if a not in info["stopped"]]
    if not alive:
        return "kontrolle"
    if any(not series[a] or series[a][-1][0] < end for a in alive):
        return None
    if len(alive) == 1:
        return alive[0]
    mean = {a: sum(d for _, d, _ in series[a][-3:]) / 3 for a in alive}
    schutz = {a: series[a][-1][2] or 0 for a in alive}
    diff = mean["neu"] - mean["kontrolle"]
    winner = "neu" if diff >= WIN_MARGIN or schutz["kontrolle"] <= schutz["neu"] - SCHUTZ_MARGIN else "kontrolle"
    info["judged"] = dict(mean=mean, schutz=schutz, winner=winner)
    note(state, f"Runde {rnd} entschieden: neu {mean['neu']:.1%} vs Kontrolle {mean['kontrolle']:.1%} "
                f"(Schutz {schutz['neu']} vs {schutz['kontrolle']}) -> {winner}")
    return winner


def latest_ema(run: Path) -> str:
    s = ema_series(run)
    steps = s[-1][0]
    ckpt = run / "checkpoints" / f"ema_step_{steps:010d}.zip"
    return str(ckpt.relative_to(ROOT))


def all_windows(state: dict):
    """(mean of 3 consecutive EMA/EMA2 milestones, run, kind, last steps) over every arm of every round."""

    out = []
    for rnd in state["rounds"]:
        for arm in ("neu", "kontrolle"):
            run = run_dir(int(rnd), arm)
            for kind in ("ema", "ema2"):
                s = ema_series(run, kind)
                for i in range(len(s) - 2):
                    out.append((sum(d for _, d, _ in s[i:i + 3]) / 3, str(run.relative_to(ROOT)), kind, s[i + 2][0]))
    return sorted(out, reverse=True)


def finish(state: dict) -> None:
    best = all_windows(state)[0]
    _, run, kind, steps = best
    ckpt = f"{run}/checkpoints/{kind}_step_{steps:010d}.zip"
    state["final_choice"] = dict(checkpoint=ckpt, window_mean=best[0])
    note(state, f"Endmodell nach fester Regel: {ckpt} (Dev-Fenster {best[0]:.1%}) -> Endauswertung")
    save_state(state)
    subprocess.run([sys.executable, "-m", "jumpnrun.rl.final8", "--checkpoint", ckpt], cwd=ROOT)
    state["done"] = True
    (STATE_DIR / "DONE").write_text(f"phase 8 finished: {ckpt}\n")


def tick() -> None:
    state = load_state()
    try:
        if state.get("done"):
            print("Phase 8 abgeschlossen.")
            return
        rnd = state["round"]
        if str(rnd) not in state["rounds"]:
            ready = ROUND_READY[rnd]
            if ready is not None and not ready.exists():
                print(f"Runde {rnd} wartet auf ihre Vorbereitung ({ready.name} fehlt).")
                return
            start_round(state, rnd)
        info = state["rounds"][str(rnd)]
        winner = info.get("judged", {}).get("winner") or judge(state, rnd)
        hours = (time.time() - state["started"]) / 3600
        if winner is None:
            if hours >= BUDGET_HOURS:
                note(state, "48-h-Budget erreicht -> Ende")
                for arm in ("neu", "kontrolle"):
                    stop(run_dir(rnd, arm))
                finish(state)
                return
            ensure_training(state, rnd)
            return
        for arm in ("neu", "kontrolle"):
            stop(run_dir(rnd, arm))
        state["base_flags"] = info["flags"][winner]
        state["start"] = latest_ema(run_dir(rnd, winner))
        if rnd >= 3 or hours >= BUDGET_HOURS - 8:
            finish(state)
            return
        state["round"] = rnd + 1
        note(state, f"Weiter mit Runde {rnd + 1} ab {state['start']}")
    finally:
        save_state(state)


def current_runs() -> list:
    state = load_state()
    info = state["rounds"].get(str(state["round"]))
    if not info or state.get("done"):
        return []
    return [str(run_dir(state["round"], a).relative_to(ROOT)) for a in ("neu", "kontrolle")]


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
