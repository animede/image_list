#!/usr/bin/env bash
# 仮想環境を作って依存を入れる。モデル(google/embeddinggemma-2)は初回起動時に Hugging Face から取得される。
# torch は CPU 版を入れる(PyPI の Linux 版は CUDA 版で、GPU 用のライブラリが約 4GB 付いてくる)。
# GPU で動かすなら TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./setup.sh のように指定する。
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install torch torchvision --index-url "${TORCH_INDEX:-https://download.pytorch.org/whl/cpu}"
.venv/bin/pip install -r requirements.txt
