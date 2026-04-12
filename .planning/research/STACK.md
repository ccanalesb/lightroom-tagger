# Stack Research — v2.0 Structured Critique, Analytics & Insights Dashboard

**Domain:** Additions for **structured AI scoring** (numeric rubrics per critique perspective), **photography-theory prompt engineering**, **analytics over Instagram dump timestamps and captions**, **lightweight time-series / pattern summaries**, and an **insights dashboard** in an existing **Flask + SQLite** backend and **React + TypeScript + Tailwind + Vite** frontend. Assumes validated core stack (catalog/jobs/vision matching/Ollama + OpenAI-compatible providers) is unchanged.

**Researched date:** 2026-04-12

**Confidence:** **HIGH** for schema validation + charting + client-side data fetching (versions verified via PyPI and npm registry JSON on this date). **MEDIUM** for optional “smart” time-series tooling (simple SQL/`datetime` often suffices before adding scientific Python). **MEDIUM** for **Instructor** vs. hand-rolled parse/retry (trade-off: convenience vs. dependency surface).

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why recommended |
|------------|---------|---------|------------------|
| **Pydantic** | **2.12.5** | Canonical models for critique payloads (per-perspective scores, rationales, tags), API response shapes, and config for “strict” JSON decoding | Gives queryable numeric fields a single source of truth in Python, integrates cleanly with Flask via explicit `model_validate` / `model_dump`, and pairs with the OpenAI Python SDK’s Pydantic-oriented parsing helpers on providers that honor JSON-schema constraints. |
| **openai** | **2.31.0** (upgrade from loose `>=1.0`) | Chat/vision calls **plus** structured parsing where the endpoint supports schema-constrained JSON | One maintained client for OpenAI-compatible gateways; v2 line documents patterns aligned with structured outputs. Keeps the same integration style as the rest of the repo while unlocking parse-and-validate flows for scoring rubrics. |
| **Recharts** | **3.8.1** | Line/area (posting cadence), bar (score distributions), composed charts for dashboard cards | Declarative React + SVG charts that fit Tailwind layout without owning a full D3 program; adequate for tens of thousands of points when the **backend pre-aggregates** series. |
| **TanStack Query (React Query)** | **5.99.0** | Server state for dashboard endpoints: caching, stale-while-revalidate, keyed refetch per catalog / date range / filter set | Avoids ad hoc `useEffect` fetch spaghetti as you add many insight widgets; works with existing REST JSON from Flask and does not require API redesign. |

### Supporting Libraries

| Library | Version | Purpose | When to use |
|---------|---------|-----------|-------------|
| **date-fns** | **4.1.0** | Parse/normalize ISO timestamps from dumps, bucket by local day/hour/DOW for “posting rhythm” views | Always if much date math moves to the browser; keeps timezone and calendar edge cases out of hand-rolled `Date` code. |
| **Zod** | **4.3.6** (or **3.24.x** if a peer dependency forces it) | Mirror critical API DTOs on the frontend (scores, aggregates) for safe chart input | When you want compile-time-friendly parsing at the UI boundary without generating OpenAPI clients yet. |
| **instructor** | **1.15.1** | Optional wrapper: Pydantic-centric structured extraction, retries, multi-provider adapters | Pull in if Ollama + multiple OpenAI-shaped hosts need **uniform** retry/validation behavior beyond what you want to maintain by hand. |
| **json-repair** | **0.59.2** | Best-effort repair of slightly malformed JSON from smaller local models before Pydantic validation | When you stay on models that do not reliably enforce JSON grammar; use behind a metric/log so you can drop it if quality improves. |
| **pandas** | **2.3.3** (project still `>=3.10`) **or** **3.0.2** (if minimum Python is raised to **≥3.11**) | Notebook/backend ETL for caption token stats, hashtag counts, rolling posting windows | Use when aggregations outgrow readable SQL but **before** reaching for distributed tooling; **3.0.2 requires Python ≥3.11** per PyPI metadata. |
| **NumPy** | **2.4.4** | Arrays for optional numeric summaries | Typically a **transitive** dependency of pandas; only list explicitly if you add small custom vectorized stats without pandas. |

---

## Installation commands

Backend (from repo root; align pins with your chosen installer):

```bash
uv add "pydantic>=2.12.5" "openai>=2.31.0"

# Optional — structured extraction helpers / salvage parsing
uv add "instructor>=1.15.1" "json-repair>=0.59.2"

# Optional — heavier analytics (pick ONE pandas line for your Python floor)
uv add "pandas>=2.3.3,<3"        # if requires-python includes 3.10
# uv add "pandas>=3.0.2"         # only after requires-python >=3.11
```

