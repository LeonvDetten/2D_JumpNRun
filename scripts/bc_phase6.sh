#!/usr/bin/env bash
# Phase 6 start model: phase-5 network + overview branch, imitation trains only the new branch. Re-runnable.
cd "$(dirname "$0")/.."
[ -f models/phase6_start.zip ] && { echo "start model exists"; exit 0; }
if pgrep -f "^python3 -m jumpnrun.imitation.bc --demos runs/demos3" > /dev/null; then echo "bc running"; exit 0; fi
nohup python3 -m jumpnrun.imitation.bc --demos runs/demos3 --init models/phase5.zip --grow --only-overview \
    --dagger-rounds 0 --epochs 3 --lr 1e-3 --max-samples 700000 --value-steps 300000 --threads 4 \
    --out models/phase6_start.zip >> runs/bc6.log 2>&1 &
echo "bc started"
