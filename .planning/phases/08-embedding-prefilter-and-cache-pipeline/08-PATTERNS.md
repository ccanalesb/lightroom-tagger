# Phase 8 — Pattern Map

**Phase:** 8 — Embedding pre-filter & catalog cache pipeline  
**Generated:** 2026-04-27  
**Source inputs:** `08-CONTEXT.md`, `08-RESEARCH.md`, `08-UI-SPEC.md`, `08-VALIDATION.md`, `CONVENTIONS.md`, `STRUCTURE.md`

---

## Files to Modify or Create and Analogs

| Target file | Role | Closest analog | Reuse pattern |
|-------------|------|----------------|---------------|
| `lightroom_tagger/scripts/match_instagram_dump.py` | `match_dump_media`: representative filter → **CLIP shortlist** → `vision_candidates` / `score_candidates_with_vision` | Same file (rep-filter block today) | Insert shortlist after `catalog_key_is_primary_grid_row` filter, before `vision_candidates = []`; plumb `clip_top_k` |
| `lightroom_tagger/core/clip_similarity.py` | New shortlist helper(s): KNN over-fetch + **intersect** with allowed candidate keys | `list_pin_similarity_candidate_keys` | `get_clip_embedding_blob_for_key` + `knn_clip_catalog_keys`; cap via `KNN_K_MAX` |
| `lightroom_tagger/core/matcher.py` | Scoring stack contract: description runs **before** vision inside `score_candidates_with_vision` | Same file | Callers must pass **shortlisted** `candidates` only (D-03); typically no signature change |
| `lightroom_tagger/core/database.py` | Instagram keys needing CLIP rows; embed upsert path | `list_catalog_keys_needing_clip_embedding` + `upsert_image_clip_embedding` | Parallel “list missing vec0” for `instagram_dump_media`; `resolve_filepath` for paths |
| `apps/visualizer/backend/jobs/handlers.py` | `handle_vision_match` + `match_dump_media` kwargs; extend `_handle_batch_embed_image_inner`; **composite cache job** (e.g. `catalog_cache_build`) calling embed → stack → similarity | `handle_batch_stack_detect` / `handle_batch_catalog_similarity` / existing embed inner | `cancel_scope`; shared stage logic; `JOB_HANDLERS` registration |
| `apps/visualizer/backend/jobs/checkpoint.py` | `fingerprint_vision_match` (+ `clip_top_k`); `fingerprint_batch_embed_image` (+ embed **scope** incl. Instagram) | Existing `fingerprint_*` payloads | Canonical JSON + SHA-256; scope must change when IG included |
| `apps/visualizer/backend/library_db.py` | Catalog-required job types set | Current `JOB_TYPES_REQUIRING_CATALOG` | Add new composite job type next to `batch_embed_image` |
| `apps/visualizer/frontend/src/components/processing/MatchingTab.tsx` | `clip_top_k` numeric field; **remove** Catalog Discovery card | Same file (Advanced + vision job today) | Keep `AdvancedOptions`; delete stack/similarity/preview block |
| `apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx` | Primary “Build catalog cache” chain CTA; **Advanced** individual jobs + `prepare_catalog` | `MatchingTab` job buttons + `AdvancedOptions` usage | One primary story; merge/de-emphasize standalone embed row per UI-SPEC |
| `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx` | DRY disclosure + controls (import into cache tab) | Self | Props + ▶/▼ toggle unchanged; do not fork a second advanced component |
| `apps/visualizer/frontend/src/services/api.ts` | `JobsAPI.create` for `vision_match` metadata + new chain type | Existing `create` | Opaque `{ type, metadata }`; invalidate jobs queries |
| `apps/visualizer/frontend/src/constants/strings.ts` | All new/changed copy (top-k, cache CTA, errors, link to cache tab) | Existing `PROCESSING_*` / `ADVANCED_*` | No inline production strings |
| `lightroom_tagger/core/test_clip_similarity.py` | Shortlist unit tests | Existing clip similarity tests | Subset + order + ≤k invariants |
| `apps/visualizer/backend/tests/test_handlers_single_match.py` | Wiring, bounds, summary logs, fingerprint interaction | Existing `add_job_log` capture | Extend with `-k` selectors per validation map |
| `apps/visualizer/backend/tests/test_handlers_batch_embed_image.py` | Instagram / scope in `batch_embed_image` | Existing embed handler tests | Fingerprint + checkpoint when IG toggles |
| `apps/visualizer/backend/tests/test_handlers_catalog_cache_build.py` | Composite chain order + cancel + stage logs | `test_handlers_batch_embed_image.py` style | New file per `08-VALIDATION.md` |
| `apps/visualizer/backend/tests/test_checkpoint_fingerprints.py` | `fingerprint_vision_match` includes `clip_top_k` | Other fingerprint tests if present | New or extend per planner |
| `apps/visualizer/frontend/src/components/processing/__tests__/MatchingTab.test.tsx` | No stack/similarity CTAs; `clip_top_k` metadata | Existing | Per `08-VALIDATION.md` |
| `apps/visualizer/frontend/src/components/processing/__tests__/CatalogCacheTab.test.tsx` | Primary CTA + `AdvancedOptions` reuse | Existing | Per `08-VALIDATION.md` |

