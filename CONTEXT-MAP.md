# Context Map

This repo uses two independent context files. Read the one closest to the area you're working in. If your work spans both, read both.

| Area | Context file | Covers |
|---|---|---|
| Library & CLI | [`lightroom_tagger/CONTEXT.md`](lightroom_tagger/CONTEXT.md) | Matching, vision, providers, scoring, identity, CLI, `library.db` write serialization |
| Visualizer product | [`apps/visualizer/CONTEXT.md`](apps/visualizer/CONTEXT.md) | Flask API, job queue, WebSocket, React SPA, blueprints, design system |

## Cross-cutting decisions

Architectural decision records live in `docs/adr/` (create as needed for decisions that affect both areas).

## Seam between contexts

The library (`lightroom_tagger`) is a standalone installable package. The visualizer is its primary consumer. The shared boundary is `library.db` and the Python API of `lightroom_tagger.core.*`. When changing that boundary, update both context files.
