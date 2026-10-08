#!/usr/bin/env bash
# Phase 12: one observation round (~9.5 min) - autopilot tick (BC start, training on cores 0-2, evaluator on core 3,
# decision points, scorecard picture), then wait.
cd "$(dirname "$0")/.."
python3 -m jumpnrun.rl.autopilot12 2>&1 | tail -4
sleep "${PHASE12_WAIT:-540}"
python3 -m jumpnrun.rl.autopilot12 2>&1 | tail -3
