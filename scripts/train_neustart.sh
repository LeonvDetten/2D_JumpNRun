#!/usr/bin/env bash
# Neustart: idempotent start of the current stage (BC, start check or PPO with --target and --time-limit-hours,
# all four cores). Running it again only restarts what stopped.
cd "$(dirname "$0")/.."
bash scripts/setup_neustart.sh > /dev/null 2>&1 || bash scripts/setup_neustart.sh
.venv/bin/python -m jumpnrun.rl.autopilot_neustart tick
