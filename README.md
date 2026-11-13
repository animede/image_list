# image_list

PC 内の画像を、文章や画像で探すアプリ。[EmbeddingGemma 2](https://huggingface.co/google/embeddinggemma-2) で画像と文章を同じ空間のベクトル(768 次元)にして、コサイン類似度で並べる。画像も索引も PC の中だけで扱い、外には送らない(モデルの取得だけ Hugging Face に接続する)。

## できること
- 文章で探す(例: 「夕焼けの海」「猫が寝ている」)
- 画像で探す(ファイルを選ぶか、画面にドロップ)
- 似た画像を探す、画像のあるフォルダを開く
- 調べるフォルダを画面で変える。変わった画像だけ索引に入れ直す

## 必要なもの
- Linux と Python 3
- CPU だけで動く。NVIDIA GPU があれば速い(bfloat16 が使える GPU)
- 初回起動時に `google/embeddinggemma-2` を Hugging Face から取得する。モデルの利用条件への同意が要る場合は、Hugging Face で同意して `huggingface-cli login` しておく

## 使い方
```
git clone git@github.com:animede/image_list.git
cd image_list
./setup.sh          # 初回だけ(.venv を作って依存を入れる)
IMAGE_ROOTS=~/Pictures:/mnt/data/images ./run.sh   # CPU で動く
```
ブラウザで http://127.0.0.1:7870 を開く。最初は索引を作るので、画像の枚数に応じて時間がかかる。フォルダは画面の「フォルダ設定」でも変えられる。

## 設定(環境変数)
| 名前 | 内容 | 既定 |
| --- | --- | --- |
| `IMAGE_ROOTS` | 調べるフォルダ(`:` 区切り)。最初の 1 回だけ使い、あとは画面で変える | `~/Pictures` |
| `DATA_DIR` | 索引の置き場所 | `./data` |
| `PORT` | 待ち受けるポート | `7870` |
| `EMBED_MODEL` | 使うモデル | `google/embeddinggemma-2` |
| `EMBED_DIM` | ベクトルの次元(768 / 512 / 256) | `768` |
| `EMBED_IMAGE_TOKENS` | 画像 1 枚のトークン数(70〜1120)。変えると索引を作り直す | CPU 140、GPU 280 |
| `EMBED_THREADS` | CPU で動かすときのスレッド数 | `8` |
| `CPU_CORES` | CPU で動かすときに割り当てるコア(例: `0,2,4,6`) | なし |
| `CUDA_VISIBLE_DEVICES` | 使う GPU の番号。指定しなければ CPU で動く | なし |

### CPU で動かす(既定)
優先度を下げ、8 スレッドで、画像を 140 トークンで表す(8 コアの性能コアで 1 枚約 0.86 秒。280 トークンだと約 2 秒)。
性能コアと効率コアがある CPU では、`CPU_CORES=0,2,4,6,8,10,12,14` のように性能コアを指定すると速い(番号は `lscpu -e` で確かめる)。

### GPU で動かす
```
CUDA_VISIBLE_DEVICES=0 ./run.sh
```
画像を 280 トークンで表す(1 枚約 0.25 秒)。CPU と GPU を切り替えて同じ索引を使うなら、`EMBED_IMAGE_TOKENS` をそろえる(違うと索引を作り直す)。

## ファイル
- `server.py` API と画面の配信
- `index.py` フォルダを調べて索引を作る(mtime と size で変わった画像だけ入れ直す)
- `embedder.py` EmbeddingGemma 2(音声部分は読み込まない)
- `static/index.html` 画面
- `setup.sh` / `run.sh` 準備と起動
- `data/` 索引(`vectors.npy`, `meta.json`, `thumbs/`)。リポジトリには含めない

## ライセンス
このリポジトリのコードは [MIT License](LICENSE)。モデル EmbeddingGemma 2 はこのリポジトリに含まれず、Google の [Gemma の利用規約](https://ai.google.dev/gemma/terms) に従う。
