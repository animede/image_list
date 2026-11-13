# image_list

PC 内の画像を、文章や画像で探すアプリ。EmbeddingGemma 2 で画像と文章を同じ空間のベクトル(768 次元)にして、コサイン類似度で並べる。

## 起動
```
./setup.sh          # 初回だけ(.venv を作って依存を入れる)
IMAGE_ROOTS=~/Pictures:/mnt/data/images ./run.sh
```
ブラウザで http://127.0.0.1:7870 を開く。フォルダは画面の「フォルダ設定」でも変えられる。

## できること
- 文章で探す(例: 「夕焼けの海」「猫が寝ている」)
- 画像で探す(ファイルを選ぶか、画面にドロップ)
- 似た画像を探す、画像のあるフォルダを開く

## ファイル
- `server.py` API と画面の配信
- `index.py` フォルダを調べて索引を作る(mtime と size で変わった画像だけ入れ直す)
- `embedder.py` EmbeddingGemma 2(音声部分は読み込まない)
- `static/index.html` 画面
- `data/` 索引(`vectors.npy`, `meta.json`, `thumbs/`)

## CPU で動かす
```
CUDA_VISIBLE_DEVICES= ./run.sh
```
優先度を下げ、8 スレッドで、画像を 140 トークンで表す(8 コアの性能コアで 1 枚約 0.86 秒。280 トークンだと約 2 秒)。
性能コアと効率コアがある CPU では、`CPU_CORES=0,2,4,6,8,10,12,14` のように性能コアを指定すると速い(番号は `lscpu -e` で確かめる)。
`EMBED_IMAGE_TOKENS`(70〜1120)、`EMBED_THREADS` でも変えられる。画像トークン数を変えると索引は自動で作り直す。
