#!/usr/bin/env bash
# Phase 8 control script (one observation round, ~9 min). Safe to run at any time:
#   autopilot step -> make sure the milestone evaluator runs for the current round -> wait -> autopilot step.
# The evaluator is a separate long-running process (an evaluation is never cut off by the round's end).
cd "$(dirname "$0")/.."
python3 -m jumpnrun.rl.autopilot8 tick
RUNS=$(python3 -m jumpnrun.rl.autopilot8 runs)
if [ -n "$RUNS" ] && [ ! -f runs/phase8/DONE ]; then
    PID=$(pgrep -f "jumpnrun.rl.milestones8 --run" | head -1)
    if [ -n "$PID" ] && [ "$(cat runs/phase8/eval_runs 2>/dev/null)" != "$RUNS" ]; then
        kill "$PID"; sleep 2; PID=""
    fi
    if [ -z "$PID" ]; then
        ARGS=""
        for r in $RUNS; do ARGS="$ARGS --run $r"; done
        echo "$RUNS" > runs/phase8/eval_runs
        OMP_NUM_THREADS=1 nohup nice -n 5 python3 -m jumpnrun.rl.milestones8 $ARGS --seconds 1000000 \
            >> runs/phase8/milestones8.log 2>&1 &
    fi
    sleep "${PHASE8_WAIT:-520}"
    python3 -m jumpnrun.rl.autopilot8 tick
fi
