"""CLIP / text embedding job handlers (catalog + Instagram dump)."""

from __future__ import annotations

import database
from database import get_job

from lightroom_tagger.core import cancel_scope
from lightroom_tagger.core.clip_embedding_service import (
    CLIP_EMBED_MODEL_ID,
    encode_images,
    numpy_to_clip_vec_blob,
)
from lightroom_tagger.core.database import (
    build_description_search_document,
    init_database,
    library_write,
    list_catalog_keys_for_clip_embed_force,
    list_catalog_keys_for_text_embed_force,
    list_catalog_keys_needing_clip_embedding,
    list_catalog_keys_needing_text_embedding,
    list_instagram_dump_keys_for_clip_embed_force,
    list_instagram_dump_keys_needing_clip_embedding,
    upsert_image_clip_embedding,
    upsert_image_text_embedding,
)
from lightroom_tagger.core.embedding_service import (
    TEXT_EMBED_MODEL_ID,
    embed_texts,
    numpy_to_vec_blob,
)
from ..checkpoint import fingerprint_batch_embed_image, fingerprint_batch_text_embed

from .common import (
    _CHECKPOINT_MAX_ENTRIES,
    _failure_severity_from_exception,
    _resolve_date_window,
    _resolve_library_db_or_fail,
)
from .path_diagnostics import (
    PREFLIGHT_FAIL_RATIO,
    PREFLIGHT_SAMPLE_SIZE,
    SKIP_DETAIL_LOG_LIMIT,
    PathSkipDiagnostics,
    empty_skip_reason_counts,
)

_BATCH_EMBED_IMAGE_SIZE = 8

# Backward-compatible aliases for existing embed handler tests.
_EMBED_PREFLIGHT_SAMPLE_SIZE = PREFLIGHT_SAMPLE_SIZE
_EMBED_PREFLIGHT_FAIL_RATIO = PREFLIGHT_FAIL_RATIO
_EMBED_SKIP_DETAIL_LOG_LIMIT = SKIP_DETAIL_LOG_LIMIT


def handle_batch_text_embed(runner, job_id: str, metadata: dict) -> None:
    """Embed catalog description text into ``image_text_embeddings`` (sqlite-vec)."""
    with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
        _handle_batch_text_embed_inner(runner, job_id, metadata)


