#!/usr/bin/env bash
# Neustart arm: idempotent environment setup for a fresh container.
#   - .venv with Python 3.11 and the package versions the models were saved with (the system Python 3.13
#     segfaults when SB3 unpickles the learning-rate lambdas of models saved under 3.11)
#   - Phase-10 data (demos, anchor/drift states, baselines) from daten_neustart/
cd "$(dirname "$0")/.."
set -e
if ! .venv/bin/python -c "import torch, stable_baselines3, gymnasium, pygame" 2>/dev/null; then
    uv venv --python /usr/bin/python3.11 .venv
    uv pip install --python .venv/bin/python torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
    uv pip install --python .venv/bin/python stable-baselines3==2.9.0 gymnasium==1.3.0 numpy==2.4.6 \
        cloudpickle==3.1.2 pygame imageio imageio-ffmpeg matplotlib pytest tensorboard py-spy
fi
if [ ! -f runs/demos10/demos.jsonl ]; then
    tar -xJf daten_neustart/runs_phase10_daten.tar.xz
fi
.venv/bin/python -c "import sys, torch, stable_baselines3; print('ok', sys.version.split()[0], torch.__version__, stable_baselines3.__version__)"
