#!/usr/bin/env bash
# Phase 6: overview map, generator v3 (tiers 10-11), random start points, teacher loss.
# Safe to re-run at any time (after a container restart it continues from the newest checkpoint).
# Stops for good when runs/phase6/STOP exists (exam passed twice) or 16 h of training are used up.
cd "$(dirname "$0")/.."
run=runs/phase6
limit_hours=${LIMIT_HOURS:-16}
mkdir -p $run
if [ -f $run/STOP ]; then echo "$run finished: $(cat $run/STOP)"; exit 0; fi
if pgrep -f "^python3 -m jumpnrun.rl.train --run $run " > /dev/null; then
    echo "$run is already running"; exit 0
fi
nohup taskset -c 0-2 python3 -m jumpnrun.rl.train --run $run --resume models/phase6_start.zip --target 80000000 \
    --overview --pool runs/demos3 --demos runs/demos3 --start-prob 0.3 --start-dirs runs/demos3 \
    --time-limit-hours $limit_hours --unlock-all --threads 3 --lr 1e-4 --clip 0.1 --ent 0.003 --target-kl 0.02 \
    --bc-coef 0.3 --bc-decay 0.995 --bc-min 0.02 \
    --checkpoint-every 100000 --keep-every 1000000 --eval-every 1000000000 \
    --handmade "levels/phase1/*.txt" "levels/phase2/*.txt" --handmade-prob 0.05 \
    >> ${run}.log 2>&1 &
echo "$run started (pid $!)"
