---
id: SEED-011
status: dormant
planted: 2026-04-17
planted_during: v2.0 (milestone complete)
trigger_when: Next UI polish milestone, design-system / component-library work, or frontend code-quality pass
scope: Medium
related: SEED-008
---

# SEED-011: Adopt CVA (class-variance-authority) for Tailwind variant composition

## Why This Matters

The frontend currently composes Tailwind class strings with inline conditional logic —
ternaries, template strings, and ad-hoc variant maps (e.g., `Badge.tsx` keeps a
`Record<BadgeVariant, string>` by hand). This pattern has three real costs:

1. **Inconsistency.** Each component invents its own variant-handling shape. Some use
   a `Record` lookup (`Badge`), some use nested ternaries, some concatenate raw
   template literals. Shared variant names (`primary`, `danger`, `accent`, `success`)
   drift in spelling and styling across components.
2. **Hard to reason about.** Complex variants (e.g., `variant` × `size` × `disabled`)
   turn into deeply nested ternaries or growing `Record` tables that obscure the
   actual style rules.
3. **No single source of truth for variant APIs.** There's no declarative place that
   says "a Button has these variants, these sizes, these defaults" — so tooling,
   docs, and the AI agent can't reliably see or enforce the shape.

**CVA (class-variance-authority)** is the de-facto pattern (used by shadcn/ui and
most modern Tailwind codebases) for this exact problem. It turns the above into:

```ts
const buttonVariants = cva("rounded font-medium", {
  variants: {
    variant: { primary: "bg-blue-500", danger: "bg-red-500" },
    size: { sm: "px-2 py-1", md: "px-4 py-2" },
  },
  defaultVariants: { variant: "primary", size: "md" },
});

function Button({ variant, size }) {
  return <button className={buttonVariants({ variant, size })} />;
}
```

This is a pattern win, not a library-for-library's-sake adoption — it makes variant
APIs declarative, composable, type-safe, and consistent across the component library.

## When to Surface

**Trigger:** Next UI polish milestone, design-system / component-library work, or a
frontend code-quality pass

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:

- UI polish, design-system unification, or component-library work
- Frontend code quality / technical debt milestone
- Before or alongside SEED-008 (Images page UI unification) — CVA is the
  implementation technique that the unified badge/card language should use
- Onboarding: if a new contributor is going to touch the component library

## Scope Estimate

**Medium** — a phase or two. Four pieces, all in scope:

### Piece 1 — Adopt CVA + convert high-impact components

- Add `class-variance-authority` (and `clsx` + `tailwind-merge` via the common `cn`
  helper) to `apps/visualizer/frontend/`.
- Convert the variant-bearing components first:
  - `components/ui/Badge/Badge.tsx` (already has a Record-style variant map —
    low-friction conversion, good first example)
  - `components/ui/badges/VisionBadge.tsx`, `StatusBadge.tsx`, `ImageTypeBadge.tsx`
  - `components/matching/PerspectiveBadge.tsx`
  - Any Button primitive that exists or should exist (audit during planning — there
    may not be a central one yet, which is itself a finding)
  - `components/matching/MatchCard.tsx` and other card primitives
- Establish the canonical `cn()` utility for the codebase (CVA + `tailwind-merge`).

### Piece 2 — Author a Cursor skill

Create `.cursor/skills/tailwind-cva/SKILL.md` (or equivalent per the project's skill
conventions) documenting:

- When to use CVA (any component with 2+ variants, or conditional classes driven by
  props)
- The canonical `cva()` + `cn()` setup
- Naming conventions (`componentVariants`, default variants declared explicitly,
  variant keys use kebab-case values, etc.)
- A before/after example drawn from the codebase
- "Don't" patterns to avoid (inline ternaries, raw template-string class concat,
  per-component Record tables)

Goal: the agent picks up CVA automatically on any new component work, and human
contributors have one place to read the pattern.

### Piece 3 — Lint / TS rules to enforce compliance

