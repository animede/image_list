"""画像の索引。フォルダを調べて、画像を EmbeddingGemma 2 でベクトルにして保存する。

保存先(DATA_DIR):
    vectors.npy  各画像のベクトル(行の順は meta.json の images と同じ)
    meta.json    {"version", "dim", "image_tokens", "roots", "images": [{id, path, mtime, size, width, height}]}
    thumbs/      サムネイル(id.jpg)
変わった画像だけを入れ直す。変更の判定は mtime と size。
"""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

INDEX_VERSION = 1
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
MAX_SIDE = 1024  # ベクトルにする前に縮める(速さのため。モデルの中でさらに縮められる)
THUMB_SIDE = 320
SAVE_EVERY = 200  # この枚数ごとに途中保存する

Image.MAX_IMAGE_PIXELS = 200_000_000


def image_id(path: str) -> str:
    return hashlib.sha1(path.encode()).hexdigest()[:16]


def load_image(path: str, side: int) -> Image.Image:
    im = Image.open(path)
    im.draft("RGB", (side, side))  # JPEG は読み込み時に縮める(速い)
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((side, side))
    return im


class ImageIndex:
    def __init__(self, embedder, data_dir: Path, roots: list[str]):
        self.embedder = embedder
        self.data_dir = data_dir
        self.thumb_dir = data_dir / "thumbs"
        self.thumb_dir.mkdir(parents=True, exist_ok=True)
        self.roots = roots
        self.images: list[dict] = []
        self.vectors = np.zeros((0, embedder.dim), dtype=np.float32)
        self.by_id: dict[str, int] = {}
        self._lock = threading.Lock()  # images / vectors の入れ替え
        self._scan_lock = threading.Lock()  # 調べるのは同時に 1 回だけ
        self.status = {"state": "idle", "done": 0, "total": 0, "errors": 0, "message": ""}
        self._load()

    # ---- 保存と読み込み ----
    def _load(self):
        meta_p, vec_p = self.data_dir / "meta.json", self.data_dir / "vectors.npy"
        if not (meta_p.exists() and vec_p.exists()):
            return
        try:
            meta = json.loads(meta_p.read_text())
            vecs = np.load(vec_p)
        except Exception:
            return
        if meta.get("roots"):
            self.roots = meta["roots"]  # 索引を作り直すときも、調べるフォルダの設定は引き継ぐ
        if (meta.get("version") != INDEX_VERSION or meta.get("dim") != self.embedder.dim
                or meta.get("image_tokens", 280) != self.embedder.image_tokens or len(meta["images"]) != len(vecs)):
            return  # 形式や画像トークン数が違う索引は捨てて作り直す(ベクトルが変わるので混ぜない)
        self._set(meta["images"], vecs)

    def _save(self, images, vecs):
        meta = {"version": INDEX_VERSION, "dim": self.embedder.dim, "image_tokens": self.embedder.image_tokens, "roots": self.roots, "images": images}
        tmp_m, tmp_v = self.data_dir / "meta.json.tmp", self.data_dir / "vectors.tmp.npy"
        tmp_m.write_text(json.dumps(meta, ensure_ascii=False))
        np.save(tmp_v, vecs)
        os.replace(tmp_v, self.data_dir / "vectors.npy")
        os.replace(tmp_m, self.data_dir / "meta.json")

    def _set(self, images, vecs):
        with self._lock:
            self.images = images
            self.vectors = vecs.astype(np.float32)
            self.by_id = {m["id"]: i for i, m in enumerate(images)}

    # ---- フォルダを調べる ----
    def _walk(self):
        for root in self.roots:
            root = os.path.expanduser(root)
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for f in filenames:
                    if Path(f).suffix.lower() in EXTS:
                        p = os.path.join(dirpath, f)
                        try:
                            st = os.stat(p)
                        except OSError:
                            continue
                        yield p, st.st_mtime, st.st_size

    def start_sync(self, roots: list[str] | None = None) -> bool:
        if self._scan_lock.locked():
            return False
        if roots is not None:
            self.roots = roots
        threading.Thread(target=self.sync, daemon=True).start()
        return True

    def sync(self):
        if not self._scan_lock.acquire(blocking=False):
            return
        try:
            self._sync()
        except Exception as e:
            self.status.update(state="error", message=str(e))
        finally:
            self._scan_lock.release()

    def _sync(self):
        self.status = {"state": "scanning", "done": 0, "total": 0, "errors": 0, "message": ""}
        with self._lock:
            old = {m["path"]: (m, self.vectors[i]) for i, m in enumerate(self.images)}
        files = list(self._walk())
        keep_m, keep_v, todo = [], [], []
        for p, mtime, size in files:
            prev = old.get(p)
            if prev and prev[0]["mtime"] == mtime and prev[0]["size"] == size:
                keep_m.append(prev[0])
                keep_v.append(prev[1])
            else:
                todo.append((p, mtime, size))
        # 消えた画像のサムネイルを片づける
        alive = {image_id(p) for p, _, _ in files}
        for path in old:
            iid = image_id(path)
            if iid not in alive:
                (self.thumb_dir / f"{iid}.jpg").unlink(missing_ok=True)

        self.status.update(state="embedding", total=len(todo))
        started = time.monotonic()
        for n, (p, mtime, size) in enumerate(todo, 1):
            try:
                im = load_image(p, MAX_SIDE)
                full_w, full_h = Image.open(p).size
                vec = self.embedder.embed_image(im)
                iid = image_id(p)
                (self.thumb_dir / f"{iid}.jpg").unlink(missing_ok=True)  # 中身が変わったので作り直す
                keep_m.append({"id": iid, "path": p, "mtime": mtime, "size": size, "width": full_w, "height": full_h})
                keep_v.append(vec)
            except Exception:
                self.status["errors"] += 1
            self.status["done"] = n
            if n % SAVE_EVERY == 0:
                self._commit(keep_m, keep_v)
                rate = n / (time.monotonic() - started)
                self.status["message"] = f"{rate:.1f} 枚/秒"
        self._commit(keep_m, keep_v)
        self.status.update(state="idle", message=f"{len(keep_m)} 枚(新しく {len(todo)} 枚)")

    def _commit(self, images, vecs):
        arr = np.vstack(vecs).astype(np.float32) if vecs else np.zeros((0, self.embedder.dim), np.float32)
        images = list(images)
        self._set(images, arr)
        self._save(images, arr)

    # ---- 検索 ----
    def _rank(self, q: np.ndarray, k: int, exclude: int | None = None):
        with self._lock:
            if not len(self.images):
                return []
            scores = self.vectors @ q
            if exclude is not None:
                scores[exclude] = -2
            k = min(k, len(scores))
            top = np.argpartition(-scores, k - 1)[:k]
            top = top[np.argsort(-scores[top])]
            return [{**self.images[i], "score": round(float(scores[i]), 4)} for i in top]

    def search_text(self, query: str, k: int):
        return self._rank(self.embedder.embed_query(query), k)

    def search_image(self, im: Image.Image, k: int):
        return self._rank(self.embedder.embed_image(im), k)

    def similar(self, iid: str, k: int):
        i = self.by_id.get(iid)
        if i is None:
            return None
        return self._rank(self.vectors[i], k, exclude=i)

    def get(self, iid: str) -> dict | None:
        i = self.by_id.get(iid)
        return self.images[i] if i is not None else None

    def thumb(self, iid: str) -> Path | None:
        m = self.get(iid)
        if not m:
            return None
        t = self.thumb_dir / f"{iid}.jpg"
        if not t.exists():
            load_image(m["path"], THUMB_SIDE).save(t, "JPEG", quality=85)
        return t
