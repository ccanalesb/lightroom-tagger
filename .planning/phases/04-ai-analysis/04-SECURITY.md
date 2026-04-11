---
phase: 4
slug: ai-analysis
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-11
---

# Phase 4 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Flask API ↔ SQLite | Backend API queries local SQLite with user-supplied filter params | Query parameters (analyzed, min_rating) |
| Flask API ↔ Vision Provider | Provider registry probes external AI APIs; health endpoint returns error strings | API keys, model lists, error messages |
| Frontend ↔ Flask API | React app sends filter values, job metadata, generate requests | JSON payloads with provider_id, provider_model, min_rating, image_type |
| Vision Cache ↔ Filesystem | Cached images stored/read from disk; oversized files filtered | Image file paths, file sizes |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-4-01 | Injection | `query_catalog_images` in database.py | mitigate | Parameterized queries: `analyzed` uses fixed SQL fragments (`d.image_key IS NOT NULL` / `IS NULL`), `min_rating` uses `i.rating >= ?` with `bindings.append()`. No string interpolation of user input. (database.py:682-722) | closed |
| T-4-02 | Information Disclosure | `list_catalog_images` in images.py | mitigate | `json.loads` wrapped in `try/except (json.JSONDecodeError, TypeError)` falling back to `{}`; outer exception handler returns `error_server_error(str(e))` with JSON error only, no Python traceback. (images.py:435-458) | closed |
| T-4-03 | Denial of Service | `probe_connection` in provider_registry.py | mitigate | `client.models.list(timeout=5.0)` with immediate `break` after first item — bounded round-trip. (provider_registry.py:89) | closed |
| T-4-04 | Spoofing | POST /api/descriptions/generate | accept | Local single-user tool with no authentication boundary. | closed |
| T-4-05 | Tampering | `handle_batch_describe` in handlers.py | mitigate | `min_rating_raw` from metadata parsed with `try: int(min_rating_raw)` / `except (TypeError, ValueError): min_rating = None`. Bad input safely ignored. (handlers.py:558-564) | closed |
| T-4-06 | Denial of Service | Vision cache + matcher batch prep | mitigate | `MAX_CACHED_IMAGE_KB = 512` cap; oversized files stored with `VISION_CACHE_OVERSIZED_SENTINEL` and return `None`; batch prep increments `skipped_oversized` and `continue`s. SR2 added to `RAW_EXTENSIONS`. (vision_cache.py:23,79-80,100-120; matcher.py:198-247; analyzer.py:13) | closed |
| T-4-07 | Information Disclosure | Health endpoint in providers.py | accept | `str(exc)` from probe returned as operational `error` at HTTP 200. Acceptable for local tool — no secrets in models.list() errors. (providers.py:61-62) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-4-01 | T-4-04 | Local single-user tool — no auth boundary on description generate endpoint | gsd-security-auditor | 2026-04-11 |
| AR-4-02 | T-4-07 | Health endpoint error strings are operational (provider connection messages), not sensitive credentials or internal paths | gsd-security-auditor | 2026-04-11 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-11 | 7 | 7 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-11
