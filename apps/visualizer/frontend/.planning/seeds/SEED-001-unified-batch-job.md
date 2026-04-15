---
id: SEED-001
status: dormant
planted: 2026-04-15
planted_during: v2.0 (milestone complete)
trigger_when: UX improvements milestone or job queue redesign
scope: Small
---

# SEED-001: Unify batch description and batch scoring into a single default job

## Why This Matters

Users have to go through two separate flows to get a full analysis (description + scoring), which is confusing and adds friction. Both operations target the same set of photos with the same selection criteria, yet require launching two independent jobs. By default, a single "Analyze" job should run both description and scoring together. Power users who only want one or the other can still opt out, but the default path should be unified.

## When to Surface

**Trigger:** When the next milestone focuses on UX improvements or job queue redesign

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- UX or usability improvements to the processing workflow
- Job queue or job creation UI redesign
- Simplifying the batch analysis experience

## Scope Estimate

**Small** — A few hours. The backend handlers already share selection logic; this is mostly about combining the two into a single job type that dispatches both, and updating the UI to present one unified flow with an advanced toggle for running them separately.

## Breadcrumbs

Related code and decisions found in the current codebase:

- `apps/visualizer/backend/jobs/handlers.py` — batch_describe and batch_score handlers (share similar selection logic)
- `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` — job queue UI where users launch jobs
- `apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx` — batch action panel for descriptions
- `apps/visualizer/frontend/src/components/descriptions/BatchActionPanel.tsx` — batch selection UI
- `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` — job detail view
- `apps/visualizer/backend/tests/test_handlers_batch_score.py` — batch score test coverage
- `apps/visualizer/backend/tests/test_handlers_batch_describe.py` — batch describe test coverage
- `apps/visualizer/backend/jobs/checkpoint.py` — checkpoint logic shared by both job types

## Notes

The two batch jobs already share selection criteria (timeframe, filters) and target the same photos. The implementation path is likely: (1) add a composite `batch_analyze` job type that runs describe then score in sequence, (2) make it the default in the UI, (3) keep separate describe/score as an "advanced" option behind a toggle.