---

## Key Existing Snippets to Mirror

### Representative filter then scoring prep (`match_dump_media`)

```152:175:lightroom_tagger/scripts/match_instagram_dump.py
        before_rep_filter = len(candidates)
        candidates = [
            c for c in candidates
            if c.get('key') and catalog_key_is_primary_grid_row(db, c['key'])
        ]
        removed_nr = before_rep_filter - len(candidates)
        if removed_nr:
            stats['non_representative_candidates_filtered'] += removed_nr
            if log_callback:
                log_callback(
                    'info',
                    f'[{media_key}] Representative-only: dropped {removed_nr} non-representative '
                    f'catalog candidate(s) ({before_rep_filter} → {len(candidates)})',
                )

        if log_callback and idx <= 3:
            log_callback('debug', f'[{media_key}] Found {initial_candidate_count} candidates by date, {len(candidates)} after filters')

        if not candidates:
            mark_dump_media_attempted(db, dump_media['media_key'])
            stats['skipped'] += 1
```

**Contract:** Shortlist runs **after** this block (and after empty check), **before** `vision_candidates = []`.

### KNN over-fetch + intersect filter (`list_pin_similarity_candidate_keys`)

```79:94:lightroom_tagger/core/clip_similarity.py
    max_candidates = max(1, int(max_candidates))
    need_neighbors = max(0, max_candidates - 1)
    knn_k = min(KNN_K_MAX, max(50, need_neighbors * 20)) if need_neighbors else 1
    knn_k = min(KNN_K_MAX, max(knn_k, 1))

    raw = knn_clip_catalog_keys(db, blob, k=knn_k)
    out: list[str] = [seed_key]
    for image_key, _dist in raw:
        if image_key == seed_key:
            continue
        if not catalog_key_is_primary_grid_row(db, image_key):
            continue
        out.append(image_key)
        if len(out) >= max_candidates:
            break
```

**Contract:** For matching, replace primary-grid filter with **membership in current `candidates` key set**; seed blob from `get_clip_embedding_blob_for_key(db, dump_media['media_key'])`; respect `KNN_K_MAX = 500`.

### `score_candidates_with_vision` gating order

```232:241:lightroom_tagger/core/matcher.py
    desc_scores_by_idx = _compute_desc_scores_for_candidates(
        insta_image,
        candidates,
        batch_size,
        desc_weight,
        skip_undescribed,
        provider_id,
        model,
        log_callback,
    )
```

**Contract:** Description scoring is first — **shortlist `candidates` before** `score_candidates_with_vision` (D-03).

### `handle_vision_match` → `match_dump_media` plumbing

```432:445:apps/visualizer/backend/jobs/handlers.py
        fp_vm = fingerprint_vision_match(
            threshold=float(custom_threshold),
            weights=dict(custom_weights),
            month=metadata.get('month'),
            year=metadata.get('year'),
            last_months=metadata.get('last_months'),
            media_key=metadata.get('media_key'),
            force_reprocess=bool(metadata.get('force_reprocess', False)),
            force_descriptions=bool(force_descriptions),
            skip_undescribed=skip_undescribed,
            provider_id=provider_id,
            provider_model=provider_model,
            max_workers=max_workers,
        )
```

