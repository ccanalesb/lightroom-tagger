"""CLIP / text embedding job handlers (catalog + Instagram dump)."""

from __future__ import annotations

import os
import random

from database import add_job_log, get_job

from lightroom_tagger.core import cancel_scope
from lightroom_tagger.core.clip_embedding_service import (
    CLIP_EMBED_MODEL_ID,
    encode_images,
    numpy_to_clip_vec_blob,
)
from lightroom_tagger.core.database import (
    VISION_CACHE_OVERSIZED_SENTINEL,
    build_description_search_document,
    get_vision_cached_image,
    init_database,
    library_write,
    list_catalog_keys_for_clip_embed_force,
    list_catalog_keys_for_text_embed_force,
    list_catalog_keys_needing_clip_embedding,
    list_catalog_keys_needing_text_embedding,
    list_instagram_dump_keys_for_clip_embed_force,
    list_instagram_dump_keys_needing_clip_embedding,
    resolve_filepath,
    upsert_image_clip_embedding,
    upsert_image_text_embedding,
)
from lightroom_tagger.core.embedding_service import (
    TEXT_EMBED_MODEL_ID,
    embed_texts,
    numpy_to_vec_blob,
)
from lightroom_tagger.core.vision_cache import get_or_create_cached_image

from ..checkpoint import fingerprint_batch_embed_image, fingerprint_batch_text_embed

from .common import (
    _CHECKPOINT_MAX_ENTRIES,
    _failure_severity_from_exception,
    _resolve_date_window,
    _resolve_library_db_or_fail,
)

_BATCH_EMBED_IMAGE_SIZE = 8
_EMBED_PREFLIGHT_SAMPLE_SIZE = 25
_EMBED_PREFLIGHT_FAIL_RATIO = 0.5
_EMBED_SKIP_DETAIL_LOG_LIMIT = 5
_EMBED_SUMMARY_LOG_EVERY = 250

