---
plan: 04
title: Analyze tab rename, strings, primary Analyze CTA, advanced split stages
wave: 3
depends_on: [02]
files_modified:
  - apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx
  - apps/visualizer/frontend/src/pages/ProcessingPage.tsx
  - apps/visualizer/frontend/src/App.tsx
  - apps/visualizer/frontend/src/constants/strings.ts
autonomous: true
requirements:
  - JOB-06
---

<objective>
Rename the Processing “Descriptions” tab to **Analyze** end-to-end (**D-13**): `git mv` the component file, switch URL slug to `?tab=analyze`, replace primary UX with a single **Analyze** button calling `JobsAPI.create('batch_analyze', …)` (**D-09**, **SC-2**), move separate-stage buttons under the existing Advanced disclosure as **Run stages separately** (**D-10**), replace one `force` checkbox with two bound to `force_describe` / `force_score` (**D-11**), and route all new copy through `ANALYZE_*` exports in `constants/strings.ts` (**D-12**). Depends on plan **02** so `'batch_analyze'` is a registered backend handler before the UI calls it.
</objective>

<context>
**Rename (D-13):** From repo root:

```bash
git mv apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx
```

Then rename the exported React function `DescriptionsTab` → `AnalyzeTab` inside the moved file.

**Strings (D-12):** Add new exports in `apps/visualizer/frontend/src/constants/strings.ts` (suggested literal values — adjust only if they violate tone, but keys are binding):

- `TAB_ANALYZE = 'Analyze'` — Processing tab label
- `ANALYZE_CARD_TITLE = 'Analyze Images'`
- `ANALYZE_CARD_SUBTITLE = 'Run AI description + scoring in a single job. Advanced options let you run stages separately.'`
- `ANALYZE_PRIMARY_BUTTON = 'Analyze'`
- `ANALYZE_ADVANCED_RUN_SEPARATELY_TITLE = 'Run stages separately'`
- `ANALYZE_ADVANCED_DESCRIBE_ONLY = 'Generate Descriptions only'`
- `ANALYZE_ADVANCED_SCORE_ONLY = 'Run scoring only'`
- `ANALYZE_FORCE_DESCRIBE_LABEL = 'Force regenerate descriptions'`
- `ANALYZE_FORCE_SCORE_LABEL = 'Force regenerate scores'`
- `ANALYZE_JOB_STARTED = 'Analyze job started! Check Job Queue tab to monitor progress.'` (or match existing alert tone)

Either **deprecate-in-place** or **repoint** `TAB_DESCRIPTIONS`: Processing must import `TAB_ANALYZE` instead of `TAB_DESCRIPTIONS`. If `TAB_DESCRIPTIONS` is still needed for `NAV_DESCRIPTIONS` / legacy nav elsewhere, keep `TAB_DESCRIPTIONS` string as-is for non-Processing routes and add `TAB_ANALYZE` for Processing only — **acceptance** uses `TAB_ANALYZE` inside `ProcessingPage.tsx`.

**Metadata builder (D-11):** Replace single `force` state with `forceDescribe` + `forceScore` booleans. `buildBatchJobMetadata()` returns:

- Always `force_describe: forceDescribe` and `force_score: forceScore` for the unified job.
- Advanced-only handlers: `JobsAPI.create('batch_describe', { ...base, force: forceDescribe })` and `JobsAPI.create('batch_score', { ...base, force: forceScore })` where `base` is the same object as today minus the old flat `force` key.

**Primary CTA (D-09):** `await JobsAPI.create('batch_analyze', { ...buildBatchJobMetadata() })` including `force_describe` / `force_score`.

**Layout (D-10):** Card shows **only** the Analyze button outside Advanced. Inside the existing Advanced disclosure (after provider + workers controls), add a subsection titled `ANALYZE_ADVANCED_RUN_SEPARATELY_TITLE` with the two secondary buttons wired to `batch_describe` / `batch_score`.

Remove the old long helper paragraph about “descriptions produce…” per D-12.

**Routes:** `App.tsx` legacy `/descriptions` redirect must change search from `?tab=descriptions` → `?tab=analyze`.

**ProcessingPage.tsx:** `PROCESSING_TAB_IDS` entry `'descriptions'` → `'analyze'`; import `AnalyzeTab` from `../components/processing/AnalyzeTab`; tabs array `id: 'analyze'`, `label: TAB_ANALYZE`, `content: <AnalyzeTab />`.
</context>

