# Mirror UI prototype — #203

**Throwaway.** Answers: *what replaces the radar-of-means to show "your prominent
techniques + the peak photos that prove them"?* (issue #203, part of map #199).
Renders the metric decided in #201 against **real** `library.db` data.

## Run

Backend must be up on `:5001` (photos load from the live thumbnail route). Then just
open the file:

```
open apps/visualizer/frontend/prototypes/mirror-prototype.html
```

Regenerate from current DB: `scratchpad/compute_mirror.py` → `mirror_data.json` →
`scratchpad/gen_html.py` (data is embedded into the HTML; no server needed for data).

## What it shows (design choices locked with the user)

- **Stacked sections** — one section per crowned technique: name + "you spike here N%
  of the time" + peak-exemplar rail. Degrades from 2 → 1 → fallback.
- **Standout dimension surfaces in the modal only** — bare thumbnails; click opens a
  modal with the photo, its standout lens + percentile + purity, a per-lens score bar
  chart, and the rationale.
- **Three states** via the bottom switcher (←/→ or `?state=`):
  - `happy` — one clean signature (Depth & Environmental Context, z=9.69).
  - `coverage` — the **real** result: 2 crowned lenses, Framing carrying the
    `scored on ~50% of your catalog` caveat (49.8% coverage).
  - `flat` — the fallback: nothing clears the bar → top-1 flagged
    "leading, but not strongly distinctive."
- Deep-link `?modal=<slug>` opens the top exemplar's modal (review affordance).

Real metric output (n=3291): **Depth & Environmental Context** (win 37%, z=9.69) and
**Framing** (win 28%, z=2.85, low coverage) are crowned; Compositional Cleanliness
(z=−8.47) and Interpretive & Human Charge (z=−3.15) are not.

## Reactions resolved (feed the PRD)

1. **Standout cue on the rail** — keep tiles clean, **rank number only** (`#1..#12`);
   the full "why" (standout lens, percentile, purity, per-lens bars, rationale) stays
   in the click-through modal. Gallery-calm over at-a-glance evidence, by choice.
2. **Signature strength stat** — **words, not numbers.** Heading shows a qualitative
   label off the z-score: `z≥6` "A defining strength", `z≥3` "A clear strength",
   crowned "A strength", fallback "Leading, but not strongly distinctive." The raw
   win-rate / chance / z sit in a hover tooltip and in the modal. (Rejected: raw "37%",
   which reads as weak without the ~25% chance anchor.)
3. **Rail layout** — **horizontal scroll rail**, one screen-row per technique (≈6 tiles
   visible, scroll for 7–12). Keeps the page tight even at 2–3 crowned lenses; accepts
   that the tail is hidden until scrolled.

## Verdict

Layout accepted. Fold into `components/identity/` when #199's PRD is authored, then
delete this folder.
