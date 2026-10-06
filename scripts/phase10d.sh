#!/usr/bin/env bash
# Phase 10, round D (P8 as teacher on own phase-8-level states): idempotent start + evaluator + wait (~9 min).
cd "$(dirname "$0")/.."
RUN=runs/phase10_d_lehrer
python3 - <<'PY'
import json
from pathlib import Path
from jumpnrun.rl import autopilot10 as A
run = "runs/phase10_d_lehrer"
target = 66_000_000 + 200_000 + 6_000_000
if A.last_step(run) < target and not A.train_running(run):
    Path(run).mkdir(parents=True, exist_ok=True)
    mix = [[0, {"skill": 0.1, "v10": 0.3, "p8": 0.6}]]
    cmd = A.train_cmd(run, {"stages": [[0, 2e-5]], "critic_warmup": 0, "ramp": 200_000}, target,
                      ["--mix-schedule", json.dumps(mix), "--demos2", "runs/demos10", "runs/demos9",
                       "--bc2-plan", json.dumps([[0, 0.03]]), "--bc2-a6-share", "0.05",
                       "--teacher", "models/phase8_final.zip", "--teacher-plan", json.dumps([[0, 1.0], [6_000_000, 0.1]])],
                      start="models/phase10_kandidat_alt.zip")
    A.spawn(cmd, Path(run + ".log"), [0, 1])
    print("Runde D: Training gestartet/fortgesetzt (Kerne [0, 1])")
try:
    A.update_drift(run)
except Exception as exc:
    print("drift:", exc)
PY
if ! pgrep -f "jumpnrun.rl.milestones10 --run $RUN" > /dev/null; then
    OMP_NUM_THREADS=1 nohup nice -n 10 taskset -c 2,3 python3 -m jumpnrun.rl.milestones10 --run $RUN \
        >> runs/phase10/milestones10d.log 2>&1 &
fi
sleep "${PHASE10_WAIT:-440}"
