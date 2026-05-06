"""Catalog ↔ Instagram match rows and validation."""

from __future__ import annotations

import sqlite3
from datetime import datetime


def catalog_has_instagram_match_conflict(
    db: sqlite3.Connection, catalog_key: str, insta_key: str
) -> bool:
    """True when *catalog_key* already has a library match to a different Instagram key."""
    row = db.execute(
        """
        SELECT 1 FROM matches
        WHERE catalog_key = ? AND insta_key IS NOT NULL AND insta_key != ?
        LIMIT 1
        """,
        (catalog_key, insta_key),
    ).fetchone()
    return row is not None


def apply_instagram_match_to_stack_members(
    db: sqlite3.Connection,
    *,
    insta_key: str,
    representative_key: str,
    template: dict,
    commit: bool = True,
) -> dict:
    """Persist matches for non-representative stack members from a rep-level template.

    The representative's match row(s) are stored by the caller. This function adds
    rows for other members, skipping members that already match a different
    ``insta_key`` (non-destructive).

    Returns:
        ``applied_count``, ``skipped_conflicts_count``, ``skipped_other_count``,
        and ``lightroom_catalog_keys`` (representative plus applied members; used
        for Lightroom keyword writes).
    """
    from .stacks import list_catalog_stack_member_keys

    members = list_catalog_stack_member_keys(db, representative_key)
    applied = 0
    skipped_conflicts = 0
    skipped_other = 0
    lightroom_catalog_keys: list[str] = [representative_key]

    for member_key in members:
        if member_key == representative_key:
            continue
        if catalog_has_instagram_match_conflict(db, member_key, insta_key):
            skipped_conflicts += 1
            continue
        exists_row = db.execute(
            "SELECT 1 FROM images WHERE key = ? LIMIT 1",
            (member_key,),
        ).fetchone()
        if not exists_row:
            skipped_other += 1
            continue

        rec = {
            "catalog_key": member_key,
            "insta_key": insta_key,
            "phash_distance": template.get("phash_distance"),
            "phash_score": template.get("phash_score"),
            "desc_similarity": template.get("desc_similarity"),
            "vision_result": template.get("vision_result"),
            "vision_score": template.get("vision_score"),
            "total_score": template.get("total_score"),
            "model_used": template.get("model_used"),
            "rank": template.get("rank", 1),
            "vision_reasoning": template.get("vision_reasoning"),
        }
        store_match(db, rec, commit=False)
        applied += 1
        lightroom_catalog_keys.append(member_key)

    if commit:
        db.commit()

    return {
        "applied_count": applied,
        "skipped_conflicts_count": skipped_conflicts,
        "skipped_other_count": skipped_other,
        "lightroom_catalog_keys": lightroom_catalog_keys,
    }


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

def init_matches_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def delete_matches_for_insta_key(db: sqlite3.Connection, insta_key: str,
                                  commit: bool = True) -> None:
    """Remove all match rows for an Instagram key (e.g. before replacing candidate set)."""
    db.execute("DELETE FROM matches WHERE insta_key = ?", (insta_key,))
    if commit:
        db.commit()


def store_match(db: sqlite3.Connection, record: dict, commit: bool = True) -> str:
    """Store match between catalog and Instagram image."""
    catalog_key = record.get('catalog_key')
    insta_key = record.get('insta_key')
    record['matched_at'] = datetime.now().isoformat()

    db.execute("""
        INSERT INTO matches (catalog_key, insta_key, phash_distance, phash_score,
            desc_similarity, vision_result, vision_score, total_score, matched_at,
            model_used, rank, vision_reasoning)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalog_key, insta_key) DO UPDATE SET
            phash_distance=excluded.phash_distance, phash_score=excluded.phash_score,
            desc_similarity=excluded.desc_similarity, vision_result=excluded.vision_result,
            vision_score=excluded.vision_score, total_score=excluded.total_score,
            matched_at=excluded.matched_at, model_used=excluded.model_used,
            rank=excluded.rank, vision_reasoning=excluded.vision_reasoning
    """, (
        catalog_key, insta_key, record.get('phash_distance'),
        record.get('phash_score'), record.get('desc_similarity'),
        record.get('vision_result'), record.get('vision_score'),
        record.get('total_score'), record['matched_at'],
        record.get('model_used'), record.get('rank', 1),
        record.get('vision_reasoning'),
    ))
    if commit:
        db.commit()
    return f"{catalog_key} <-> {insta_key}"


