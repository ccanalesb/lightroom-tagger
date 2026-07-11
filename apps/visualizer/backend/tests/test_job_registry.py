"""Tests for the explicit ``JOB_TYPES`` job-type registry."""

from __future__ import annotations

from jobs.handlers import JOB_HANDLERS
from jobs.handlers.analyze import (
    handle_batch_analyze,
    handle_batch_describe,
    handle_batch_score,
    handle_single_describe,
    handle_single_score,
)
from jobs.handlers.catalog import handle_catalog_sync
from jobs.handlers.embed import handle_batch_embed_image, handle_batch_text_embed
from jobs.handlers.instagram import handle_analyze_instagram, handle_instagram_import
from jobs.handlers.matching import (
    handle_enrich_catalog,
    handle_prepare_catalog,
    handle_vision_match,
)
from jobs.handlers.stacks import (
    handle_batch_catalog_similarity,
    handle_batch_stack_detect,
    handle_catalog_cache_build,
)
from jobs.registry import JOB_TYPES, JOB_TYPES_BY_NAME, catalog_requiring_job_types
from library_db import JOB_TYPES_REQUIRING_CATALOG

# Snapshot of the pre-registry handler map — guards against accidental drift.
_EXPECTED_JOB_HANDLERS = {
    'analyze_instagram': handle_analyze_instagram,
    'instagram_import': handle_instagram_import,
    'vision_match': handle_vision_match,
    'enrich_catalog': handle_enrich_catalog,
    'prepare_catalog': handle_prepare_catalog,
    'batch_describe': handle_batch_describe,
    'single_describe': handle_single_describe,
    'single_score': handle_single_score,
    'batch_score': handle_batch_score,
    'batch_analyze': handle_batch_analyze,
    'batch_stack_detect': handle_batch_stack_detect,
    'batch_catalog_similarity': handle_batch_catalog_similarity,
    'batch_text_embed': handle_batch_text_embed,
    'batch_embed_image': handle_batch_embed_image,
    'catalog_sync': handle_catalog_sync,
    'catalog_cache_build': handle_catalog_cache_build,
}

_EXPECTED_CATALOG_JOB_TYPES = frozenset(
    {
        'vision_match',
        'enrich_catalog',
        'prepare_catalog',
        'batch_describe',
        'batch_score',
        'batch_analyze',
        'batch_stack_detect',
        'batch_catalog_similarity',
        'batch_text_embed',
        'batch_embed_image',
        'single_describe',
        'single_score',
        'instagram_import',
        'catalog_cache_build',
        'catalog_sync',
    }
)

_COMPOSITE_JOB_TYPES = frozenset({'batch_analyze', 'catalog_cache_build'})


def test_job_types_has_exactly_one_entry_per_enqueueable_type():
    names = [jt.name for jt in JOB_TYPES]
    assert len(names) == len(set(names))
    assert len(JOB_TYPES) == len(_EXPECTED_JOB_HANDLERS)


def test_job_types_by_name_matches_list():
    assert set(JOB_TYPES_BY_NAME) == {jt.name for jt in JOB_TYPES}
    for jt in JOB_TYPES:
        assert JOB_TYPES_BY_NAME[jt.name] is jt


def test_derived_job_handlers_matches_legacy_map():
    assert JOB_HANDLERS == _EXPECTED_JOB_HANDLERS


def test_derived_catalog_set_matches_legacy_set():
    assert catalog_requiring_job_types() == _EXPECTED_CATALOG_JOB_TYPES
    assert JOB_TYPES_REQUIRING_CATALOG == _EXPECTED_CATALOG_JOB_TYPES


def test_checkpoint_fields_are_all_present_or_all_none():
    for jt in JOB_TYPES:
        fields = (
            jt.fingerprint,
            jt.resume_loader,
            jt.build_checkpoint_body,
            jt.checkpoint_mismatch_message,
        )
        assert all(f is None for f in fields) or all(
            f is not None for f in fields
        ), f'{jt.name}: checkpoint fields must be uniformly None or present'


def test_composite_job_types_have_no_checkpoint_fields():
    for name in _COMPOSITE_JOB_TYPES:
        jt = JOB_TYPES_BY_NAME[name]
        assert jt.fingerprint is None
        assert jt.resume_loader is None
        assert jt.build_checkpoint_body is None
        assert jt.checkpoint_mismatch_message is None


def test_analyze_instagram_does_not_require_catalog():
    jt = JOB_TYPES_BY_NAME['analyze_instagram']
    assert jt.requires_catalog is False
    assert 'analyze_instagram' not in JOB_TYPES_REQUIRING_CATALOG
