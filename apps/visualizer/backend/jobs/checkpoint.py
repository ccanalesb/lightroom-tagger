"""Job checkpoint helpers for persisting resume state in ``jobs.metadata[\"checkpoint\"]``.

Checkpoint payloads are versioned with ``checkpoint_version: 1`` and a fingerprint so
stale metadata from different inputs is ignored (handlers log ``checkpoint mismatch``).

**batch_describe** — ``job_type``, ``fingerprint``, ``processed_pairs`` (``\"key|itype\"`` strings),
``total_at_start``. Fingerprint includes sorted ``perspective_slugs`` when metadata carries a
non-empty list (empty/missing → ``null`` in the canonical payload).

**vision_match** — ``job_type``, ``fingerprint``, ``processed_media_keys`` (Instagram dump
``media_key`` values).

**enrich_catalog** — ``job_type``, ``fingerprint``, ``processed_image_keys`` (catalog image keys).

**prepare_catalog** — ``job_type``, ``fingerprint``, ``processed_image_keys`` (catalog image keys).

**batch_score** — ``job_type``, ``fingerprint``, ``processed_triplets`` (``\"key|itype|slug\"`` strings),
``total_at_start`` (int). Fingerprint canonical JSON matches ``batch_describe`` knobs plus an ordered
triple list (sorted by ``f\"{key}|{itype}|{slug}\"``).

**batch_analyze** — top-level ``job_type: 'batch_analyze'`` with ``stage`` (``'describe'`` or
``'score'``) and two nested objects: ``describe`` (``fingerprint``, ``processed_pairs``,
``total_at_start``) and ``score`` (``fingerprint``, ``processed_triplets``, ``total_at_start``).
``checkpoint_version: 1`` still applies at the merged checkpoint root. Fingerprints for each
``batch_analyze`` sub-object are computed exactly as ``batch_describe`` / ``batch_score`` over
their own slice of ``metadata`` (the analyze handler normalizes ``force_describe`` /
``force_score`` into each sub-payload before fingerprinting).

**batch_text_embed** — ``job_type``, ``fingerprint``, ``processed_pairs`` (``"key|catalog"`` strings),
``total_at_start`` (same semantics as ``batch_describe``).

**batch_embed_image** — ``job_type: 'batch_embed_image'``, ``fingerprint``, ``processed_pairs`` (sorted list of
catalog ``image_key`` strings — the same strings that appear in the fingerprint's ``pairs`` array),
``total_at_start``, ``checkpoint_version: 1``.

**batch_stack_detect** — ``job_type``, ``fingerprint``, ``processed_image_keys`` (catalog ``images.key``
values, sorted on persist), ``total_at_start`` (int), ``checkpoint_version: 1``. Fingerprint includes
``delta_ms`` (resolved ms), ``force_mode`` (``incremental`` | ``full`` | ``preserve_edited``), and
``keys`` (sorted work-list at job start, before checkpoint resume filtering).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from lightroom_tagger.core.clip_embedding_service import CLIP_EMBED_DIM, CLIP_EMBED_MODEL_ID
from lightroom_tagger.core.embedding_service import TEXT_EMBED_DIM, TEXT_EMBED_MODEL_ID

CHECKPOINT_VERSION: int = 1


def fingerprint_batch_describe(
    metadata: dict[str, Any], ordered_pairs: list[tuple[str, str]]
) -> str:
    """SHA-256 hex of canonical JSON for batch_describe inputs and ordered pair list."""
    min_rating_raw = metadata.get("min_rating")
    min_rating: int | None
    try:
        min_rating = int(min_rating_raw) if min_rating_raw is not None else None
    except (TypeError, ValueError):
        min_rating = None
    pairs = [f"{key}|{itype}" for key, itype in ordered_pairs]
    ps_raw = metadata.get("perspective_slugs")
    if isinstance(ps_raw, list) and len(ps_raw) > 0:
        perspective_slugs_fp: Any = sorted(str(x) for x in ps_raw)
    else:
        perspective_slugs_fp = None
    payload = {
        "backfill_visual_tags": bool(metadata.get("backfill_visual_tags", False)),
        "date_filter": metadata.get("date_filter", "all"),
        "force": bool(metadata.get("force", False)),
        "image_type": metadata.get("image_type", "both"),
        "max_workers": int(metadata.get("max_workers", 4)),
        "min_rating": min_rating,
        "pairs": pairs,
        "perspective_slugs": perspective_slugs_fp,
        "provider_id": metadata.get("provider_id"),
        "provider_model": metadata.get("provider_model"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_batch_text_embed(
    metadata: dict[str, Any], ordered_pairs: list[tuple[str, str]]
) -> str:
    """SHA-256 hex of canonical JSON for batch_text_embed inputs and ordered pair list."""
    min_rating_raw = metadata.get("min_rating")
    min_rating: int | None
    try:
        min_rating = int(min_rating_raw) if min_rating_raw is not None else None
    except (TypeError, ValueError):
        min_rating = None
    pairs = sorted(f"{key}|{itype}" for key, itype in ordered_pairs)
    payload = {
        "date_filter": metadata.get("date_filter", "all"),
        "embedding_dim": TEXT_EMBED_DIM,
        "embedding_model_id": TEXT_EMBED_MODEL_ID,
        "force": bool(metadata.get("force", False)),
        "image_type": str(metadata.get("image_type", "catalog")),
        "min_rating": min_rating,
        "pairs": pairs,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalized_batch_embed_image_type(metadata: dict[str, Any]) -> str:
    """Canonical embed scope for resume identity: ``catalog`` vs ``catalog_and_instagram``."""
    raw = metadata.get("image_type", "catalog")
    s = str(raw).strip() if raw is not None else "catalog"
    if s == "catalog_and_instagram":
        return "catalog_and_instagram"
    return "catalog"


def fingerprint_catalog_cache_build(
    metadata: dict[str, Any],
    *,
    resolved_months: int | None = None,
    resolved_year: str | None = None,
) -> str:
    """SHA-256 hex for catalog_cache_build composite job identity (metadata knobs only).

    Mirrors embed/stack/similarity inputs that affect how much work runs — without embedding
    ordered key lists (those vary per catalog snapshot).
    """
    min_rating_raw = metadata.get("min_rating")
    min_rating: int | None
    try:
        min_rating = int(min_rating_raw) if min_rating_raw is not None else None
    except (TypeError, ValueError):
        min_rating = None
    payload: dict[str, Any] = {
        "embedding_dim": CLIP_EMBED_DIM,
        "embedding_model_id": CLIP_EMBED_MODEL_ID,
        "force_embed": bool(metadata.get("force_embed", False)),
        "force_similarity": bool(metadata.get("force_similarity", False)),
        "force_stack": bool(metadata.get("force_stack", False)),
        "image_type": "catalog_and_instagram",
        "last_months": metadata.get("last_months"),
        "min_rating": min_rating,
        "month": metadata.get("month"),
        "resolved_months": resolved_months,
        "resolved_year": resolved_year,
        "year": metadata.get("year"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_batch_embed_image(
    metadata: dict[str, Any],
    ordered_keys: list[str],
    *,
    resolved_months: int | None = None,
    resolved_year: str | None = None,
) -> str:
    """SHA-256 hex of canonical JSON for batch_embed_image inputs and ordered key list.

    Pass ``resolved_months`` and ``resolved_year`` from ``_resolve_date_window`` so the
    fingerprint reflects the *effective* date window rather than the raw metadata string,
    which may represent the same window under multiple spellings (``date_filter='3months'``
    vs ``last_months=3``).
    """
    min_rating_raw = metadata.get("min_rating")
    min_rating: int | None
    try:
        min_rating = int(min_rating_raw) if min_rating_raw is not None else None
    except (TypeError, ValueError):
        min_rating = None
    pairs = sorted(ordered_keys)
    payload = {
        "embedding_dim": CLIP_EMBED_DIM,
        "embedding_model_id": CLIP_EMBED_MODEL_ID,
        "force": bool(metadata.get("force", False)),
        "image_type": _normalized_batch_embed_image_type(metadata),
        "min_rating": min_rating,
        "pairs": pairs,
        "resolved_months": resolved_months,
        "resolved_year": resolved_year,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_batch_stack_detect(
    metadata: dict[str, Any],
    image_keys: list[str],
    *,
    resolved_delta_ms: int,
    force_mode: str,
) -> str:
    """SHA-256 hex of canonical JSON for stack detect run identity (work list + delta + force).

    ``image_keys`` is the **initial** work list (entirety before resume filtering);
    ``sorted(image_keys)`` is stored in the payload as ``keys``.
    ``force_mode`` is ``incremental``, ``full``, or ``preserve_edited`` (caller must normalize per job contract).
    """
    _ = metadata  # Reserved for future fingerprint fields (e.g. filters) without breaking callers
    keys_sorted = sorted(image_keys)
    payload: dict[str, Any] = {
        "delta_ms": int(resolved_delta_ms),
        "force_mode": str(force_mode),
        "keys": keys_sorted,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_batch_score(
    metadata: dict[str, Any], work_units: list[tuple[str, str, str]]
) -> str:
    """SHA-256 hex of canonical JSON for batch_score inputs and ordered work-unit triples."""
    min_rating_raw = metadata.get("min_rating")
    min_rating: int | None
    try:
        min_rating = int(min_rating_raw) if min_rating_raw is not None else None
    except (TypeError, ValueError):
        min_rating = None
    ordered = sorted(work_units, key=lambda u: f"{u[0]}|{u[1]}|{u[2]}")
    triples = [f"{key}|{itype}|{slug}" for key, itype, slug in ordered]
    ps_raw = metadata.get("perspective_slugs")
    if isinstance(ps_raw, list) and len(ps_raw) > 0:
        perspective_slugs_fp: Any = sorted(str(x) for x in ps_raw)
    else:
        perspective_slugs_fp = None
    payload = {
        "date_filter": metadata.get("date_filter", "all"),
        "force": bool(metadata.get("force", False)),
        "image_type": metadata.get("image_type", "both"),
        "max_workers": int(metadata.get("max_workers", 4)),
        "min_rating": min_rating,
        "perspective_slugs": perspective_slugs_fp,
        "provider_id": metadata.get("provider_id"),
        "provider_model": metadata.get("provider_model"),
        "triples": triples,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_vision_match(
    *,
    threshold: float,
    weights: dict[str, Any],
    month: Any,
    year: Any,
    last_months: Any,
    media_key: Any,
    force_reprocess: bool,
    force_descriptions: bool,
    skip_undescribed: bool,
    provider_id: Any,
    provider_model: Any,
    max_workers: int,
    clip_top_k: int = 50,
) -> str:
    """SHA-256 hex of canonical JSON for vision_match checkpoint scope."""
    stable_weights = {k: weights[k] for k in sorted(weights)}
    payload = {
        "force_descriptions": bool(force_descriptions),
        "force_reprocess": bool(force_reprocess),
        "last_months": last_months,
        "max_workers": int(max_workers),
        "media_key": media_key,
        "month": month,
        "provider_id": provider_id,
        "provider_model": provider_model,
        "skip_undescribed": bool(skip_undescribed),
        "threshold": float(threshold),
        "weights": stable_weights,
        "year": year,
    }
    # Omit default so fingerprints match checkpoints from builds before clip_top_k existed.
    if int(clip_top_k) != 50:
        payload["clip_top_k"] = int(clip_top_k)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_catalog_keys(*, total: int, keys: list[str]) -> str:
    """SHA-256 hex for enrich_catalog / prepare_catalog input identity."""
    payload = {"keys": sorted(keys), "total": int(total)}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def merge_checkpoint_into_metadata(
    existing_metadata: dict[str, Any], checkpoint_body: dict[str, Any]
) -> dict[str, Any]:
    """Shallow-copy metadata and set ``checkpoint`` to a versioned body."""
    out = dict(existing_metadata)
    out["checkpoint"] = {"checkpoint_version": CHECKPOINT_VERSION, **checkpoint_body}
    return out
