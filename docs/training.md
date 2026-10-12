# Bot trainieren und auswerten

[← zurück zur README](../README.md)

Für das Training reicht die CPU-Version von PyTorch:
`pip install torch --index-url https://download.pytorch.org/whl/cpu`. Die Hintergründe zu jeder Phase stehen im
[Lerntagebuch](lernen/00_ueberblick.md).

## Die ersten Phasen

```
# Phase 1: laufen und springen lernen
python -m jumpnrun.rl.train --run runs/phase1 --max-tier 2 --steps 1500000 --handmade "levels/phase1/*.txt"

# live zuschauen (zweites Terminal, braucht einen Bildschirm)
python -m jumpnrun.rl.watch --run runs/phase1 --live --level levels/showcase/luecken.txt

# oder beides in einem: Training mit Live-Fenster
python -m jumpnrun.rl.train --run runs/phase1 --max-tier 2 --watch --watch-level levels/showcase/luecken.txt
```

## Vom Löser abschauen (Phase 5)

```
python -m jumpnrun.imitation.demos --out runs/demos          # Musterlösungen + geprüfter Level-Pool
python -m jumpnrun.imitation.bc --demos runs/demos --init models/phase3.zip --out models/phase5_bc.zip
scripts/train_phase5.sh main                                 # PPO mit Vorbild-Bremse
scripts/train_phase5.sh control                              # Vergleich ohne Vorbild
```

## Übersichtskarte und lange Level (Phase 6)

```
python -m jumpnrun.imitation.demos --out runs/demos3 --tiers 10 11 --counts 500 400 --merge-pool runs/demos/pool.json
python -m jumpnrun.imitation.bc --demos runs/demos3 --init models/phase5.zip --grow --only-overview \
    --dagger-rounds 0 --out models/phase6_start.zip
scripts/train_phase6.sh                                      # max. 16 h, danach oder bei bestandener Prüfung Schluss
```

## Ab Phase 7

Längere Läufe starten über idempotente Skripte `scripts/train_phaseN.sh` (mit `--target` und
`--time-limit-hours`). Sie sind auf die Kerne 0–2 gepinnt; Auswertungen laufen auf Kern 3. Die Abläufe der
einzelnen Phasen (Autopiloten, Vorregistrierungen, Messgruppen) stehen in den Kapiteln 07–13 des Tagebuchs. Die
Rohdaten liegen in `docs/lernen/daten/`.

## Auswerten

```
tensorboard --logdir runs                                     # Dashboard im Browser
python -m jumpnrun.rl.report runs/phase1 --png lernkurve.png  # Lernkurve als Bild
python -m jumpnrun.rl.evaluate --model models/phase1.zip --tiers 0 1 2
python -m jumpnrun.rl.milestones --run runs/phase6            # Validierung, Test-Serie, Prüfung, „wo enden die Versuche“
python -m jumpnrun.rl.status --run runs/<lauf>                # Statusbild + Einschätzung
python -m jumpnrun.rl.watch --run runs/phase1 --timelapse zeitraffer.mp4 --level levels/showcase/luecken.txt
```

## README-Medien neu erzeugen

```
python scripts/make_readme_media.py all     # Messung, Lernkurve, Videos, GIFs, Banner, Screenshots -> docs/medien/
```

## Tests

```
python -m pytest tests -q
```
