"""Candidate discovery (EXIF and date-window SQL queries over catalog rows)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from lightroom_tagger.core.analyzer import VIDEO_EXTENSIONS
from lightroom_tagger.core.database import _deserialize_row


def query_by_exif(db, insta_exif: dict, date_window_days: int = 7) -> list[dict]:
    """Query catalog by EXIF (camera, lens, date within window)."""
    camera = insta_exif.get('camera')
    lens = insta_exif.get('lens')

    if not camera and not lens:
        return []

    if camera and lens:
        sql = (
            "SELECT * FROM images WHERE "
            "json_extract(exif, '$.camera') = ? AND json_extract(exif, '$.lens') = ?"
        )
        params = (camera, lens)
    elif camera:
        sql = "SELECT * FROM images WHERE json_extract(exif, '$.camera') = ?"
        params = (camera,)
    else:
        sql = "SELECT * FROM images WHERE json_extract(exif, '$.lens') = ?"
        params = (lens,)

    rows = db.execute(sql, params).fetchall()
    return [_deserialize_row(r) for r in rows]


def find_candidates_by_date(db, insta_image: dict, days_before: int = 90) -> list:
    """Find catalog candidates within date window before Instagram posting."""
    date_folder = insta_image.get('date_folder', '')
    if len(date_folder) != 6:
        return []

    post_year = int(date_folder[:4])
    post_month = int(date_folder[4:6])
    post_date = datetime(post_year, post_month, 15)
    window_start = post_date - timedelta(days=days_before)

    candidates = []
    sql = (
        "SELECT i.*, COALESCE(d.summary, '') AS ai_summary "
        "FROM images i "
        "LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog' "
        "WHERE i.instagram_posted = 0"
    )
    for row in db.execute(sql).fetchall():
        row_dict = dict(row)
        img = _deserialize_row(row_dict)
        img["ai_summary"] = str(row_dict.get("ai_summary") or "")
        filepath = img.get('filepath', '')
        if filepath:
            ext = os.path.splitext(filepath)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                continue
        date_taken = img.get('date_taken', '')
        if not date_taken:
            continue
        try:
            img_date = datetime.fromisoformat(date_taken.replace('Z', '+00:00'))
            if window_start <= img_date <= post_date:
                candidates.append(img)
        except Exception:
            continue

    candidates.sort(key=lambda c: c.get('date_taken', ''), reverse=True)
    return candidates