<tasks>
<task id="4.1">
<action>
From repo root run:

`git mv apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx`

Edit `apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx`:

- Rename export to `export function AnalyzeTab() { ... }`
- Replace card title/subtitle/button copy with imports from `../../constants/strings` using the `ANALYZE_*` / `TAB_ANALYZE` keys added in task 4.2 (no raw English strings in JSX except unavoidable dynamic error text already using `alert(...)` pattern — success/error alerts must also use `ANALYZE_*` or reuse existing generic JOB strings if any exist; if none, add `ANALYZE_JOB_FAILED_PREFIX` etc. under `ANALYZE_*`).

State: `const [forceDescribe, setForceDescribe] = useState(false); const [forceScore, setForceScore] = useState(false);` removing the old single `force` state.

`buildBatchJobMetadata` must return an object including **both** `force_describe: forceDescribe` and `force_score: forceScore`, plus all existing keys (`image_type`, `date_filter`, `max_workers`, `perspective_slugs`, optional `min_rating`, optional `provider_id` / `provider_model`) **excluding** legacy flat `force` for the unified path.

Handlers:

- `startAnalyze` → `JobsAPI.create('batch_analyze', buildBatchJobMetadata())`
- `startDescriptionsOnly` → `JobsAPI.create('batch_describe', { ...buildBatchJobMetadata(), force: forceDescribe })` — **must** omit conflicting flat `force` from spread before override OR build `const m = buildBatchJobMetadata(); delete m.force_describe; delete m.force_score;` then add `force: forceDescribe` — simplest: `const base = buildBatchJobMetadata(); return JobsAPI.create('batch_describe', { ...base, force: forceDescribe, force_describe: undefined, force_score: undefined })` is ugly — **preferred:** create `buildAdvancedDescribeMetadata()` returning `{ image_type, date_filter, max_workers, perspective_slugs, ..., force: forceDescribe }` without the analyze-only keys.

Implement two small builders or one `buildSharedBaseMetadata(): Record<string, unknown>` without any `force*` keys, then compose three payloads:

1. `batch_analyze`: `{ ...shared, force_describe, force_score }`
2. `batch_describe`: `{ ...shared, force: forceDescribe }`
3. `batch_score`: `{ ...shared, force: forceScore }`

Remove the old visible “Run batch scoring” primary button row; scoring-only moves inside Advanced per D-10.

Wire checkboxes: labels `ANALYZE_FORCE_DESCRIBE_LABEL` / `ANALYZE_FORCE_SCORE_LABEL`.
</action>
<read_first>
- apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx
- apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx
- apps/visualizer/frontend/src/constants/strings.ts
- .planning/phases/03-unified-analyze-job/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `test -f apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx && echo ok` prints `ok`
- `test ! -f apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx && echo ok` prints `ok`
- `rg -n "export function AnalyzeTab" apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` matches 1 line
- `rg -l "DescriptionsTab" apps/visualizer/frontend/src/` returns **no** output (exit code 1 from `rg` is OK)
- `rg -n "JobsAPI\.create\('batch_analyze'" apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` matches 1 line
- `rg -n "JobsAPI\.create\('batch_describe'" apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` matches 1 line
- `rg -n "JobsAPI\.create\('batch_score'" apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` matches 1 line
- `rg -n "force_describe" apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` matches at least 1 line
- `rg -n "force_score" apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` matches at least 1 line
- `rg -n "'force':" apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` matches at least 2 lines (one per advanced-only `JobsAPI.create` payload)
- `rg -n "force_describe: forceDescribe" apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` matches 1 line inside `buildBatchJobMetadata` (or equivalent builder returned object literal)
- `rg -n "force_score: forceScore" apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx` matches 1 line inside the same builder
</acceptance_criteria>
</task>

<task id="4.2">
<action>
Edit `apps/visualizer/frontend/src/constants/strings.ts`:

- Add the `ANALYZE_*` constants and `TAB_ANALYZE` listed in `<context>` (export each with `export const ...`).
- Keep `TAB_DESCRIPTIONS` export if other files still import it; **do not** repoint unrelated nav constants like `NAV_DESCRIPTIONS` unless a grep shows they are Processing-tab-specific only.

