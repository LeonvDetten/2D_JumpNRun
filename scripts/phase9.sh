#!/usr/bin/env bash
# Phase 9 control script (one observation round, ~9 min). Safe to run at any time:
#   autopilot step -> make sure the milestone evaluator runs for the current round -> wait -> autopilot step.
# The evaluator is a separate long-running process (an evaluation is never cut off by the round's end).
cd "$(dirname "$0")/.."
python3 -m jumpnrun.rl.autopilot9 tick
RUNS=$(python3 -m jumpnrun.rl.autopilot9 runs)
if [ -n "$RUNS" ] && [ ! -f runs/phase9/DONE ]; then
    PID=$(pgrep -f "jumpnrun.rl.milestones9 --run" | head -1)
    if [ -n "$PID" ] && [ "$(cat runs/phase9/eval_runs 2>/dev/null)" != "$RUNS" ]; then
        kill "$PID"; sleep 2; PID=""
    fi
    if [ -z "$PID" ]; then
        ARGS=""
        for r in $RUNS; do ARGS="$ARGS --run $r"; done
        echo "$RUNS" > runs/phase9/eval_runs
        OMP_NUM_THREADS=1 nohup nice -n 5 python3 -m jumpnrun.rl.milestones9 $ARGS --seconds 1000000 \
            >> runs/phase9/milestones9.log 2>&1 &
    fi
    sleep "${PHASE9_WAIT:-520}"
    python3 -m jumpnrun.rl.autopilot9 tick
fi
