---
created: 2026-04-26T18:21:47.459Z
title: Plan backend restart and compression fix
area: tooling
files:
  - scripts/restart-backend.sh:1-26
  - apps/visualizer/backend/app.py:145-231
  - lightroom_tagger/core/analyzer.py:158-203
  - apps/visualizer/backend/jobs/handlers.py:2160-2312
---

## Problem

Backend restart behavior and resumed job execution need a controlled implementation plan before additional edits. During restart, orphaned `batch_analyze` work can resume immediately and produce repeated image compression logs, which makes startup feel blocked or unstable. This thread also established a process constraint: do not apply code changes without explicit user validation first.

## Solution

Create and execute a plan-first rollout:

1. Reproduce and measure startup/resume responsiveness with current auto-resume behavior.
2. Identify where redundant compression happens for resumed analyze/describe flow.
3. Design a minimal, reversible fix that preserves auto-resume while skipping unnecessary compression work.
4. Add focused tests for restart recovery + compression skip conditions.
5. Apply changes only after explicit user approval on the final implementation plan.
