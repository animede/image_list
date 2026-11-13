"""PC 内の画像を文章や画像で探すアプリ。

起動:
    CUDA_VISIBLE_DEVICES=1 .venv/bin/uvicorn server:app --host 127.0.0.1 --port 7870
    ブラウザで http://127.0.0.1:7870 を開く

環境変数:
    IMAGE_ROOTS  調べるフォルダ(Linux は ":"、Windows は ";" 区切り)。最初の 1 回だけ使い、あとは画面で変える。既定は ~/Pictures
    DATA_DIR     索引の置き場所。既定は ./data
    EMBED_DIM    ベクトルの次元(768 / 512 / 256)。既定は 768
    EMBED_THREADS  CPU で動かすときのスレッド数。既定は 8
    EMBED_IMAGE_TOKENS  画像 1 枚のトークン数(70〜1120)。既定は GPU 280、CPU 140。変えると索引を作り直す
"""
import io
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from PIL import Image, ImageOps
from pydantic import BaseModel

from embedder import Embedder
import folders
from index import ImageIndex

HERE = Path(__file__).parent
DATA_DIR = Path(os.getenv("DATA_DIR", HERE / "data"))
ROOTS = [r for r in os.getenv("IMAGE_ROOTS", "~/Pictures").split(os.pathsep) if r]
MAX_UPLOAD = 30 * 2**20

index = ImageIndex(Embedder(int(os.getenv("EMBED_DIM", "768"))), DATA_DIR, ROOTS)
index.start_sync()  # 起動時に変わった画像だけ入れ直す

app = FastAPI(title="image_list")


def public(items):
    return [{k: m[k] for k in ("id", "path", "width", "height", "score") if k in m} for m in items]


@app.get("/")
def page():
    return FileResponse(HERE / "static" / "index.html")


@app.get("/api/status")
def status():
    return {**index.status, "count": len(index.images), "roots": index.roots, "device": index.embedder.device, "pathsep": os.pathsep,
            "image_tokens": index.embedder.image_tokens}


class Roots(BaseModel):
    roots: list[str]


@app.post("/api/roots")
def set_roots(body: Roots):
    roots = [r.strip() for r in body.roots if r.strip()]
    missing = [r for r in roots if not os.path.isdir(os.path.expanduser(r))]
    if missing:
        raise HTTPException(400, f"フォルダがありません: {', '.join(missing)}")
    if not index.start_sync(roots):
        raise HTTPException(409, "索引を作っている最中です")
    return {"ok": True}


@app.get("/api/folders/suggest")
def folder_suggest():
    return {"folders": folders.suggestions()}


@app.post("/api/folders/pick")
def folder_pick():
    """OS のフォルダ選択画面を開く(選ぶまで待つ)。"""
    try:
        return {"path": folders.pick_folder()}
    except RuntimeError as e:
        raise HTTPException(501, str(e))


@app.post("/api/reindex")
def reindex():
    if not index.start_sync():
        raise HTTPException(409, "索引を作っている最中です")
    return {"ok": True}


@app.get("/api/search")
def search(q: str = Query(..., min_length=1, max_length=500), k: int = Query(60, ge=1, le=500)):
    res, took = index.search_text(q, k)
    return {"results": public(res), "time": took}


@app.get("/api/similar/{iid}")
def similar(iid: str, k: int = Query(60, ge=1, le=500)):
    found = index.similar(iid, k)
    if found is None:
        raise HTTPException(404, "画像がありません")
    res, took = found
    return {"results": public(res), "time": took}


@app.post("/api/search_image")
async def search_image(request: Request, k: int = Query(60, ge=1, le=500)):
    """画像ファイルの中身をそのまま本文で送る(multipart は使わない)。"""
    data = await request.body()
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(400, "画像が空か、大きすぎます")
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        im.thumbnail((1024, 1024))
    except Exception:
        raise HTTPException(400, "画像として読めません")
    res, took = index.search_image(im, k)
    return {"results": public(res), "time": took}


@app.get("/api/thumb/{iid}")
def thumb(iid: str):
    try:
        t = index.thumb(iid)
    except Exception:
        raise HTTPException(500, "サムネイルを作れません")
    if not t:
        raise HTTPException(404)
    return FileResponse(t, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/image/{iid}")
def image(iid: str):
    m = index.get(iid)  # 索引にある画像だけを返す(任意のパスは読ませない)
    if not m or not os.path.exists(m["path"]):
        raise HTTPException(404)
    return FileResponse(m["path"])


@app.post("/api/open/{iid}")
def open_folder(iid: str):
    """画像のあるフォルダをファイルマネージャで開く。"""
    m = index.get(iid)
    if not m:
        raise HTTPException(404)
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(m["path"])])  # 画像を選んだ状態で開く
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, os.path.dirname(m["path"])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True}
