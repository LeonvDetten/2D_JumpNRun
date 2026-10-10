#!/usr/bin/env bash
# Phase 13: one observation round (~9.5 min) - autopilot tick (training on cores 0-2, evaluator on core 3,
# protection rules, scorecard picture), then wait.
cd "$(dirname "$0")/.."
python3 -m jumpnrun.rl.autopilot13 2>&1 | tail -4
sleep "${PHASE13_WAIT:-540}"
python3 -m jumpnrun.rl.autopilot13 2>&1 | tail -3
