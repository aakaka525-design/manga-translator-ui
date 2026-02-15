#!/bin/bash
set -e
cd "$(dirname "$0")"

CONDA_ENV_NAME="manga-env"
MINICONDA_DIR="$HOME/miniconda3"

if [ -f "$MINICONDA_DIR/bin/activate" ]; then
  source "$MINICONDA_DIR/bin/activate" "$CONDA_ENV_NAME" || {
    echo "[ERROR] 无法激活 conda 环境: $CONDA_ENV_NAME"
    exit 1
  }
fi

python -m manga_translator web
