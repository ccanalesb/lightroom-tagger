"""Stack detection, catalog CLIP similarity, and catalog cache build handlers."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from database import add_job_log, get_job

from lightroom_tagger.core import cancel_scope
from lightroom_tagger.core.clip_similarity import NoClipEmbeddingError, run_clip_similar_for_seed
from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import (
    catalog_key_is_primary_grid_row,
    clear_catalog_similarity_results,
    insert_catalog_similarity_group,
    init_database,
    library_write,
    list_catalog_keys_needing_clip_embedding,
    list_clip_embedded_catalog_keys_newest_first,
    list_instagram_dump_keys_needing_clip_embedding,
)

from ..checkpoint import fingerprint_batch_stack_detect, fingerprint_catalog_cache_build, job_type_entry, load_resume_state

from .common import (
    _CHECKPOINT_MAX_ENTRIES,
    _failure_severity_from_exception,
    _resolve_date_window,
    _resolve_library_db_or_fail,
)
from .catalog import _handle_catalog_sync_inner
from .embed import _handle_batch_embed_image_inner

_CATALOG_SIMILARITY_SUMMARY_EVERY = 500
_STACK_DETECT_SUMMARY_EVERY = 500


_CATALOG_CACHE_STAGE_COUNT = 4


def _catalog_cache_stage_mapped_progress(stage_index: int, inner_pct: int) -> int:
    """Map a standalone handler's 5–100% progress into one quarter of the composite bar."""
    inner_pct = max(5, min(100, int(inner_pct)))
    span_total = 100 - 5
    stage_span = span_total / float(_CATALOG_CACHE_STAGE_COUNT)
    frac = (inner_pct - 5) / span_total if span_total else 0.0
    base = 5 + stage_index * stage_span
    return int(min(100, base + frac * stage_span))


class _CatalogCacheStageRunner:
    """Delegates to ``JobRunner`` but captures ``complete_job`` / ``finalize_cancelled`` per stage."""

    __slots__ = (
        '_runner',
        'job_id',
        'stage_index',
        'stage_complete_result',
        'stage_cancelled',
    )

    def __init__(self, runner, job_id: str, stage_index: int):
        object.__setattr__(self, '_runner', runner)
        object.__setattr__(self, 'job_id', job_id)
        object.__setattr__(self, 'stage_index', stage_index)
        object.__setattr__(self, 'stage_complete_result', None)
        object.__setattr__(self, 'stage_cancelled', False)

    @property
    def db(self):  # noqa: ANN201 — mirror runner.db typing
        return self._runner.db

    def update_progress(self, job_id: str, pct: int, msg: str | None = None) -> None:
        mapped = _catalog_cache_stage_mapped_progress(self.stage_index, int(pct))
        self._runner.update_progress(job_id, mapped, msg)

    def complete_job(self, job_id: str, result: dict) -> None:
        self.stage_complete_result = result

    def finalize_cancelled(self, job_id: str) -> None:
        object.__setattr__(self, 'stage_cancelled', True)

    def persist_checkpoint(self, job_id: str, body: dict) -> None:
        """Composite job uses chain-local checkpoint suppression on embed/stack inners."""
        return

    def clear_checkpoint(self, job_id: str) -> None:
        return

    def fail_job(self, job_id: str, msg: str, *, severity: str = 'error') -> None:
        self._runner.fail_job(job_id, msg, severity=severity)

    def __getattr__(self, name: str):
        return getattr(self._runner, name)


def _normalize_stack_detect_force(metadata: dict) -> str:
    """Return ``incremental`` | ``full`` | ``preserve_edited`` (CONTEXT D-05).

    Phase 4: ``preserve_edited`` issues the same full DB clear as ``full`` because
    ``user_modified`` is always 0. Phase 7 (STACK-05) may skip user-edited stacks.
    """
    raw = metadata.get('force', False)
    if raw is True:
        return 'full'
    if raw == 'preserve_edited':
        return 'preserve_edited'
    return 'incremental'


