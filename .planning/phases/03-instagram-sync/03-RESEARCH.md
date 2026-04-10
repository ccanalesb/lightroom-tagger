# Phase 3 — Instagram sync: research notes

**Purpose:** Answer “What do I need to know to **plan** this phase well?” by mapping requirements IG-01–IG-06 to the current codebase, surfacing gaps, and noting dependencies on Phases 1 and 2.

**Sources:** `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `apps/visualizer/frontend/DESIGN.md`, and repository inspection (backend API, jobs, core matching/import, Lightroom writer, frontend tabs/modals).

---

## 1. Current state assessment (by requirement)

### IG-01 — User can upload Instagram export dump

| Area | State |
|------|--------|
| **CLI** | `lightroom-import-dump` → `lightroom_tagger/scripts/import_instagram_dump.py` reads a dump directory (`--dump-path` or `INSTAGRAM_DUMP_PATH`). |
| **Visualizer API** | **No** HTTP upload or “ingest dump” endpoint. Ingest is **not** exposed through the Flask app; `.env.example` documents `INSTAGRAM_DUMP_PATH` as a **server-side path** the operator must set. |
| **UI** | No upload flow in the SPA. |

**Verdict for planning:** Ingest is **operator/CLI + filesystem path**, not productized “user uploads in browser.”

---

### IG-02 — System parses images and metadata from dump

| Area | State |
|------|--------|
| **Core** | `import_dump()` discovers files, optional visual dedup, merges JSON metadata (`posts`, `archived_posts`, `other_content`), URL extraction (`parse_saved_and_reposted_urls`), stores rows in `instagram_dump_media` via `store_instagram_dump_media`. |
| **API** | `GET /api/images/instagram`, `GET /api/images/instagram/months`, `GET /api/images/instagram/<key>/thumbnail`, `GET /api/images/dump-media` expose parsed rows (listing/thumbnails). |
| **UI** | **Instagram** tab on `/images` lists dump media with month filter and detail modal (caption, EXIF, match hints). |

**Verdict:** Parsing and persistence are **strong**; visibility in-app depends on import having been run against data the backend can read.

---

### IG-03 — System matches dump images to catalog photos with confidence scores

| Area | State |
|------|--------|
| **Core** | `match_dump_media()` in `lightroom_tagger/scripts/match_instagram_dump.py`: date-window candidates, cascade scoring via `score_candidates_with_vision` (pHash, description, vision), configurable threshold/weights; stores **multiple** ranked rows in `matches` per `insta_key` when above threshold. |
| **Jobs** | `vision_match` job in `handle_vision_match` (`apps/visualizer/backend/jobs/handlers.py`) runs the same pipeline with progress logs, cancellation (Phase 2), optional `media_key` for single-image jobs. |
| **API** | `GET /api/images/matches` returns groups/candidates with `total_score` as **`score`** in enriched match objects. |
| **UI** | Batch matching: **Processing → Vision Matching** (`MatchingTab.tsx`). Per-image: **Instagram image detail modal** (`ImageDetailsModal` + `useSingleMatch`) starts `vision_match` with `media_key`. |

**Verdict:** Matching + scores are **implemented end-to-end** for the dump pipeline.

---

### IG-04 — User can confirm or reject proposed matches

| Area | State |
|------|--------|
| **API** | `PATCH .../validate` toggles `validated_at`; `PATCH .../reject` deletes match, blocklists pair, resets `instagram_dump_media` processed state, may clear `images.instagram_posted` if no other matches for that catalog key (`reject_match` in `lightroom_tagger/core/database.py`). |
| **Frontend components** | `MatchDetailModal`, `RejectConfirmModal`, `MatchingAPI.validate` / `.reject`, `useMatchGroups` **exist** but are **not mounted** on any route. |
| **Matches tab** | `MatchesTab.tsx` is a **placeholder** (“placeholder matches view”) — no list, no modal, no wiring to `MatchingAPI.list`. |

**Verdict:** Backend persistence for validate/reject is **real** and tested (`test_match_validation.py`); the **primary matches review UI is missing** from the app shell.

---

### IG-05 — System writes “posted” keyword to confirmed matches in Lightroom catalog

| Area | State |
|------|--------|
| **Writer** | `update_lightroom_from_matches()` in `lightroom_tagger/lightroom/writer.py` adds keyword **`Posted`** (literal string in code) after `raise_if_catalog_locked` and rotated backup (`backup_catalog_if_needed`). |
| **Config** | `Config.instagram_keyword` defaults to `"Posted"` in `lightroom_tagger/core/config.py` — **not** referenced by `update_lightroom_from_matches` today (keyword name is fixed in writer). |
| **When it runs** | `handle_vision_match` calls `update_lightroom_from_matches` for **every** successful auto-match returned from `match_dump_media` when catalog path exists — **not** gated on `validated_at` or user confirmation. |
| **Side effects** | On auto-match, `update_instagram_status(..., posted=True)` runs immediately (library DB), regardless of validation. |

**Verdict:** Lightroom writeback **exists** and is integrated with Phase 2 safety (lock check, backups, job failure on lock). Semantics are **“auto-match ⇒ tag”**, not **“confirm ⇒ tag”** — misaligned with roadmap wording unless product accepts auto-tagging.

---

### IG-06 — User can see which catalog photos are marked as posted

| Area | State |
|------|--------|
| **Library DB** | `images.instagram_posted` (+ optional URL/date fields). |
| **API** | `GET /api/images/catalog?posted=true|false`; `GET /api/stats` includes `posted_to_instagram` count. |
| **UI** | **Catalog** tab: posted / not-posted filter (`CatalogTab.tsx`). **CatalogImageCard** / **CatalogImageModal**: “Posted” / “Posted to Instagram” badges when `instagram_posted`. |
| **Lightroom vs app** | UI reflects **library DB**, not a live read of Lightroom keywords. Rejecting a match clears DB posted flag but **does not remove** the `Posted` keyword from `.lrcat` if it was already written. |

**Verdict:** In-app visibility is **largely met** for DB-backed state; **consistency with Lightroom** after reject or external LR edits is a known edge case.

---

## 2. Gap analysis (summary table)

| ID | Requirement | Met? | Notes |
|----|-------------|------|--------|
| IG-01 | Upload dump | **Partial / no (product sense)** | Path-based + CLI; no in-app upload or job-triggered import API. |
| IG-02 | Parse dump | **Strong** | Import script + DB + list APIs + Instagram tab. |
| IG-03 | Match + confidence | **Strong** | Core + `vision_match` job + scores in `matches`; UI shows match summary in modal / job result (not full candidate grid in Matches tab). |
| IG-04 | Confirm / reject | **Backend yes, UI no** | Validate/reject APIs tested; Matches tab placeholder; `MatchDetailModal` unused. |
| IG-05 | Keyword writeback | **Partial** | Writes on **auto** match completion; not tied to confirmation; keyword string not driven by `instagram_keyword` config in writer. |
| IG-06 | See posted | **Mostly** | Filters + badges + stats; possible drift vs Lightroom keyword after reject or manual LR changes. |

**Cross-cutting API issue (planning should address):** `GET /api/images/matches` builds `instagram_image` from the **`instagram_images`** (legacy crawl) table. Dump pipeline stores `insta_key` = `instagram_dump_media.media_key`. Those keys typically **do not** exist in `instagram_images`, so match list responses may omit Instagram-side thumbnails/metadata unless the handler is extended to join `instagram_dump_media` (or equivalent).

---

## 3. Architecture notes

**Data flow (today):**

1. Operator runs import (CLI) → `instagram_dump_media` (+ hashes, captions, paths).
2. User starts `vision_match` (Processing page or per-image modal) → `match_dump_media` → `matches` rows + `mark_dump_media_processed` + `update_instagram_status` + optional descriptions.
3. Job completion → `update_lightroom_from_matches` → Lightroom `Posted` keyword (if catalog path configured and not locked).
4. Catalog browse reads `images.*` including `instagram_posted`.

**Human-in-the-loop (intended vs actual):**

- **Intended (roadmap):** propose → user confirms/rejects → then writeback / durable “posted.”
- **Actual:** propose + **immediate** library DB “posted” + **immediate** Lightroom keyword on job success; validate is only a stamp; reject fixes DB/blocklist but not necessarily LR.

**Frontend surface area:**

- **Live:** `InstagramTab`, `ImageDetailsModal`, `MatchStatusDisplay`, `MatchAdvancedOptions`, `CatalogTab`, `MatchingTab`, job queue.
- **Dormant / incomplete:** `MatchesTab`, `MatchDetailModal` + `useMatchGroups`.

---

## 4. Implementation recommendations (for the plan phase)

1. **Decide product semantics for IG-04 + IG-05** (blocks design):
   - **Option A — Confirm-gated writeback:** Defer `update_instagram_status(..., posted=True)` and `update_lightroom_from_matches` until user validates (new job or synchronous API on validate). Matching job only writes `matches` + marks dump row “pending review.”
   - **Option B — Auto-tag with review for corrections:** Keep current auto behavior; treat validate as audit-only and reject as “undo path” (then **add** LR keyword removal or a repair job when match rejected after write — harder).

2. **Ship the Matches UI:** Replace `MatchesTab` placeholder with `MatchingAPI.list` + grouping already returned by API; embed `MatchDetailModal` for validate/reject; ensure thumbnails use **`instagram_dump_media`** + `/api/images/instagram/.../thumbnail` when legacy `instagram_image` is null.

3. **IG-01 in-app:** If required literally, add upload (zip?) + extract to temp + call `import_dump` in a **new job type** (reuse Phase 2 job UX, cancellation, error severity). If “upload” can mean “point server at folder,” add settings API + UI for `INSTAGRAM_DUMP_PATH` and a **Run import** job button.

4. **Config alignment:** Use `instagram_keyword` from config in `update_lightroom_from_matches` (and document case: `Posted` vs `posted` vs user override).

5. **Observability:** Surface parse/import errors in UI if import moves to API (today CLI prints to console).

6. **Small fix opportunity:** `useSingleMatch` reads `job.result.best_score`; `handle_vision_match` completion payload may not set `best_score` — align result shape or UI for score display after single-image jobs.

---

## 5. Risk / complexity assessment

| Topic | Difficulty | Comment |
|-------|------------|---------|
| Wiring Matches tab + dump-media joins | **Straightforward** | Mostly frontend + one API enrichment change. |
| Confirm-gated Lightroom writes | **Moderate** | Refactor match pipeline and job results; define idempotency if user re-runs matching. |
| In-browser dump upload + extract | **Moderate** | Storage limits, zip safety, long-running import job, progress UX. |
| Removing LR keywords on reject | **Moderate–high** | Requires writer support + rules for when multiple dump posts map to one catalog image. |
| Multi-candidate UX (ranked list) | **Low–moderate** | Data already stored; UI must show alternates clearly. |

---

## 6. Dependencies (Phase 1 & 2)

From `.planning/ROADMAP.md` and implementation:

- **Phase 1:** Catalog rows in `images`, browse/search APIs, stable keys — **required** as match targets and for posted filters/badges.
- **Phase 2:** Job lifecycle, **cooperative cancel** on `vision_match`, **backup + Lightroom lock guard** before `.lrcat` writes, **error severity** in API/UI — **required** for reliable Instagram jobs and safe writeback.

No additional external services are mandatory beyond existing vision providers for matching.

---

## RESEARCH COMPLETE
