# Phase 5: Image Embed & Search Chat — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 05-image-embed-search-chat
**Areas discussed:** Chat panel placement, Image embedding model, Search routing in chat, Result refinement behavior

---

## Chat panel placement

| Option | Description | Selected |
|--------|-------------|----------|
| A — Dedicated `/search` page | Full page split: conversation thread (~40%) + results grid (~60%). New "Search" nav item in Layout. | ✓ |
| B — Tab in ImagesPage | "Search" tab alongside Instagram / Catalog / Matches. Split panel inside tab. | |
| C — Slide-out panel overlay | Drawer accessible from any page. Condensed results within the panel. | |

**User's choice:** A — Dedicated `/search` route, full split layout
**Notes:** Clean separation from image-browsing pages; the split layout doesn't fit naturally inside the tab structure of ImagesPage.

---

## Image embedding model

| Option | Description | Selected |
|--------|-------------|----------|
| A — `open_clip` | Pure image embeddings, ViT-B/32 (~512-dim) or ViT-L/14 (~768-dim). Separate text/image spaces. | |
| B — `sentence-transformers` CLIP variant | `clip-ViT-B-32` via sentence-transformers. Same library already in requirements. Shared text+image vector space. | ✓ |
| C — Claude's discretion | Planner picks something pragmatic and offline. | |

**User's choice:** B — `sentence-transformers` CLIP (`clip-ViT-B-32`, 512-dim)
**Notes:** Shared vector space was the deciding factor — enables text→image retrieval in the chat panel without extra infrastructure. Consistent with the existing sentence-transformers dependency from Phase 3.

---

## Search routing in chat

| Option | Description | Selected |
|--------|-------------|----------|
| A — Semantic only | Every message → `POST /api/images/semantic-search`. Single code path. No structured filter support. | |
| B — NL-first cascade | Message → Phase 2 NL filter extraction first. Falls through to Phase 3 semantic if no filters found. | ✓ |
| C — Parallel hybrid | Both Phase 2 and Phase 3 run simultaneously, results merged. More powerful, more complex. | |
| D — Claude's discretion | Route selection is an implementation detail. | |

**User's choice:** B — NL-first cascade
**Notes:** Best coverage (structured filters + semantic) without the complexity of two parallel round-trips and merge logic.

---

## Result refinement behavior

| Option | Description | Selected |
|--------|-------------|----------|
| A — Independent searches | Each message is a fresh query. History shown visually but no LLM memory. | |
| B — LLM sees prior turns | Full conversation history sent with each request. LLM understands references like "those" and "now narrow to…". | ✓ |
| C — Client-side narrowing | New search constrained to prior result image keys. Gets progressively narrower. No LLM memory. | |

**User's choice:** B — True multi-turn LLM context
**Notes:** Conversation history stored client-side in React state, sent as `messages` array in each request. Results grid always shows current turn's results; prior results visible as thumbnail strip/count in the conversation thread.

---

## Claude's Discretion

- Exact sqlite-vec table name for image embeddings
- Whether CLIP text encoder path (text → image KNN) is wired in Phase 5 or deferred to Phase 6
- Exact API route for chat search endpoint
- How conversation history is serialized in the request
- Empty, loading, and error state copy and visual treatment

## Deferred Ideas

- NLS-06 pin-to-image: explicitly Phase 7
- SIM-02 "more like this" UI: explicitly Phase 6
- CLIP text encoder → KNN image search: model choice enables it; whether Phase 5 or 6 wires it is Claude's discretion