def _parse_date_taken_utc(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _build_burst_segments(
    rows: list[dict],
    delta_ms: int,
) -> tuple[list[list[str]], int]:
    """Return consecutive-time burst segments and a count of rows with bad/missing *date_taken*."""
    parsed: list[tuple[str, datetime]] = []
    skipped_no_date = 0
    for row in rows:
        key = str(row.get('key') or '')
        raw_dt = row.get('date_taken')
        p = _parse_date_taken_utc(raw_dt)
        if p is None:
            skipped_no_date += 1
            continue
        parsed.append((key, p))
    if not parsed:
        return [], skipped_no_date
    parsed.sort(key=lambda t: (t[1].timestamp(), t[0]))
    segments: list[list[str]] = []
    cur: list[str] = [parsed[0][0]]
    prev_ts = parsed[0][1]
    for i in range(1, len(parsed)):
        key, ts = parsed[i]
        gap_ms = (ts - prev_ts).total_seconds() * 1000.0
        if gap_ms > float(delta_ms):
            segments.append(cur)
            cur = [key]
        else:
            cur.append(key)
        prev_ts = ts
    segments.append(cur)
    return list(reversed(segments)), skipped_no_date


def _select_stack_representative_key(lib_db: sqlite3.Connection, burst_keys: tuple[str, ...]) -> str | None:
    if not burst_keys:
        return None
    ph = ','.join('?' * len(burst_keys))
    sql = (
        'SELECT i.key AS k FROM images i '
        'LEFT JOIN ( '
        '  SELECT s.image_key AS image_key, AVG(s.score) AS ai_score '
        '  FROM image_scores s '
        '  INNER JOIN perspectives p ON p.slug = s.perspective_slug AND p.active = 1 '
        "  WHERE s.is_current = 1 AND s.image_type = 'catalog' "
        '  GROUP BY s.image_key '
        ') agg ON agg.image_key = i.key '
        f'WHERE i.key IN ({ph}) '
        'ORDER BY (i.rating > 0) DESC, i.rating DESC, COALESCE(agg.ai_score, 0) DESC, '
        'i.date_taken DESC, i.key DESC LIMIT 1'
    )
    row = lib_db.execute(sql, burst_keys).fetchone()
    if not row:
        return None
    r = row.get('k') if isinstance(row, dict) else row[0]
    return str(r) if r is not None else None


def _catalog_similarity_why_matched_line(similarity: float) -> str:
    pct = max(0, min(100, int(round(float(similarity) * 100.0))))
    return f"Visual match ({pct}%)"


def handle_batch_catalog_similarity(runner, job_id: str, metadata: dict) -> None:
    """Materialize catalog-to-catalog CLIP similarity groups for later review."""
    _handle_catalog_similarity_inner(runner, job_id, metadata)


def _handle_catalog_similarity_inner(runner, job_id: str, metadata: dict) -> None:
    lib_db: sqlite3.Connection | None = None
    try:
        db_path = _resolve_library_db_or_fail(runner, job_id)
        if db_path is None:
            return
        lib_db = init_database(db_path)

        chain_mode = bool(metadata.get('_catalog_cache_chain'))

        try:
            min_similarity = float(metadata.get('min_similarity', 0.9))
        except (TypeError, ValueError):
            min_similarity = 0.9
        min_similarity = max(0.0, min(1.0, min_similarity))
        try:
            limit_per_seed = int(metadata.get('limit_per_seed', 8))
        except (TypeError, ValueError):
            limit_per_seed = 8
        limit_per_seed = max(1, min(limit_per_seed, 50))

        all_keys = list_clip_embedded_catalog_keys_newest_first(lib_db)
        total = len(all_keys)
        if not chain_mode:
            add_job_log(
                runner.db,
                job_id,
                'info',
                (
                    'batch_catalog_similarity stage=find_similar_photos '
                    f'min_similarity={min_similarity:.2f}, limit_per_seed={limit_per_seed}, '
                    f'embedded_catalog_images={total}'
                ),
            )
        runner.update_progress(job_id, 5, f'Found {total} embedded catalog images')

        clear_catalog_similarity_results(lib_db)

        groups_created = 0
        candidates_created = 0
        skipped_non_primary = 0
        skipped_no_embedding = 0
        seen_pairs: set[tuple[str, str]] = set()

        for idx, seed_key in enumerate(all_keys, start=1):
            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
                return
            if not catalog_key_is_primary_grid_row(lib_db, seed_key):
                skipped_non_primary += 1
                continue
            try:
                pairs, _meta = run_clip_similar_for_seed(
                    lib_db,
                    seed_key,
                    limit=limit_per_seed,
                    offset=0,
                )
            except NoClipEmbeddingError:
                skipped_no_embedding += 1
                continue

            candidates: list[dict] = []
            for candidate_key, distance in pairs:
                sim = max(0.0, min(1.0, 1.0 - float(distance)))
                if sim < min_similarity:
                    continue
                pair_key = tuple(sorted((seed_key, candidate_key)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                candidates.append(
                    {
                        'candidate_key': candidate_key,
                        'similarity': sim,
                        'rank': len(candidates) + 1,
                        'why_matched': _catalog_similarity_why_matched_line(sim),
                    }
                )

            if candidates:
                insert_catalog_similarity_group(
                    lib_db,
                    seed_key=seed_key,
                    candidates=candidates,
                    job_id=job_id,
                )
                groups_created += 1
                candidates_created += len(candidates)

            if idx % _CATALOG_SIMILARITY_SUMMARY_EVERY == 0 or idx == total:
                progress = int(5 + (idx / max(total, 1)) * 95)
                msg = (
                    f'Similarity scan {idx}/{total}: groups={groups_created}, '
                    f'candidates={candidates_created}, skipped_non_primary={skipped_non_primary}'
                )
                runner.update_progress(job_id, min(progress, 100), msg)

        result = {
            'groups_created': int(groups_created),
            'candidates_created': int(candidates_created),
            'embedded_catalog_images': int(total),
            'skipped_non_primary': int(skipped_non_primary),
            'skipped_no_embedding': int(skipped_no_embedding),
            'min_similarity': float(min_similarity),
            'limit_per_seed': int(limit_per_seed),
        }
        if not chain_mode:
            add_job_log(runner.db, job_id, 'info', f'Catalog similarity complete: {result}')
        runner.complete_job(job_id, result)
    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)
    finally:
        if lib_db:
            lib_db.close()


def handle_batch_stack_detect(runner, job_id: str, metadata: dict) -> None:
    """Group catalog images into burst stacks by *date_taken* gaps (``batch_stack_detect`` job)."""
    with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
        _handle_batch_stack_detect_inner(runner, job_id, metadata)


def _handle_batch_stack_detect_inner(runner, job_id: str, metadata: dict) -> None:
    """Burst stacks by ``date_taken``; checkpoint lists keys finished per CONTEXT D-10–D-11.

    **Incremental mode:** the work list is only images not in ``image_stack_members``; gap detection
    does not consider neighbors that remain stacked from a prior run. Use ``force: true`` for a
    global re-scan.
    * ``delta_ms`` in metadata: override config only when the value is not ``None`` and not ``0``
      (0 is treated as unset, same as omitting the key; CONTEXT D-07).
    """
    lib_db: sqlite3.Connection | None = None
    try:
        db_path = _resolve_library_db_or_fail(runner, job_id)
        if db_path is None:
            return
        lib_db = init_database(db_path)
        cfg = load_config()
        force_mode = _normalize_stack_detect_force(metadata)
        raw_delta = metadata.get('delta_ms')
        if raw_delta is not None and raw_delta != 0:
            try:
                resolved_delta_ms = int(raw_delta)
            except (TypeError, ValueError):
                runner.fail_job(
                    job_id,
                    'Invalid delta_ms in metadata (must be integer >= 1)',
                    severity='warning',
                )
                return
            if resolved_delta_ms < 1:
                runner.fail_job(
                    job_id,
                    'delta_ms override must be >= 1 when non-zero (invalid delta_ms)',
                    severity='warning',
                )
                return
        else:
            resolved_delta_ms = int(getattr(cfg, 'stack_burst_delta_ms', 2000))
            if resolved_delta_ms < 1:
                resolved_delta_ms = 2000

        images_skipped_already_stacked = 0
        if force_mode == 'incremental':
            row_m = lib_db.execute('SELECT COUNT(*) AS c FROM image_stack_members').fetchone()
            images_skipped_already_stacked = int(
                (row_m.get('c') if row_m and isinstance(row_m, dict) else 0) or 0
            )

        if force_mode in ('full', 'preserve_edited'):
            with library_write(lib_db):
                lib_db.execute('DELETE FROM image_stacks')

        if force_mode == 'incremental':
            key_rows = lib_db.execute(
                'SELECT i.key AS key FROM images i WHERE i.key NOT IN '
                '(SELECT image_key FROM image_stack_members)'
            ).fetchall()
        else:
            key_rows = lib_db.execute('SELECT key AS key FROM images').fetchall()

        all_keys = sorted(
            {str(r['key']) for r in key_rows if r and (r.get('key') if isinstance(r, dict) else r[0])}
        )
        total_at_start = len(all_keys)
        initial_sorted_keys = sorted(all_keys)
        fp = fingerprint_batch_stack_detect(
            metadata,
            initial_sorted_keys,
            resolved_delta_ms=resolved_delta_ms,
            force_mode=force_mode,
        )

        chain_mode = bool(metadata.get('_catalog_cache_chain'))

        processed_image_keys: set[str] = set()
        jt_batch_stack_detect = job_type_entry('batch_stack_detect')
        if not chain_mode:
            row_job = get_job(runner.db, job_id)
            processed_image_keys = load_resume_state(
                'batch_stack_detect',
                (row_job.get('metadata') or {}) if row_job and isinstance(row_job.get('metadata'), dict) else {},
                fp,
                lambda msg: add_job_log(runner.db, job_id, 'info', msg),
            )

        if total_at_start == 0:
            runner.update_progress(job_id, 5, 'No catalog images in stack-detect work list')
            z = {
                'stacks_created': 0,
                'stacks_updated': 0,
                'images_stacked': 0,
                'images_skipped_no_date': 0,
                'images_skipped_already_stacked': int(images_skipped_already_stacked),
            }
            add_job_log(
                runner.db,
                job_id,
                'info',
                f'Stack detection complete: {z}; 0 images skipped (no date_taken)',
            )
            if not chain_mode:
                runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, z)
            return

        runner.update_progress(
            job_id,
            5,
            f'Found {total_at_start} images to scan for stacks',
        )

        def fetch_rows_for_keys(keys: list[str]) -> list[dict]:
            if not keys:
                return []
            out: list[dict] = []
            chunk = 500
            for i in range(0, len(keys), chunk):
                part = keys[i : i + chunk]
                ph = ','.join('?' * len(part))
                q = f'SELECT key, date_taken, rating FROM images WHERE key IN ({ph})'
                for r in lib_db.execute(q, tuple(part)).fetchall():
                    out.append(dict(r))
            return out

        row_dicts = fetch_rows_for_keys(list(all_keys))
        fetched_by_key = {str(r.get('key')): r for r in row_dicts}
        for key in all_keys:
            if key not in fetched_by_key:
                row_dicts.append({'key': key, 'date_taken': None, 'rating': 0})
        segments, images_skipped_no_date = _build_burst_segments(row_dicts, resolved_delta_ms)

        keys_with_parsed_date: set[str] = set()
        for seg in segments:
            keys_with_parsed_date.update(seg)
        total_work_units = len(keys_with_parsed_date)
        if total_work_units == 0:
            res = {
                'stacks_created': 0,
                'stacks_updated': 0,
                'images_stacked': 0,
                'images_skipped_no_date': int(images_skipped_no_date),
                'images_skipped_already_stacked': int(images_skipped_already_stacked),
            }
            add_job_log(
                runner.db,
                job_id,
                'info',
                f'Stack detection complete: {res}; {images_skipped_no_date} images skipped (no date_taken)',
            )
            if not chain_mode:
                runner.clear_checkpoint(job_id)
            runner.complete_job(job_id, res)
            return

        stacks_created = 0
        stacks_updated = 0
        images_stacked = 0
        last_stack_summary = 0

        def emit_stack_summary(*, force: bool = False) -> None:
            nonlocal last_stack_summary
            done = len(processed_image_keys)
            if not force and done - last_stack_summary < _STACK_DETECT_SUMMARY_EVERY:
                return
            last_stack_summary = done
            pct = int(5 + (done / max(total_work_units, 1)) * 95)
            runner.update_progress(
                job_id,
                min(pct, 100),
                (
                    f'Stack scan {done}/{total_work_units}: stacks_created={stacks_created}, '
                    f'images_stacked={images_stacked}, skipped_no_date={images_skipped_no_date}'
                ),
            )

        def persist_progress() -> bool:
            if len(processed_image_keys) > _CHECKPOINT_MAX_ENTRIES:
                runner.fail_job(
                    job_id,
                    'checkpoint too large: exceeds 100000 entries',
                    severity='error',
                )
                return False
            if chain_mode:
                return True
            runner.persist_checkpoint(
                job_id,
                jt_batch_stack_detect.build_checkpoint_body(
                    fingerprint=fp,
                    processed=processed_image_keys,
                    total_at_start=total_at_start,
                ),
            )
            return True

        for segment in segments:
            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
                return
            if not segment:
                continue
            if all(k in processed_image_keys for k in segment):
                continue
            if len(segment) < 2:
                processed_image_keys.update(segment)
                if not persist_progress():
                    return
                row_s = get_job(runner.db, job_id)
                if row_s and row_s.get('status') == 'failed':
                    return
                emit_stack_summary()
                continue

            burst_tuple = tuple(segment)
            rep = _select_stack_representative_key(lib_db, burst_tuple)
            if not rep or rep not in segment:
                runner.fail_job(
                    job_id,
                    'Stack representative selection failed (internal error)',
                    severity='error',
                )
                return
            n = len(segment)
            with library_write(lib_db):
                cur = lib_db.execute(
                    'INSERT INTO image_stacks (representative_key, stack_size, user_modified) '
                    'VALUES (?, ?, ?)',
                    (rep, n, 0),
                )
                stack_id = int(cur.lastrowid)
                for mkey in segment:
                    lib_db.execute(
                        'INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)',
                        (stack_id, mkey),
                    )
            stacks_created += 1
            images_stacked += n
            processed_image_keys.update(segment)
            if not persist_progress():
                return
            row_s2 = get_job(runner.db, job_id)
            if row_s2 and row_s2.get('status') == 'failed':
                return
            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
                return
            emit_stack_summary()

        if runner.is_cancelled(job_id):
            runner.finalize_cancelled(job_id)
            return
        row_done = get_job(runner.db, job_id)
        if row_done and row_done.get('status') == 'failed':
            return

        result = {
            'stacks_created': int(stacks_created),
            'stacks_updated': int(stacks_updated),
            'images_stacked': int(images_stacked),
            'images_skipped_no_date': int(images_skipped_no_date),
            'images_skipped_already_stacked': int(images_skipped_already_stacked),
        }
        add_job_log(
            runner.db,
            job_id,
            'info',
            f'Stack detection complete: {result}; {images_skipped_no_date} images skipped (no date_taken)',
        )
        emit_stack_summary(force=True)
        if not chain_mode:
            runner.clear_checkpoint(job_id)
        runner.complete_job(job_id, result)
    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)
    finally:
        if lib_db:
            lib_db.close()


