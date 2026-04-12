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