def _backfill_instagram_created_at_from_catalog(
    db: sqlite3.Connection, catalog_key: str, insta_key: str
) -> None:
    """If catalog has date_taken and Instagram side has no created_at, copy it (D-12)."""
    cat = db.execute(
        "SELECT date_taken FROM images WHERE key = ?", (catalog_key,)
    ).fetchone()
    if not cat:
        return
    raw_dt = cat.get("date_taken")
    if raw_dt is None or (isinstance(raw_dt, str) and not raw_dt.strip()):
        return
    date_val = raw_dt.strip() if isinstance(raw_dt, str) else str(raw_dt)

    insta_img = db.execute(
        "SELECT key, created_at FROM instagram_images WHERE key = ? LIMIT 1",
        (insta_key,),
    ).fetchone()
    if insta_img is not None:
        ca = insta_img.get("created_at")
        if ca is None or (isinstance(ca, str) and not str(ca).strip()):
            db.execute(
                "UPDATE instagram_images SET created_at = ? WHERE key = ?",
                (date_val, insta_key),
            )
        return

    dump = db.execute(
        "SELECT media_key, created_at FROM instagram_dump_media WHERE media_key = ? LIMIT 1",
        (insta_key,),
    ).fetchone()
    if dump is None:
        return
    ca = dump.get("created_at")
    if ca is None or (isinstance(ca, str) and not str(ca).strip()):
        db.execute(
            "UPDATE instagram_dump_media SET created_at = ? WHERE media_key = ?",
            (date_val, insta_key),
        )


def validate_match(db: sqlite3.Connection, catalog_key: str, insta_key: str) -> bool:
    """Stamp a match as human-validated.

    Also mirrors the pairing onto ``instagram_dump_media.matched_catalog_key``
    so both matching pipelines (bulk script + on-demand) share one
    "matched" signal for the Instagram tab badge, and marks the catalog
    image as posted to Instagram.
    """
    with db:
        cursor = db.execute(
            "UPDATE matches SET validated_at = ? WHERE catalog_key = ? AND insta_key = ?",
            (datetime.now().isoformat(), catalog_key, insta_key),
        )
        if cursor.rowcount == 0:
            return False
        db.execute(
            "UPDATE instagram_dump_media SET matched_catalog_key = ? "
            "WHERE media_key = ?",
            (catalog_key, insta_key),
        )
        db.execute(
            "UPDATE images SET instagram_posted = 1 WHERE key = ?",
            (catalog_key,),
        )
        _backfill_instagram_created_at_from_catalog(db, catalog_key, insta_key)
    return True


def unvalidate_match(db: sqlite3.Connection, catalog_key: str, insta_key: str) -> bool:
    """Remove human validation (undo validate, not reject).

    Clears ``instagram_dump_media.matched_catalog_key`` when no other
    validated match remains for the same insta_key, so the IG tab
    "matched" badge reflects the current validation state.
    """
    with db:
        cursor = db.execute(
            "UPDATE matches SET validated_at = NULL WHERE catalog_key = ? AND insta_key = ?",
            (catalog_key, insta_key),
        )
        if cursor.rowcount == 0:
            return False
        # Match the most-recent validated pairing so unvalidate → next
        # validation → unvalidate is deterministic. Mirrors the selection
        # used by `_backfill_matched_catalog_key_from_validated_matches`.
        remaining = db.execute(
            "SELECT catalog_key FROM matches "
            "WHERE insta_key = ? AND validated_at IS NOT NULL "
            "ORDER BY validated_at DESC LIMIT 1",
            (insta_key,),
        ).fetchone()
        if remaining:
            db.execute(
                "UPDATE instagram_dump_media SET matched_catalog_key = ? "
                "WHERE media_key = ?",
                (remaining['catalog_key'], insta_key),
            )
        else:
            db.execute(
                "UPDATE instagram_dump_media SET matched_catalog_key = NULL "
                "WHERE media_key = ?",
                (insta_key,),
            )
        # Clear instagram_posted if no validated match still references this catalog image
        still_validated = db.execute(
            "SELECT 1 FROM matches WHERE catalog_key = ? AND validated_at IS NOT NULL LIMIT 1",
            (catalog_key,),
        ).fetchone()
        if not still_validated:
            db.execute(
                "UPDATE images SET instagram_posted = 0 WHERE key = ?",
                (catalog_key,),
            )
    return True


def reject_match(db: sqlite3.Connection, catalog_key: str, insta_key: str) -> bool:
    """Delete match row and add pair to rejected blocklist.

    Also resets the instagram image's processed flag so it can match other
    catalog candidates in future runs.
    """
    db.execute(
        "DELETE FROM matches WHERE catalog_key = ? AND insta_key = ?",
        (catalog_key, insta_key),
    )
    db.execute(
        "INSERT OR REPLACE INTO rejected_matches (catalog_key, insta_key, rejected_at) "
        "VALUES (?, ?, ?)",
        (catalog_key, insta_key, datetime.now().isoformat()),
    )
    db.execute(
        "UPDATE instagram_dump_media SET processed = 0, matched_catalog_key = NULL "
        "WHERE media_key = ?",
        (insta_key,),
    )
    # Reset instagram_posted only if no validated match still references this catalog image
    still_validated = db.execute(
        "SELECT 1 FROM matches WHERE catalog_key = ? AND validated_at IS NOT NULL LIMIT 1",
        (catalog_key,),
    ).fetchone()
    if not still_validated:
        db.execute(
            "UPDATE images SET instagram_posted = 0 WHERE key = ?",
            (catalog_key,),
        )
    db.commit()
    return True


def get_rejected_pairs(db: sqlite3.Connection) -> set[tuple[str, str]]:
    """Return set of (catalog_key, insta_key) pairs in the blocklist."""
    rows = db.execute("SELECT catalog_key, insta_key FROM rejected_matches").fetchall()
    return {(r['catalog_key'], r['insta_key']) for r in rows}
