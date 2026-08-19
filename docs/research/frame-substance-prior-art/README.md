# Frame substance: prior art on detecting technically-failed frames

Research finding for wayfinder ticket #276 (map #275 — *frame substance: gate void frames out of
scoring, and stop one perspective crowning a photo*).

**The question:** how do existing photo tools detect technically-failed frames (voids, gross
underexposure, blown frames, missed focus) **without** rejecting intentional low-key or minimalist
work?

Five parallel investigations, primary sources throughout:

| | Sub-report | Scope |
|---|---|---|
| 1 | [Commercial tools](01-commercial-tools.md) | Lightroom, Capture One, Aftershoot, Narrative, ON1, Excire, Optyx, Photo Mechanic + patent literature |
| 2 | [Learned IQA](02-learned-iqa.md) | NIMA, BRISQUE/NIQE/PIQE, MUSIQ/MANIQA/LIQE/CLIP-IQA, LAION aesthetic predictor — **with measurements on our own library** |
| 3 | [Classical discriminators](03-classical-discriminators.md) | FFmpeg `blackdetect`, broadcast QC standards, luminance/entropy/percentile/blob/focus metrics |
| 4 | [Subject presence](04-subject-presence.md) | Salient Object Subitizing, SOD, SAM, open-vocab detection, CLIP prompt pairs, complexity measures |
| 5 | [Local feasibility](05-local-feasibility.md) | What this repo already has: cached pixels, CLIP vectors, pHash, descriptions, the pipeline seam |

## Verdict

**The map's single "frame substance" signal is actually two signals, and they need different
mechanisms and different authority.**

Four investigations converged on this independently, so it is the finding that matters most:

- **Class A — the void.** Lens cap, misfire, shutter test, blown white. A *cheap, safe, classical*
  rule catches these with published thresholds inherited from twenty years of broadcast QC. Sub-report
  3 proposes five such rules that fire on neither of our test cases in error. Sub-report 5 measures
  the cost at **57 seconds** for all 42,136 frames, off the local cache, with the NAS unmounted.
- **Class B — the illegible frame.** `_DSF1528` and friends: a crescent moon on black. A subject
  *is* present, so the frame is not void; there is simply not enough there to judge. **No scalar
  statistic separates this from a genuinely excellent night photograph.** Sub-report 3 shows why
  algebraically (percentiles, standard deviation and contrast are three views of one axis —
  lit-area — and the distributions touch). Sub-report 2 confirms it empirically: on the best
  learned axis found, our Statue-of-Liberty keeper sits at percentile 92 and the crescent moon at
  percentile **91**.

The map assumed one gate. It needs a **two-tier** signal: an auto-reject tier for Class A and a
**flag-for-review** tier for Class B.

**This puts pressure on two settled premises of map #275.** The map records that the gate *acts
immediately without confirmation* and *stops the scoring pass*. That is defensible for Class A —
the rules are precise and the failure is unambiguous. For Class B it is not supportable by any
evidence found: every candidate mechanism has a false-positive rate that would cost real
photographs their scores. **Recommend re-opening gate authority as a per-tier decision** rather
than a single map-wide one. See "Consequences for the map" below.

## The industry's answer, and the one patent that solves our problem

**Negative finding, checked deliberately rather than merely unobserved: not one of ten commercial
tools documents any protection for intentionally dark, low-key or minimalist work.** The industry
has accepted motion blur and closed eyes as deliberate — Aftershoot has boudoir and newborn
profiles, FilterPixel has a REVIEW bucket for "dragging the shutter" — but it has never accepted
*darkness* as deliberate.

Worse, exposure-based auto-reject is new and now shipping: Lightroom Classic 15.0 Assisted Culling
(Oct 2025) has an **"Exposure issues"** reject checkbox with no sensitivity control, and Capture
One 16.8 (May 2026) advertises filtering out "black frames". Both would reject our night
photographs. The tools that spare them — Narrative, Photo Mechanic, Excire, ON1 — are safe by
*accident*, because they never look at brightness at all. Optyx is safe only because it is
face-gated.

**The most useful single source found is PhotoSi's US11586669B2**, the only primary source that
solves our exact problem and states its parameters:

- Percent-of-pixels-in-extreme-bins (**75%**) only *triggers* analysis.
- The verdict is **noise-trimmed contrast**: 2% percentile trim, threshold **125/255**.
- Its own worked example is a dark photograph *kept* "as it has sufficient contrast" — a lit
  artwork in a dark room — versus a flat night landscape rejected.

Two patterns worth stealing, and one to avoid:

- **Steal:** brightness as trigger only, contrast as verdict (PhotoSi). Judge by *kind* — "is this
  a misfire?" — not by *degree* — "is this too dark?" (Google US10891485B2, which keys its shipped
  auto-hide on semantic kind and user intent, not pixel statistics).
- **Steal:** reject relative to siblings, never absolutely (Apple AU2017261537B2, ratio 0.6–0.9
  against the best frame in a burst). Our catalog has stacks; this is available to us.
- **Avoid:** Apple's US20130058590A1 "substantially blank image" test — a *global* detail-energy
  floor (constant C = 3.0). A small lit subject on a large black field falls under the floor.
  That is precisely our false-positive mechanism, patented.

Adobe's US10521705B2 confirms darkness is a learned negative in their stack: it trains "good
exposure as high quality… bad lighting, blur, and noise as low quality", and its own landscape
example scores lower "due to the building being in shadow".

**Excire's shipping behaviour is closest to what we want:** "Dark" and "High Contrast" are
searchable *descriptive keywords*, never quality penalties. Describe the darkness; do not judge it.

## Numbers we can inherit

Class A thresholds do not need inventing. From FFmpeg's source (`libavfilter/vf_blackdetect.c:64-73`)
and corroborated across four independent commercial implementations:

| Parameter | Value | Source |
|---|---|---|
| `pixel_black_th` | **0.10** | FFmpeg `blackdetect` |
| `picture_black_ratio_th` | **0.98** | FFmpeg `blackdetect` |
| Rule | `is_black = luma <= th` (inclusive), `ratio = nb_black/(w*h)`, frame black if `ratio >= th` | `vf_blackdetect.h:41` |
| Full-range 8-bit constant | **Y ≤ 25** (`0.10*255 = 25.5`, truncated) | our previews are full-range JPEG — **25, not 37** |
| Limited-range 8-bit constant | Y ≤ 37 (`16+0.10*219 = 37.9`) | for reference only |

The 98% area figure is the strongest number in this whole report because it is **independently
converged on**, not merely popular: FFmpeg 0.98, Dolby Hybrik `black_pixel_ratio` 0.98, Tektronix
WFM 98%, AWS Rekognition `MinCoveragePercentage` 99. FFmpeg's older `blackframe` filter (2002
MPlayer lineage) uses `amount=98`, `threshold=32`.

Other inherited values: Rekognition `MaxPixelThreshold` 0.2 → max black pixel value **51**
full-range, luminance via BT.709; Tektronix black level **5 mV** with a 60% × 80% measurement
area; Cerify publishes the bridge from code values to a percentage UI verbatim — **0% = luma 16,
100% = luma 235**. AWS MediaLive is the outlier and stricter than everyone: *"every pixel in a
frame must be below this threshold"*, an implicit 100% coverage requirement.

**No standard numerically defines "black frame."** BT.601/709/2100, EBU R 103, FADGI, Metamorfoze
and ISO 19264-1 define black *levels* (16/235, 64/940); only tools define *detection*. EBU QC item
0016B comes closest and still leaves every threshold as an input parameter — and specifies its
colour as 8-bit RGB `#000000` with a Euclidean tolerance, not a luma threshold.

Also worth noting for the cull surface: Rekognition documents that black frames **with audio**
are treated as content, not as blanks — the same black-plus-silence coupling Netflix requires. The
general principle transfers: a second, independent channel of evidence is what makes a blank
verdict safe.

## What is ruled out, with evidence

Several plausible-sounding options are dead, and knowing which saves the prototype weeks:

- **LAION aesthetic predictor — ruled out on our own data, not by argument.** Sub-report 2 ran the
  official v1 head over all 41,566 embeddings already in `library.db`. **All 26 Statue-of-Liberty
  night frames land in percentile 0–3.** The top of its ranking is eleven near-duplicates of a
  person in a red shirt in front of a turquoise waterfall. It is a colourfulness detector, and this
  collection is monochrome and minimal. Not a darkness penalty either — the broad night cohort
  (n=5,447) sits unpenalised at p47; the penalty is specifically monochrome + low-content +
  high-black-fraction.
- **The canonical CLIP-IQA `Good photo./Bad photo.` prompt pair is a night detector here.** Its
  twelve lowest-scoring images are all night, silhouette and moon scenes; the Statue sits at p29.
  Shipping it would delete good work.
- **Our own intuitive "content vs nothing" prompt pairs fail and invert** — AUC 0.266–0.454,
  ranking the keeper *below* the illegible frames. Do not ship them.
- **NIMA's technical head is a dead end twice over.** TID2013 is 25 daylight references × 24
  *synthetic* distortions rated *with the reference visible*; no empty frame, no gross
  underexposure. Google released no weights, and `pyiqa` ships no TID2013 checkpoint at all.
