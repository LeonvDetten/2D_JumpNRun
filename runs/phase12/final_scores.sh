#!/usr/bin/env bash
# Phase 12 final: paired scorecards (seeds 1, 2) for the candidates and the reference models.
cd "$(dirname "$0")/../.."
for seed in 1 2; do
  for spec in p12_52e2=runs/phase12/kandidaten/p12_52_ema2.zip p12_40=runs/phase12/kandidaten/p12_40_ema.zip \
              p12_44e2=runs/phase12/kandidaten/p12_44_ema2.zip p12_54=runs/phase12/kandidaten/p12_54_ema.zip \
              p8=models/phase8_final.zip phase11=models/phase11_kandidat.zip neustart=models/neustart_kandidat_pruefung.zip; do
    tag=${spec%%=*}; path=${spec#*=}
    [ -f runs/phase12/score_final_${tag}_s${seed}.json ] && continue
    OMP_NUM_THREADS=1 python3 -m jumpnrun.rl.scorecard12 eval "$path" --tag final_${tag}_s${seed} --seed $seed --procs 4
  done
done
echo FERTIG
