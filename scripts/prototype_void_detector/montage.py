"""PROTOTYPE — THROWAWAY. Ticket #277.

Contact sheets for visual ground truth. Each tile is shown twice: as-is and
auto-stretched to full range, because a void frame and a night photograph look
identical at native exposure — the stretch is what reveals whether a subject is
present at all.

    .venv/bin/python scripts/prototype_void_detector/montage.py <sql-where> <out.png> [limit]
"""

from __future__ import annotations

import os
import sqlite3
import sys

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRATCH_DB = os.path.join(REPO, "scripts/prototype_void_detector/PROTOTYPE-wipe-me.db")

TILE = 190
PAD = 4
LABEL_H = 26
COLS = 6


def stretched(path: str) -> tuple[Image.Image, Image.Image]:
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        rgb.thumbnail((TILE, TILE))
        a = np.asarray(rgb, dtype=np.float32)
    lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.9)
    if hi - lo < 1e-3:
        hi = lo + 1e-3
    st = np.clip((a - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
    return rgb, Image.fromarray(st)


def main() -> int:
    where, out_path = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 60

    s = sqlite3.connect(SCRATCH_DB)
    s.row_factory = sqlite3.Row
    s.execute("ATTACH DATABASE 'file:%s?mode=ro' AS lib" % os.path.join(REPO, "library.db"))
    rows = s.execute(
        f"""
        SELECT st.key, st.entropy, st.lap_var, st.tile_max, st.black_frac_25,
               st.blown_frac_235, st.luma_mean, vc.compressed_path
        FROM stats st
        JOIN lib.vision_cache vc ON vc.key = st.key
        WHERE {where}
        LIMIT {limit}
        """
    ).fetchall()
    print(f"{len(rows)} tiles -> {out_path}")
    if not rows:
        return 1

    cell_w = TILE * 2 + PAD
    cell_h = TILE + LABEL_H
    ncols = COLS
    nrows = (len(rows) + ncols - 1) // ncols
    sheet = Image.new("RGB", (ncols * (cell_w + PAD), nrows * (cell_h + PAD)), (24, 24, 28))
    d = ImageDraw.Draw(sheet)

    for i, r in enumerate(rows):
        cx = (i % ncols) * (cell_w + PAD)
        cy = (i // ncols) * (cell_h + PAD)
        try:
            native, st = stretched(r["compressed_path"])
        except Exception as e:
            d.text((cx + 4, cy + 4), f"FAIL {r['key']}: {e}", fill=(255, 90, 90))
            continue
        sheet.paste(native, (cx, cy))
        sheet.paste(st, (cx + TILE + PAD, cy))
        d.text(
            (cx + 2, cy + TILE + 2),
            f"{r['key']}\nH={r['entropy']:.2f} L={r['lap_var']:.1f} "
            f"tmax={r['tile_max']:.0f} blk={r['black_frac_25']:.4f}",
            fill=(225, 225, 230),
        )
    sheet.save(out_path)
    print("saved", out_path, sheet.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