Frontend (`apps/visualizer/frontend`):

```bash
npm install recharts@^3.8.1 @tanstack/react-query@^5.99.0 date-fns@^4.1.0 zod@^4.3.6
```

---

## Alternatives considered

| Choice | Alternative | When the alternative wins |
|--------|-------------|-----------------------------|
| **Pydantic + OpenAI SDK parsing** | **instructor** everywhere | You want one abstraction across many providers and built-in retry recipes, and accept the extra dependency chain. |
| **Recharts** | **@tremor/react**, **Apache ECharts** (`echarts-for-react`), **Visx** | Tremor for rapid dashboard UI kits; ECharts for dense interaction/performance at very large series; Visx when you need bespoke photo-centric visuals and already know D3 concepts. |
| **TanStack Query** | **SWR**, **RTK Query**, hand-rolled fetch | SWR is comparable for many dashboards; RTK Query fits if you centralize on Redux Toolkit (you currently use Zustand, so Query is the lighter fit). |
| **pandas** | **Polars**, **SQL-only** in SQLite/app DB | Polars when analytics grow large enough to justify another dataframe API; SQL-only when every insight is a well-defined aggregate query and the UI only plots small result sets. |
| **date-fns** | **Day.js**, **Luxon**, **Temporal polyfills** | Day.js for tiny bundles; Luxon/Temporal when you need first-class timezone and calendar policies beyond what date-fns already covers. |
| **Zod** | **Valibot**, **TypeScript-only types** | Valibot for smaller bundles; TS-only when you fully trust the server and want zero runtime parse cost (weaker guardrail for evolving Flask JSON). |

---

## What NOT to use

| Avoid | Why | Use instead |
|-------|-----|-------------|
| **LangChain / LlamaIndex** (for this milestone) | Your flow is bounded: prompt templates + one vision/text call + validate + persist. Frameworks add indirection, version churn, and harder testing for little gain. | Plain Python string/Jinja templates + Pydantic validation + your existing job runner. |
| **Prophet, heavy forecasting stacks, or a separate TSDB** | Instagram export analytics here are **exploratory** (cadence, DOW/hour histograms, gaps vs catalog), not sub-minute operational metrics. | SQLite aggregates + optional pandas rolling/groupby; upgrade only if you later prove forecast accuracy is a product requirement. |
| **Full OpenAPI codegen pipeline** (initially) | Valuable at scale, but easy to over-build before critique JSON and insight endpoints stabilize. | Pydantic models on the server + Zod (optional) on the client, then codegen later if duplication hurts. |
| **Embedding every image for “style fingerprint”** (as the first implementation) | High GPU/storage cost; overlaps poorly with “on-demand analysis” unless carefully scoped. | Start with **textual** themes from existing critiques + hashtag/caption stats + score clustering; add embeddings only as a deliberate phase with a budget. |
| **ORM mapped to Adobe `AgLibrary*` tables** | Undocumented, version-sensitive Lightroom schema. | Keep thin SQL for `.lrcat`; store critique scores and analytics in **your** app tables or sidecar DB as already implied by PROJECT.md. |

---

## Sources

- **PyPI JSON API** (`https://pypi.org/pypi/{package}/json`), retrieved **2026-04-12**: `pydantic` **2.12.5**, `openai` **2.31.0**, `instructor` **1.15.1**, `json-repair` **0.59.2**, `pandas` **3.0.2** (requires Python **≥3.11**), `numpy` **2.4.4**; latest **pandas 2.x** line noted as **2.3.3** for **Python 3.10** compatibility.
- **npm registry** (`https://registry.npmjs.org/{package}/latest`), retrieved **2026-04-12**: `recharts` **3.8.1**, `@tanstack/react-query` **5.99.0**, `date-fns` **4.1.0**, `zod` **4.3.6**.
- **`.planning/PROJECT.md`** — v2.0 scope (structured scores, new perspectives, posting/caption analytics, insights dashboard) and constraints (SQLite catalogs, export-based Instagram, on-demand analysis).
- **`pyproject.toml`** / **`apps/visualizer/frontend/package.json`** — current Python `>=3.10` floor and existing React 19 / Vite 5 / Tailwind 3 baseline for integration assumptions.

---

*Research scope: NEW v2.0 capabilities only — structured AI output, scoring schemas, analytics computation, dashboard visualization, and critique prompt patterns. Core Flask/React/job/vision stack treated as validated and out of scope for this document.*
