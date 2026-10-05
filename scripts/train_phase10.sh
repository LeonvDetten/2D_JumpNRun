#!/usr/bin/env bash
# Phase 10: idempotent start of the current round's training (the autopilot spawns both arms with --target and
# --time-limit-hours, pinned to cores [0,1] and [2,3]). Running it again only restarts arms that stopped.
cd "$(dirname "$0")/.."
python3 -m jumpnrun.rl.autopilot10 tick
