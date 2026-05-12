# Phase 19 — Pattern mapping (GSD pattern-mapper)

**Inputs:** `19-CONTEXT.md`, `19-RESEARCH.md`  
**Purpose:** Classify planned/new/touched files, anchor each to the closest existing analog, and cite concrete symbols for implementers.

---

## 1. End-to-end data flow (phase intent)

1. **Capture (write path):** During `match_dump_media`, after `score_candidates_with_vision` returns, persist a durable snapshot of the evaluated pool + per-candidate evidence (ordering, scores, model) keyed by Instagram row / run identity.
2. **Report (read path):** CLI loads library DB, selects unmatched+attempted dump rows (filters), loads snapshot rows when present; otherwise runs best-effort reconstruction and marks UI as non-exact. Writes `report.html` + compressed files under `assets/`.

---

## 2. Files from CONTEXT + RESEARCH (create / modify / read)

| Path | Role | Flow | Closest analog |
|------|------|------|----------------|
| `lightroom_tagger/scripts/match_instagram_dump.py` | **Modify:** pool snapshot hook after scoring | Write | Same file: existing `vision_candidates` build + `score_candidates_with_vision` call |
| `lightroom_tagger/core/database/library_bootstrap_schema.py` | **Modify (optional):** new tables in base DDL if greenfield | Write | Existing `instagram_dump_media`, `vision_comparisons`, indexes in same module |
| `lightroom_tagger/core/database/db_init.py` | **Modify:** run migration for new tables/columns | Write | Calls `_migrate_*` and `_migrate_add_column` after `executescript(BASE_LIBRARY_SCHEMA_SQL)` |
| `lightroom_tagger/core/database/db_init_migrations.py` | **Modify:** idempotent `CREATE TABLE IF NOT EXISTS` + indexes (pattern like `_migrate_catalog_similarity`) | Write | `_migrate_catalog_similarity` |
| `lightroom_tagger/core/database/<match_pool_snapshots TBD>.py` | **New:** insert/query snapshot parent+children | Write/read | `lightroom_tagger/core/database/similarity.py` |
| `lightroom_tagger/scripts/<generate_comparison_pool_report TBD>.py` | **New:** CLI + HTML + asset copy | Read DB → filesystem | `generate_validation_report.py` / `generate_subset_report.py` (adapt to external assets) |
| `lightroom_tagger/core/path_utils.py` | **Read/reuse** | — | `resolve_catalog_path` |
| `lightroom_tagger/core/database/instagram.py` | **Modify or reuse** | Read | `get_instagram_by_date_filter`, `mark_dump_media_attempted`, dump queries |
| `lightroom_tagger/core/matcher/score_with_vision.py` | **Read** (evidence fields) | — | `score_candidates_with_vision` |
| `lightroom_tagger/core/matcher/candidates.py` | **Read** (reconstruction) | — | `find_candidates_by_date` |
| `lightroom_tagger/core/clip_similarity.py` | **Read** (reconstruction) | — | `shortlist_catalog_candidates_by_clip` |
| `lightroom_tagger/core/database/matches.py` | **Read** | — | `store_match`, rejection helpers |
| `lightroom_tagger/core/database/vision_cache.py` | **Read** | — | Compressed catalog paths; not a pool snapshot |
| `apps/visualizer/backend/jobs/handlers/matching.py` | **Optional modify:** pass `job_id` into `match_dump_media` for snapshot provenance / `--job-id` | Write | `handle_vision_match` → `match_dump_media(...)` |

---

## 3. SQLite: bootstrap + migrations

**Bootstrap DDL** lives in a single string and is applied with `executescript` on every `init_database`:

```3:64:lightroom_tagger/core/database/library_bootstrap_schema.py
BASE_LIBRARY_SCHEMA_SQL = '''

        CREATE TABLE IF NOT EXISTS images (
            key TEXT PRIMARY KEY,
            ...
        );

        CREATE TABLE IF NOT EXISTS instagram_dump_media (
            media_key TEXT PRIMARY KEY,
            ...
            last_attempted_at TEXT,
            ...
        );

        CREATE INDEX IF NOT EXISTS idx_dump_media_processed_attempted ON instagram_dump_media(processed, last_attempted_at);
        ...
```

