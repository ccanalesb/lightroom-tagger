# Data sufficiency for an identity "strength profile"

Research finding for Wayfinder ticket #200 (map #199 — reconceive the identity page).
Source: direct queries against `library.db`, replicating the identity service filter
(`is_current=1 AND image_type='catalog' AND not_attempted=0`, joined to `active=1` perspectives).

## Verdict

**A strength profile is feasible — but only if scores are normalized _within each perspective_ before any cross-perspective comparison.** A naive peak/argmax or raw-8+ metric is *not* meaningful on this data: it would report the same "signature" for almost everyone, because the perspectives are not on a comparable scale.

## Data snapshot

- **11,506** current catalog score rows on the 4 active perspectives, across **3,292** images (~3.5 perspectives/image).
- **Coverage is healthy**: 49.7% of images scored on all 4 perspectives, 50.2% on 3, and only 5 images on ≤2. The "3-covered" half is almost entirely images missing **framing** (framing coverage = **49.8%**); the other three perspectives are scored on ~3,289 images each.
- 4 active perspectives, only 1 non-optional (`compositional-cleanliness`); the other three are `optional=1`.

## The confound: perspectives are not on a comparable scale

| perspective | n | mean | sd | % scoring ≥8 |
|---|---|---|---|---|
| environmental-context-legibility | 3289 | **5.90** | 1.54 | **9.4%** |
| intensity-suggestion | 3287 | 4.63 | 1.09 | 0.3% |
| compositional-cleanliness | 3291 | 4.47 | 0.92 | 0.3% |
| framing | 1639 | 3.87 | 1.31 | 1.3% |

`environmental-context-legibility` runs ~1.3–2 points hotter than the others and produces
9.4% of all 8+ scores vs 0.3% for two of the others. Consequence:

- **Raw peak (argmax) is env-context in 80.4% of images.** Not a personal signature — an artifact of rubric calibration.
- Raw peaks are shallow: **56% of images have a peak that beats the runner-up by ≤1 point**, 20.6% are outright ties. So raw 1–10 scores can't decisively separate techniques.

## The fix: normalize within perspective

Convert each raw score to a per-perspective z-score `(score − mean_perspective) / sd_perspective`
(percentile-rank within perspective would work equally well), then compare across perspectives.
Peak distribution rebalances into something meaningful, and ties disappear:

| perspective | RAW peak % | NORMALIZED peak % |
|---|---|---|
| environmental-context-legibility | 80.4 | 35.4 |
| intensity-suggestion | 23.7 | 26.1 |
| compositional-cleanliness | 14.9 | 23.7 |
| framing | 7.0 | 14.8 |

- **100% of images get a unique normalized peak** (z-scores break the raw ties); median normalized peak gap ≈ 0.54 z.
- The per-perspective mean/sd needed for this baseline is computed from the existing scores — **no new data or rescoring required.**

## Caveats the metric (#201) must account for

1. **Normalization is mandatory, not optional.** Any peak / "reliably spikes on" definition on raw scores will be dominated by env-context. This means the parked "distinctiveness vs. baseline" idea ("C") is *not* fully deferrable — the core metric needs a **per-perspective baseline** (its own score distribution), which we have. External/corpus baselines remain out of core.
2. **Framing coverage is only 49.8%.** For half the images framing can't be a candidate peak, and the per-perspective baseline for framing rests on ~1,639 scores. Decide whether the signature is computed only over images with full coverage, or per-perspective independently (recommended: per-perspective, since normalization already handles differing n).
3. **Only 4 perspectives, 1 non-optional.** A "signature" drawn from 4 lenses is coarse — likely top-1 or top-2 techniques is the honest resolution, not a fine-grained ranking.
4. **Small effective spread.** Normalized separations are modest (median 0.54 z); the metric should lean on *body-of-work aggregation* (how often an image spikes on a perspective, in normalized terms) rather than any single photo's peak, to get a stable signal.

## Recommendation to #201 (metric definition)

Define "your work reliably spikes on perspective X" as a **body-of-work rate of normalized peaks**: normalize scores within perspective, then per image take its normalized peak(s), then rank perspectives by how often they are (or are near) an image's normalized peak. Surface the top 1–2 as the signature. Rank exemplar photos within a technique by that perspective's normalized score. Compute baselines over the current active-perspective scores; no rescoring needed.