# Test-only seed override for the embed preflight sampler. Setting this from a
# test gives deterministic random.sample() output without exposing the seed in
# production behaviour. ``None`` (default) uses real entropy.
_PREFLIGHT_RNG_SEED: int | None = None


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

        add_job_log(
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
                        add_job_log(
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
                add_job_log(
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
            add_job_log(
                runner.db,
                job_id,
                'info',
                f'batch_embed_image: model={CLIP_EMBED_MODEL_ID}',
            )
            add_job_log(
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
            add_job_log(
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
                add_job_log(
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
                            add_job_log(
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
                    'skip_reason_counts': {
                        'no_row': 0,
                        'empty_path': 0,
                        'unresolved_or_missing': 0,
                        'encode_failed': 0,
                    },
                },
            )
            return

        embedded = 0
        skipped = 0
        failed = 0
        # D-07 embed diagnostics (stable keys): no_row → no catalog/dump row;
        # empty_path → empty filepath; unresolved_or_missing → missing file or
        # unreachable path; encode_failed → vision-cache/encode path failures.
        skip_reason_counts = {
            'no_row': 0,
            'empty_path': 0,
            'unresolved_or_missing': 0,
            'encode_failed': 0,
        }
        buf_keys: list[str] = []
        buf_paths: list[str] = []
        skip_detail_logged = {
            'no_row': 0,
            'empty_path': 0,
            'unresolved_or_missing': 0,
            'encode_failed': 0,
        }
        summary_marker = 0

        def _try_vision_cache(image_key: str) -> str | None:
            """Return the cached compressed JPEG path when it exists on disk.

            Cache-first short-circuit: ``prepare_catalog`` may already have
            decoded + JPEG-compressed this image, in which case the original
            RAW/JPG can be missing or unmounted and we still have everything
            embedding needs. Skips the OVERSIZED sentinel and any row whose
            ``compressed_path`` no longer exists on disk (stale cache).
            """
            cached_row = get_vision_cached_image(lib_db, image_key)
            if not cached_row:
                return None
            comp = str(cached_row.get('compressed_path') or '').strip()
            if not comp or comp == VISION_CACHE_OVERSIZED_SENTINEL:
                return None
            if not os.path.isfile(comp):
                return None
            return comp

        def classify_path(image_key: str) -> tuple[str | None, str | None, str | None]:
            cached_now = _try_vision_cache(image_key)
            if cached_now is not None:
                return cached_now, None, None

            row = lib_db.execute(
                "SELECT filepath FROM images WHERE key = ?",
                (image_key,),
            ).fetchone()
            if row:
                filepath = str(row['filepath'] or '').strip()
                if not filepath:
                    return None, 'empty_path', None
                resolved = resolve_filepath(filepath)
                if not resolved or not os.path.isfile(resolved):
                    return None, 'unresolved_or_missing', (resolved or filepath)
                cached = get_or_create_cached_image(lib_db, image_key, resolved)
                if cached and os.path.isfile(cached):
                    return cached, None, None
                # Compression/viewable conversion can fail for unsupported sources
                # (e.g. videos/motion-photo sidecars). Treat as encode failure so
                # preflight keeps focusing on true path accessibility problems.
                return None, 'encode_failed', resolved

            row_dm = lib_db.execute(
                "SELECT file_path FROM instagram_dump_media WHERE media_key = ?",
                (image_key,),
            ).fetchone()
            if row_dm:
                filepath = str(row_dm['file_path'] or '').strip()
                if not filepath:
                    return None, 'empty_path', None
                resolved = resolve_filepath(filepath)
                if not resolved or not os.path.isfile(resolved):
                    return None, 'unresolved_or_missing', (resolved or filepath)
                cached = get_or_create_cached_image(lib_db, image_key, resolved)
                if cached and os.path.isfile(cached):
                    return cached, None, None
                return None, 'encode_failed', resolved

            return None, 'no_row', None

        def maybe_log_skip_detail(reason: str, message: str) -> None:
            count = skip_detail_logged.get(reason, 0)
            if count < _EMBED_SKIP_DETAIL_LOG_LIMIT:
                add_job_log(runner.db, job_id, 'warning', message)
                skip_detail_logged[reason] = count + 1
                return
            if count == _EMBED_SKIP_DETAIL_LOG_LIMIT:
                add_job_log(
                    runner.db,
                    job_id,
                    'info',
                    (
                        f'additional {reason} skip logs suppressed after '
                        f'{_EMBED_SKIP_DETAIL_LOG_LIMIT} samples; see skip_reason_counts'
                    ),
                )
                skip_detail_logged[reason] = count + 1

        def maybe_log_summary() -> None:
            nonlocal summary_marker
            done = embedded + skipped + failed
            if done - summary_marker < _EMBED_SUMMARY_LOG_EVERY and done != total_at_start:
                return
            summary_marker = done
            add_job_log(
                runner.db,
                job_id,
                'info',
                (
                    f'embed-summary done={done}/{total_at_start} embedded={embedded} '
                    f'skipped={skipped} failed={failed} '
                    f'reasons={skip_reason_counts}'
                ),
            )

        sample_size = min(len(remaining), _EMBED_PREFLIGHT_SAMPLE_SIZE)
        if sample_size > 0:
            sample_failures = {
                'no_row': 0,
                'empty_path': 0,
                'unresolved_or_missing': 0,
            }
            sample_examples: dict[str, list[str]] = {
                'no_row': [],
                'empty_path': [],
                'unresolved_or_missing': [],
            }
            # Random sample so a sticky inaccessible subdirectory at the head
            # of the list (e.g. motion-photo lrdata sidecars) doesn't poison
            # the preflight verdict for an otherwise healthy catalog.
            # ``random.Random(None)`` seeds from entropy; tests inject an int.
            preflight_rng = random.Random(_PREFLIGHT_RNG_SEED)
            sample_keys = (
                preflight_rng.sample(remaining, sample_size)
                if len(remaining) > sample_size
                else list(remaining)
            )
            for sample_key in sample_keys:
                _, sample_reason, sample_detail = classify_path(sample_key)
                if sample_reason in sample_failures:
                    sample_failures[sample_reason] += 1
                    if len(sample_examples[sample_reason]) < 3:
                        detail = f" ({sample_detail})" if sample_detail else ""
                        sample_examples[sample_reason].append(f"{sample_key}{detail}")
            sample_failed_count = (
                sample_failures['no_row']
                + sample_failures['empty_path']
                + sample_failures['unresolved_or_missing']
            )
            fail_ratio = sample_failed_count / sample_size
            if fail_ratio > _EMBED_PREFLIGHT_FAIL_RATIO:
                preflight_msg = (
                    f'Embed preflight: {sample_failed_count}/{sample_size} sampled images '
                    'have missing or inaccessible paths '
                    f"(no_row={sample_failures['no_row']}, empty_path={sample_failures['empty_path']}, "
                    f"unresolved_or_missing={sample_failures['unresolved_or_missing']}). "
                    f"Examples: no_row={sample_examples['no_row']}, "
                    f"empty_path={sample_examples['empty_path']}, "
                    f"unresolved_or_missing={sample_examples['unresolved_or_missing']}."
                )
                if chain_mode:
                    add_job_log(
                        runner.db,
                        job_id,
                        'warning',
                        f'{preflight_msg} Continuing — missing files will be skipped per-image.',
                    )
                else:
                    abort_msg = (
                        f'{sample_failed_count}/{sample_size} sampled paths unreachable — '
                        'this usually means your network share is not mounted. '
                        'Check your mount and retry.'
                    )
                    add_job_log(runner.db, job_id, 'error', abort_msg)
                    runner.fail_job(job_id, abort_msg, severity='critical')
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
                add_job_log(runner.db, job_id, 'warning',
                            f'batch encode failed ({enc_err}), retrying one by one')
                # Fall back to per-image encoding so one bad file doesn't lose the whole batch.
                import numpy as np
                vecs_list = []
                for path, img_key in zip(buf_paths, buf_keys):
                    try:
                        row_vec = encode_images([path], batch_size=1)
                        vecs_list.append(row_vec[0])
                    except Exception as per_err:
                        maybe_log_skip_detail(
                            'encode_failed',
                            f'{img_key}: failed to encode ({per_err}), skipping',
                        )
                        vecs_list.append(None)
                vecs = vecs_list  # type: ignore[assignment]
            for j, img_key in enumerate(buf_keys):
                if runner.is_cancelled(job_id):
                    return False
                vec = vecs[j]
                if vec is None:
                    failed += 1
                    skip_reason_counts['encode_failed'] += 1
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
                maybe_log_summary()
            buf_keys.clear()
            buf_paths.clear()
            return True

        for key in remaining:
            if runner.is_cancelled(job_id):
                runner.finalize_cancelled(job_id)
                return
            filepath, skip_reason, skip_detail = classify_path(key)
            if skip_reason:
                skipped += 1
                skip_reason_counts[skip_reason] += 1
                reason_msg = {
                    'no_row': 'catalog/dump row missing',
                    'empty_path': 'filepath is empty',
                    'unresolved_or_missing': 'resolved path missing or inaccessible',
                    'encode_failed': 'compression/viewable image unavailable',
                }[skip_reason]
                detail = f" ({skip_detail})" if skip_detail else ""
                maybe_log_skip_detail(skip_reason, f'{key}: skipped image embed ({reason_msg}){detail}')
                processed_pairs.add(key)
                if not persist_progress():
                    return
                pct = int(5 + ((embedded + skipped) / max(total_at_start, 1)) * 95)
                runner.update_progress(job_id, pct, f'Embedded {embedded}/{total_at_start} (skipped {skipped})')
                maybe_log_summary()
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
                'skip_reason_counts': skip_reason_counts,
            },
        )
    except Exception as e:
        severity = _failure_severity_from_exception(e)
        runner.fail_job(job_id, str(e), severity=severity)
    finally:
        if lib_db:
            lib_db.close()
