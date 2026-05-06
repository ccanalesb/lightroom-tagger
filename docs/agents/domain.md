# Domain Docs

This repo uses a **multi-context** layout with two independent context files.

## Contexts

| Context | File | Covers |
|---|---|---|
| Library / CLI | `lightroom_tagger/CONTEXT.md` | Matching, vision, providers, ProviderRegistry, Lightroom catalog, Instagram parsing, CLI |
| Visualizer product | `apps/visualizer/CONTEXT.md` | Flask API, job queue, WebSocket, React UI, blueprints |

## Cross-cutting decisions

Architectural decision records live in `docs/adr/`:

| ADR | Decision |
|---|---|
| [ADR-0001](../../docs/adr/0001-split-analyzer.md) | Split `analyzer.py` into `image_prep`, `image_inspect`, `vision_compare`, `description` |
| [ADR-0002](../../docs/adr/0002-split-database.md) | Split `database.py` into focused store modules with `database.py` as permanent re-export shim |
| [ADR-0003](../../docs/adr/0003-pipeline-layer.md) | Pipeline layer in `lightroom_tagger/core/pipelines.py`; handlers become thin adapters |
| [ADR-0004](../../docs/adr/0004-shared-exceptions.md) | Shared `lightroom_tagger/core/exceptions/` package as single entry point for all error types |

## Usage by skills

- `diagnose`, `tdd`, `improve-codebase-architecture` — read the context file closest to the files being worked on
- If work spans both contexts, read both
- `CONTEXT.md` files do not exist yet — create them when the domain language stabilizes or when a skill asks for them
