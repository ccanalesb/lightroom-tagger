---
title: Generate read-only HTML comparison-pool report
date: 2026-05-06
priority: high
context: Needed to diagnose why Instagram-to-catalog image matching misses expected matches before changing prompts
---

# Generate Read-Only HTML Comparison-Pool Report

## Problem

Some Instagram images still do not get matched to the expected catalog images, even after the search space is narrowed. We do not yet know whether those misses happen because the expected catalog image is absent from the comparison pool, because the comparison prompt fails to identify the match, or because scoring/ranking buries the correct candidate.

Prompt changes would be premature until we can inspect real unmatched cases with the exact candidate pool the system evaluated.

## Goal

Create an offline, read-only HTML report from existing logs/job data that lets a human inspect unmatched Instagram images against the catalog images that were actually in their comparison pool.

## Report Shape

For each unmatched Instagram image:

1. Show the Instagram image thumbnail/preview and stable identifier.
2. Show every catalog image that was included in the actual comparison pool for that run.
3. Include stable catalog identifiers next to each candidate image.
4. Include current comparison evidence when available, such as score, rank, reason, prompt response, or log excerpt.
5. Make it easy to visually answer:
   - the expected catalog image was present but scored/ranked poorly;
   - the expected catalog image was absent from the pool;
   - there is no obvious catalog match in the pool.

## Constraints

- Investigation artifact only; do not add a product screen.
- Read-only; do not persist labels or write judgments back to the app/database.
- Use only the actual comparison pool. Do not show every catalog image outside the pool, because that does not diagnose the pipeline behavior.

## Success Criteria

- A generated HTML file can be opened locally and inspected without running the app frontend.
- Each unmatched Instagram image is traceable to the candidate catalog images that were actually compared.
- The report contains enough identifiers to let the user say "Instagram image X should have matched catalog image Y" when Y was present.
- The report makes pool absence visible when the expected match is not present.
