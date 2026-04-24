from __future__ import annotations

import numpy as np
import sqlite_vec
from PIL import Image
from sentence_transformers import SentenceTransformer

CLIP_EMBED_MODEL_ID = "clip-ViT-B-32"
CLIP_EMBED_DIM = 512

_clip_model: SentenceTransformer | None = None


def _get_clip_model() -> SentenceTransformer:
    global _clip_model
    if _clip_model is None:
        _clip_model = SentenceTransformer(CLIP_EMBED_MODEL_ID)
    return _clip_model


def encode_images(paths: list[str], *, batch_size: int = 8) -> np.ndarray:
    """Load images from paths, return float32 array of shape (N, CLIP_EMBED_DIM)."""
    if not paths:
        return np.empty((0, CLIP_EMBED_DIM), dtype=np.float32)
    out_chunks: list[np.ndarray] = []
    for i in range(0, len(paths), batch_size):
        chunk_paths = paths[i : i + batch_size]
        images: list[Image.Image] = [
            Image.open(p).convert("RGB") for p in chunk_paths
        ]
        raw = _get_clip_model().encode(
            images,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        out_chunks.append(np.asarray(raw, dtype=np.float32))
    if len(out_chunks) == 1:
        return out_chunks[0]
    return np.concatenate(out_chunks, axis=0)


def encode_text_for_clip(texts: list[str], *, batch_size: int = 24) -> np.ndarray:
    """Encode text strings in CLIP space; shape (N, CLIP_EMBED_DIM)."""
    if not texts:
        return np.empty((0, CLIP_EMBED_DIM), dtype=np.float32)
    raw = _get_clip_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return np.asarray(raw, dtype=np.float32)


def numpy_to_clip_vec_blob(arr: np.ndarray) -> bytes:
    v = np.asarray(arr)
    if v.ndim == 2 and v.shape == (1, CLIP_EMBED_DIM):
        v = v.squeeze(0)
    assert v.shape == (CLIP_EMBED_DIM,), v.shape
    return sqlite_vec.serialize_float32(
        v.astype("float32", copy=False).tolist()
    )
