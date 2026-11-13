"""EmbeddingGemma 2 で画像と文章を同じ空間のベクトルにする(音声の部分は読み込まない)。"""
import os
import threading

import numpy as np
import torch
from PIL import Image
from sentence_transformers import SentenceTransformer

MODEL = os.getenv("EMBED_MODEL", "google/embeddinggemma-2")
# CPU で動かすときに使うスレッド数。既定は 8
CPU_THREADS = int(os.getenv("EMBED_THREADS", "8"))
# 画像 1 枚を表すトークン数(70〜1120)。少ないほど速いが細部を見分ける力が落ちる。
# 既定は GPU 280(モデルの既定)、CPU 140(280 の約 2.4 倍速く、上位 1 件は 3/4 が同じ)
IMAGE_TOKENS = os.getenv("EMBED_IMAGE_TOKENS")


class Embedder:
    def __init__(self, dim: int = 768):
        self.dim = dim  # 768 / 512 / 256(Matryoshka。画像では 128 は精度が大きく落ちる)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # float16 は NaN になるので使わない。GPU は bfloat16、CPU は float32
        dtype = torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported() else torch.float32
        self.device = device
        if device == "cpu":
            torch.set_num_threads(CPU_THREADS)
            torch.set_num_interop_threads(1)
        self.model = SentenceTransformer(
            MODEL, device=device, model_kwargs={"torch_dtype": dtype}, config_kwargs={"audio_config": None},
        )
        self.image_tokens = int(IMAGE_TOKENS) if IMAGE_TOKENS else (280 if device == "cuda" else 140)
        proc = self.model[0].processor
        proc.image_processor.max_soft_tokens = self.image_tokens
        proc.image_processor.image_seq_length = self.image_tokens
        if hasattr(proc, "image_seq_length"):
            proc.image_seq_length = self.image_tokens
        self._lock = threading.Lock()  # モデルは同時に 1 件ずつ使う

    def _encode(self, x, **kw) -> np.ndarray:
        with self._lock:
            v = self.model.encode(x, truncate_dim=self.dim, normalize_embeddings=True, convert_to_numpy=True, **kw)
        return v.astype(np.float32)

    def embed_image(self, im: Image.Image) -> np.ndarray:
        return self._encode({"image": im})  # 画像には前置きを付けない(モデルカードの指定)

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode(text, prompt_name="SearchQuery")
