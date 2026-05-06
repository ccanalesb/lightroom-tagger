---
id: SEED-021
status: dormant
planted: 2026-05-06
planted_during: exploration — image matching diagnostics and scoring calibration
trigger_when: after missed-match diagnostics identify where the matching pipeline fails
scope: small
---

# SEED-021: Benchmark Aesthetic Scoring Against Award-Winning Reference Photos

## Why This Matters

The current "best photo" scoring prompt may be poorly calibrated. Very few, if any,
images receive 9-10 scores, but it is unclear whether that reflects the image set or
whether the prompt/model is reluctant to use the top of the scale.

Before treating low top-end scores as meaningful feedback, compare the scoring behavior
against reference images from award-winning photographers or competitions. If those
images also rarely score 9-10, the scale or rubric likely needs recalibration.

## When to Surface

**Trigger:** After the missed-match investigation clarifies whether match failures are
caused by pool generation, comparison prompt behavior, or ranking. Matching diagnostics
come first so scoring calibration does not distract from finding expected catalog matches.

## Scope Estimate

**Small** — likely a standalone analysis task or narrow phase:

1. Curate a small reference set of award-winning or highly regarded photographs.
2. Run the existing aesthetic scoring prompt/model against the reference set.
3. Compare score distributions against the user's catalog images.
4. Decide whether the rubric should be recalibrated, the prompt should force fuller scale usage, or the current low scores are credible.

## Notes

Useful outputs would include score histograms, example images at each score band, and
side-by-side reasoning text for user images versus reference images.
