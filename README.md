# 2D_JumpNRun – Space Pirate + lernender Bot

## Spielbeschreibung
Das Spiel Space Pirate ist ein 2D-Spiel, in welchem ein Pirat gesteuert wird. Der Pirat muss sich durch ein Level kämpfen und dabei Gegner besiegen und Hindernisse überwinden. Gegner können durch einen Sprung auf den Kopf oder durch einen Revolverschuss besiegt werden. Das Ziel ist es, das Level zu beenden, indem die Kiste am Ende des Levels geöffnet wird. Sobald das Level beendet ist, wird die benötigte Zeit ausgegeben.

Neu seit 2026: Ein **Bot lernt das Spiel per Reinforcement Learning (PPO)** – und man kann ihm dabei zusehen
(Geister-Ansicht: viele Bots gleichzeitig im selben Level). Wie das funktioniert, erklärt das
**Lerntagebuch** in [`docs/lernen/`](docs/lernen/00_ueberblick.md).

## Installation
Python 3.9 oder neuer.

```
pip install -r requirements.txt
```

Für das Training reicht die CPU-Version von PyTorch (kleiner Download):
`pip install torch --index-url https://download.pytorch.org/whl/cpu`

## Selbst spielen

```
python game.py                                   # Prüfungslevel (das Original-Level)
python game.py levels/phase1/p1_luecken_01.txt   # beliebiges anderes Level
```

| Taste | Aktion |
|---|---|
| `A` / `D` oder Pfeiltasten | laufen |
| `W`, Leertaste oder Pfeil hoch | springen |
| Enter | schießen |
| `R` | Neustart |
| Esc | beenden |

## Level
Level sind Textdateien mit 13 Zeilen: `B` = Block, `E` = Gegner, `C` = Kiste (Ziel), `P` = Startpunkt (optional).
Mehrere Kisten sind erlaubt, jede ist ein Ziel.

| Ordner | Inhalt |
|---|---|
| `levels/exam/` | Prüfungslevel – der Bot trainiert **nie** darauf |
| `levels/phase1/`, `phase2/`, … | handgebaute Trainingslevel je Phase |
| `levels/showcase/` | feste Level für Videos / Geister-Ansicht |

Werkzeuge:

```
python -m jumpnrun.levelgen.solver mein_level.txt          # ist das Level für den Bot schaffbar?
python -m jumpnrun.levelgen.solver mein_level.txt --map    # wo kann man überall stehen?
python -m jumpnrun.levelgen.generator --tier 4 --seed 7 --out mein_level.txt   # Level erzeugen
```

## Bot trainieren und zuschauen

```
# Phase 1: laufen und springen lernen
python -m jumpnrun.rl.train --run runs/phase1 --max-tier 2 --steps 1500000 --handmade "levels/phase1/*.txt"

# live zuschauen (zweites Terminal, braucht einen Bildschirm)
python -m jumpnrun.rl.watch --run runs/phase1 --live --level levels/showcase/luecken.txt

# oder beides in einem: Training mit Live-Fenster
python -m jumpnrun.rl.train --run runs/phase1 --max-tier 2 --watch --watch-level levels/showcase/luecken.txt

# Auswertung
tensorboard --logdir runs                         # Dashboard im Browser
python -m jumpnrun.rl.report runs/phase1 --png lernkurve.png
python -m jumpnrun.rl.evaluate --model models/phase1.zip --tiers 0 1 2
python -m jumpnrun.rl.watch --run runs/phase1 --timelapse zeitraffer.mp4 --level levels/showcase/luecken.txt
```

## Projektaufbau

```
game.py              selbst spielen
jumpnrun/core/       deterministische Spielsimulation (ohne Grafik, ohne Uhr)
jumpnrun/render/     Grafik: Spiel, Geister-Ansicht, Video-Export
jumpnrun/levelgen/   Level-Generator und Löser
jumpnrun/rl/         Gymnasium-Umgebung, Netz, Curriculum, Training, Auswertung
levels/              Level-Dateien
models/              trainierte Bots
tests/               python -m pytest tests
docs/lernen/         Lerntagebuch
UML/                 UML-Diagramm des Originalspiels (2023)
```

## Lizenzen
Die verwendeten Bilder (Sprites) sind lizenzfrei und dürfen frei verwendet werden. Die Bilder können auf folgenden Seiten heruntergeladen werden:
- Player Sprites: [Craftpix](https://craftpix.net/freebies/free-2d-pirate-character-sprites/)
- Enemy Sprites: [Pipoya](https://pipoya.itch.io/pipoya-free-rpg-character-sprites-32x32)
- Block (Ground) Sprites: [PNG Wing](https://www.pngwing.com/en/free-png-zoola/download)
- Chest Sprites: [Admurin](https://admurin.itch.io/free-chest-animations)
