#!/usr/bin/env bash
# Phase 13 verdict: paired scorecards (fresh seeds 1, 2) at T = 1 and T = 0.3 for every candidate and stand 0,
# plus the left extras (mirrored jump probes, spiegelweg, the three fork dev levels) - after the training (4 cores).
cd "$(dirname "$0")/.."
K=runs/phase13/kandidaten
MODELS="stand0=models/phase12_kandidat.zip p13_46=$K/p13_46_ema.zip p13_49=$K/p13_49_ema.zip p13_53=$K/p13_53_ema.zip p13_54=$K/p13_54_ema.zip p13_end=$K/p13_end_ema.zip"
for seed in 1 2; do for T in 0.3 1.0; do for spec in $MODELS; do
  tag=${spec%%=*}; path=${spec#*=}; out=urteil13_${tag}_T${T}_s${seed}
  [ -f "$path" ] || continue
  [ -f runs/phase12/score_${out}.json ] && continue
  OMP_NUM_THREADS=1 python3 -m jumpnrun.rl.scorecard12 eval "$path" --tag $out --seed $seed --procs 4 --temperature $T
done; done; done
OMP_NUM_THREADS=1 python3 scripts/urteil13_extras.py $MODELS
echo FERTIG
