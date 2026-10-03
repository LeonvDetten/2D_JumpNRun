#!/usr/bin/env bash
# Phase 6 teacher demos for tiers 10-11; safe to re-run (keeps finished demos).
cd "$(dirname "$0")/.."
if pgrep -f "^python3 -m jumpnrun.imitation.demos --out runs/demos3" > /dev/null; then echo "demos running"; exit 0; fi
[ -f runs/demos3/pool.json ] && grep -q '"10"' runs/demos3/pool.json && { echo "demos done"; exit 0; }
nohup python3 -m jumpnrun.imitation.demos --out runs/demos3 --tiers 10 11 --counts 400 300 --resume \
    --merge-pool runs/demos/pool.json --procs 4 >> runs/demos3.log 2>&1 &
echo "demos started"
