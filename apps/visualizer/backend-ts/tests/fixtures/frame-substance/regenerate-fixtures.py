#!/usr/bin/env python3
"""Regenerate the golden files that pin the frame substance detector.

NOT part of the runtime. The backend is pure TypeScript; this script exists so the
statistics the TypeScript detector computes can be checked against the numpy and
Pillow ones that produced every verdict already in `library.db`. Run it by hand
after a deliberate threshold change:

    ../../../../../../.venv/bin/python regenerate-fixtures.py

Images are synthetic, deterministic, and saved as PNG so decoding is lossless and
the parity test isolates the arithmetic from the codec. Nothing from the user's
catalog is committed here.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from lightroom_tagger.core.frame_substance_detector import (
    classify_verdict,
    compute_statistics_from_greyscale,
    detector_version,
)

HERE = Path(__file__).parent


def make_images() -> dict[str, Image.Image]:
    """One image per branch of the verdict rules, plus the tiling edge cases."""
    out: dict[str, Image.Image] = {}

    out["flat_black"] = Image.fromarray(np.zeros((128, 128), dtype=np.uint8), "L")
    out["flat_white"] = Image.fromarray(np.full((128, 128), 255, dtype=np.uint8), "L")

    # Dark frame with a bright speck too small to fill a tile: illegible, not void.
    cluster = np.zeros((512, 512), dtype=np.uint8)
    cluster[254:258, 254:258] = 255
    out["black_bright_cluster"] = Image.fromarray(cluster, "L")

    # Dark frame with a bright patch that fills whole tiles: legible after all.
    patch = np.zeros((512, 512), dtype=np.uint8)
    patch[240:280, 240:280] = 255
    out["black_bright_patch"] = Image.fromarray(patch, "L")

    # Blown but not perfectly flat — the blown trigger's illegible branch.
    blown = np.full((128, 128), 250, dtype=np.uint8)
    blown[16:112, 16:112] = 245
    out["blown_near_uniform"] = Image.fromarray(blown, "L")

    rng = np.random.default_rng(0)
    out["noisy_mid_grey"] = Image.fromarray(
        rng.integers(80, 176, size=(128, 128), dtype=np.uint8), "L"
    )

    # Just under the black-area trigger: ok whatever the structure statistics say.
    below = np.zeros((128, 128), dtype=np.uint8)
    below.ravel()[: int(128 * 128 * 0.02) + 8] = 128
    out["below_trigger_grey"] = Image.fromarray(below, "L")

    # RGB, so the parity test also covers Image.convert("L").
    h, w = 137, 251
    yy, xx = np.mgrid[0:h, 0:w]
    out["gradient_rgb_251x137"] = Image.fromarray(
        np.stack([
            (xx * 255 // (w - 1)).astype(np.uint8),
            (yy * 255 // (h - 1)).astype(np.uint8),
            ((xx + yy) * 255 // (w + h - 2)).astype(np.uint8),
        ], axis=-1),
        "RGB",
    )

    # Tiling edges: a size the 32x32 grid divides exactly, and one it does not.
    rng = np.random.default_rng(295)
    out["exact_32x32"] = Image.fromarray(
        rng.integers(0, 256, size=(32, 32), dtype=np.uint8), "L"
    )
    out["odd_37x53"] = Image.fromarray(
        rng.integers(0, 256, size=(53, 37), dtype=np.uint8), "L"
    )
    return out


def main() -> None:
    entries = []
    for name, img in make_images().items():
        img.save(HERE / f"{name}.png", "PNG", optimize=True)
        grey = np.asarray(img.convert("L"), dtype=np.uint8)
        stats = compute_statistics_from_greyscale(grey)
        entries.append({
            "name": name,
            "file": f"{name}.png",
            "mode": img.mode,
            "width": img.size[0],
            "height": img.size[1],
            "stats": {k: float(v) for k, v in stats.items()},
            "verdict": classify_verdict(stats),
        })
        print(f"{name}: {img.mode} {img.size[0]}x{img.size[1]} -> {entries[-1]['verdict']}")

    (HERE / "manifest.json").write_text(json.dumps({
        "pillow": __import__("PIL").__version__,
        "numpy": np.__version__,
        "detector_version": detector_version(),
        "note": "Golden values for the frame substance detector. See regenerate-fixtures.py.",
        "images": entries,
    }, indent=1) + "\n")
    print(f"\nwrote manifest for {len(entries)} images, detector {detector_version()}")


if __name__ == "__main__":
    main()
