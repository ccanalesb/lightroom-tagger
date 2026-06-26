"""Shared path preflight and skip-reason diagnostics for path-dependent jobs."""

from __future__ import annotations

import os
import random
from typing import Callable

import database

from lightroom_tagger.core.database import (
    VISION_CACHE_OVERSIZED_SENTINEL,
    get_vision_cached_image,
    resolve_filepath,
)
from lightroom_tagger.core.vision_cache import get_or_create_cached_image

PREFLIGHT_SAMPLE_SIZE = 25
PREFLIGHT_FAIL_RATIO = 0.5
SKIP_DETAIL_LOG_LIMIT = 5
SUMMARY_LOG_EVERY = 250

# Test-only seed override for deterministic random.sample() in tests.
_PREFLIGHT_RNG_SEED: int | None = None

SKIP_REASON_BUCKETS = (
    'no_row',
    'empty_path',
    'unresolved_or_missing',
    'encode_failed',
)

SKIP_REASON_MESSAGES = {
    'no_row': 'catalog/dump row missing',
    'empty_path': 'filepath is empty',
    'unresolved_or_missing': 'resolved path missing or inaccessible',
    'encode_failed': 'compression/viewable image unavailable',
}


def empty_skip_reason_counts() -> dict[str, int]:
    return {bucket: 0 for bucket in SKIP_REASON_BUCKETS}


def try_vision_cache(lib_db, image_key: str) -> str | None:
    """Return cached compressed JPEG path when usable on disk (cache-first)."""
    cached_row = get_vision_cached_image(lib_db, image_key)
    if not cached_row:
        return None
    comp = str(cached_row.get('compressed_path') or '').strip()
    if not comp or comp == VISION_CACHE_OVERSIZED_SENTINEL:
        return None
    if not os.path.isfile(comp):
        return None
    return comp


def classify_path(
    lib_db,
    image_key: str,
) -> tuple[str | None, str | None, str | None]:
    """Classify catalog or Instagram dump path accessibility.

    Returns ``(usable_path, skip_reason, skip_detail)``. When ``skip_reason`` is
    set, ``usable_path`` is ``None``.
    """
    cached_now = try_vision_cache(lib_db, image_key)
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


