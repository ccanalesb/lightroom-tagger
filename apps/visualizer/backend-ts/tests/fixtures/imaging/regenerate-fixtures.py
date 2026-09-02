#!/usr/bin/env python3
"""Regenerate the golden files that pin our Pillow-exact resampler.

NOT part of the runtime. The backend is pure TypeScript; this script exists only so
the golden files can be reproduced and audited, and it is the one place Pillow is
still allowed to appear. Run it by hand after a deliberate Pillow upgrade:

    ../../../../../.venv/bin/python regenerate-fixtures.py

Images are synthetic and deterministic — gradients, high-frequency checkerboards and
pseudo-random noise from a fixed seed — chosen to exercise the filter edges. Nothing
from the user's catalog is committed here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import scipy.fftpack
from PIL import Image

HERE = Path(__file__).parent
BICUBIC = Image.Resampling.BICUBIC
LANCZOS = Image.Resampling.LANCZOS


def make_images() -> dict[str, Image.Image]:
    """Deterministic sources. Sizes deliberately include odd and non-square cases."""
    out: dict[str, Image.Image] = {}

    # Smooth diagonal gradient — catches systematic coefficient error.
    h, w = 137, 251
    yy, xx = np.mgrid[0:h, 0:w]
    grad = np.stack([
        (xx * 255 // (w - 1)).astype(np.uint8),
        (yy * 255 // (h - 1)).astype(np.uint8),
        ((xx + yy) * 255 // (w + h - 2)).astype(np.uint8),
    ], axis=-1)
    out["gradient_251x137"] = Image.fromarray(grad, "RGB")

    # 1px checkerboard — worst case for a resampling kernel; any phase error shows.
    h, w = 96, 96
    yy, xx = np.mgrid[0:h, 0:w]
    check = np.where(((xx + yy) % 2) == 0, 255, 0).astype(np.uint8)
    out["checker_96x96"] = Image.fromarray(np.stack([check] * 3, axis=-1), "RGB")

    # Fixed-seed noise — exercises negative lobes and the clamp at both ends.
    rng = np.random.default_rng(20260902)
    out["noise_160x107"] = Image.fromarray(
        rng.integers(0, 256, size=(107, 160, 3), dtype=np.uint8), "RGB"
    )

    # Tiny image, to exercise upscaling and the edge-clamped support.
    out["tiny_7x5"] = Image.fromarray(
        np.array([[[(x * 37 + y * 91) % 256, (x * 13) % 256, (y * 53) % 256]
                   for x in range(7)] for y in range(5)], dtype=np.uint8), "RGB"
    )
    return out


def phash_hex(img: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    """imagehash.phash, inlined so the golden value does not depend on imagehash."""
    size = hash_size * highfreq_factor
    pixels = np.asarray(img.convert("L").resize((size, size), LANCZOS))
    dct = scipy.fftpack.dct(scipy.fftpack.dct(pixels, axis=0), axis=1)
    low = dct[:hash_size, :hash_size]
    diff = (low > np.median(low)).flatten()
    return "".join(
        f"{int(''.join('1' if b else '0' for b in diff[i:i + 4]), 2):x}"
        for i in range(0, len(diff), 4)
    )


def clip_pixel_values(img: Image.Image) -> np.ndarray:
    """CLIPImageProcessor for openai/clip-vit-base-patch32, written out explicitly."""
    mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float64)
    std = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float64)

    rgb = img.convert("RGB")
    w, h = rgb.size
    short, long_ = (w, h) if w <= h else (h, w)
    new_long = int(224 * long_ / short)
    new_w, new_h = (224, new_long) if w <= h else (new_long, 224)
    resized = rgb.resize((new_w, new_h), BICUBIC)

    left = (new_w - 224) // 2
    top = (new_h - 224) // 2
    cropped = np.asarray(resized.crop((left, top, left + 224, top + 224)), dtype=np.float64)

    norm = (cropped / 255.0 - mean) / std
    return np.transpose(norm, (2, 0, 1)).astype(np.float32)  # CHW


def main() -> None:
    manifest = []
    for name, img in make_images().items():
        img.save(HERE / f"{name}.png")
        w, h = img.size

        entry: dict = {"name": name, "width": w, "height": h, "resizes": []}

        # Downscale, upscale, square-ify, and the 32x32 used by phash.
        # PNG, not raw: lossless, so still bit-exact, but a fraction of the bytes.
        # Upscale target is a modest bump rather than 2x, to keep fixtures small
        # while still exercising the upscale path (filterscale clamped to 1.0).
        targets = [(224, 224), (32, 32), (w + 31, h + 17), (17, 41), (w, 60)]
        for filt_name, filt in (("bicubic", BICUBIC), ("lanczos", LANCZOS)):
            for (tw, th) in targets:
                fname = f"{name}.{filt_name}.{tw}x{th}.png"
                img.resize((tw, th), filt).save(HERE / fname, "PNG", optimize=True)
                entry["resizes"].append(
                    {"filter": filt_name, "width": tw, "height": th, "file": fname}
                )

        grey_img = img.convert("L")
        grey_img.save(HERE / f"{name}.grey.png", "PNG", optimize=True)
        entry["grey"] = f"{name}.grey.png"

        # The phash input path is greyscale-THEN-resize on a 1-channel plane, which
        # the RGB resize goldens above do not exercise. Pin it separately.
        entry["grey_resizes"] = []
        for filt_name, filt in (("lanczos", LANCZOS), ("bicubic", BICUBIC)):
            for (tw, th) in ((32, 32), (16, 9)):
                fname = f"{name}.grey.{filt_name}.{tw}x{th}.png"
                grey_img.resize((tw, th), filt).save(HERE / fname, "PNG", optimize=True)
                entry["grey_resizes"].append(
                    {"filter": filt_name, "width": tw, "height": th, "file": fname}
                )

        # Flag images whose DCT block is dominated by exact zeros. For those the
        # `coefficient > median` test is decided by floating-point cancellation
        # rather than by image content, so a bit-exact hash comparison across two
        # independent DCT implementations is meaningless. Synthetic periodic
        # patterns do this; photographs do not.
        small = np.asarray(grey_img.resize((32, 32), LANCZOS)).astype(np.float64)
        dct_full = scipy.fftpack.dct(scipy.fftpack.dct(small, axis=0), axis=1)
        low = dct_full[:8, :8]
        near_median = int(np.sum(np.isclose(low, np.median(low), atol=1e-9)))
        entry["dct_ties"] = near_median
        entry["phash_degenerate"] = near_median > 1
        entry["dct8"] = [float(v) for v in low.reshape(-1)]  # 64 values, inline

        # A float32 224x224x3 tensor is 602KB per image. Pin it by digest plus a
        # few spot values: the digest detects any bit of drift, and the resize that
        # produces it is already pinned bit-exactly by the goldens above.
        pv = clip_pixel_values(img)
        entry["clip_shape"] = list(pv.shape)
        entry["clip_sha256"] = hashlib.sha256(pv.tobytes()).hexdigest()
        flat = pv.reshape(-1)
        entry["clip_spot"] = {
            str(i): float(flat[i])
            for i in (0, 1, 12345, len(flat) // 2, len(flat) - 1)
        }

        entry["phash"] = phash_hex(img)
        manifest.append(entry)
        print(f"{name}: {w}x{h}, phash={entry['phash']}, {len(entry['resizes'])} resizes")

    (HERE / "manifest.json").write_text(json.dumps({
        "pillow": __import__("PIL").__version__,
        "note": "Golden files for the Pillow-exact resampler. See regenerate-fixtures.py.",
        "images": manifest,
    }, indent=1) + "\n")
    print(f"\nwrote manifest for {len(manifest)} images")


if __name__ == "__main__":
    main()
