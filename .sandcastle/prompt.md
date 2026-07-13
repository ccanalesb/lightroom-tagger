# Context

Project: a Python tool (`lightroom-tagger`) that indexes a Lightroom catalog,
tags images with vision models, and matches against Instagram. Package source
is under `lightroom_tagger/`, tests under the repo. Conventions live in
`docs/architecture.md` and `CONTEXT-MAP.md`.

Recent history:

!`git log --oneline -10`

# Task

<!-- Describe what the agent should do. Replace this section before running locally. -->

# Contract (OpenAPI → generated TS)

The visualizer's frontend types are generated from the backend OpenAPI spec
(ADR-0013); `apps/visualizer/frontend/src/types/api.gen.ts` is committed and a CI
gate fails on drift. If you touch a pydantic response model
(`apps/visualizer/backend/api/schemas/**`) or a route's `@spec.validate`
decorator, you MUST regenerate and commit the types:

    cd apps/visualizer/frontend && npm run generate:api   # then commit src/types/api.gen.ts
    npx tsc --noEmit                                       # must pass

Never wrap a `send_file`/binary/streaming route in `@spec.validate` — it 500s
with "direct passthrough mode". Binary endpoints are not part of the JSON contract.

# Done

The project and its dev deps are already installed in the active venv, so run
the test suite with:

!`echo "Run: python -m pytest -q"`

When the task is complete and tests pass, stage and commit ALL your changes
(including any regenerated `api.gen.ts`):

    git add -A && git commit -m "..."

Then output <promise>COMPLETE</promise>.
