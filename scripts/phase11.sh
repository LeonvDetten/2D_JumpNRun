#!/usr/bin/env bash
# Phase 11: one observation round (~9.5 min): idempotent autopilot tick (start/resume arms, brakes, verdict),
# evaluator (milestones11, nice, unpinned), then wait.
cd "$(dirname "$0")/.."
python3 -m jumpnrun.rl.autopilot11 2>&1 | tail -5
if ! pgrep -f "jumpnrun.rl.milestones11 --run" > /dev/null; then
    OMP_NUM_THREADS=1 nohup nice -n 10 python3 -m jumpnrun.rl.milestones11 --run runs/phase11_a --run runs/phase11_b \
        >> runs/phase11/milestones11.log 2>&1 &
fi
sleep "${PHASE11_WAIT:-540}"
python3 -m jumpnrun.rl.autopilot11 2>&1 | tail -3
