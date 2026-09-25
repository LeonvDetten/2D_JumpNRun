#!/usr/bin/env bash
# Phase 5: PPO with fine control on generator-v2 levels. Safe to re-run after a restart.
#   scripts/train_phase5.sh main      # start from the imitation model, with the teacher's loss
#   scripts/train_phase5.sh control   # start from the phase-3 model, no teacher (comparison)
cd "$(dirname "$0")/.."
which="${1:-main}"
if [ "$which" = "main" ]; then
    run=runs/phase5; start=models/phase5_bc.zip; extra="--demos runs/demos"
else
    run=runs/phase5_control; start=models/phase3.zip; extra=""
fi
if pgrep -f "python3 -m jumpnrun.rl.train --run $run " > /dev/null; then
    echo "$run is already running"; exit 0
fi
nohup python3 -m jumpnrun.rl.train --run $run --resume $start --target 17050000 \
    --pool runs/demos --unlock-all --threads 4 \
    --lr 1e-4 --clip 0.1 --ent 0.003 --target-kl 0.02 \
    --checkpoint-every 100000 --eval-every 500000 --eval-per-tier 6 \
    --handmade "levels/phase1/*.txt" "levels/phase2/*.txt" --handmade-prob 0.1 \
    $extra >> ${run}.log 2>&1 &
echo "$run started (pid $!)"