- **BRISQUE / NIQE / PIQE are actively harmful.** MSCN normalisation collapses to zero on flat
  regions — NIQE's reference implementation using `nanmean`/`nancov` is the tell — and **PIQE
  returns exactly 100, its worst score, on a uniform frame by arithmetic**.
- **Laplacian variance must never be applied globally to a night collection.** It is *quadratic in
  contrast*, so dark-but-sharp frames score low for reasons unrelated to focus. The folk threshold
  of 100 comes from a blog post that itself calls it scene-dependent; the actual source
  (Pech-Pacheco, ICPR 2000) defines something different from `cv2.Laplacian().var()` in three ways
  and does not recommend it.
- **Object detection as a presence test is ruled out with hard numbers.** CODaN day→night, same
  classes: 80.39% → 48.31%. WIDER→DARK FACE with Faster-RCNN: **1.7 mAP**. Enhancement
  preprocessing buys ≤0.5 mAP. A detector gate would systematically reject legitimate night work.
- **SOD saliency mass and SAM confidence both fail.** In U²-Net / BASNet / InSPyReNet the
  statistic is not even measurable — min-max normalisation plus input auto-gain destroys the scale.
  Itti-Koch's normalisation explicitly *promotes* "a small number of strong peaks", so it favours
  the moon by design. SAM's design goal is "always predict a valid mask" — a bright disc on black
  is the *easiest* possible segmentation, so its confidence heads invert.
- **pHash cannot see this.** DCT drops the DC term and thresholds against its own median, so
  absolute brightness is discarded by construction. Verified on our two confirmed voids: both hash
  like ordinary busy frames.

## What is worth prototyping, cheapest first

1. **Lit-area fraction on a downsampled frame (Class A, and the honest Class B signal).** Free,
   57 s for the catalog, off the local cache. Sub-report 4's probe separates the two test cases
   0.72% vs 11.38%, **bit-identical across three noise levels**. Sub-report 3 independently makes
   area the *only* differing axis: Statue ≈ 0.05 of frame, crescent moon 2e-4 (50mm) to 6e-3
   (600mm) — a 70–250× typical gap, **but the distributions touch**, so this belongs in the
   flag tier, never in auto-reject.
2. **A linear probe on the CLIP embeddings we already have.** `nn.Linear(512,1)`. CLIP's own paper
   reports linear probes beating zero-shot by 10–25 points at a median 5.4 labels per class; LAION
   v1 was 769 parameters fitted on 5,000 ratings and went on to select Stable Diffusion v1's
   training set. Our text tower is in-process, our vectors are already L2-normalised, and
   **over 20,000 human-labelled negatives exist** to bootstrap from: SOS 14K, XPIE's 8,598 "no
   clear object", SOC's **2,217 "aurora, sky"** images (literally our Class B), SOSB's 6,182.
3. **LIQE, if a learned model is wanted.** The only model whose label space *names* our failure
   mode: joint quality × scene × distortion, with `night scene` among 9 scenes and
   **`under-exposure` / `over-exposure`** among 11 distortions. Runs on CLIP ViT-B/32 — the
   backbone we already use — 353 MB, open weights. Measured **~84 min CPU / ~46 min MPS** for 42k
   on this machine. Risk: the scene and distortion labels were added by the authors post hoc, so
   `under-exposure` may be thinly supervised.
4. **A vision call, for a shortlist only.** ~1.54 s/image measured ⇒ 18 h for the catalog, versus
   57 s for the pixel pass. Viable for adjudicating a few hundred borderline frames (~13 min), not
   as a gate.

**Best-supported framing, if prompts are used at all:** phrase both poles positively — VLMs are at
chance on negation (NegBench, CVPR 2025) — and fit thresholds to our own score histogram rather
than adopting an absolute cut. The best pair measured on our data was
`"a deliberately dark low-key night photograph"` / `"an accidentally underexposed failed
photograph"`, AUC **0.862**. It still does not separate the moon.

## The named published problem, and the labels that come with it

The reframing the map guessed at is real and has a literature. **Salient Object Subitizing**
(Zhang et al., CVPR 2015 / IJCV 2017, arXiv:1607.07525) predicts the *existence and number* of
salient objects with **0 as a first-class class**, at **94% recall on the 0-class**, which the
authors describe as matching human accuracy. It already implements our intended architecture:
*"if our SOS method predicts zero salient objects, then we do not apply salient object detection"*
— for a >35% relative AP gain. A second precedent (Jiang et al., joint SOD + existence
prediction) reports 88.36% existence accuracy on 6,182 purpose-collected background images.

