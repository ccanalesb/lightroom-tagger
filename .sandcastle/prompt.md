# Context

Project: a TypeScript tool (`lightroom-tagger`) that indexes a Lightroom catalog,
tags images with vision models, and matches against Instagram. Source and tests
live under `apps/visualizer/backend-ts/`, with a React frontend in
`apps/visualizer/frontend/`. Conventions live in `docs/architecture.md` and
`CONTEXT-MAP.md`.

Recent history:

!`git log --oneline -10`

# Task

<!-- Describe what the agent should do. Replace this section before running locally. -->

# Contract (OpenAPI → generated TS)

The visualizer's frontend types are generated from the backend OpenAPI spec
(ADR-0013); `apps/visualizer/frontend/src/types/api.gen.ts` is committed and a CI
gate fails on drift. If you touch a Zod schema
(`apps/visualizer/backend-ts/src/api/schemas/**`) or a route's `createRoute`
definition, you MUST regenerate and commit the types:

    cd apps/visualizer/frontend && npm run generate:api   # then commit src/types/api.gen.ts
    npx tsc --noEmit                                       # must pass

Binary and streaming routes (thumbnails, downloads) are registered as plain Hono
handlers, never through `createRoute`/`.openapi()`. They are not part of the JSON
contract.

# Done

Dependencies are already installed, so run the test suite with:

!`echo "Run: cd apps/visualizer/backend-ts && npm test"`

When the task is complete and tests pass, stage and commit ALL your changes
(including any regenerated `api.gen.ts`):

    git add -A && git commit -m "..."

Then output <promise>COMPLETE</promise>.
