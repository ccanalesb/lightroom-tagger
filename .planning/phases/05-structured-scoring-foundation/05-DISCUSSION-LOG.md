# Phase 5: Structured Scoring Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 05-structured-scoring-foundation
**Areas discussed:** Score storage schema, Perspective registry & rubric design, Structured output validation & repair, Job checkpointing & resume

---

## Score Storage Schema

| Option | Description | Selected |
|--------|-------------|----------|
| New normalized table | `image_scores`: one row per image × perspective × version — flexible, supports arbitrary perspectives and version history | ✓ |
| Extend `image_descriptions` | Add score columns — simpler but rigid, version history harder | |
| You decide | Claude picks best approach | |

**User's choice:** New normalized table
**Notes:** Chosen for flexibility with arbitrary perspectives (SCORE-06) and built-in version history (SCORE-03/04).

### Follow-up: Version strategy (current vs historical)

| Option | Description | Selected |
|--------|-------------|----------|
| `is_current` flag | New rows set flag, old rows flipped to 0 | |
| Supersede chain | `superseded_by` pointer to newer row | |
| Timestamp-based | Current = MAX(scored_at) per image×perspective | |
| You decide | Claude picks | ✓ |

**User's choice:** You decide
**Notes:** Claude has discretion on the versioning mechanism.

### Follow-up: Relationship to image_descriptions

| Option | Description | Selected |
|--------|-------------|----------|
| Scores table independent | References image_key directly, no FK to descriptions | |
| Scoring run parent table | `image_scoring_runs` groups all perspectives from one invocation | |
| You decide | Claude picks | ✓ |

**User's choice:** You decide
**Notes:** Claude has discretion on grouping strategy.

---

## Perspective Registry & Rubric Design

### Where should rubric prompts live?

| Option | Description | Selected |
|--------|-------------|----------|
| Prompt template files on disk | `.md` files in `prompts/perspectives/` directory | |
| Config-driven (YAML/JSON) | Perspectives in config file | |
| Database-stored | Perspectives in DB table, editable via API | |

**User's choice:** Hybrid — markdown files as factory defaults, seeded into DB, DB is runtime truth
**Notes:** User wanted both the authoring experience of markdown AND UI editability without restart. Settled on `.md` files as factory defaults that seed the DB on first run.

### Follow-up: Conflict resolution (disk vs DB)

| Option | Description | Selected |
|--------|-------------|----------|
| DB always wins | Once in DB, disk files ignored. Reset to defaults is explicit. | ✓ |
| Disk wins unless user-modified | Track `user_modified` flag, auto-propagate shipped improvements | |
| Show diff/conflict | Surface divergence in UI | |
| You decide | Claude picks | |

**User's choice:** DB always wins
**Notes:** Keeps it simple. User has full control once perspectives are in the DB.

### Follow-up: Editing UI

| Option | Description | Selected |
|--------|-------------|----------|
| Simple textarea | Raw markdown, minimal UI | |
| Code editor component | CodeMirror/Monaco with syntax highlighting, line numbers | ✓ |
| You decide | Claude picks | |

**User's choice:** Code editor component

### Follow-up: Perspective equality

| Option | Description | Selected |
|--------|-------------|----------|
| All equal | Original three have no special status, can be deleted | ✓ |
| Originals protected | Original three can be edited but not deleted | |
| You decide | Claude picks | |

**User's choice:** All equal

---

## Structured Output Validation & Repair

### Repair aggressiveness

| Option | Description | Selected |
|--------|-------------|----------|
| Best-effort repair, then reject | Try common fixes, fail if repair fails | |
| Repair + retry with simpler prompt | Repair first, retry LLM call on failure, then fail | ✓ |
| Strict — no repair | Fail on first parse error | |
| You decide | Claude picks | |

**User's choice:** Repair + retry with simpler prompt

### Follow-up: Validation tooling

| Option | Description | Selected |
|--------|-------------|----------|
| Add Pydantic | Schema models as Pydantic classes | ✓ |
| Keep lightweight | Manual checks or JSON Schema, no new dependency | |
| You decide | Claude picks | |

**User's choice:** Add Pydantic

---

## Job Checkpointing & Resume

### Checkpoint granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Per-image | Record progress after each image | |
| Per-batch | Record every N images | |
| You decide | Claude picks | ✓ |

**User's choice:** You decide

### Follow-up: Resume behavior on startup

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-resume immediately | Re-enqueue orphaned jobs, no user action | |
| Mark as "resumable" and wait | New status, user clicks Resume | |
| Auto-resume with UI toast | Auto-enqueue + notification | ✓ |
| You decide | Claude picks | |

**User's choice:** Auto-resume with UI toast

### Follow-up: Scope of checkpointing

| Option | Description | Selected |
|--------|-------------|----------|
| All long-running jobs | Retrofit onto batch describe, vision match, + new scoring | ✓ |
| New scoring jobs only | Keep existing handlers as-is | |
| You decide | Claude picks | |

**User's choice:** All long-running jobs

---

## Claude's Discretion

- Score versioning strategy (current vs historical)
- Scoring run grouping (independent table vs parent run table)
- Checkpoint granularity (per-image vs per-batch)
- Code editor choice (CodeMirror vs Monaco)
- Perspectives table schema details

## Deferred Ideas

None — discussion stayed within phase scope
