from __future__ import annotations

import numpy as np
import sqlite_vec
from sentence_transformers import SentenceTransformer

TEXT_EMBED_MODEL_ID = "sentence-transformers/all-mpnet-base-v2"
TEXT_EMBED_DIM = 768

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(TEXT_EMBED_MODEL_ID)
    return _model


def embed_texts(texts: list[str], *, batch_size: int = 24) -> np.ndarray:
    raw = _get_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return np.asarray(raw, dtype=np.float32)


def embed_query_text(text: str) -> np.ndarray:
    return embed_texts([text], batch_size=1)[0]


def numpy_to_vec_blob(vec: np.ndarray) -> bytes:
    v = np.asarray(vec)
    if v.ndim == 2 and v.shape == (1, TEXT_EMBED_DIM):
        v = v.squeeze(0)
    assert v.shape == (TEXT_EMBED_DIM,), v.shape
    return sqlite_vec.serialize_float32(
        v.astype("float32", copy=False).tolist()
    )


def embed_query_to_vec_blob(text: str) -> bytes:
    return numpy_to_vec_blob(embed_query_text(text))


def embed_text_to_vec_blob(text: str) -> bytes:
    """Encode one document string and return a sqlite-vec float32 blob (768×4 bytes)."""
    return embed_query_to_vec_blob(text)