```548:568:apps/visualizer/backend/jobs/handlers.py
            stats, matches = match_dump_media(
                db,
                threshold=custom_threshold,
                month=month,
                year=year,
                last_months=last_months,
                progress_callback=progress_callback,
                log_callback=log_callback,
                weights=custom_weights,
                media_key=media_key,
                force_descriptions=force_descriptions,
                force_reprocess=force_reprocess,
                skip_undescribed=skip_undescribed,
                provider_id=provider_id,
                provider_model=provider_model,
                max_workers=max_workers,
                should_cancel=lambda: runner.is_cancelled(job_id),
                resume_processed_keys=resume_media or None,
                on_media_complete=on_media_complete,
                batch_progress_callback=batch_progress_callback,
            )
```

**Contract:** Read `clip_top_k` from `metadata`, clamp 1..500, pass into `fingerprint_vision_match` and `match_dump_media`.

### `batch_embed_image` catalog-only gate (extension point)

```2560:2567:apps/visualizer/backend/jobs/handlers.py
        image_type = metadata.get('image_type', 'catalog')
        if image_type != 'catalog':
            runner.fail_job(
                job_id,
                'batch_embed_image only supports catalog images',
                severity='warning',
            )
            return
```

**Contract:** Replace with branching / union for catalog + Instagram per D-01; keep checkpoint + `fingerprint_batch_embed_image` alignment.

### `fingerprint_*` payload shape

```131:142:apps/visualizer/backend/jobs/checkpoint.py
    payload = {
        "embedding_dim": CLIP_EMBED_DIM,
        "embedding_model_id": CLIP_EMBED_MODEL_ID,
        "force": bool(metadata.get("force", False)),
        "image_type": str(metadata.get("image_type", "catalog")),
        "min_rating": min_rating,
        "pairs": pairs,
        "resolved_months": resolved_months,
        "resolved_year": resolved_year,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

```201:233:apps/visualizer/backend/jobs/checkpoint.py
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
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

**Contract:** Extend payloads so **embed scope** and **`clip_top_k`** participate in resume identity; `sort_keys=True` JSON canonicalization preserved.

### Throttled summary log pattern (`_EMBED_SUMMARY_LOG_EVERY`)

```61:61:apps/visualizer/backend/jobs/handlers.py
_EMBED_SUMMARY_LOG_EVERY = 250
```

```2726:2741:apps/visualizer/backend/jobs/handlers.py
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
```

**Contract:** D-07/D-08 use **batch summaries**, not per-image spam; introduce a matching throttle constant (e.g. every N media) analogous to embed.

### `JobsAPI.create` contract

```151:159:apps/visualizer/frontend/src/services/api.ts
  create: async (type: string, metadata?: Record<string, any>) => {
    const job = await request<Job>('/jobs/', {
      method: 'POST',
      body: JSON.stringify({ type, metadata }),
    })
    invalidateAll(['jobs.list'])
    invalidateAll(['jobs.health'])
    return job
  },
```

**Contract:** Post `{ type, metadata }`; `clip_top_k` and chain args ride in `metadata` without API schema change.

### `AdvancedOptions` component shape

```19:72:apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx
interface AdvancedOptionsProps {
  isOpen: boolean;
  onToggle: () => void;
  providerId: string | null;
  providerModel: string | null;
  onProviderChange: (providerId: string | null, modelId: string | null) => void;
  threshold: number;
  onThresholdChange: (value: number) => void;
  phashWeight: number;
  onPhashWeightChange: (value: number) => void;
  descWeight: number;
  onDescWeightChange: (value: number) => void;
  visionWeight: number;
  onVisionWeightChange: (value: number) => void;
  maxWorkers: number;
  onMaxWorkersChange: (value: number) => void;
  skipUndescribed: boolean;
  onSkipUndescribedChange: (value: boolean) => void;
  weightsError: string | null;
  onReset: () => void;
}

export function AdvancedOptions({
  isOpen,
  onToggle,
  ...
}: AdvancedOptionsProps) {
  ...
  return (
    <div className="border-t pt-4">
      <button
        onClick={onToggle}
        className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
      >
        {isOpen ? '▼' : '▶'} {ADVANCED_OPTIONS_TITLE}
      </button>
```

