---
status: issues_found
phase: 03
issues_count: 6
---

# Phase 03 Code Review

## Summary

Phase 03 adds Instagram dump configuration (YAML + REST), an `instagram_import` job wired to `import_dump`, richer `/matches` responses by joining `instagram_dump_media`, catalog “posted” filtering tests, Matches tab UI with pagination, and configurable Lightroom keyword tagging (replacing a hardcoded “Posted”). SQL uses bound parameters for dynamic `IN` lists; React uses `encodeURIComponent` for thumbnail URLs. No critical defects surfaced; findings are mostly UX, operational defaults, and trust-boundary notes.

## Issues

1. **warning** — `apps/visualizer/frontend/src/components/images/InstagramDumpSettingsPanel.tsx` (lines 54–60) — **Run Import** queues `instagram_import` with only `reimport` / `skip_dedup`. It does not pass `metadata.dump_path` or the draft field, so the job uses `load_config()` / `INSTAGRAM_DUMP_PATH` only. Users who edit “Dump directory path” but forget **Save dump path** will import from the previously saved path, which is easy to misread as a bug.

2. **info** — `apps/visualizer/frontend/src/hooks/useMatchGroups.ts` (lines 9–24) and `MatchesTab.tsx` (Load more) — `fetchGroups` has no in-flight guard. Rapid “Load more” clicks can fire two requests with the same `offset` before state updates; duplicate groups are mostly avoided by deduplicating on `instagram_key`, but redundant work and ordering edge cases remain possible under concurrent DB changes.

3. **warning** — `lightroom_tagger/core/config.py` (defaults / `load_config` defaults) — `mount_point` and `instagram_url` defaults changed from hardcoded values to empty strings, and `instagram_dump_path` was added. Deployments or scripts that relied on implicit defaults without YAML/env may behave differently until configuration is set explicitly.

4. **info** — `apps/visualizer/backend/api/lt_config.py`, `apps/visualizer/backend/jobs/handlers.py` — New `GET`/`PUT /api/config/instagram-dump` and the `instagram_import` job type extend the same unauthenticated local-server pattern as existing config/job APIs. Anyone who can reach the API can point imports at server paths and trigger work; acceptable only if the visualizer stays on a trusted host.

5. **info** — `lightroom_tagger/scripts/match_instagram_dump.py` (line 288) — Success log uses `config.instagram_keyword!r`, while `update_lightroom_from_matches` applies `.strip()` and falls back to `"Posted"`. Whitespace-only keywords would be logged inaccurately vs what Lightroom actually receives.

6. **info** — `apps/visualizer/backend/api/images.py` (lines 382–385) — `model_lookup` is built by iterating `matches`; multiple rows per `insta_key` leave the last `model_used` winning. Usually consistent; if not, `matched_model` on enriched dump media can be arbitrary.
