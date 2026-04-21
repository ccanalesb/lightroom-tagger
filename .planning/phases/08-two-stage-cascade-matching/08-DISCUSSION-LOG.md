# Phase 8: Two-stage cascade matching — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 08-two-stage-cascade-matching
**Areas discussed:** compare_descriptions_batch design, Frontend controls

---

## compare_descriptions_batch design

| Option | Description | Selected |
|--------|-------------|----------|
| Instagram caption vs catalog AI summaries | Use the Instagram post's caption as reference text | |
| Catalog summary vs catalog summaries | If the Instagram image also has an AI description, use that as reference | ✓ |
| Claude's discretion | — | |

**User's choice:** Catalog summary vs catalog summaries — the Instagram image's AI summary (from `image_descriptions`) is used as reference, not the post caption.

---

### Follow-up: where does the Instagram image's summary come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Always describe on-the-fly | If no summary exists, describe inline before comparison | ✓ |
| Only use existing summaries | Skip description stage if no summary | |
| Claude's discretion | — | |

**User's choice:** Describe on-the-fly using current description methods if Instagram image has no summary.

---

### Follow-up: response shape for `compare_descriptions_batch`

| Option | Description | Selected |
|--------|-------------|----------|
| Same shape as `compare_images_batch` | `{"results": [{"id": N, "confidence": 0-100}]}` | ✓ |
| Different shape | Include reasoning field or separate similarity dimensions | |
| Claude's discretion | — | |

**User's choice:** Same shape — symmetric with vision batch.

---

## Frontend controls

| Option | Description | Selected |
|--------|-------------|----------|
| Inside AdvancedOptions.tsx | Alongside existing weight sliders | ✓ |
| Above Advanced Options section | Visible in main launcher UI | |
| Claude's discretion | — | |

**User's choice:** Inside `AdvancedOptions.tsx`.
**Notes:** Toggle should be disabled (greyed out) when `descWeight === 0`.

---

### Follow-up: default state for `skip_undescribed`

| Option | Description | Selected |
|--------|-------------|----------|
| Default ON (true) | Skip undescribed candidates, no surprise API calls | ✓ |
| Default OFF (false) | Auto-describe inline by default | |
| Match ROADMAP default | Same as ON | |

**User's choice:** Default ON — matches backend default.

---

## Claude's Discretion

- Exact SQL join form for `find_candidates_by_date`
- Whether `compare_descriptions_batch` lives in `vision_client.py` or a new file
- Batch size for description stage
- How inline-describe for Instagram image is triggered
- Test file naming and coverage structure

## Deferred Ideas

None.