Two supporting findings sharpen *why* our case is hard: Xia et al. (CVPR 2017) name "low
objectness" as a distinct reason a high-contrast region is *not* salient — the crescent moon
exactly; and SOS reports that saliency-map features are *worse* than HOG/GIST at predicting
existence. Low-level signals are the wrong instrument for Class B, and that is a published result,
not our inference.

**Negative finding: no negative-space, minimalism or low-key classifier exists.** AVA's style
vocabulary is exactly 14 labels and contains none of them (`Light_On_White` and `Silhouettes` are
nearest); AADB's 11 attributes likewise. **Nobody has separated intentional from failed
underexposure.** The closest thing is an implicit fix in defect-detection work
(arXiv:1612.01635): learn "bad exposure" from *human severity ratings* rather than from
statistics — which suggests our bug may be a **labelling** problem before it is a model problem.

**Negative finding: nobody has measured CLIP under illumination or exposure corruption.** The CLIP
paper's robustness section explicitly excludes ImageNet-C-style synthetic shifts, so every
low-light number available is from a CNN. Night transfer is the untested link in *every* path
surveyed. YLLSOD (3,263 pairs, explicit "extreme darkness" class) and NTI-V1 (577 night images)
are ready-made evaluation sets for exactly this.

## Repo hazard found while researching

**`analyzer/image_prep.py:89` calls `raw.postprocess(use_camera_wb=True, half_size=True)`.**
rawpy's `no_auto_bright` defaults to `False`, so LibRaw **brightens until ~1% of pixels clip**
(`auto_bright_thr=0.01`, gamma `(2.222, 4.5)`). A genuinely black RAW frame is silently lifted
before it is ever cached or measured.

Two consequences: it works directly against the discrimination we want, and it means **absolute
luminance thresholds are not comparable between the RAW path and the JPEG path**. Any Class A
threshold must be calibrated on whichever path actually produced the cached pixels — or
`no_auto_bright=True` must be set for the detector's read. This is the highest-leverage
single-line finding in the report and belongs in the prototype's first hour.

## Consequences for map #275

1. **Split the signal into two tiers, and decide authority per tier.** Class A auto-rejects on
   inherited thresholds; Class B flags for review. The map's current single answer — acts without
   confirmation, stops the scoring pass — is well-supported for A and unsupported by any evidence
   for B. This is a decision for the driving dev, not for the research, and it is the one place
   the research contradicts a settled premise.
2. **A third verdict value is required: `unknown`.** 1,041 catalog images (2.5%) have no local
   pixels — 974 with no `vision_cache` row plus 67 `__oversized__` sentinels. They cannot be
   judged without the NAS and must not be guessed at.
3. **`BLANK_FRAME_SCORE_FLOOR` is confirmed dead**, and now for two reasons rather than one: it
   reads the *max* score (so it misses all four reported frames), and its stated discriminator is a
   0.35-point gap on a 10-point scale. Sub-report 1 also shows the wider industry moving the *other*
   way — from score thresholds toward descriptive labels.
4. **The rubric may already contain the separator, unstably.** `environmental-context-legibility`
   is **1** for all four crescent-moon frames versus 3–8 for the Statue keepers, and `_DSF1526`
   reproduces the reported pathology exactly (cleanliness 9, legibility 1). But it is unstable
   across `prompt_version` — `L1007429` scored 2 on one version and 7 on another. That instability
   is a prerequisite to using it, and it is a finding for the corroboration ticket, not the gate.
5. **The detector does not belong in the vision-op engine.** ADR-0014 §6 already places embedding
   generation outside it; a pixel-statistic detector is the same kind of thing. Gate at two seams:
   `scoring_service.py:196` for correctness, `_select_catalog_keys` (`common.py:107`) for
   throughput.

## Caveats

- Two Google Patents searches on intent-aware IQA were rate-limited and did not complete, so
  "no such patent exists" is **not** established for that class.
- Vendor QC defaults for Interra BATON, Venera Pulsar, Dalet AmberFin and Telestream Aurora are
  genuinely unpublished — units are documented, values are not. Treat any third-party figure for
  those as unverified until read in a licensed user guide.
- All row counts and timings in sub-report 5 are from a live read on 2026-08-19 and move with every
  batch run. Re-verify before acting.
- Licensing flags for whoever owns OSS review, if any of this ever leaves personal use: `rembg`'s
  *default* model is RMBG-2.0, which is **non-commercial** and ~1 GB, picked up silently on a naive
  install; BiRefNet (MIT) is the permissive equivalent; Ultralytics is AGPL-3.0. Redistributing
  Netflix Partner Help Center, Tektronix and Telestream manual contents is a separate question from
  citing them.

---

*Created using Anthropic Claude. This line should stay on internal versions until a human has
reviewed and verified the content. Share only with people authorised to see this catalog's data.*