**Post-bootstrap evolution** uses `_migrate_add_column` and dedicated `_migrate_*` functions, invoked from `init_database` in fixed order:

```170:213:lightroom_tagger/core/database/db_init.py
    conn.executescript(
        library_bootstrap_schema.BASE_LIBRARY_SCHEMA_SQL
    )

    # Migrations for existing databases
    _migrate_add_column(conn, 'instagram_dump_media', 'last_attempted_at', 'TEXT')
    ...
    _migrate_catalog_similarity(conn)
    seed_perspectives_from_prompts_dir(conn)
    conn.commit()
    return conn
```

**Additive column pattern** (safe, repeatable):

```9:13:lightroom_tagger/core/database/db_init_migrations.py
def _migrate_add_column(conn: sqlite3.Connection, table: str, column: str, col_type: str):
    """Add a column if it doesn't already exist. Safe to call repeatedly."""
    cols = {row['name'] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
```

**New table group pattern** (parent + child + FK + rank index) — closest analog for **Instagram-keyed pool snapshots**:

```226:256:lightroom_tagger/core/database/db_init_migrations.py
def _migrate_catalog_similarity(conn: sqlite3.Connection) -> None:
    """Idempotent derived tables for job-driven catalog visual similarity."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalog_similarity_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            seed_key TEXT NOT NULL,
            ...
        );
        ...
        CREATE TABLE IF NOT EXISTS catalog_similarity_candidates (
            group_id INTEGER NOT NULL
                REFERENCES catalog_similarity_groups(group_id) ON DELETE CASCADE,
            candidate_key TEXT NOT NULL,
            similarity REAL NOT NULL,
            rank INTEGER NOT NULL,
            ...
            PRIMARY KEY (group_id, candidate_key)
        );
        CREATE INDEX IF NOT EXISTS idx_catalog_similarity_candidates_group_rank
            ON catalog_similarity_candidates(group_id, rank);
        """
    )
```

**Plan implication:** Phase 19 snapshots should mirror this **group row + ranked children** shape, but keyed by `insta_key` (and optional `run_id` / `job_id` / `captured_at`) rather than catalog `seed_key`.

---

## 4. Parent / child ranked persistence (write API)

**Analog:** `insert_catalog_similarity_group` — insert parent, `lastrowid`, `executemany` children with `rank`.

```28:72:lightroom_tagger/core/database/similarity.py
def insert_catalog_similarity_group(
    db: sqlite3.Connection,
    *,
    seed_key: str,
    candidates: Sequence[dict],
    job_id: str | None = None,
) -> int:
    """Persist one catalog similarity group and its ranked candidate rows."""
    ...
    cur = db.execute(
        """
        INSERT INTO catalog_similarity_groups
            (seed_key, candidate_count, best_similarity, job_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ...
    )
    group_id = int(cur.lastrowid)
    db.executemany(
        """
        INSERT INTO catalog_similarity_candidates
            (group_id, candidate_key, similarity, rank, why_matched)
        VALUES (?, ?, ?, ?, ?)
        """,
        ...
    )
    db.commit()
    return group_id
```

**Evidence fields** to mirror on snapshot child rows should align with scoring dicts from `score_candidates_with_vision` (e.g. `total_score`, `phash_distance`, `desc_similarity`, `vision_result`, `vision_score`, `vision_reasoning`, `model_used`, `rate_limited`).

---

## 5. Match pipeline insertion point (`vision_candidates` → `score_candidates_with_vision`)

**Build `vision_candidates`** (pool membership + hydrated paths via `resolve_catalog_path`):

```268:317:lightroom_tagger/scripts/match_instagram_dump.py
        vision_candidates = []
        for catalog_img in candidates:
            catalog_path = resolve_catalog_path(catalog_img.get('filepath', ''))
            ...
            vision_candidates.append(candidate)
```

**Score and receive ordered `results`** — **capture point: immediately after this returns** (both pool and scores in memory):