def _handle_batch_text_embed_inner(runner, job_id: str, metadata: dict) -> None:
    lib_db = None
    try:
        image_type = metadata.get('image_type', 'catalog')
        if image_type != 'catalog':
            runner.fail_job(
                job_id,
                'batch_text_embed only supports catalog images',
                severity='warning',
            )
            return

        db_path = _resolve_library_db_or_fail(runner, job_id)
        if db_path is None:
            return
        lib_db = init_database(db_path)

        database.add_job_log(
            runner.db,
            job_id,
            'info',
            f'batch_text_embed: model={TEXT_EMBED_MODEL_ID}',
        )

        months, year = _resolve_date_window(metadata)
        min_rating_raw = metadata.get('min_rating')
        min_rating = None
        if min_rating_raw is not None:
            try:
                min_rating = int(min_rating_raw)
            except (TypeError, ValueError):
                min_rating = None

        force = bool(metadata.get('force', False))
        if force:
            full_list = list_catalog_keys_for_text_embed_force(
                lib_db, months=months, year=year, min_rating=min_rating
            )
        else:
            full_list = list_catalog_keys_needing_text_embedding(
                lib_db, months=months, year=year, min_rating=min_rating
            )

        total_at_start = len(full_list)
        fp = fingerprint_batch_text_embed(metadata, full_list)

        def pair_label(key: str, itype: str) -> str:
            return f'{key}|{itype}'

        processed_pairs: set[str] = set()
        row_job = get_job(runner.db, job_id)
        if row_job:
            meta_job = row_job.get('metadata') or {}
            if isinstance(meta_job, dict):
                chk = meta_job.get('checkpoint')
                if (
                    isinstance(chk, dict)
                    and chk.get('checkpoint_version') == 1
                    and chk.get('job_type') == 'batch_text_embed'
                ):
                    if chk.get('fingerprint') == fp:
                        processed_pairs = set(chk.get('processed_pairs') or [])
                    elif chk.get('fingerprint'):
                        database.add_job_log(
                            runner.db,
                            job_id,
                            'info',
                            'checkpoint mismatch: batch_text_embed fingerprint changed, starting fresh',
                        )

        remaining = [(k, t) for k, t in full_list if pair_label(k, t) not in processed_pairs]
        runner.update_progress(
            job_id,
            5,
            f'Found {total_at_start} images to embed ({len(remaining)} remaining)',
        )

        if total_at_start == 0:
            runner.clear_checkpoint(job_id)
            runner.complete_job(
                job_id,
                {'embedded': 0, 'skipped': 0, 'failed': 0, 'total': 0},
            )
            return

        embedded = 0
        skipped = 0
        failed = 0
        batch_buf: list[tuple[str, str]] = []

        def persist_progress() -> bool:
            if len(processed_pairs) > _CHECKPOINT_MAX_ENTRIES:
                runner.fail_job(
                    job_id,
                    'checkpoint too large: exceeds 100000 entries',
                    severity='error',
                )
                return False
            runner.persist_checkpoint(
                job_id,
                {
                    'job_type': 'batch_text_embed',
                    'fingerprint': fp,
                    'processed_pairs': sorted(processed_pairs),
                    'total_at_start': total_at_start,
                },
            )
            return True

        def flush_batch(buf: list[tuple[str, str]]) -> bool:
            nonlocal embedded
            if not buf:
                return True
            texts = [t for _, t in buf]
            vecs = embed_texts(texts, batch_size=16)
            for j, (img_key, _text) in enumerate(buf):
                if runner.is_cancelled(job_id):
                    return False
                vec_blob = numpy_to_vec_blob(vecs[j])
                with library_write(lib_db):
                    upsert_image_text_embedding(lib_db, img_key, vec_blob)
                processed_pairs.add(pair_label(img_key, 'catalog'))
                embedded += 1
                if not persist_progress():
                    return False
                pct = int(5 + (embedded / max(total_at_start, 1)) * 95)
                runner.update_progress(job_id, pct, f'Embedded {embedded}/{total_at_start}')
            buf.clear()
            return True

        for img_key, itype in remaining:
            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
                return
            row = lib_db.execute(
                "SELECT description_search_document, summary, subjects FROM image_descriptions "
                "WHERE image_key = ? AND image_type = 'catalog'",
                (img_key,),
            ).fetchone()
            text = ''
            if row:
                doc = row.get('description_search_document')
                if doc is not None and str(doc).strip():
                    text = str(doc).strip()
                else:
                    text = str(
                        build_description_search_document(
                            row.get('summary') or '',
                            row.get('subjects') if row.get('subjects') is not None else '[]',
                        )
                    ).strip()
            if not text:
                skipped += 1
                database.add_job_log(
                    runner.db,
                    job_id,
                    'info',
                    f'{img_key}: skipped text embed (no embeddable document)',
                )
                processed_pairs.add(pair_label(img_key, itype))
                if not persist_progress():
                    return
                continue

            batch_buf.append((img_key, text))
            if len(batch_buf) >= 16:
                if not flush_batch(batch_buf):
                    if runner.is_cancelled(job_id):
                        runner.finalize_cancelled(job_id)
                    return
                row_status = get_job(runner.db, job_id)
                if row_status and row_status.get('status') == 'failed':
                    return

        if not flush_batch(batch_buf):
            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
            return

        if runner.is_cancelled(job_id):
            runner.finalize_cancelled(job_id)
            return

        row_done = get_job(runner.db, job_id)
        if row_done and row_done.get('status') == 'failed':
            return

        runner.clear_checkpoint(job_id)
        runner.complete_job(
            job_id,
            {
                'embedded': embedded,
                'skipped': skipped,
                'failed': failed,
                'total': total_at_start,
            },
        )
    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)
    finally:
        if lib_db:
            lib_db.close()


def handle_batch_embed_image(runner, job_id: str, metadata: dict) -> None:
    """Embed catalog and/or Instagram dump images into ``image_clip_embeddings`` (sqlite-vec)."""
    with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
        _handle_batch_embed_image_inner(runner, job_id, metadata)


