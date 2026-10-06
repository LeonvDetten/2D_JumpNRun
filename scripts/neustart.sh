#!/usr/bin/env bash
# Neustart observation round (~9 min). Safe to run at any time:
#   autopilot step -> make sure the milestone evaluator follows the Neustart runs -> wait -> autopilot step.
# Only ever touches Neustart processes (never phase10.sh: its pgrep would also catch this evaluator).
cd "$(dirname "$0")/.."
PY=.venv/bin/python
bash scripts/setup_neustart.sh > /dev/null 2>&1 || bash scripts/setup_neustart.sh
$PY -m jumpnrun.rl.autopilot_neustart tick
RUNS=$($PY -m jumpnrun.rl.autopilot_neustart runs)
if [ -n "$RUNS" ]; then
    PID=$(pgrep -f "jumpnrun.rl.milestones10 --run runs/neustart_" | head -1)
    if [ -n "$PID" ] && [ "$(cat runs/neustart/eval_runs 2>/dev/null)" != "$RUNS" ]; then
        kill "$PID"; sleep 2; PID=""
    fi
    if [ -z "$PID" ]; then
        ARGS=""
        for r in $RUNS; do ARGS="$ARGS --run $r"; done
        echo "$RUNS" > runs/neustart/eval_runs
        OMP_NUM_THREADS=1 nohup nice -n 10 $PY -m jumpnrun.rl.milestones10 $ARGS >> runs/neustart/milestones10.log 2>&1 &
    fi
fi
sleep "${PHASE_WAIT:-470}"
$PY -m jumpnrun.rl.autopilot_neustart tick