**Contract:** Reuse this disclosure + props surface from `CatalogCacheTab` (D-05); cache tab may supply handlers/defaults for unused sliders if needed.

### `MatchingTab` removal targets (“Catalog Discovery Jobs”)

```174:217:apps/visualizer/frontend/src/components/processing/MatchingTab.tsx
      <Card padding="lg" className="mt-6">
        <CardHeader>
          <CardTitle>Catalog Discovery Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div className="rounded-base border border-border bg-surface p-4">
              <h3 className="text-sm font-semibold text-text">Detect Burst Stacks</h3>
              ...
              <Button
                variant="primary"
                size="lg"
                fullWidth
                className="mt-3"
                onClick={startStackDetection}
                disabled={isStackStarting}
              >
                {isStackStarting ? 'Starting Stack Detection...' : 'Detect Burst Stacks'}
              </Button>
            </div>

            <div className="rounded-base border border-border bg-surface p-4">
              <h3 className="text-sm font-semibold text-text">Find Similar Catalog Photos</h3>
              ...
              <Button
                variant="primary"
                size="lg"
                fullWidth
                className="mt-3"
                onClick={startCatalogSimilarity}
                disabled={isSimilarityStarting}
              >
                {isSimilarityStarting ? 'Starting Similarity Job...' : 'Find Similar Photos'}
              </Button>
            </div>
            <CatalogSimilarityGroupsPreview groups={groups} total={catalogSimilarity.total} />
          </div>
        </CardContent>
      </Card>
```

**Contract:** Remove card + related hooks/queries; optional single line + link to Catalog Cache per `08-UI-SPEC.md`.

### Path resolution for embed pipeline

```156:166:lightroom_tagger/core/database.py
def resolve_filepath(path: str) -> str:
    """Resolve UNC/network paths to local mount points.

    Set NAS_PATH_PREFIX and NAS_MOUNT_POINT env vars to configure.
    Falls back to auto-detecting SMB mounts under /Volumes/.
    Handles case-insensitive server names (NAS vs tnas vs TNAS).
    
    Example: //tnas/ccanales/Foo/bar.jpg -> /Volumes/ccanales/Foo/bar.jpg
    """
    if not path or not path.startswith('//'):
        return path
```

**Contract:** Instagram embed listing should normalize paths through the same helpers as catalog embed — no duplicate UNC logic.

### `JOB_HANDLERS` registration pattern

```3415:3430:apps/visualizer/backend/jobs/handlers.py
JOB_HANDLERS = {
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
}
```

**Contract:** Register composite cache job type alongside existing handlers; mirror `library_db.JOB_TYPES_REQUIRING_CATALOG` update.

### Catalog DB gate for jobs

```38:54:apps/visualizer/backend/library_db.py
JOB_TYPES_REQUIRING_CATALOG: frozenset[str] = frozenset(
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
    }
)
```

**Contract:** Any new catalog-touching job type must appear here.

---

## Guardrails

- **Phase 7 representative-only contract:** Keep `catalog_key_is_primary_grid_row` filtering **before** CLIP shortlist; do not regress non-representative exclusion.
- **Checkpoint / resume:** Preserve `vision_match` (`processed_media_keys` + fingerprint) and `batch_embed_image` checkpoint semantics when extending scope or fingerprints.
- **DRY:** Reuse `AdvancedOptions`; do not add a parallel advanced-options component.
- **Vector backend:** sqlite-vec / `image_clip_embeddings` remains the KNN store — no FAISS migration in Phase 8.
- **No new LLM HTTP surfaces:** Reuse existing vision provider path inside `score_candidates_with_vision`; no new LLM endpoints for Phase 8.
- **UI copy:** Centralize in `strings.ts` — no new inline production strings.
- **Job log contract:** Throttled summaries for pre-filter and cache-chain stages — not per-image log lines for routine progress.
- **MATCH-03 out of scope:** No wider-search fallback when shortlist is empty — do not implement or plan it.