def handle_catalog_cache_build(runner, job_id: str, metadata: dict) -> None:
    """Run catalog CLIP embed → stack detection → catalog similarity in-process (CACHE-01)."""
    with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
        _handle_catalog_cache_build_inner(runner, job_id, metadata)


def _handle_catalog_cache_build_inner(runner, job_id: str, metadata: dict) -> None:
    db_path = _resolve_library_db_or_fail(runner, job_id)
    if db_path is None:
        return

    months, year = _resolve_date_window(metadata)
    min_rating_raw = metadata.get('min_rating')
    min_rating = None
    if min_rating_raw is not None:
        try:
            min_rating = int(min_rating_raw)
        except (TypeError, ValueError):
            min_rating = None

    fp_chain = fingerprint_catalog_cache_build(metadata, resolved_months=months, resolved_year=year)

    add_job_log(
        runner.db,
        job_id,
        'info',
        '[catalog-cache-build] chain_start sync→embed→stack_detect→catalog_similarity',
    )

    add_job_log(runner.db, job_id, 'info', '[catalog-cache-build] stage=sync status=start')
    sr_sync = _CatalogCacheStageRunner(runner, job_id, 0)
    sync_result = _handle_catalog_sync_inner(sr_sync, job_id, metadata, chain_mode=True) or {}

    if sr_sync.stage_cancelled:
        runner.finalize_cancelled(job_id)
        return

    add_job_log(
        runner.db,
        job_id,
        'info' if not sync_result.get('failed') and not sync_result.get('skipped') else 'warning',
        (
            '[catalog-cache-build] stage=sync status=complete '
            f"added={sync_result.get('added', 0)} stale={sync_result.get('stale', 0)} "
            f"locking_mode={sync_result.get('locking_mode', 'unknown')}"
            + (f" error={sync_result.get('error')}" if sync_result.get('error') else '')
        ),
    )

    if runner.is_cancelled(job_id):
        runner.finalize_cancelled(job_id)
        return

    embed_meta = dict(metadata)
    embed_meta['image_type'] = 'catalog_and_instagram'
    embed_meta['force'] = bool(metadata.get('force_embed', False))
    embed_meta['_catalog_cache_chain'] = True

    add_job_log(runner.db, job_id, 'info', '[catalog-cache-build] stage=embed status=start')
    sr_embed = _CatalogCacheStageRunner(runner, job_id, 1)
    _handle_batch_embed_image_inner(sr_embed, job_id, embed_meta)

    if sr_embed.stage_cancelled:
        runner.finalize_cancelled(job_id)
        return
    row_j = get_job(runner.db, job_id)
    if row_j and row_j.get('status') == 'failed':
        return

    embed_result = sr_embed.stage_complete_result or {}

    add_job_log(
        runner.db,
        job_id,
        'info',
        (
            '[catalog-cache-build] stage=embed status=complete '
            f"embedded={embed_result.get('embedded', 0)} skipped={embed_result.get('skipped', 0)} "
            f"failed={embed_result.get('failed', 0)}"
        ),
    )

    lib_db = init_database(db_path)
    try:
        cat_need = list_catalog_keys_needing_clip_embedding(
            lib_db, months=months, year=year, min_rating=min_rating
        )
        ig_need = list_instagram_dump_keys_needing_clip_embedding(
            lib_db, months=months, year=year, min_rating=min_rating
        )
        overlap = set(cat_need) & set(ig_need)
        incomplete_k = len(cat_need) + len(ig_need) - len(overlap)
    finally:
        lib_db.close()

    if incomplete_k > 0:
        add_job_log(
            runner.db,
            job_id,
            'warning',
            (
                '[catalog-cache-build] stage=embed warning=incomplete_embeddings '
                f'count={incomplete_k} proceeding'
            ),
        )

    if runner.is_cancelled(job_id):
        runner.finalize_cancelled(job_id)
        return

    stack_meta = dict(metadata)
    stack_meta['force'] = metadata.get('force_stack', False)
    stack_meta['_catalog_cache_chain'] = True

    add_job_log(runner.db, job_id, 'info', '[catalog-cache-build] stage=stack status=start')
    sr_stack = _CatalogCacheStageRunner(runner, job_id, 2)
    _handle_batch_stack_detect_inner(sr_stack, job_id, stack_meta)

    if sr_stack.stage_cancelled:
        runner.finalize_cancelled(job_id)
        return
    row_s = get_job(runner.db, job_id)
    if row_s and row_s.get('status') == 'failed':
        return

    stk_result = sr_stack.stage_complete_result or {}
    add_job_log(
        runner.db,
        job_id,
        'info',
        (
            '[catalog-cache-build] stage=stack status=complete '
            f"stacks_created={stk_result.get('stacks_created', 0)} "
            f"images_skipped_no_date={stk_result.get('images_skipped_no_date', 0)} "
            f"images_skipped_already_stacked={stk_result.get('images_skipped_already_stacked', 0)}"
        ),
    )

    if runner.is_cancelled(job_id):
        runner.finalize_cancelled(job_id)
        return

    sim_meta = dict(metadata)
    sim_meta['_catalog_cache_chain'] = True

    add_job_log(runner.db, job_id, 'info', '[catalog-cache-build] stage=similarity status=start')
    sr_sim = _CatalogCacheStageRunner(runner, job_id, 3)
    _handle_catalog_similarity_inner(sr_sim, job_id, sim_meta)

    if sr_sim.stage_cancelled:
        runner.finalize_cancelled(job_id)
        return
    row_sim = get_job(runner.db, job_id)
    if row_sim and row_sim.get('status') == 'failed':
        return

    sim_result = sr_sim.stage_complete_result or {}
    add_job_log(
        runner.db,
        job_id,
        'info',
        (
            '[catalog-cache-build] stage=similarity status=complete '
            f"groups_created={sim_result.get('groups_created', 0)} "
            f"candidates_created={sim_result.get('candidates_created', 0)} "
            f"skipped_non_primary={sim_result.get('skipped_non_primary', 0)} "
            f"skipped_no_embedding={sim_result.get('skipped_no_embedding', 0)}"
        ),
    )

    runner.complete_job(
        job_id,
        {
            'catalog_cache_build': True,
            'fingerprint': fp_chain,
            'sync': sync_result,
            'embed': embed_result,
            'stack': stk_result,
            'similarity': sim_result,
        },
    )
