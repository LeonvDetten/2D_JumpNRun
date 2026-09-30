#!/usr/bin/env bash
# Phase 7 control script: one autopilot step, then a milestone round (~9 min). Safe to run at any time.
cd "$(dirname "$0")/.."
python3 -m jumpnrun.rl.autopilot tick
if [ -f runs/phase7/smoke_ok ] && [ ! -f runs/phase7/DONE ]; then
    OMP_NUM_THREADS=1 nice -n 5 timeout 560 python3 -m jumpnrun.rl.milestones --run runs/phase7a --run runs/phase7b \
        --seconds 520 --exam-attempts 64 --validations v2 v3 v4 --exam2 \
        --stop-exam 0.5625 --stop-series 0.75 --stop-file CANDIDATE 2>&1 | grep -v Warn
    python3 -m jumpnrun.rl.autopilot tick
else
    sleep 5
fi
