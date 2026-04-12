# Phase 06 — execution summary

## Plan 06-02

- **feat(06-02): add score history and all-scores list database helpers** — Added `list_score_history_for_perspective` and `list_all_scores_for_image` in `lightroom_tagger/core/database.py` (parameterized SQL, docstrings for supersede/`is_current` semantics).
- **feat(06-02): add read-only scores REST blueprint** — New `apps/visualizer/backend/api/scores.py`: `GET /<path:image_key>` (current rows), `GET /<path:image_key>/history` (requires `perspective_slug`, validates slug charset via `_SLUG_RE`).
- **feat(06-02): register scores blueprint on Flask app** — `app.register_blueprint(scores.bp, url_prefix='/api/scores')` in `apps/visualizer/backend/app.py`.
- **feat(06-02): add ScoresAPI and ImageScoreRow TypeScript helpers** — `apps/visualizer/frontend/src/services/api.ts` mirrors `DescriptionsAPI` path style under `VITE_API_URL`.
- **test(06-02): cover list_score_history_for_perspective ordering** — `lightroom_tagger/core/test_database_scores.py` asserts `scored_at` descending.
- **test(06-02): add Flask tests for scores API** — `apps/visualizer/backend/tests/test_scores_api.py` covers empty current, `is_current` filter, history 400, newest-first history.
- **fix(06-02): type-annotate scores routes for mypy** — `ResponseReturnValue` + `sqlite3.Connection` on handlers; ruff import order on `api/scores.py`.

## Verification (plan 06-02)

- `pytest lightroom_tagger/core/test_database_scores.py apps/visualizer/backend/tests/test_scores_api.py -q` — pass.
- `mypy apps/visualizer/backend/api/scores.py --follow-imports=skip` — pass. Running `mypy lightroom_tagger/core/database.py` (with or without `--follow-imports=skip`) still reports many pre-existing issues in that module under `disallow_untyped_defs` / legacy signatures; new helpers are fully annotated.
- `ruff check apps/visualizer/backend/api/scores.py` — pass. `ruff check` on `lightroom_tagger/core/database.py` and `apps/visualizer/backend/app.py` still reports pre-existing lint in those files (not introduced by 06-02).

## Plan 06-03

- **feat(06-03): add ImageScoresPanel for catalog score display and history** — New `apps/visualizer/frontend/src/components/catalog/ImageScoresPanel.tsx`: loads current rows via `ScoresAPI.getCurrent`, per-perspective lazy `getHistory` when “Version history” is expanded, score badge + rationale + model/prompt_version/scored_at, repaired hint, Latest/Archived badges on history rows; `reloadToken` resets local history and collapses sections so post-job refresh stays consistent.
- **feat(06-03): wire catalog modal scoring job and ImageScoresPanel** — `CatalogImageModal.tsx`: scores card under the AI description panel; active-perspective checkboxes (default all), shared `ProviderModelSelect` overrides with describe flow, `force` checkbox, `JobsAPI.create('single_score', …)` with explicit `perspective_slugs`; `useJobSocket` handles `pendingScoreJobId` alongside describe jobs and bumps `scoresReloadToken` on completion.
- **chore(06-03): add catalog score copy constants and use shared ScoresAPI** — `constants/strings.ts` exports `SECTION_IMAGE_SCORES`, `ACTION_RUN_SCORING`, `SCORES_LOADING`, and related modal/panel strings; panel uses `ScoresAPI` / `ImageScoreRow` from `api.ts` (no duplicate fetch client).

## Verification (plan 06-03)

- `npm run build` and `npm run lint` in `apps/visualizer/frontend` — pass.

## Plan 06-04

- **feat(06-04): add catalog score join, filter, and sort to query_catalog_images** — `lightroom_tagger/core/database.py`: optional `score_perspective`, `min_score` (1–10, requires perspective), `sort_by_score` (`asc`|`desc`, requires perspective); `LEFT JOIN image_scores s` with `is_current=1` and `image_type='catalog'`; shared joins/WHERE for `COUNT(*)` and page rows; `ORDER BY (s.score IS NULL) ASC, s.score …, i.key ASC` so unscored rows sort after scored; exposes `catalog_perspective_score` in row dict when the join is active.
- **feat(06-04): add catalog score query params to list_catalog_images** — `apps/visualizer/backend/api/images.py`: query params `score_perspective`, `min_score`, `sort_by_score`; slug validated with same charset as perspectives (`^[a-z][a-z0-9_]{0,63}$`); 400 when `sort_by_score` or `min_score` lacks perspective, invalid enum, or out-of-range `min_score`; response adds `catalog_perspective_score` and `catalog_score_perspective` only when a score perspective is requested.
- **feat(06-04): extend listCatalog and CatalogImage for score filters** — `apps/visualizer/frontend/src/services/api.ts`: URL params and optional `CatalogImage` fields for persisted catalog scores.
- **feat(06-04): add catalog score filter and sort controls to CatalogTab** — Perspective select (active perspectives + Any), min score 1–10 + Any, sort None / High→Low / Low→High; clears min/sort when perspective is Any; resets page on change; wired into `ImagesAPI.listCatalog`.
- **feat(06-04): show persisted catalog score pill on CatalogImageCard** — Subtle `Badge` with optional truncated slug + `n/10` when `catalog_perspective_score` is present.
- **test(06-04): cover query_catalog_images score sort and min_score** — `lightroom_tagger/core/test_database_scores.py`.
- **chore(06-04): ruff import order in images blueprint** — isort-compatible grouping in `api/images.py`.
- **test(06-04): add Flask tests for catalog score query params** — `apps/visualizer/backend/tests/test_catalog_score_query.py`: 400 when `sort_by_score` without `score_perspective`; ordered catalog list with seeded `image_scores`; `PRAGMA wal_checkpoint(TRUNCATE)` after seeding so the Flask client’s new connection sees WAL writes under the default journal mode.

## Verification (plan 06-04)

- `pytest lightroom_tagger/core/test_database_scores.py apps/visualizer/backend/tests/test_catalog_score_query.py -q` — pass.
- `npm run build` in `apps/visualizer/frontend` — pass.
- `mypy lightroom_tagger/core/database.py apps/visualizer/backend/api/images.py` — still reports many pre-existing issues across the import graph (same situation as plan 06-02 for `database.py`); no new errors specific to the score-catalog changes were isolated in that run.
- `ruff check` on `lightroom_tagger/core/database.py` — still reports pre-existing issues in that large module; `ruff check apps/visualizer/backend/api/images.py apps/visualizer/backend/tests/test_catalog_score_query.py` — remaining SIM105 findings in `images.py` are pre-existing try/parse patterns, not introduced by 06-04.