class PathSkipDiagnostics:
    """Preflight sampler + grouped skip-reason counters for one job."""

    def __init__(
        self,
        runner,
        job_id: str,
        lib_db,
        *,
        job_label: str,
        chain_mode: bool = False,
        log_action: str = 'skipped',
        sample_size: int | None = None,
        fail_ratio: float | None = None,
    ) -> None:
        self.runner = runner
        self.job_id = job_id
        self.lib_db = lib_db
        self.job_label = job_label
        self.chain_mode = chain_mode
        self.log_action = log_action
        self.sample_size = PREFLIGHT_SAMPLE_SIZE if sample_size is None else sample_size
        self.fail_ratio = PREFLIGHT_FAIL_RATIO if fail_ratio is None else fail_ratio
        self.skip_reason_counts = empty_skip_reason_counts()
        self._skip_detail_logged = {bucket: 0 for bucket in SKIP_REASON_BUCKETS}
        self._summary_marker = 0

    def classify(self, image_key: str) -> tuple[str | None, str | None, str | None]:
        return classify_path(self.lib_db, image_key)

    def record_skip(
        self,
        reason: str,
        image_key: str,
        *,
        detail: str | None = None,
        log_prefix: str = '',
    ) -> None:
        if reason not in self.skip_reason_counts:
            return
        self.skip_reason_counts[reason] += 1
        reason_msg = SKIP_REASON_MESSAGES.get(reason, reason)
        detail_suffix = f" ({detail})" if detail else ''
        message = (
            f'{log_prefix}{image_key}: skipped {self.log_action} ({reason_msg}){detail_suffix}'
            if log_prefix
            else f'{image_key}: skipped {self.log_action} ({reason_msg}){detail_suffix}'
        )
        self._maybe_log_skip_detail(reason, message)

    def maybe_log_summary(
        self,
        done: int,
        total: int,
        *,
        embedded: int | None = None,
        skipped: int | None = None,
        failed: int | None = None,
        extra: str = '',
    ) -> None:
        if done - self._summary_marker < SUMMARY_LOG_EVERY and done != total:
            return
        self._summary_marker = done
        parts = [f'done={done}/{total}']
        if embedded is not None:
            parts.append(f'embedded={embedded}')
        if skipped is not None:
            parts.append(f'skipped={skipped}')
        if failed is not None:
            parts.append(f'failed={failed}')
        parts.append(f'reasons={self.skip_reason_counts}')
        if extra:
            parts.append(extra)
        database.add_job_log(
            self.runner.db,
            self.job_id,
            'info',
            f'{self.job_label}-summary {" ".join(parts)}',
        )

    def run_preflight(self, keys: list[str]) -> bool:
        """Sample keys for path accessibility.

        Returns ``False`` when the job should abort (fatal preflight).
        """
        sample_size = min(len(keys), self.sample_size)
        if sample_size <= 0:
            return True

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
        preflight_rng = random.Random(_PREFLIGHT_RNG_SEED)
        sample_keys = (
            preflight_rng.sample(keys, sample_size)
            if len(keys) > sample_size
            else list(keys)
        )
        for sample_key in sample_keys:
            _, sample_reason, sample_detail = self.classify(sample_key)
            if sample_reason in sample_failures:
                sample_failures[sample_reason] += 1
                if len(sample_examples[sample_reason]) < 3:
                    detail = f" ({sample_detail})" if sample_detail else ''
                    sample_examples[sample_reason].append(f'{sample_key}{detail}')

        sample_failed_count = (
            sample_failures['no_row']
            + sample_failures['empty_path']
            + sample_failures['unresolved_or_missing']
        )
        fail_ratio = sample_failed_count / sample_size
        if fail_ratio <= self.fail_ratio:
            return True

        preflight_msg = (
            f'{self.job_label} preflight: {sample_failed_count}/{sample_size} sampled images '
            'have missing or inaccessible paths '
            f"(no_row={sample_failures['no_row']}, empty_path={sample_failures['empty_path']}, "
            f"unresolved_or_missing={sample_failures['unresolved_or_missing']}). "
            f"Examples: no_row={sample_examples['no_row']}, "
            f"empty_path={sample_examples['empty_path']}, "
            f"unresolved_or_missing={sample_examples['unresolved_or_missing']}."
        )
        if self.chain_mode:
            database.add_job_log(
                self.runner.db,
                self.job_id,
                'warning',
                f'{preflight_msg} Continuing — missing files will be skipped per-image.',
            )
            return True

        abort_msg = (
            f'{sample_failed_count}/{sample_size} sampled paths unreachable — '
            'this usually means your network share is not mounted. '
            'Check your mount and retry.'
        )
        database.add_job_log(self.runner.db, self.job_id, 'error', abort_msg)
        self.runner.fail_job(self.job_id, abort_msg, severity='critical')
        return False

    def _maybe_log_skip_detail(self, reason: str, message: str) -> None:
        count = self._skip_detail_logged.get(reason, 0)
        if count < SKIP_DETAIL_LOG_LIMIT:
            database.add_job_log(self.runner.db, self.job_id, 'warning', message)
            self._skip_detail_logged[reason] = count + 1
            return
        if count == SKIP_DETAIL_LOG_LIMIT:
            database.add_job_log(
                self.runner.db,
                self.job_id,
                'info',
                (
                    f'additional {reason} skip logs suppressed after '
                    f'{SKIP_DETAIL_LOG_LIMIT} samples; see skip_reason_counts'
                ),
            )
            self._skip_detail_logged[reason] = count + 1


def classify_path_for_key(
    lib_db,
    image_key: str,
    itype: str,
) -> tuple[str | None, str | None, str | None]:
    """Classify path for catalog or Instagram keys used by describe/score jobs."""
    return classify_path(lib_db, image_key)


def make_path_classify_fn(lib_db) -> Callable[[str], tuple[str | None, str | None, str | None]]:
    return lambda image_key: classify_path(lib_db, image_key)
