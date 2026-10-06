#!/usr/bin/env bash
# Neustart: copy the measurement data (milestones, drift, state, status image) to docs/lernen/daten/neustart/ and
# commit it together with any new restart pack in backup_neustart/; then push the Neustart branch.
cd "$(dirname "$0")/.."
OUT=docs/lernen/daten/neustart
mkdir -p "$OUT"
for r in runs/neustart_*/; do
    a=$(basename "$r")
    for f in milestones10.json drift.json config.json curriculum.json; do
        [ -f "$r$f" ] && cp "$r$f" "$OUT/${a}_$f"
    done
done
[ -f runs/neustart/state.json ] && cp runs/neustart/state.json "$OUT/state.json"
[ -f runs/neustart/status.png ] && cp runs/neustart/status.png "$OUT/status.png"
for f in runs/phase10/baseline_neustart_*.json; do [ -f "$f" ] && cp "$f" "$OUT/"; done
for f in runs/neustart/bc*.bc.json runs/neustart/bc*.log; do [ -f "$f" ] && cp "$f" "$OUT/"; done
git add "$OUT" backup_neustart 2>/dev/null
if ! git diff --cached --quiet; then
    git commit -q -m "Neustart: data snapshot $(date -u +%Y-%m-%dT%H:%MZ)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Q4GKk2mkcWWtE43kCjRk8y"
fi
for i in 1 2 3 4; do git push -q -u origin claude/jumpnrun-neustart && break; sleep $((2 ** i)); done
