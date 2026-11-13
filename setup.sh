#!/usr/bin/env bash
# 仮想環境を作って依存を入れる。モデル(google/embeddinggemma-2)は初回起動時に Hugging Face から取得される。
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
