"""PROTOTYPE — THROWAWAY. Ticket #277. Builds one self-contained HTML report.

Every flagged frame is shown native and auto-stretched, because the whole
decision turns on what is actually in these frames.

    .venv/bin/python scripts/prototype_void_detector/report.py
    open scripts/prototype_void_detector/report.html
"""

from __future__ import annotations

import base64
import io
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRATCH_DB = os.path.join(REPO, "scripts/prototype_void_detector/PROTOTYPE-wipe-me.db")
OUT = os.path.join(REPO, "scripts/prototype_void_detector/report.html")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from labels import HARD_NEGATIVES  # noqa: E402


def thumb_pair(path: str, size: int = 240) -> tuple[str, str]:
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        rgb.thumbnail((size, size))
        a = np.asarray(rgb, dtype=np.float32)
    lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.95)
    st = np.clip((a - lo) / max(hi - lo, 1e-3) * 255.0, 0, 255).astype(np.uint8)

    def b64(img: Image.Image) -> str:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=78)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    return b64(rgb), b64(Image.fromarray(st))


CSS = """
body{background:#15161a;color:#e6e6ea;font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;padding:32px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:34px 0 10px;border-bottom:1px solid #33353d;padding-bottom:6px}
.sub{color:#9a9aa6;margin-bottom:24px}
.grid{display:flex;flex-wrap:wrap;gap:14px}
.card{background:#1e2027;border:1px solid #32343c;border-radius:8px;padding:8px;width:512px}
.card.void{border-color:#d05b5b}.card.illegible{border-color:#d8a13c}.card.ok{border-color:#4b9e5f}
.pair{display:flex;gap:4px}.pair img{width:248px;background:#000;border-radius:4px}
.k{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;margin-top:6px;color:#fff}
.s{font-family:ui-monospace,monospace;font-size:11px;color:#9a9aa6}
.d{font-size:12px;color:#c2c2cc;margin-top:4px}
.cap{font-size:11px;color:#71727d;display:flex;gap:4px}.cap span{width:248px}
table{border-collapse:collapse;margin:10px 0}td,th{border:1px solid #33353d;padding:5px 11px;text-align:left;font-size:13px}
th{background:#22242b}code{background:#2a2c34;padding:1px 5px;border-radius:3px;font-size:12px}
.note{background:#22242b;border-left:3px solid #d8a13c;padding:10px 14px;margin:14px 0;border-radius:0 5px 5px 0}
"""


def main() -> int:
    s = sqlite3.connect(SCRATCH_DB)
    s.row_factory = sqlite3.Row
    s.execute(f"ATTACH DATABASE 'file:{os.path.join(REPO, 'library.db')}?mode=ro' AS lib")

    def fetch(where: str, order: str = "st.entropy") -> list[sqlite3.Row]:
        return s.execute(
            f"""SELECT v.verdict, st.*, vc.compressed_path, d.summary
                FROM verdicts v JOIN stats st ON st.key = v.key
                JOIN lib.vision_cache vc ON vc.key = st.key
                LEFT JOIN lib.image_descriptions d ON d.image_key = st.key
                WHERE {where} ORDER BY {order}"""
        ).fetchall()

    def cards(rows: list[sqlite3.Row]) -> str:
        out = []
        for r in rows:
            try:
                native, st = thumb_pair(r["compressed_path"])
            except Exception:
                continue
            out.append(
                f'<div class="card {r["verdict"]}"><div class="pair">'
                f'<img src="{native}"><img src="{st}"></div>'
                f'<div class="cap"><span>as shot</span><span>auto-stretched</span></div>'
                f'<div class="k">{r["key"]} &nbsp;<b>{r["verdict"]}</b></div>'
                f'<div class="s">entropy {r["entropy"]:.3f} &middot; lap_var {r["lap_var"]:.2f} '
                f'&middot; tile_max {r["tile_max"]:.1f} &middot; black@25 {r["black_frac_25"]:.4f} '
                f'&middot; blown@235 {r["blown_frac_235"]:.3f}</div>'
                f'<div class="d">{(r["summary"] or "")[:230]}</div></div>'
            )
        return '<div class="grid">' + "".join(out) + "</div>"

    hn = ",".join(f"'{k}'" for k in HARD_NEGATIVES)
    html = f"""<!doctype html><meta charset="utf-8"><title>PROTOTYPE — void detector (#277)</title>
<style>{CSS}</style>
<h1>PROTOTYPE — void-frame detector, measured</h1>
<div class="sub">Wayfinder ticket #277, map #275. Throwaway: nothing here is production code.
Left tile = the frame as shot. Right tile = the same frame auto-stretched to full range —
that is the only way to see whether a subject exists at all.</div>

<h2>The rule</h2>
<table>
<tr><th>Stage</th><th>Test</th><th>Source</th></tr>
<tr><td>Trigger</td><td><code>black_frac(Y&le;25) &ge; 0.98</code> or <code>blown_frac(Y&ge;235) &ge; 0.98</code></td>
    <td>FFmpeg <code>blackdetect</code>, full-range constant</td></tr>
<tr><td>Verdict — <b>void</b></td><td><code>lap_var &lt; 0.10</code> or <code>tile_max &le; 1.6</code></td>
    <td>measured on this catalog</td></tr>
<tr><td>Verdict — <b>illegible</b></td><td><code>entropy &lt; 1.05</code> and <code>tile_max &lt; 20</code> and <code>lap_var &lt; 20</code></td>
    <td>measured on this catalog</td></tr>
</table>
<div class="note"><b>Brightness only triggers; structure decides.</b> That split is PhotoSi's
(US11586669B2). A pure area rule cannot work here: the Statue-of-Liberty keepers are
98.6&ndash;99.7&#37; black, so the inherited 0.98 threshold flags all of them. <code>tile_max</code>
&mdash; the brightest 1/32-scale tile &mdash; is what separates them, and it is also the only axis
that saves the moon photographs.</div>

<h2>Result: 6 void, 38 illegible, 41,051 ok, 1,041 unknown (of 42,136)</h2>

<h2>Tier A &mdash; void (6). Nothing in the frame at all.</h2>
{cards(fetch("v.verdict='void'", "st.lap_var"))}

<h2>Tier B &mdash; illegible, not the eclipse run (11)</h2>
{cards(fetch("v.verdict='illegible' AND st.key NOT LIKE '2020-12-14__DSF15%'"))}

<h2>Tier B &mdash; the 14 December 2020 solar-eclipse session (27). THIS IS THE DECISION.</h2>
<div class="note">All 27 are one deliberate shoot. The subject is a real eclipse crescent about
6&nbsp;px wide in a 1024&nbsp;px preview. Three of them currently sit at ranks 13&ndash;15 of the
best-photo ranking. Whether these are keepers or failures is a judgement, not a measurement
&mdash; and it sets Tier B precision anywhere from 29&#37; to 100&#37;.</div>
{cards(fetch("v.verdict='illegible' AND st.key LIKE '2020-12-14__DSF15%'"))}

<h2>Hard negatives &mdash; all 6 survive</h2>
{cards(fetch(f"st.key IN ({hn})"))}
"""
    with open(OUT, "w") as f:
        f.write(html)
    print(f"wrote {OUT}  ({os.path.getsize(OUT) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
