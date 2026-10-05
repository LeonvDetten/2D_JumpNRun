#!/usr/bin/env bash
# Phase 10 observation round (~9 min). Safe to run at any time:
#   autopilot step -> make sure the milestone evaluator follows the current runs -> wait -> autopilot step.
cd "$(dirname "$0")/.."
python3 -m jumpnrun.rl.autopilot10 tick
RUNS=$(python3 -m jumpnrun.rl.autopilot10 runs)
if [ -n "$RUNS" ] && [ ! -f runs/phase10/DONE ]; then
    PID=$(pgrep -f "jumpnrun.rl.milestones10 --run" | head -1)
    if [ -n "$PID" ] && [ "$(cat runs/phase10/eval_runs 2>/dev/null)" != "$RUNS" ]; then
        kill "$PID"; sleep 2; PID=""
    fi
    if [ -z "$PID" ]; then
        ARGS=""
        for r in $RUNS; do ARGS="$ARGS --run $r"; done
        echo "$RUNS" > runs/phase10/eval_runs
        OMP_NUM_THREADS=1 nohup nice -n 5 taskset -c 3 python3 -m jumpnrun.rl.milestones10 $ARGS \
            >> runs/phase10/milestones10.log 2>&1 &
    fi
fi
sleep "${PHASE10_WAIT:-520}"
python3 -m jumpnrun.rl.autopilot10 tick
