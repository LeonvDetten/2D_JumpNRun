#!/usr/bin/env bash
# Start or continue phase 3. Safe to run any time (e.g. after a container restart):
# does nothing if training is already running, otherwise resumes from the newest checkpoint.
cd "$(dirname "$0")/.."
if pgrep -f "^python3 -m jumpnrun.rl.train --run runs/phase3" > /dev/null; then
    echo "phase 3 training is already running"
    exit 0
fi
nohup python3 -m jumpnrun.rl.train --run runs/phase3 --resume models/phase2.zip --target 14000000 \
    --max-tier 9 --threads 4 --eval-per-tier 6 --eval-every 250000 \
    --handmade "levels/phase1/*.txt" "levels/phase2/*.txt" --handmade-prob 0.15 \
    >> runs_phase3.log 2>&1 &
echo "phase 3 training started (pid $!)"
