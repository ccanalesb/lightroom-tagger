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
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

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
    provider_id: Any,
    provider_model: Any,
    max_workers: int,
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
        "threshold": float(threshold),
        "weights": stable_weights,
        "year": year,
    }
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
