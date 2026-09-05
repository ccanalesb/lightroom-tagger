# Context Map

This repo has one context file. Read it before working anywhere in `apps/`.

| Area | Context file | Covers |
|---|---|---|
| Visualizer product | [`apps/visualizer/CONTEXT.md`](apps/visualizer/CONTEXT.md) | HTTP API, CLI, job queue, WebSocket, React SPA, vision, providers, scoring, identity, `library.db` |

## Cross-cutting decisions

Architectural decision records live in `docs/adr/`. Boundary and layering policy for the backend lives in [`docs/architecture.md`](docs/architecture.md).

## History

Until the TypeScript cutover this was a two-context repo: a standalone Python package at `lightroom_tagger/` (library + CLI) and a Flask backend that consumed it. Both are gone, and the TypeScript replacement now occupies the path the Flask tree used to hold. Everything the package did lives under `apps/visualizer/backend/src/`, with the CLI as a second entry point over the same services (`src/cli/`), so there is no longer a seam between two codebases to keep in sync — only the layer boundaries within one.
