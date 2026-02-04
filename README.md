# Space Pirate 2D Jump'n'Run + PPO Agent

This repository contains a custom 2D platformer written with Pygame and an integrated PPO training pipeline (Gymnasium + Stable-Baselines3).

The current codebase is focused on **one RL approach (PPO)**. Legacy DQN code and old generated artifacts were removed to keep the project easier to understand and maintain.

## Core Idea

- `game.py` runs the manual game loop (keyboard control).
- `rl/game_session.py` wraps the existing game objects into a `reset/step/observation` API.
- `rl/pirate_game_env.py` exposes the game as a Gymnasium environment.
- `train_ppo.py` trains PPO agents (single-level or curriculum).
- `GameWithBot.py` loads a PPO model and lets you watch it play.

## Project Structure

```text
2D_JumpNRun/
├── game.py                    # Manual game (Pygame loop)
├── player.py                  # Player logic and controls
├── world.py                   # World loading/collision/chunks
├── enemy.py                   # Enemy behavior
├── object.py                  # Chest/bullet objects
├── level.txt                  # Full/original level
├── level_medium.txt           # Medium curriculum level
├── level_easy.txt             # Easy curriculum level
├── rl/
│   ├── game_types.py          # RL dataclasses (action/status)
│   ├── game_session.py        # Game wrapper for RL stepping
│   ├── pirate_game_env.py     # Gymnasium env + reward shaping
│   └── training_metrics.py    # CSV + TensorBoard metrics callback
├── train_ppo.py               # Training entrypoint
├── GameWithBot.py             # Visual bot playback entrypoint
├── export_metrics.py          # Export plots from episode CSV
└── requirements-rl.txt        # Dependencies for game + RL
```

## Installation

Recommended Python: `3.9+`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-rl.txt
```

## Run the Game (manual)

```bash
python3 game.py
```

Controls:
- `A` left
- `D` right
- `W` or `SPACE` jump
- `ENTER` shoot

## Train PPO

### Simple run

```bash
python3 train_ppo.py \
  --run-name ppo_baseline \
  --level-path level_medium.txt \
  --timesteps 200000 \
  --action-preset simple \
  --obs-profile balanced \
  --game-log-level WARNING \
  --progress-bar
```

### Curriculum run (easy -> medium -> full)

```bash
python3 train_ppo.py \
  --run-name ppo_curriculum \
  --curriculum \
  --easy-level-path level_easy.txt \
  --curriculum-easy-steps 100000 \
  --medium-level-path level_medium.txt \
  --curriculum-medium-steps 120000 \
  --level-path level.txt \
  --timesteps 420000 \
  --action-preset simple \
  --obs-profile balanced \
  --game-log-level WARNING \
  --progress-bar
```

### Continue from checkpoint

```bash
python3 train_ppo.py \
  --run-name ppo_resume \
  --load-model runs/ppo_curriculum/checkpoints/best_model.zip \
  --level-path level_medium.txt \
  --timesteps 120000
```

## Watch the Bot Play

```bash
python3 GameWithBot.py \
  --model-path runs/ppo_curriculum/checkpoints/best_model.zip \
  --level-path level_medium.txt \
  --action-preset simple \
  --obs-profile balanced \
  --loop
```

> Important: `--obs-profile` should match the profile used during training (`balanced` or `legacy`).

## Metrics

### TensorBoard

```bash
tensorboard --logdir runs
```

### PNG export

```bash
python3 export_metrics.py --run-dir runs/ppo_curriculum --window 50
```

## Observation Vector (shape = 16)

`0..9, 14, 15` are stable base features. `10..13` depend on profile:

- `legacy`: old features (enemy ahead, gap ahead, enemy close, safe ground distance)
- `balanced`: hazard-focused features (short/mid hazard + threat ahead/behind)

This keeps model input shape stable while allowing safer feature experiments.

## What to Tune Next

- Reward weights in `rl/pirate_game_env.py`
- Hazard feature thresholds in `rl/game_session.py`
- Curriculum step split in `train_ppo.py`
- Action set (`simple` vs `full`)
- `frame_skip` (default is `2` for more reactive control)

## Assets / Licenses

Sprites and art assets are stored in `img/` and remain under their original source licenses.
