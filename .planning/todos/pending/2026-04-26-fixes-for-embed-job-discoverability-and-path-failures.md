---
created: 2026-04-26T18:30:56.139Z
title: Fixes for embed job discoverability and path failures
area: ui
files:
  - apps/visualizer/frontend/src/components/image-view/ImageDetailModal.tsx:89-189
  - apps/visualizer/frontend/src/constants/strings.ts:288-295
  - apps/visualizer/frontend/src/components/image-view/__tests__/ImageDetailModal.test.tsx:71-128
  - apps/visualizer/frontend/src/services/api.ts:132-160
  - apps/visualizer/backend/jobs/handlers.py:2538-2660
  - lightroom_tagger/core/database.py:3021-3055
---

## Problem

When users click "More like this" and see `Visual similarity is unavailable`, the app tells them to run an embed job but does not clearly show where to do that in-product. This causes confusion during normal browsing ("where do I execute anything?").

After manually enqueueing `batch_embed_image`, the job can also appear to be "running but doing nothing" because many catalog rows are skipped due to missing/unreachable file paths (example path style: `//tnas/...`). Users do not get a clear early explanation that storage access is the blocker, so the workflow feels broken.

## Solution

1. Keep and ship the inline CTA from the similarity error state that can start `batch_embed_image` directly from the modal.
2. Add explicit navigation affordance to Job Queue after enqueue (link/button to `/processing?tab=jobs`), not just text.
3. Improve embed preflight UX:
   - before full run, sample-check a small set of filepaths for readability;
   - if unreachable rate is high, fail fast with a single actionable message (mount path/share offline) instead of thousands of skip logs.
4. Add a concise "why skipped" summary in job result payload (counts grouped by missing file, empty path, no DB row) so UI can render a clear diagnosis.
5. Document expected storage/mount requirements for environments that use network shares (`//tnas/...`) and add troubleshooting steps in Processing/Catalog Cache help copy.
6. In Phase 8 planning, explicitly decide and document why matching/stacking should depend on original filepaths versus operating virtually on cached/compressed derivatives:
   - validate whether "virtual stacking on compressed cache outputs" can satisfy quality + traceability requirements;
   - if original files are still required, record the non-negotiable reasons (fidelity, reproducibility, write-back identity contract).
