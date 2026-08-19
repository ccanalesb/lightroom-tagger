"""PROTOTYPE — THROWAWAY. Wayfinder ticket #277 (map #275). Delete when sliced.

Stage 1: compute pixel statistics for every catalog image off the local vision
cache and write them to a scratch DB. Nothing here is production code; the
detector that ships will live outside the vision-op engine (ADR-0014 §6).

Reads library.db read-only. Writes only PROTOTYPE-wipe-me.db.

    .venv/bin/python scripts/prototype_void_detector/sweep.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB_DB = os.path.join(REPO, "library.db")
SCRATCH_DB = os.path.join(REPO, "scripts/prototype_void_detector/PROTOTYPE-wipe-me.db")

# FFmpeg blackdetect (libavfilter/vf_blackdetect.c:64-73): pixel_black_th=0.10.
# Our cached previews are full-range JPEG, so the constant is 0.10*255 = 25, not
# the limited-range 16 + 0.10*(235-16) = 37.9. Both are swept.
BLACK_THRESHOLDS = (16, 25, 32, 38, 51)
BLOWN_THRESHOLDS = (235, 245, 250, 254)
LIT_THRESHOLDS = (25, 38, 51, 64, 96)


def _percentile_from_hist(cdf: np.ndarray, total: int, q: float) -> float:
    """Smallest bin whose cumulative count reaches q of total (q in 0..1)."""
    target = q * total
    return float(np.searchsorted(cdf, target, side="left"))


def measure(path: str) -> dict | None:
    try:
        with Image.open(path) as im:
            g = im.convert("L")
            a = np.asarray(g, dtype=np.uint8)
    except Exception:
        return None
    if a.size == 0:
        return None

    hist = np.bincount(a.ravel(), minlength=256).astype(np.int64)
    total = int(a.size)
    cdf = np.cumsum(hist)
    bins = np.arange(256, dtype=np.float64)

    mean = float((hist * bins).sum() / total)
    var = float((hist * (bins - mean) ** 2).sum() / total)
    nz = np.nonzero(hist)[0]
    lo, hi = int(nz[0]), int(nz[-1])

    p = hist / total
    nzp = p[p > 0]
    entropy = float(-(nzp * np.log2(nzp)).sum())

    out: dict = {
        "width": int(a.shape[1]),
        "height": int(a.shape[0]),
        "px": total,
        "luma_mean": mean,
        "luma_std": var**0.5,
        "luma_min": lo,
        "luma_max": hi,
        "entropy": entropy,
    }
    for q, name in (
        (0.01, "p01"), (0.02, "p02"), (0.05, "p05"), (0.50, "p50"),
        (0.95, "p95"), (0.98, "p98"), (0.99, "p99"), (0.999, "p999"),
    ):
        out[f"luma_{name}"] = _percentile_from_hist(cdf, total, q)

    # PhotoSi US11586669B2: verdict is noise-trimmed contrast (2% trim), threshold
    # 125/255; brightness only *triggers* the analysis (75% of pixels extreme).
    out["photosi_contrast"] = out["luma_p98"] - out["luma_p02"]
    dark_extreme = float(cdf[51]) / total
    bright_extreme = float(total - cdf[203]) / total
    out["extreme_frac"] = dark_extreme + bright_extreme
    out["dark_extreme_frac"] = dark_extreme
    out["bright_extreme_frac"] = bright_extreme

    for t in BLACK_THRESHOLDS:
        out[f"black_frac_{t}"] = float(cdf[t]) / total
    for t in BLOWN_THRESHOLDS:
        out[f"blown_frac_{t}"] = float(total - cdf[t - 1]) / total
    for t in LIT_THRESHOLDS:
        out[f"lit_frac_{t}"] = float(total - cdf[t]) / total

    f = a.astype(np.float32)
    lap = (
        -4.0 * f[1:-1, 1:-1]
        + f[:-2, 1:-1] + f[2:, 1:-1] + f[1:-1, :-2] + f[1:-1, 2:]
    )
    out["lap_var"] = float(lap.var()) if lap.size else 0.0
    # Contrast-normalised Laplacian: raw lap_var is quadratic in contrast, so a
    # global threshold punishes dark-but-sharp frames (ruled out in #276).
    out["lap_var_norm"] = out["lap_var"] / max(out["luma_std"] ** 2, 1e-6)

    # Brightest 1/32 tile: a small bright subject (the crescent moon) that global
    # percentiles average away still lights up one tile.
    ty, tx = max(a.shape[0] // 32, 1), max(a.shape[1] // 32, 1)
    cropped = f[: ty * 32, : tx * 32]
    if cropped.size:
        tiles = cropped.reshape(32, ty, 32, tx).mean(axis=(1, 3))
        out["tile_max"] = float(tiles.max())
        out["tile_std"] = float(tiles.std())
        out["tile_lit_frac"] = float((tiles > 25).mean())
    else:
        out["tile_max"] = out["tile_std"] = out["tile_lit_frac"] = 0.0
    return out


def _worker(item: tuple[str, str]) -> tuple[str, dict | None, float]:
    key, path = item
    t0 = time.perf_counter()
    return key, measure(path), time.perf_counter() - t0


def main() -> int:
    lib = sqlite3.connect(f"file:{LIB_DB}?mode=ro", uri=True)
    lib.row_factory = sqlite3.Row
    rows = lib.execute(
        """
        SELECT i.key, i.filename, vc.compressed_path
        FROM images i
        LEFT JOIN vision_cache vc ON vc.key = i.key
        ORDER BY i.key
        """
    ).fetchall()
    lib.close()

    work: list[tuple[str, str]] = []
    unknown: list[tuple[str, str]] = []
    for r in rows:
        cp = str(r["compressed_path"] or "").strip()
        if not cp:
            unknown.append((r["key"], "no_cache_row"))
        elif cp == "__oversized__":
            unknown.append((r["key"], "oversized_sentinel"))
        elif not os.path.isfile(cp):
            unknown.append((r["key"], "cache_file_missing"))
        else:
            work.append((r["key"], cp))

    print(f"catalog images: {len(rows)}  measurable: {len(work)}  unknown: {len(unknown)}")

    if os.path.exists(SCRATCH_DB):
        os.unlink(SCRATCH_DB)
    out = sqlite3.connect(SCRATCH_DB)
    out.execute("CREATE TABLE unknown (key TEXT PRIMARY KEY, reason TEXT)")
    out.executemany("INSERT INTO unknown VALUES (?,?)", unknown)

    probe = measure(work[0][1])
    assert probe is not None
    cols = list(probe.keys())
    out.execute(
        "CREATE TABLE stats (key TEXT PRIMARY KEY, "
        + ", ".join(f"{c} REAL" for c in cols)
        + ", ms REAL)"
    )
    ins = f"INSERT INTO stats VALUES ({','.join('?' * (len(cols) + 2))})"

    t0 = time.perf_counter()
    done = failed = 0
    total_ms = 0.0
    batch: list[tuple] = []
    with ProcessPoolExecutor() as ex:
        for key, st, dt in ex.map(_worker, work, chunksize=64):
            done += 1
            if st is None:
                failed += 1
                out.execute("INSERT OR REPLACE INTO unknown VALUES (?,?)", (key, "decode_failed"))
                continue
            total_ms += dt * 1000
            batch.append(tuple([key] + [st[c] for c in cols] + [dt * 1000]))
            if len(batch) >= 2000:
                out.executemany(ins, batch)
                batch.clear()
                print(f"  {done}/{len(work)}  {time.perf_counter() - t0:.0f}s", flush=True)
    if batch:
        out.executemany(ins, batch)
    out.commit()

    measured = done - failed
    print(
        f"measured {measured}  decode_failed {failed}  "
        f"wall {time.perf_counter() - t0:.1f}s  cpu {total_ms / max(measured, 1):.2f} ms/img"
    )
    out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
