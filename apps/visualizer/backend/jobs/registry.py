"""Explicit job-type registry for the visualizer job processor.

``JOB_TYPES`` is the single source of truth for dispatch, catalog requirements,
and checkpoint co-location. Mirrors ADR-0006's explicit CLI ``COMMANDS`` list —
greppable, no decorators, no auto-discovery.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .checkpoint import (
    build_batch_describe_checkpoint_body,
    build_batch_embed_image_checkpoint_body,
    build_batch_score_checkpoint_body,
    build_batch_stack_detect_checkpoint_body,
    build_batch_text_embed_checkpoint_body,
    build_enrich_catalog_checkpoint_body,
    build_prepare_catalog_checkpoint_body,
    build_vision_match_checkpoint_body,
    fingerprint_batch_describe,
    fingerprint_batch_embed_image,
    fingerprint_batch_score,
    fingerprint_batch_stack_detect,
    fingerprint_batch_text_embed,
    fingerprint_catalog_keys,
    fingerprint_vision_match,
    resume_processed_image_keys,
    resume_processed_media_keys,
    resume_processed_pairs,
    resume_processed_triplets,
)
from .handlers.analyze import (
    handle_batch_analyze,
    handle_batch_describe,
    handle_batch_score,
    handle_single_describe,
    handle_single_score,
)
from .handlers.catalog import handle_catalog_sync
from .handlers.embed import handle_batch_embed_image, handle_batch_text_embed
from .handlers.instagram import handle_analyze_instagram, handle_instagram_import
from .handlers.matching import (
    handle_enrich_catalog,
    handle_prepare_catalog,
    handle_vision_match,
)
from .handlers.stacks import (
    handle_batch_catalog_similarity,
    handle_batch_stack_detect,
    handle_catalog_cache_build,
)

HandlerFn = Callable[..., Any]
CheckpointFn = Callable[..., Any]


@dataclass(frozen=True)
class JobType:
    name: str
    handler: HandlerFn
    fingerprint: CheckpointFn | None
    resume_loader: CheckpointFn | None
    build_checkpoint_body: CheckpointFn | None
    checkpoint_mismatch_message: str | None
    requires_catalog: bool


JOB_TYPES: list[JobType] = [
    JobType(
        'analyze_instagram',
        handle_analyze_instagram,
        None,
        None,
        None,
        None,
        requires_catalog=False,
    ),
    JobType(
        'instagram_import',
        handle_instagram_import,
        None,
        None,
        None,
        None,
        requires_catalog=True,
    ),
    JobType(
        'vision_match',
        handle_vision_match,
        fingerprint_vision_match,
        resume_processed_media_keys,
        build_vision_match_checkpoint_body,
        'checkpoint mismatch: vision_match fingerprint changed, starting fresh',
        requires_catalog=True,
    ),
    JobType(
        'enrich_catalog',
        handle_enrich_catalog,
        fingerprint_catalog_keys,
        resume_processed_image_keys,
        build_enrich_catalog_checkpoint_body,
        'checkpoint mismatch: enrich_catalog fingerprint changed, starting fresh',
        requires_catalog=True,
    ),
    JobType(
        'prepare_catalog',
        handle_prepare_catalog,
        fingerprint_catalog_keys,
        resume_processed_image_keys,
        build_prepare_catalog_checkpoint_body,
        'checkpoint mismatch: prepare_catalog fingerprint changed, starting fresh',
        requires_catalog=True,
    ),
    JobType(
        'batch_describe',
        handle_batch_describe,
        fingerprint_batch_describe,
        resume_processed_pairs,
        build_batch_describe_checkpoint_body,
        'checkpoint mismatch: batch_describe fingerprint changed, starting fresh',
        requires_catalog=True,
    ),
    JobType(
        'single_describe',
        handle_single_describe,
        None,
        None,
        None,
        None,
        requires_catalog=True,
    ),
    JobType(
        'single_score',
        handle_single_score,
        None,
        None,
        None,
        None,
        requires_catalog=True,
    ),
    JobType(
        'batch_score',
        handle_batch_score,
        fingerprint_batch_score,
        resume_processed_triplets,
        build_batch_score_checkpoint_body,
        'checkpoint mismatch: batch_score fingerprint changed, starting fresh',
        requires_catalog=True,
    ),
    JobType(
        'batch_analyze',
        handle_batch_analyze,
        None,
        None,
        None,
        None,
        requires_catalog=True,
    ),
    JobType(
        'batch_stack_detect',
        handle_batch_stack_detect,
        fingerprint_batch_stack_detect,
        resume_processed_image_keys,
        build_batch_stack_detect_checkpoint_body,
        'checkpoint mismatch: batch_stack_detect fingerprint changed, starting fresh',
        requires_catalog=True,
    ),
    JobType(
        'batch_catalog_similarity',
        handle_batch_catalog_similarity,
        None,
        None,
        None,
        None,
        requires_catalog=True,
    ),
    JobType(
        'batch_text_embed',
        handle_batch_text_embed,
        fingerprint_batch_text_embed,
        resume_processed_pairs,
        build_batch_text_embed_checkpoint_body,
        'checkpoint mismatch: batch_text_embed fingerprint changed, starting fresh',
        requires_catalog=True,
    ),
    JobType(
        'batch_embed_image',
        handle_batch_embed_image,
        fingerprint_batch_embed_image,
        resume_processed_pairs,
        build_batch_embed_image_checkpoint_body,
        'checkpoint mismatch: batch_embed_image fingerprint changed, starting fresh',
        requires_catalog=True,
    ),
    JobType(
        'catalog_sync',
        handle_catalog_sync,
        None,
        None,
        None,
        None,
        requires_catalog=True,
    ),
    JobType(
        'catalog_cache_build',
        handle_catalog_cache_build,
        None,
        None,
        None,
        None,
        requires_catalog=True,
    ),
]

JOB_TYPES_BY_NAME: dict[str, JobType] = {jt.name: jt for jt in JOB_TYPES}


def get_job_handler(job_type: str) -> HandlerFn | None:
    """Return the handler for ``job_type``, or ``None`` if unknown."""
    entry = JOB_TYPES_BY_NAME.get(job_type)
    return entry.handler if entry else None


def catalog_requiring_job_types() -> frozenset[str]:
    """Job types whose handlers open the Lightroom catalog SQLite mirror."""
    return frozenset(jt.name for jt in JOB_TYPES if jt.requires_catalog)