```325:347:lightroom_tagger/scripts/match_instagram_dump.py
        results = score_candidates_with_vision(
            db, dump_image, vision_candidates,
            phash_weight=weights.get('phash', 0.4),
            desc_weight=weights.get('description', 0.3),
            vision_weight=weights.get('vision', 0.3),
            threshold=threshold,
            ...
        )
        ...
        above_threshold = [r for r in results if r['total_score'] >= threshold]
```

**Unmatched branch** currently only stores best vision fields on the dump row, not the pool:

```402:408:lightroom_tagger/scripts/match_instagram_dump.py
        else:
            best = results[0] if results else None
            mark_dump_media_attempted(
                db, dump_media['media_key'],
                vision_result=best.get('vision_result') if best else None,
                vision_score=best.get('vision_score') if best else None,
            )
```

**`mark_dump_media_attempted` semantics** (attempted ≠ processed):

```229:245:lightroom_tagger/core/database/instagram.py
def mark_dump_media_attempted(db: sqlite3.Connection, media_key: str,
                               vision_result: str = None,
                               vision_score: float = None) -> bool:
    """Record an attempt without marking as permanently processed.
    ...
    """
    cursor = db.execute("""
        UPDATE instagram_dump_media SET
            last_attempted_at = ?,
            vision_result = COALESCE(?, vision_result),
            vision_score = COALESCE(?, vision_score)
        WHERE media_key = ?
    """, (datetime.now().isoformat(), vision_result, vision_score, media_key))
```

**Vision scoring** uses `InstagramCache.compress_instagram_image` once per insta row before the candidate loop when `vision_weight > 0` — relevant for understanding artifacts, not for replacing D-11 asset copy:

```53:65:lightroom_tagger/core/matcher/score_with_vision.py
    # Compress Instagram image ONCE before candidate loop (vision stage only)
    insta_cache = _matcher.InstagramCache(db)
    insta_path = insta_image.get('local_path')
    compressed_insta = None
    if vision_weight > 0 and insta_path:
        try:
            compressed_insta = insta_cache.compress_instagram_image(insta_path)
```

**Job orchestration** (optional `job_id` for filters): `handle_vision_match` calls `match_dump_media` with callbacks but does not pass `job_id` today:

```210:231:apps/visualizer/backend/jobs/handlers/matching.py
            stats, matches = match_dump_media(
                db,
                threshold=custom_threshold,
                month=month,
                ...
                batch_progress_callback=batch_progress_callback,
            )
```

---

## 6. CLI patterns

**Standalone script** (matcher already has `--db`, `--month`, etc.):

```419:434:lightroom_tagger/scripts/match_instagram_dump.py
def main():
    import argparse

    parser = argparse.ArgumentParser(description='Match Instagram dump media to catalog')
    parser.add_argument('--db', default='library.db', help='Database path')
    ...
    parser.add_argument('--month', help='Filter by month (e.g., 202603)')
```

**Packaged CLI** uses subparsers (`lightroom-tagger`); Phase 19 can add a subcommand here or stay `python -m ...` per RESEARCH §5:

```18:65:lightroom_tagger/core/cli.py
def create_parser() -> argparse.ArgumentParser:
    ...
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    scan_parser = subparsers.add_parser("scan", help="Scan catalog, index all images")
```

**Month filtering** for dump media aligns with `get_instagram_by_date_filter` (`date_folder = ?` for `YYYYMM`):

```175:209:lightroom_tagger/core/database/instagram.py
def get_instagram_by_date_filter(db: sqlite3.Connection, month: str = None,
                                  year: str = None, last_months: int = None,
                                  ...
```

---

## 7. HTML report + image compression + asset naming

**Closest precedent:** inline base64 JPEG (quality 85, max dimension resize) — Phase 19 should **differ** (D-11/D-12): write files under `assets/` and reference `src="assets/..."`.

```12:26:lightroom_tagger/scripts/generate_validation_report.py
def image_to_base64(path: str, max_size: int = 400) -> str:
    """Convert image to base64 for HTML embedding, resizing if needed."""
    try:
        with Image.open(path) as img:
            if img.width > max_size or img.height > max_size:
                ratio = max_size / max(img.width, img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            ...
            img.save(buffer, format='JPEG', quality=85)
```

