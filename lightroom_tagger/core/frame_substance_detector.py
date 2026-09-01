"""Frame substance detector — local preview statistics and verdict rules (#295)."""

from __future__ import annotations

import hashlib
from typing import Literal

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# Trigger thresholds — inherited from prototype classify.py (FFmpeg blackdetect).
BLACK_PIXEL_TH = 25
BLACK_AREA_TH = 0.98
BLOWN_PIXEL_TH = 235
BLOWN_AREA_TH = 0.98

# Verdict thresholds — measured on catalog, not inherited.
VOID_LAP_VAR = 0.10
VOID_TILE_MAX = 1.6
ILLEGIBLE_ENTROPY = 1.05
ILLEGIBLE_TILE_MAX = 20.0
ILLEGIBLE_LAP_VAR = 20.0

Verdict = Literal["void", "illegible", "ok", "unknown"]
UnknownReason = Literal[
    "no_cache_row",
    "oversized_sentinel",
    "cache_file_missing",
    "decode_failed",
    "",
]

_THRESHOLD_TUPLE = (
    BLACK_AREA_TH,
    BLOWN_AREA_TH,
    VOID_LAP_VAR,
    VOID_TILE_MAX,
    ILLEGIBLE_ENTROPY,
    ILLEGIBLE_TILE_MAX,
    ILLEGIBLE_LAP_VAR,
)


def detector_version() -> str:
    """Stable version string derived from the active threshold tuple."""
    payload = ",".join(str(t) for t in _THRESHOLD_TUPLE)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:8]
    return f"v1-{digest}"


def compute_statistics_from_greyscale(grey: np.ndarray) -> dict[str, float]:
    """Compute the five rule-input statistics from an 8-bit greyscale array."""
    if grey.size == 0:
        return {
            "black_frac_25": 0.0,
            "blown_frac_235": 0.0,
            "entropy": 0.0,
            "lap_var": 0.0,
            "tile_max": 0.0,
        }

    hist = np.bincount(grey.ravel(), minlength=256).astype(np.int64)
    total = int(grey.size)
    cdf = np.cumsum(hist)

    black_frac_25 = float(cdf[BLACK_PIXEL_TH]) / total
    blown_frac_235 = float(total - cdf[BLOWN_PIXEL_TH - 1]) / total

    p = hist / total
    nzp = p[p > 0]
    entropy = float(-(nzp * np.log2(nzp)).sum())

    f = grey.astype(np.float32)
    lap = (
        -4.0 * f[1:-1, 1:-1]
        + f[:-2, 1:-1]
        + f[2:, 1:-1]
        + f[1:-1, :-2]
        + f[1:-1, 2:]
    )
    lap_var = float(lap.var()) if lap.size else 0.0

    ty = max(grey.shape[0] // 32, 1)
    tx = max(grey.shape[1] // 32, 1)
    cropped = f[: ty * 32, : tx * 32]
    if cropped.size:
        tiles = cropped.reshape(32, ty, 32, tx).mean(axis=(1, 3))
        tile_max = float(tiles.max())
    else:
        tile_max = 0.0

    return {
        "black_frac_25": black_frac_25,
        "blown_frac_235": blown_frac_235,
        "entropy": entropy,
        "lap_var": lap_var,
        "tile_max": tile_max,
    }


def compute_statistics_from_path(path: str) -> dict[str, float] | None:
    """Decode a cached preview JPEG and return rule-input statistics."""
    try:
        with Image.open(path) as im:
            grey = np.asarray(im.convert("L"), dtype=np.uint8)
    except Exception:
        return None
    return compute_statistics_from_greyscale(grey)


def classify_verdict(stats: dict[str, float]) -> Verdict:
    """Return void | illegible | ok from the five rule-input statistics."""
    triggered_dark = stats["black_frac_25"] >= BLACK_AREA_TH
    triggered_blown = stats["blown_frac_235"] >= BLOWN_AREA_TH
    if not (triggered_dark or triggered_blown):
        return "ok"
    if stats["lap_var"] < VOID_LAP_VAR or stats["tile_max"] <= VOID_TILE_MAX:
        return "void"
    if triggered_blown:
        return "illegible" if stats["entropy"] < ILLEGIBLE_ENTROPY else "ok"
    if (
        stats["entropy"] < ILLEGIBLE_ENTROPY
        and stats["tile_max"] < ILLEGIBLE_TILE_MAX
        and stats["lap_var"] < ILLEGIBLE_LAP_VAR
    ):
        return "illegible"
    return "ok"
