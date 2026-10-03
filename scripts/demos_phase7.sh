#!/usr/bin/env bash
# Phase 7 teacher demos for tiers 10-12 with the final generator (v4); safe to re-run (keeps finished demos).
cd "$(dirname "$0")/.."
if pgrep -f "^python3 -m jumpnrun.imitation.demos --out runs/demos4" > /dev/null; then echo "demos running"; exit 0; fi
[ -f runs/demos4/pool.json ] && grep -q '"12"' runs/demos4/pool.json && { echo "demos done"; exit 0; }
nohup python3 -m jumpnrun.imitation.demos --out runs/demos4 --tiers 10 11 12 --counts 600 500 700 --resume \
    --merge-pool runs/demos/pool.json --procs 4 >> runs/demos4.log 2>&1 &
echo "demos started"