def _handle_batch_embed_image_inner(runner, job_id: str, metadata: dict) -> None:
    lib_db = None
    try:
        raw_scope = metadata.get('image_type', 'catalog')
        image_type = str(raw_scope).strip() if raw_scope is not None else 'catalog'
        if image_type not in ('catalog', 'catalog_and_instagram'):
            runner.fail_job(
                job_id,
                (
                    "batch_embed_image: image_type must be 'catalog' "
                    "or 'catalog_and_instagram'"
                ),
                severity='warning',
            )
            return

        db_path = _resolve_library_db_or_fail(runner, job_id)
        if db_path is None:
            return
        lib_db = init_database(db_path)

        chain_mode = bool(metadata.get('_catalog_cache_chain'))

        if not chain_mode:
            database.add_job_log(
                runner.db,
                job_id,
                'info',
                f'batch_embed_image: model={CLIP_EMBED_MODEL_ID}',
            )
            database.add_job_log(
                runner.db,
                job_id,
                'info',
                (
                    'batch_embed_image stage=precompute_embeddings '
                    '(builds similarity index only; does not produce matches). '
                    'After completion, run vision_match or stack detection.'
                ),
            )

        months, year = _resolve_date_window(metadata)
        min_rating_raw = metadata.get('min_rating')
        min_rating = None
        if min_rating_raw is not None:
            try:
                min_rating = int(min_rating_raw)
            except (TypeError, ValueError):
                min_rating = None

        force = bool(metadata.get('force', False))
        if not chain_mode:
            database.add_job_log(
                runner.db,
                job_id,
                'info',
                (
                    'batch_embed_image filters: '
                    f'force={force}, months={months}, year={year}, min_rating={min_rating}'
                ),
            )
        if image_type == 'catalog':
            if force:
                full_list = list_catalog_keys_for_clip_embed_force(
                    lib_db, months=months, year=year, min_rating=min_rating
                )
            else:
                full_list = list_catalog_keys_needing_clip_embedding(
                    lib_db, months=months, year=year, min_rating=min_rating
                )
        else:
            if force:
                cat_keys = list_catalog_keys_for_clip_embed_force(
                    lib_db, months=months, year=year, min_rating=min_rating
                )
                ig_keys = list_instagram_dump_keys_for_clip_embed_force(
                    lib_db, months=months, year=year, min_rating=min_rating
                )
            else:
                cat_keys = list_catalog_keys_needing_clip_embedding(
                    lib_db, months=months, year=year, min_rating=min_rating
                )
                ig_keys = list_instagram_dump_keys_needing_clip_embedding(
                    lib_db, months=months, year=year, min_rating=min_rating
                )
            overlap = set(cat_keys) & set(ig_keys)
            if overlap:
                database.add_job_log(
                    runner.db,
                    job_id,
                    'warning',
                    (
                        'batch_embed_image: catalog and Instagram dump share '
                        f'{len(overlap)} key(s); embedding each once'
                    ),
                )
            seen_keys: set[str] = set()
            full_list = []
            for k in cat_keys:
                if k not in seen_keys:
                    seen_keys.add(k)
                    full_list.append(k)
            for k in ig_keys:
                if k not in seen_keys:
                    seen_keys.add(k)
                    full_list.append(k)

        total_at_start = len(full_list)
        fp = fingerprint_batch_embed_image(
            metadata, full_list, resolved_months=months, resolved_year=year
        )

        processed_pairs: set[str] = set()
        if not chain_mode:
            row_job = get_job(runner.db, job_id)
            if row_job:
                meta_job = row_job.get('metadata') or {}
                if isinstance(meta_job, dict):
                    chk = meta_job.get('checkpoint')
                    if (
                        isinstance(chk, dict)
                        and chk.get('checkpoint_version') == 1
                        and chk.get('job_type') == 'batch_embed_image'
                    ):
                        if chk.get('fingerprint') == fp:
                            processed_pairs = set(chk.get('processed_pairs') or [])
                        elif chk.get('fingerprint'):
                            database.add_job_log(
                                runner.db,
                                job_id,
                                'info',
                                'checkpoint mismatch: batch_embed_image fingerprint changed, starting fresh',
                            )

        remaining = [k for k in full_list if k not in processed_pairs]
        runner.update_progress(
            job_id,
            5,
            f'Found {total_at_start} images to embed ({len(remaining)} remaining)',
        )

        if total_at_start == 0:
            if not chain_mode:
                runner.clear_checkpoint(job_id)
            runner.complete_job(
                job_id,
                {
                    'embedded': 0,
                    'skipped': 0,
                    'failed': 0,
                    'total': 0,
                    'skip_reason_counts': empty_skip_reason_counts(),
                },
            )
            return

        embedded = 0
        skipped = 0
        failed = 0
        path_diag = PathSkipDiagnostics(
            runner,
            job_id,
            lib_db,
            job_label='batch_embed_image',
            chain_mode=chain_mode,
            log_action='image embed',
            sample_size=_EMBED_PREFLIGHT_SAMPLE_SIZE,
            fail_ratio=_EMBED_PREFLIGHT_FAIL_RATIO,
        )
        buf_keys: list[str] = []
        buf_paths: list[str] = []

        if not path_diag.run_preflight(remaining):
            return

        def persist_progress() -> bool:
            if len(processed_pairs) > _CHECKPOINT_MAX_ENTRIES:
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
                {
                    'job_type': 'batch_embed_image',
                    'fingerprint': fp,
                    'processed_pairs': sorted(processed_pairs),
                    'total_at_start': total_at_start,
                },
            )
            return True

        def flush_batch() -> bool:
            nonlocal embedded, failed
            if not buf_keys:
                return True
            try:
                vecs = encode_images(buf_paths, batch_size=_BATCH_EMBED_IMAGE_SIZE)
            except Exception as enc_err:
                database.add_job_log(runner.db, job_id, 'warning',
                            f'batch encode failed ({enc_err}), retrying one by one')
                # Fall back to per-image encoding so one bad file doesn't lose the whole batch.
                import numpy as np
                vecs_list = []
                for path, img_key in zip(buf_paths, buf_keys):
                    try:
                        row_vec = encode_images([path], batch_size=1)
                        vecs_list.append(row_vec[0])
                    except Exception as per_err:
                        path_diag.record_skip(
                            'encode_failed',
                            img_key,
                            detail=str(per_err),
                        )
                        vecs_list.append(None)
                vecs = vecs_list  # type: ignore[assignment]
            for j, img_key in enumerate(buf_keys):
                if runner.is_cancelled(job_id):
                    return False
                vec = vecs[j]
                if vec is None:
                    failed += 1
                    path_diag.skip_reason_counts['encode_failed'] += 1
                    processed_pairs.add(img_key)
                else:
                    vec_blob = numpy_to_clip_vec_blob(vec)
                    with library_write(lib_db):
                        upsert_image_clip_embedding(lib_db, img_key, vec_blob)
                    processed_pairs.add(img_key)
                    embedded += 1
                if not persist_progress():
                    return False
                pct = int(5 + ((embedded + skipped + failed) / max(total_at_start, 1)) * 95)
                runner.update_progress(job_id, pct, f'Embedded {embedded}/{total_at_start}')
                path_diag.maybe_log_summary(
                    embedded + skipped + failed,
                    total_at_start,
                    embedded=embedded,
                    skipped=skipped,
                    failed=failed,
                )
            buf_keys.clear()
            buf_paths.clear()
            return True

        for key in remaining:
            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
                return
            filepath, skip_reason, skip_detail = path_diag.classify(key)
            if skip_reason:
                skipped += 1
                path_diag.record_skip(skip_reason, key, detail=skip_detail)
                processed_pairs.add(key)
                if not persist_progress():
                    return
                pct = int(5 + ((embedded + skipped) / max(total_at_start, 1)) * 95)
                runner.update_progress(job_id, pct, f'Embedded {embedded}/{total_at_start} (skipped {skipped})')
                path_diag.maybe_log_summary(
                    embedded + skipped + failed,
                    total_at_start,
                    embedded=embedded,
                    skipped=skipped,
                    failed=failed,
                )
                continue

            buf_keys.append(key)
            buf_paths.append(filepath)
            if len(buf_keys) >= _BATCH_EMBED_IMAGE_SIZE:
                if not flush_batch():
                    if runner.is_cancelled(job_id):
                        runner.finalize_cancelled(job_id)
                    return
                row_status = get_job(runner.db, job_id)
                if row_status and row_status.get('status') == 'failed':
                    return

        if not flush_batch():
            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
            return

        if runner.is_cancelled(job_id):
            runner.finalize_cancelled(job_id)
            return

        row_done = get_job(runner.db, job_id)
        if row_done and row_done.get('status') == 'failed':
            return

        if not chain_mode:
            runner.clear_checkpoint(job_id)
        runner.complete_job(
            job_id,
            {
                'embedded': embedded,
                'skipped': skipped,
                'failed': failed,
                'total': total_at_start,
                'skip_reason_counts': path_diag.skip_reason_counts,
            },
        )
    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)
    finally:
        if lib_db:
            lib_db.close()
