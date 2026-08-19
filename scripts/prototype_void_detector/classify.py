"""PROTOTYPE — THROWAWAY. Ticket #277. The candidate detector + its measurement.

Structure copied from PhotoSi US11586669B2: brightness only *triggers* the
analysis; a separate structure statistic delivers the verdict. Thresholds
inherited from FFmpeg blackdetect (libavfilter/vf_blackdetect.c:64-73) with the
full-range constant, because our cached previews are full-range JPEG.

    .venv/bin/python scripts/prototype_void_detector/classify.py
"""

from __future__ import annotations

import os
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRATCH_DB = os.path.join(REPO, "scripts/prototype_void_detector/PROTOTYPE-wipe-me.db")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from labels import CLASS_B_SEED, HARD_NEGATIVES  # noqa: E402

# --- Trigger: inherited, unmodified -----------------------------------------
BLACK_PIXEL_TH = 25       # 0.10 * 255, full-range JPEG (FFmpeg's 0.10 pixel_black_th)
BLACK_AREA_TH = 0.98      # FFmpeg picture_black_ratio_th; corroborated by Dolby
BLOWN_PIXEL_TH = 235      # ITU-R BT.601/709 nominal white
BLOWN_AREA_TH = 0.98      # symmetric with the black side

# --- Verdict: measured on this catalog, not inherited -----------------------
# Tier A ("void"): no spatial structure of any kind. lap_var is ~0 only for a
# frame that is flat to the sensor's noise floor; tile_max <= 1.6 means not one
# 1/32-scale tile is even dimly lit.
VOID_LAP_VAR = 0.10
VOID_TILE_MAX = 1.6

# Tier B ("illegible"): structure exists but no legible subject. All three must
# hold. Margins against the nearest surviving keeper are reported below.
ILLEGIBLE_ENTROPY = 1.05  # nearest keeper: L1007465 at 1.08
ILLEGIBLE_TILE_MAX = 20.0  # nearest keeper: DSF6319 at 42.8
ILLEGIBLE_LAP_VAR = 20.0  # nearest keeper: L1006700 at 13.4 -> see report


def verdict(r: dict) -> str:
    """Return 'void' | 'illegible' | 'ok'. 'unknown' is assigned upstream."""
    triggered_dark = r["black_frac_25"] >= BLACK_AREA_TH
    triggered_blown = r["blown_frac_235"] >= BLOWN_AREA_TH
    if not (triggered_dark or triggered_blown):
        return "ok"
    if r["lap_var"] < VOID_LAP_VAR or r["tile_max"] <= VOID_TILE_MAX:
        return "void"
    if triggered_blown:
        # Blown side: no locally-dark structure to measure, so entropy alone.
        return "illegible" if r["entropy"] < ILLEGIBLE_ENTROPY else "ok"
    if (
        r["entropy"] < ILLEGIBLE_ENTROPY
        and r["tile_max"] < ILLEGIBLE_TILE_MAX
        and r["lap_var"] < ILLEGIBLE_LAP_VAR
    ):
        return "illegible"
    return "ok"


def main() -> int:
    s = sqlite3.connect(SCRATCH_DB)
    s.row_factory = sqlite3.Row
    s.execute(f"ATTACH DATABASE 'file:{os.path.join(REPO, 'library.db')}?mode=ro' AS lib")

    rows = [dict(r) for r in s.execute("SELECT * FROM stats")]
    for r in rows:
        r["verdict"] = verdict(r)

    s.execute("DROP TABLE IF EXISTS verdicts")
    s.execute("CREATE TABLE verdicts (key TEXT PRIMARY KEY, verdict TEXT)")
    s.executemany(
        "INSERT INTO verdicts VALUES (?,?)", [(r["key"], r["verdict"]) for r in rows]
    )
    unknown = s.execute("SELECT key FROM unknown").fetchall()
    s.executemany(
        "INSERT OR REPLACE INTO verdicts VALUES (?,'unknown')", [(u["key"],) for u in unknown]
    )
    s.commit()

    n = len(rows)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(f"measured {n}  +unknown {len(unknown)}  = {n + len(unknown)}")
    for k in ("void", "illegible", "ok"):
        c = counts.get(k, 0)
        print(f"  {k:<10} {c:>6}  ({100 * c / (n + len(unknown)):.3f}%)")
    print(f"  {'unknown':<10} {len(unknown):>6}  ({100 * len(unknown) / (n + len(unknown)):.3f}%)")

    by_key = {r["key"]: r for r in rows}
    print("\n--- acceptance: the four motivating frames ---")
    for k in CLASS_B_SEED:
        print(f"  {k}  -> {by_key[k]['verdict']}")
    print("--- acceptance: hard negatives (must be 'ok') ---")
    ok = True
    for k in HARD_NEGATIVES:
        v = by_key[k]["verdict"]
        ok &= v == "ok"
        print(f"  {k}  -> {v}{'' if v == 'ok' else '   <-- FALSE POSITIVE'}")
    print(f"  all hard negatives survive: {ok}")

    print("\n--- margin to the nearest surviving keeper, per axis ---")
    flagged = [r for r in rows if r["verdict"] in ("void", "illegible")]
    survivors = [r for r in rows if r["verdict"] == "ok" and r["black_frac_25"] >= 0.98]
    for axis, worst in (("entropy", max), ("tile_max", max), ("lap_var", max)):
        f = worst(r[axis] for r in flagged)
        nearest = min(
            (r for r in survivors), key=lambda r, a=axis: abs(r[a] - f)
        )
        print(
            f"  {axis:<10} highest flagged {f:8.2f}   nearest surviving keeper "
            f"{nearest[axis]:8.2f}  ({nearest['key']})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
