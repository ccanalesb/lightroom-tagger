#!/usr/bin/env python3
"""Generate a read-only offline comparison-pool HTML report.

Run with:
    python -m lightroom_tagger.scripts.generate_comparison_pool_report --out ./pool-report

Large catalogs can produce large output folders when --limit is omitted.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sqlite3
from pathlib import Path

from PIL import Image

from lightroom_tagger.core.analyzer.image_prep import RAW_EXTENSIONS
from lightroom_tagger.core.clip_similarity import shortlist_catalog_candidates_by_clip
from lightroom_tagger.core.database import (
    catalog_key_is_primary_grid_row,
    fetch_comparison_pool_snapshot_bundle,
    get_rejected_pairs,
    init_database,
    list_comparison_pool_report_targets,
)
from lightroom_tagger.core.matcher.candidates import find_candidates_by_date
from lightroom_tagger.core.path_utils import resolve_catalog_path

_DEFAULT_CLIP_TOP_K_REPORT = 50
_SAFE_ASSET_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def _sha(text: str, chars: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:chars]


def _sha12(text: str) -> str:
    return _sha(text, 12)


def _sha8(text: str) -> str:
    return _sha(text, 8)


def _e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def compress_image_to_jpeg(
    src: str,
    dest: str,
    *,
    max_dim: int = 512,
    quality: int = 82,
) -> bool:
    """Write a compressed baseline JPEG, returning False for missing/unreadable input."""
    try:
        if not src or not Path(src).exists():
            return False
        viewable_path = _report_viewable_path(src)
        if not viewable_path:
            return False
        with Image.open(viewable_path) as img:
            if img.width > max_dim or img.height > max_dim:
                ratio = max_dim / max(img.width, img.height)
                new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(dest, format="JPEG", quality=quality, optimize=True)
            return True
    except Exception:
        return False


def _report_viewable_path(src: str) -> str | None:
    """Return a viewable source image for reports without slow RAW conversion."""
    ext = os.path.splitext(src)[1].lower()
    if ext not in RAW_EXTENSIONS:
        return src
    for suffix in (".JPG", ".jpg", ".JPEG", ".jpeg"):
        sidecar = src.rsplit(".", 1)[0] + suffix
        if Path(sidecar).exists():
            return sidecar
    return None


def safe_asset_name(insta_key: str, catalog_key: str, rank: int) -> str:
    """Deterministic safe JPEG asset name for one catalog candidate tile."""
    name = f"ig_{_sha12(insta_key)}_r{rank}_{_sha8(catalog_key)}.jpg"
    if not _SAFE_ASSET_RE.match(name):
        raise ValueError(f"unsafe asset name generated: {name!r}")
    return name


def _asset_ref(path: Path) -> str:
    return f"assets/{path.name}"


def _compress_asset(src: str | None, dest: Path) -> str | None:
    if dest.exists():
        return _asset_ref(dest)
    if src and compress_image_to_jpeg(src, str(dest)):
        return _asset_ref(dest)
    return None


def _render_snapshot_diagnostics(parent: dict | None) -> str:
    if not parent:
        return ""
    try:
        diagnostics = json.loads(parent.get("diagnostics_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        diagnostics = {}
    if not diagnostics:
        return ""

    rows = [
        ("date window candidates", diagnostics.get("date_window_count")),
        ("rejected pair drops", diagnostics.get("rejected_filtered_count")),
        ("non-representative drops", diagnostics.get("non_representative_filtered_count")),
        ("CLIP input", diagnostics.get("clip_input_count")),
        ("CLIP output", diagnostics.get("clip_output_count")),
        ("vision candidates", diagnostics.get("vision_candidate_count")),
    ]
    table_rows = "".join(
        f"<tr><th>{_e(label)}</th><td>{_e(value)}</td></tr>"
        for label, value in rows
        if value is not None
    )
    dropped_keys = {
        "rejected_filtered_keys": diagnostics.get("rejected_filtered_keys") or [],
        "non_representative_filtered_keys": diagnostics.get("non_representative_filtered_keys") or [],
        "clip_output_keys": diagnostics.get("clip_output_keys") or [],
    }
    debug = "\n".join(
        f"{label}: {', '.join(map(str, values))}"
        for label, values in dropped_keys.items()
        if values
    )
    debug_html = f"<pre>{_e(debug)}</pre>" if debug else ""
    return (
        '<details class="lt-diagnostics">'
        "<summary>Pipeline diagnostics</summary>"
        f"<table>{table_rows}</table>"
        f"{debug_html}"
        "</details>"
    )


def _catalog_filepath(db: sqlite3.Connection, catalog_key: str) -> str:
    row = db.execute("SELECT filepath FROM images WHERE key = ?", (catalog_key,)).fetchone()
    if row is None:
        return ""
    return resolve_catalog_path(row.get("filepath") or "")


def reconstruct_vision_pool_for_report(
    db: sqlite3.Connection,
    dump_media: dict,
    *,
    clip_top_k: int,
) -> list[dict]:
    """Best-effort read-only reconstruction of the current candidate pool."""
    candidates = find_candidates_by_date(db, dump_media, days_before=90)
    rejected = get_rejected_pairs(db)
    if rejected:
        media_key = dump_media.get("media_key")
        candidates = [
            c for c in candidates if (c.get("key"), media_key) not in rejected
        ]
    candidates = [
        c
        for c in candidates
        if c.get("key") and catalog_key_is_primary_grid_row(db, c["key"])
    ]
    cand_keys = [c["key"] for c in candidates if c.get("key")]
    short_keys = shortlist_catalog_candidates_by_clip(
        db,
        dump_media["media_key"],
        cand_keys,
        clip_top_k,
    )
    row_by_key = {c["key"]: c for c in candidates if c.get("key")}
    out = []
    for key in short_keys:
        catalog_img = row_by_key.get(key)
        if not catalog_img:
            continue
        out.append(
            {
                "key": key,
                "local_path": resolve_catalog_path(catalog_img.get("filepath", "")),
            }
        )
    return out


def _score_cell(value: object) -> str:
    return "n/a (reconstructed)" if value is None else _e(value)


def _render_candidate_tile(
    *,
    insta_key: str,
    child: dict,
    assets_dir: Path,
    db: sqlite3.Connection,
    reconstructed: bool,
) -> tuple[str, str]:
    catalog_key = str(child.get("catalog_key") or child.get("key") or "")
    rank = int(child.get("rank") or 0)
    if reconstructed:
        catalog_path = child.get("local_path") or ""
    else:
        catalog_path = (
            child.get("asset_path")
            or child.get("source_path")
            or child.get("debug_resolved_path")
            or _catalog_filepath(db, catalog_key)
        )
    asset_name = safe_asset_name(insta_key, catalog_key, rank)
    asset_ref = _compress_asset(catalog_path, assets_dir / asset_name)

    if asset_ref:
        image_html = (
            f'<img src="{_e(asset_ref)}" alt="Catalog candidate {_e(catalog_key)}">'
        )
    else:
        image_html = '<div class="lt-missing-image">image unavailable</div>'

    rows = [
        ("rank", rank),
        ("catalog_key", catalog_key),
        ("total_score", child.get("total_score")),
        ("phash_distance", child.get("phash_distance")),
        ("phash_score", child.get("phash_score")),
        ("desc_similarity", child.get("desc_similarity")),
        ("vision_result", child.get("vision_result")),
        ("vision_score", child.get("vision_score")),
        ("model_used", child.get("model_used")),
        ("rate_limited", child.get("rate_limited")),
    ]
    table_rows = "".join(
        f"<tr><th>{_e(label)}</th><td>{_score_cell(value)}</td></tr>"
        for label, value in rows
    )
    tile = (
        '<article class="lt-candidate-card">'
        f"{image_html}"
        "<table>"
        f"{table_rows}"
        "</table>"
        "</article>"
    )

    debug = ""
    if not reconstructed:
        debug = (
            '<details class="lt-pool-debug">'
            f"<summary>{_e(catalog_key)} debug</summary>"
            f"<p><strong>captured_asset_path:</strong> {_e(child.get('asset_path'))}</p>"
            f"<p><strong>source_available:</strong> {_e(child.get('source_available'))}</p>"
            f"<p><strong>source_path:</strong> {_e(child.get('source_path'))}</p>"
            f"<p><strong>debug_resolved_path:</strong> {_e(child.get('debug_resolved_path'))}</p>"
            f"<pre>{_e(child.get('vision_reasoning'))}</pre>"
            "</details>"
        )
    return tile, debug


def write_comparison_pool_report(
    out_dir: str,
    db: sqlite3.Connection,
    *,
    month: str | None,
    job_id: str | None,
    media_key: str | None,
    limit: int | None,
) -> Path:
    """Write report.html and assets/ for unmatched attempted Instagram rows."""
    out_path = Path(out_dir)
    assets_dir = out_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    rows = list_comparison_pool_report_targets(
        db,
        month=month,
        job_id=job_id,
        media_key=media_key,
        limit=limit,
    )

    cards: list[str] = []
    debug_panels: list[str] = []
    for row in rows:
        insta_key = str(row["media_key"])
        parent, children = fetch_comparison_pool_snapshot_bundle(
            db,
            insta_key,
            source_job_id=job_id,
        )
        reconstructed = parent is None
        if reconstructed:
            children = [
                {
                    "rank": idx,
                    "key": candidate["key"],
                    "local_path": candidate.get("local_path"),
                }
                for idx, candidate in enumerate(
                    reconstruct_vision_pool_for_report(
                        db,
                        row,
                        clip_top_k=_DEFAULT_CLIP_TOP_K_REPORT,
                    )
                )
            ]

        ig_asset = assets_dir / f"ig_insta_{_sha12(insta_key)}.jpg"
        ig_src = parent.get("insta_asset_path") if parent else None
        ig_ref = _compress_asset(ig_src or row.get("file_path"), ig_asset)
        if ig_ref:
            ig_html = f'<img src="{_e(ig_ref)}" alt="Instagram {_e(insta_key)}">'
        else:
            ig_html = '<div class="lt-missing-image">instagram image unavailable</div>'

        banner = ""
        if reconstructed:
            banner = '<p class="lt-reconstructed">Reconstructed — not exact run evidence</p>'
            # PHASE19_RECONSTRUCT_HOOK implemented by reconstruct_vision_pool_for_report.
        elif parent:
            banner = (
                '<p class="lt-snapshot-meta">'
                f"Snapshot {_e(parent.get('snapshot_id'))} captured {_e(parent.get('captured_at'))}"
                "</p>"
            )

        candidate_tiles = []
        for child in children:
            tile, debug = _render_candidate_tile(
                insta_key=insta_key,
                child=child,
                assets_dir=assets_dir,
                db=db,
                reconstructed=reconstructed,
            )
            candidate_tiles.append(tile)
            if debug:
                debug_panels.append(debug)

        if not candidate_tiles and reconstructed:
            candidate_tiles.append(
                '<div class="lt-empty-pool">Reconstructed — not exact run evidence</div>'
            )

        cards.append(
            '<section class="lt-pool-card">'
            f"{banner}"
            f"<h2>{_e(insta_key)}</h2>"
            f"{_render_snapshot_diagnostics(parent)}"
            '<div class="lt-instagram-preview">'
            f"{ig_html}"
            "</div>"
            '<div class="lt-candidate-grid">'
            f"{''.join(candidate_tiles)}"
            "</div>"
            "</section>"
        )

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        "<title>Comparison Pool Report</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 24px; background: #f5f5f5; color: #222; }",
        ".lt-summary, .lt-pool-card, .lt-debug-appendix { background: #fff; border-radius: 10px; padding: 18px; margin: 18px 0; box-shadow: 0 1px 4px rgba(0,0,0,0.12); }",
        ".lt-candidate-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }",
        ".lt-candidate-card { border: 1px solid #ddd; border-radius: 8px; padding: 10px; background: #fafafa; }",
        ".lt-candidate-card img, .lt-instagram-preview img { max-width: 100%; height: auto; border-radius: 6px; }",
        ".lt-candidate-card table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }",
        ".lt-candidate-card th { text-align: left; color: #555; width: 42%; }",
        ".lt-candidate-card td { word-break: break-word; }",
        ".lt-reconstructed { background: #fff3cd; border: 1px solid #ffe08a; padding: 8px; border-radius: 6px; font-weight: bold; }",
        ".lt-missing-image, .lt-empty-pool { background: #eee; color: #666; padding: 24px; border-radius: 6px; text-align: center; }",
        ".lt-pool-debug { margin: 10px 0; }",
        "pre { white-space: pre-wrap; overflow-wrap: anywhere; }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>Comparison Pool Report</h1>",
        '<div class="lt-summary">',
        f"<p>Rows: {_e(len(rows))}</p>",
        f"<p>Filters: month={_e(month)} job_id={_e(job_id)} media_key={_e(media_key)} limit={_e(limit)}</p>",
        "</div>",
        '<main id="lt-primary-comparison-pool">',
        *cards,
        "</main>",
    ]
    if debug_panels:
        html_parts.extend(
            [
                '<section class="lt-debug-appendix">',
                "<h2>Hidden Debug Evidence</h2>",
                *debug_panels,
                "</section>",
            ]
        )
    html_parts.extend(["</body>", "</html>"])

    html_path = out_path / "report.html"
    html_path.write_text("\n".join(html_parts), encoding="utf-8")
    return html_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Generate read-only offline comparison-pool HTML report'
    )
    parser.add_argument("--db", default="library.db")
    parser.add_argument("--out", required=True, type=str)
    parser.add_argument("--month", type=str)
    parser.add_argument("--job-id", dest="job_id", type=str)
    parser.add_argument("--media-key", type=str)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    db = init_database(args.db)
    try:
        html_path = write_comparison_pool_report(
            args.out,
            db,
            month=args.month,
            job_id=args.job_id,
            media_key=args.media_key,
            limit=args.limit,
        )
    finally:
        db.close()
    print(f"Wrote {html_path}")


if __name__ == "__main__":
    main()
