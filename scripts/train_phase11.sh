#!/usr/bin/env bash
# Phase 11: start/resume both arms idempotently (target and time limit from the preregistration).
cd "$(dirname "$0")/.."
python3 -m jumpnrun.rl.autopilot11