Edit `apps/visualizer/frontend/src/pages/ProcessingPage.tsx`:

- `import { AnalyzeTab } from '../components/processing/AnalyzeTab';`
- Replace `TAB_DESCRIPTIONS` import with `TAB_ANALYZE`.
- `PROCESSING_TAB_IDS`: replace `'descriptions'` with `'analyze'`.
- Tabs entry: `{ id: 'analyze', label: TAB_ANALYZE, content: <AnalyzeTab /> }`.

Edit `apps/visualizer/frontend/src/App.tsx` route `/descriptions` Navigate search string: `?tab=analyze` instead of `?tab=descriptions`.

Optional copy tweak: ProcessingPage hero sentence still says “descriptions” — update plain English clause to “analysis jobs” or similar **without** removing the sentence entirely; this sentence is **not** required to move to `strings.ts` unless you touch it (minimize churn: leave as-is if still accurate enough).
</action>
<read_first>
- apps/visualizer/frontend/src/constants/strings.ts
- apps/visualizer/frontend/src/pages/ProcessingPage.tsx
- apps/visualizer/frontend/src/App.tsx
- apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx
- .planning/phases/03-unified-analyze-job/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "export const TAB_ANALYZE" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `rg -n "export const ANALYZE_PRIMARY_BUTTON" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `rg -n "TAB_ANALYZE" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches at least 2 lines (import + label)
- `rg -n "'analyze'" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches at least 2 lines (`PROCESSING_TAB_IDS` + tabs array)
- `rg -n "AnalyzeTab" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches at least 2 lines
- `rg -n '\?tab=analyze' apps/visualizer/frontend/src/App.tsx` matches 1 line
- `rg -n "'?tab=descriptions'" apps/visualizer/frontend/src/` returns **no** matches
- `rg -n "TAB_DESCRIPTIONS" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` returns **no** matches
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</acceptance_criteria>
</task>

<task id="4.3">
<action>
Run `rg -n "descriptions" apps/visualizer/frontend/src/` and for every **frontend routing** hit (not REST paths like `/descriptions/` API URLs in `api.ts`), confirm `?tab=descriptions` is gone and Processing tab IDs remain coherent. Do **not** rename API routes.

Run frontend unit tests (entire suite is OK): `cd apps/visualizer/frontend && npm test -- --run` — if too slow, minimally `npx vitest run` with no args; executor should prefer full `npm test -- --run` once.

Manual smoke (document only): visit `/processing?tab=analyze`, toggle both force boxes, click Analyze, confirm network POST body contains `type":"batch_analyze"` with `force_describe`/`force_score` booleans.
</action>
<read_first>
- apps/visualizer/frontend/src/services/api.ts
- apps/visualizer/frontend/src/pages/ProcessingPage.tsx
- .planning/phases/03-unified-analyze-job/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "from '\\.\\./components/processing/DescriptionsTab'|from \"\\.\\./components/processing/DescriptionsTab\"" apps/visualizer/frontend/src/` returns no matches
- `rg -n '\?tab=descriptions' apps/visualizer/frontend/src/` returns no matches
- `rg -n "batch_analyze" apps/visualizer/frontend/src/` matches at least 1 line
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
- `cd apps/visualizer/frontend && npm test -- --run` exits 0
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
- `cd apps/visualizer/frontend && npm test -- --run` exits 0
- `rg -l "DescriptionsTab" apps/visualizer/frontend/src/` returns no paths
- `rg -n '\?tab=descriptions' apps/visualizer/frontend/src/` returns no matches
</verification>

<must_haves>
- **D-09 / SC-2:** Default button creates `batch_analyze` job with shared metadata superset.
- **D-10:** Separate describe/score launches live only under Advanced “Run stages separately”.
- **D-11:** Two independent booleans → `force_describe` / `force_score` for analyze; flat `force` only for legacy job types’ advanced buttons.
- **D-12 / D-13:** No `DescriptionsTab` symbol; slug `analyze`; history preserved via `git mv`; user-facing strings centralized under `ANALYZE_*` / `TAB_ANALYZE`.
- **Dependency:** Plan **02** merged first so backend accepts `batch_analyze`.
</must_haves>