**String-built HTML structure** (cards, flex, badges) — reuse layout ideas, swap embedding for file refs:

```40:76:lightroom_tagger/scripts/generate_validation_report.py
    html_parts = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        ...
        '        .match-card { background: white; margin: 20px 0; ...',
```

**Subset report** duplicates the same `image_to_base64` + DNG→JPG fallback pattern:

```12:36:lightroom_tagger/scripts/generate_subset_report.py
def image_to_base64(path: str, max_size: int = 400) -> str:
    """Convert image to base64 for HTML embedding, resizing if needed."""
    # If DNG file, try JPG version instead
    if path.endswith('.DNG'):
        jpg_path = path.replace('.DNG', '.JPG')
```

**Collapsible debug (D-08):** no strong precedent in-repo; use `<details>`/`<summary>` or minimal JS — static output only.

---

## 8. Vision / path helpers (not pool storage)

**`vision_cache`** stores compressed catalog paths per key — useful diagnostics, not evaluated-pool proof:

```28:33:lightroom_tagger/core/database/vision_cache.py
def get_vision_cached_image(db: sqlite3.Connection, catalog_key: str) -> dict | None:
    """Get cached compressed image by catalog key."""
    row = db.execute(
        "SELECT * FROM vision_cache WHERE key = ?", (catalog_key,)
    ).fetchone()
```

**Catalog filesystem resolution** for candidates — report generator should use the same helper as matching (`resolve_catalog_path` in `lightroom_tagger/core/path_utils.py`).

---

## 9. Test fixture patterns

**Matcher unit test** style: `MagicMock` db + patch internals of `match_instagram_dump` / `get_unprocessed_dump_media` / `find_candidates_by_date`:

```1:28:lightroom_tagger/scripts/test_match_instagram_dump.py
from unittest.mock import patch, MagicMock
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media


@patch('lightroom_tagger.scripts.match_instagram_dump.init_catalog_table')
...
def test_media_key_filters_to_single_image(
    mock_mark_attempted, mock_find, mock_get_unprocessed, mock_init_insta, mock_init_catalog
):
    """When media_key is provided, only that image is processed."""
    db = MagicMock()
    ...
    stats, matches = match_dump_media(db, media_key='202603/12345')
```

**Suggested Phase 19 tests (from RESEARCH §11):**

- After mocked `score_candidates_with_vision`, assert snapshot rows (or serialized blob) preserve order and scores.
- Temp output dir: `report.html` exists, `assets/` non-empty, `<img src="assets/...">` only in primary body; regex assert no absolute paths in main HTML (D-13).
- Reconstruction branch: visible “reconstructed” flag in HTML when snapshot missing.

**Integration:** `pytest lightroom_tagger/scripts/test_match_instagram_dump.py`; extend visualizer handler tests only if job/signature changes.

---

## 10. Symbol index (quick lookup)

| Symbol | Module |
|--------|--------|
| `match_dump_media` | `lightroom_tagger/scripts/match_instagram_dump.py` |
| `score_candidates_with_vision` | `lightroom_tagger/core/matcher/score_with_vision.py` |
| `find_candidates_by_date` | `lightroom_tagger/core/matcher/candidates.py` |
| `shortlist_catalog_candidates_by_clip` | `lightroom_tagger/core/clip_similarity.py` |
| `init_database` | `lightroom_tagger/core/database/db_init.py` |
| `BASE_LIBRARY_SCHEMA_SQL` | `lightroom_tagger/core/database/library_bootstrap_schema.py` |
| `_migrate_catalog_similarity`, `_migrate_add_column` | `lightroom_tagger/core/database/db_init_migrations.py` |
| `insert_catalog_similarity_group` | `lightroom_tagger/core/database/similarity.py` |
| `get_instagram_by_date_filter`, `mark_dump_media_attempted` | `lightroom_tagger/core/database/instagram.py` |
| `handle_vision_match` | `apps/visualizer/backend/jobs/handlers/matching.py` |
| `generate_html_report` / `image_to_base64` | `lightroom_tagger/scripts/generate_validation_report.py` |

---

*Pattern map produced for Phase 19 planning / implementation.*
