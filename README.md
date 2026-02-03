# 2D_JumpNRun
  
## Spielbeschreibung:  
Das Spiel Space Pirate ist ein 2D-Spiel, in welchem ein Pirat gesteuert wird. Der Pirat muss sich durch ein Level kämpfen und dabei Gegner besiegen und Hindernisse überwinden. Gegner können durch einen Sprung auf den Kopf oder durch einen Revolverschuss besiegt werden. Das Spiel ist in Python geschrieben und verwendet die Pygame-Bibliothek. Das Ziel ist es, das Level zu beenden, indem die Kiste am Ende des Levels geöffnet wird. Sobald das Level beendet ist, wird die benötigte Zeit ausgegeben.  
  
Bitte beachten Sie, dass es sich bei diesem Spiel um einen Prototyp handelt, welcher noch kein Game Over Screen oder Menü enthält. Des Weiteren existiert lediglich ein Level. Dieses kann jedoch beliebig bearbeitet werden. Das Level wird verändert, indem die `level.txt` Datei bearbeitet wird. Hierbei müssen ASCII Zeichen verwendet werden, um die verschiedenen Objekte zu platzieren:  
- `E` = Enemy (Gegner)  
- `B` = Block  
- `C` = Chest (Kiste)  
  
Es können mehrere Kisten in der Welt platziert werden. In diesem Fall dient jede Kiste als Endpunkt und das Spiel wird nach Öffnen dieser Kiste beendet.  
  
## Anforderungen:  
Siehe `requirement.txt` Datei.  
  
## Installation:  
Um die Applikation ausführen zu können, müssen die benötigten Bibliotheken heruntergeladen werden. Für dieses Spiel werden die Pygame und Loguru Bibliotheken benötigt. Diese können mit folgenden Befehlen heruntergeladen werden:  
- `pip install loguru==0.7.0`  
- `pip install pygame==2.1.0`  
  
Außerdem wird Python3 benötigt. Diese Applikation wurde mit Python 3.9.13 entwickelt. Die Version kann auf der offiziellen Python-Seite heruntergeladen werden: [Python Downloads](https://www.python.org/downloads/windows/)  
  
## Ausführen des Spiels:  
Um das Spiel zu starten, muss die Datei `game.py` ausgeführt werden. Sobald das Spiel gestartet wird, öffnet sich ein neues Fenster und das Spiel beginnt. Das Spiel kann lediglich durch das Schließen des Fensters beendet werden. Sollte der Spieler durch einen Gegner eliminiert werden, beendet sich die Applikation automatisch.  
  
## Steuerung:  
Der Piratenspieler kann mit den Tasten `W`, `A`, `D`, Leertaste und Enter gesteuert werden.  
- Die `W`-Taste und Leertaste führen einen Sprung aus.  
- Mit der `A`-Taste wird der Spieler nach links bewegt.  
- Mit der `D`-Taste wird der Spieler nach rechts bewegt.  
- Mit Enter führt der Spieler einen Revolverschuss aus.  

## RL Agent (PPO)  
Das Projekt enthält zusätzlich eine RL-Pipeline mit Gymnasium + Stable-Baselines3 (PPO), die auf den echten Spielzuständen trainiert.  

### Projektstruktur (RL)
- `rl/` enthält die RL-Kernmodule (`game_session`, `pirate_game_env`, `training_metrics`, `game_types`).
- Root-Dateien (`pirate_game_env.py`, `game_session.py`, ...) sind nur noch Kompatibilitäts-Wrapper.
- `train_ppo.py` und `export_metrics.py` bleiben als einfache CLI-Entrypoints im Projektroot.

### RL-Setup  
1. Virtuelle Umgebung aktivieren  
2. RL-Abhängigkeiten installieren:
   - `pip install -r requirements-rl.txt`

### Training starten  
- `python3 train_ppo.py --timesteps 500000 --run-name ppo_level1`
- Optional mit geringerem Log-Noise:
  - `python3 train_ppo.py --timesteps 500000 --run-name ppo_level1 --game-log-level WARNING`
- Optional mit Progressbar:
  - `python3 train_ppo.py --timesteps 500000 --run-name ppo_level1 --progress-bar`
- Action-Set für schnelleres Lernen:
  - `python3 train_ppo.py --timesteps 500000 --run-name ppo_level1 --action-preset simple`
  - Für volle Aktionstiefe später: `--action-preset full`
- Curriculum (empfohlen):
  - `python3 train_ppo.py --timesteps 500000 --run-name ppo_curriculum --curriculum --easy-level-path level_easy.txt --curriculum-easy-steps 120000 --action-preset simple`

### Fine-Tuning / Resume
- Bestehendes Modell weitertrainieren:
  - `python3 train_ppo.py --timesteps 200000 --run-name ppo_finetune --load-model runs/ppo_curriculum/models/final_model.zip --action-preset simple`

Das Training schreibt Artefakte nach `runs/<run-name>/`:
- `tb/` (TensorBoard-Logs)
- `metrics/episodes.csv` (Episode-Metriken)
- `eval/` (Evaluation-Logs)
- `checkpoints/` (Best/Checkpoint-Modelle)
- `models/` (Finales Modell)
- `plots/` (exportierte PNG-Visualisierungen)

Bei Curriculum-Läufen werden die Artefakte zusätzlich in:
- `curriculum_easy/`
- `curriculum_full/`
gespeichert.

### Live-Metriken mit TensorBoard  
- `tensorboard --logdir runs`

### PNG-Metriken exportieren  
- `python3 export_metrics.py --run-dir runs/ppo_level1 --window 50`

Hinweis: Python `3.9.6` ist für diese RL-Skripte kompatibel.

Dabei werden folgende Diagramme erzeugt:
- `reward_curve.png`
- `episode_length.png`
- `success_rate.png`
- `progress_x.png`
  
## Lizenzen:  
Die verwendeten Bilder (Sprites) sind lizenzfrei und dürfen frei verwendet werden. Die Bilder können auf folgenden Seiten heruntergeladen werden:  
- Player Sprites: [Craftpix](https://craftpix.net/freebies/free-2d-pirate-character-sprites/)  
- Enemy Sprites: [Pipoya](https://pipoya.itch.io/pipoya-free-rpg-character-sprites-32x32)  
- Block (Ground) Sprites: [PNG Wing](https://www.pngwing.com/en/free-png-zoola/download)  
- Chest Sprites: [Admurin](https://admurin.itch.io/free-chest-animations)  
