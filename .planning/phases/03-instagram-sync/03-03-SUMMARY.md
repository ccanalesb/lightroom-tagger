# Plan 03-03 — Summary

**Title:** Instagram dump path in config + instagram_import job handler  
**Phase:** 03 — Instagram sync  
**Requirements:** IG-01, IG-02  
**Completed:** 2026-04-10

## Outcome

- **Core config:** `Config.instagram_dump_path` (default empty), YAML/env defaults, and `INSTAGRAM_DUMP_PATH` → `instagram_dump_path` in `_load_from_env`. `update_config_yaml_instagram_dump_path` mirrors catalog YAML updates (non-empty strip, `sort_keys=False`).
- **API:** `GET` / `PUT` `/api/config/instagram-dump` return or persist the dump directory with `resolved_path` and `exists` (directory check). PUT rejects missing paths or non-directories. Tests clear `INSTAGRAM_DUMP_PATH` so temp `config.yaml` is authoritative under dev environments that set the variable globally.
- **Jobs:** `handle_instagram_import` resolves dump path from `metadata.dump_path`, then config, then `INSTAGRAM_DUMP_PATH`; fails with warning if unset or not a directory; uses `LIBRARY_DB` / `config.db_path` / `library.db` for the library DB; runs `import_dump(..., skip_existing=not reimport, skip_dedup=skip_dedup)` with `db.close()` in `finally`. Registered as `instagram_import` in `JOB_HANDLERS`.
- **Tests:** `lightroom_tagger/core/test_config.py` env mapping for `INSTAGRAM_DUMP_PATH`; `test_lt_config_api` coverage for instagram-dump routes; `test_jobs_api` POST creates `instagram_import` with 201.

## Commits

| Commit   | Message |
|----------|---------|
| `a024266` | `feat(03-03): add instagram_dump_path to Config and INSTAGRAM_DUMP_PATH env` |
| `38f6bbc` | `feat(03-03): add update_config_yaml_instagram_dump_path helper` |
| `1309281` | `feat(03-03): add GET/PUT /api/config/instagram-dump and tests` |
| `2d88848` | `feat(03-03): add instagram_import job handler calling import_dump` |
| `41015d2` | `test(03-03): assert POST creates instagram_import job` |

## Verification

- `pytest apps/visualizer/backend/tests/test_lt_config_api.py` — exit 0.
- `pytest apps/visualizer/backend/tests/test_jobs_api.py` — exit 0.
- `grep -q "'instagram_import'" apps/visualizer/backend/jobs/handlers.py` — exit 0.
- `python -m pytest lightroom_tagger/core/test_config.py` — exit 0 (task 1).

## Notes

- `test_default_values` in `test_config.py` now expects `mount_point == ""` to match the `Config` dataclass default (fixes a pre-existing mismatch).