Add ESLint rules (in `apps/visualizer/frontend/.eslintrc.cjs`) to flag:

- Conditional expressions evaluated inside `className` props (e.g.,
  `className={x ? "a" : "b"}` when more than trivially simple)
- Template literals inside `className` that concatenate variant-like fragments
- Multiple `className=` patterns that could be CVA

Options:
- Use `eslint-plugin-tailwindcss` + custom rule, or
- Write a small custom rule specific to the project.

If a full lint rule is too heavy, at minimum add a rule doc / linting checklist that
code review can reference.

### Piece 4 — Refactor existing codebase to compliance

Systematically walk the component tree and convert non-compliant components. Likely
split into sub-phases:

1. `components/ui/` primitives first (highest reuse, highest payoff)
2. `components/matching/`, `components/catalog/`, `components/identity/` (feature
   components using the primitives)
3. Page-level components last (where `className` logic is usually thinnest)

Regression coverage: existing visual tests / Storybook (if present) should stay
green. If there's no visual regression net, add one before large refactors.

## Breadcrumbs

### Current patterns to replace
- `apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx` — `Record<BadgeVariant, string>` at line 11; template-literal concat at line 22. Canonical "convert me first" example.
- `apps/visualizer/frontend/src/components/ui/badges/VisionBadge.tsx`
- `apps/visualizer/frontend/src/components/ui/badges/StatusBadge.tsx`
- `apps/visualizer/frontend/src/components/ui/badges/ImageTypeBadge.tsx`
- `apps/visualizer/frontend/src/components/matching/PerspectiveBadge.tsx`
- `apps/visualizer/frontend/src/components/matching/MatchCard.tsx`
- `apps/visualizer/frontend/src/components/catalog/CatalogImageCard.tsx`

### Infrastructure
- `apps/visualizer/frontend/package.json` — will gain `class-variance-authority`, `clsx`, `tailwind-merge`
- `apps/visualizer/frontend/.eslintrc.cjs` — where the enforcement rules will live
- Tailwind config — no changes expected, CVA is purely a class-composition layer

### No pre-existing CVA/clsx
- Grep confirmed: neither `class-variance-authority`, `clsx`, nor `tailwind-merge` are
  currently dependencies. Greenfield adoption.

### Related seeds
- **SEED-008 (Images page UI consistency)** — this seed is the *implementation
  technique* SEED-008 should use for the unified badge/card visual language. Ideally
  SEED-011 lands first or lands together with SEED-008's component work.
- SEED-007 (reusable filter component) — the filter primitives should also use CVA
- SEED-003 (rethink Identity page) — any new primitives introduced there should use CVA
- SEED-012 (skeleton loading + reusable image-grid) — the new `<Skeleton>` and
  `<ImageGrid>` primitives should be authored with CVA from day one; if this seed
  ships first they become prime refactor targets

## Notes

User feedback (2026-04-17, with a reference image showing the Khaled-Javdan
"don't / do" CVA example):

> "I want to use this way to use tailwind inside the code. I'll need to create a
> skill too for this, and some TS rules I guess, with a refactor to be compliant
> with this rule."

Captured scope (all four pieces explicitly in): CVA adoption + Cursor skill +
lint/TS rules + codebase refactor.

Size-check note: the "Medium" sizing assumes Piece 4 is time-boxed to the highest-
reuse components (primitives + badge family + cards). A full audit-and-convert of
every `className=` in the codebase could easily blow into Large — scope that
decision at planning time based on how many non-compliant sites the lint rule
surfaces.

Phased rollout within the milestone:
- **Phase 1:** Add CVA + `cn()` util + convert `Badge.tsx` as the reference example.
  Also ship the Cursor skill so the agent adopts the pattern immediately.
- **Phase 2:** Convert the badge family + Button (if exists, or introduce one) + card
  primitives.
- **Phase 3:** Add lint rule. Triage what it flags, fix the easy ones.
- **Phase 4:** Systematic refactor of remaining feature components. Possibly
  time-boxed.
