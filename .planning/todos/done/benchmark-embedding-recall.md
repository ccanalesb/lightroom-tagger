---
title: Benchmark DINOv2/CLIP embeddings against user-validated match pairs
date: 2026-04-24
priority: high
context: Required before committing to embedding pre-filter threshold in image comparison pipeline
---

# Benchmark Embedding Recall on Validated Matches

## Goal

Empirically determine the cosine similarity threshold (and top-k value) needed to achieve
high recall (99%+) on real match pairs before building the embedding pre-filter into the pipeline.

## Steps

1. Extract all user-validated match pairs from the database (catalog image ↔ Instagram image confirmed matches)
2. Generate DINOv2 embeddings for both sides of each pair (and a sample of known non-matches)
3. Compute cosine similarity for all pairs
4. Plot the similarity distribution: true matches vs. non-matches
5. Identify the threshold at which recall ≥ 99% (note the false positive rate at that threshold)
6. Determine what top-k value is needed to capture all true matches within the 90-day date window

## Success Criteria

- Know what cosine similarity threshold gives ≥ 99% recall on validated pairs
- Know the expected false positive rate (candidates sent to LLM that aren't true matches)
- Know the effective top-k needed per query image
- Have a go/no-go signal for whether DINOv2 global embeddings are sufficient or regional embeddings needed

## Notes

- Also test CLIP and SigLIP for comparison — DINOv2 is the hypothesis but worth validating
- Test with images that have aggressive crops (~20%) to confirm global embedding holds up
- Dataset: use `matching` table or equivalent where user has confirmed/rejected matches

---

Closed Phase 10 (2026-05-01): recall-only measurement — see [.planning/phases/10-match-02-quantitative-benchmark/10-RECALL.md](../phases/10-match-02-quantitative-benchmark/10-RECALL.md). Recall measurement only — cost-reduction benchmark and DINOv2/CLIP/SigLIP A/B comparison are deferred follow-ups.
