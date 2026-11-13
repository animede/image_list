#!/usr/bin/env bash
# 起動。ブラウザで http://127.0.0.1:7870
#   CPU: ./run.sh                        (既定。優先度を下げ、画像 140 トークンで動かす)
#   GPU: CUDA_VISIBLE_DEVICES=0 ./run.sh  (使う GPU の番号を指定する。画像 280 トークン)
#        CPU_CORES=0,2,4,6 を付けると、そのコアだけに割り当てる(性能コアと効率コアがある CPU では性能コアを指定すると速い)
cd "$(dirname "$0")"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-}"  # 指定しなければ CPU で動く
[ -x .venv/bin/uvicorn ] || { echo "先に ./setup.sh を実行してください" >&2; exit 1; }
CMD=(.venv/bin/uvicorn server:app --host 127.0.0.1 --port "${PORT:-7870}")
if [ -z "$CUDA_VISIBLE_DEVICES" ]; then
  export EMBED_THREADS="${EMBED_THREADS:-8}" OMP_NUM_THREADS="${EMBED_THREADS:-8}"
  [ -n "${CPU_CORES:-}" ] && CMD=(taskset -c "$CPU_CORES" "${CMD[@]}")
  CMD=(nice -n 10 "${CMD[@]}")
fi
exec "${CMD[@]}"
