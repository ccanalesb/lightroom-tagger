---
title: Image Comparison Narrowing Strategy
date: 2026-04-24
context: Exploration session — replacing LLM-only comparison with a layered pre-filter approach
---

# Image Comparison Narrowing Strategy

## Problem

The current comparison pipeline is 100% LLM-based (direct image comparison + description comparison).
At n=1,000 vs m=40,000, that's up to 40M potential pairs — too slow, too expensive, and imperfect accuracy.

Images being compared are edited/processed versions of the same source: crops (up to ~20%), color corrections, filters.
The goal is **not** to replace LLM judgment, but to protect it from doing unnecessary work.

## Proposed Architecture

### Normal Path

```
1. Date window filter     → reduce catalog from 40k to "images within 90 days"
2. Embedding pre-filter   → FAISS KNN on DINOv2/CLIP vectors → top-k candidates per query image
3. LLM comparison         → runs only on shortlisted candidates (not the full catalog)
```

### Opt-in Fallback Path

Triggered when the normal path yields **zero candidates**:

```
1. User explicitly opts in to a wider search (no date window, or extended window e.g. 180/365 days)
2. Embedding pre-filter → same FAISS KNN, wider candidate pool
3. LLM comparison → runs on shortlisted candidates
```

The fallback is **never automatic** — the system surfaces "no matches found within 90 days" and the user decides whether to broaden the search. This keeps the normal path fast and cheap.

## Key Design Decisions

- **Recall-first tuning:** The pre-filter top-k should be generous (top-100 or top-200) since missing a true match is worse than sending extra candidates to LLM. A 400x reduction in LLM calls (40M → 100k) is still a major win.
- **DINOv2 preferred over CLIP** for this use case — self-supervised encoders hold up better for near-duplicates with color/filter edits. 20% crop is within global embedding tolerance.
- **FAISS locally** (not a managed vector DB) — batch Python jobs don't benefit from network round-trips; local FAISS is simpler and faster for offline processing.
- **Date window is the first filter** — this likely cuts the effective catalog size dramatically before any embedding work.

## Validation Approach

The database already has user-validated matches. Run DINOv2 embeddings on known match pairs, measure cosine similarity distribution, and set the top-k threshold empirically to achieve target recall (e.g. 99%+).

## References

- HuggingFace image similarity blog: https://huggingface.co/blog/image-similarity
- HF Transformers image feature extraction: https://huggingface.co/docs/transformers/main/en/tasks/image_feature_extraction
- Image matching webui (for re-ranking): https://github.com/Vincentqyw/image-matching-webui
