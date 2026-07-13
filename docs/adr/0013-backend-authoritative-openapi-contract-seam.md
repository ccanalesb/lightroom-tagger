# ADR-0013: Backend-authoritative OpenAPI contract seam

**Status:** Accepted  
**Date:** 2026-07-12

## Context

The visualizer frontend and Flask backend share domain types (jobs, images, scores, …) but today most TypeScript interfaces are hand-written in `frontend/src/services/api.ts` and `frontend/src/types/`. The backend emits JSON without a single schema source; drift between layers is discovered only at runtime or during manual review. Issue #57 defines a phased migration: pydantic models on the backend, OpenAPI export, generated frontend types, and CI gates that fail on either side of the seam.

## Decision

Establish the **contract invariant** for the visualizer API:

1. **Every response shape is a pydantic model** registered with `spectree` on its Flask route. Request bodies use pydantic where applicable.
2. **Frontend types for that surface are generated** from the backend OpenAPI document (`openapi-typescript` → committed `frontend/src/types/api.gen.ts`). Hand-written duplicates are deleted; thin re-exports (e.g. `types/job.ts`) may alias `components.schemas.*` for stable import paths.
3. **Drift fails CI** in both directions:
   - Regenerate TS from the backend spec; `git diff --exit-code` on the committed artifact.
   - `tsc` over the frontend.
   - Backend `pytest` with spectree **response validation** enabled on decorated routes (wrong status/body → test failure).
4. **Socket emits for a domain model use the same pydantic model** as REST (e.g. `Job` for `job_updated` / `job_created`). No parallel hand-written socket types.

Tooling layout (V1 Jobs slice):

| Piece | Location |
|---|---|
| spectree instance | `apps/visualizer/backend/api/openapi.py` |
| pydantic schemas | `apps/visualizer/backend/api/schemas/` |
| OpenAPI export | `apps/visualizer/backend/scripts/export_openapi.py` |
| TS codegen | `apps/visualizer/frontend/scripts/generate-api-types.mjs` (`npm run generate:api`) |
| Local gate | `apps/visualizer/scripts/verify-contract.sh` |
| CI gate template | `.sandcastle/ci-drift-gate.yml` (maintainer installs into `.github/workflows/`) |

Coverage is **incremental**: V1 protects the Jobs group only (`api/jobs.py`, eight routes + socket emits). Later slices (V2–V7) add models and decorators per endpoint group, regenerate, and delete their hand-written interfaces — they do not re-touch this tooling.

## Consequences

- **Positive:** Jobs types are provably aligned; socket and REST share one `Job` model; drift is caught before merge.
- **Negative:** `api.ts` remains a mix of generated (Jobs) and hand-written (everything else) until V7 — do not claim the contract is complete until then.
- **Operational:** Agents and sandcastle runners must not commit under `.github/workflows/`; the drift gate ships as `.sandcastle/ci-drift-gate.yml` for human installation.

## References

- Parent PRD: GitHub issue #57 (frontend↔backend contract seam)
- V1 implementation: Jobs processing surface (`ProcessingPage`, `useJobSocket`, …)
- Prior art: ADR-0010 (job-type registry seam), ADR-0011 (library-DB lifecycle seam)
