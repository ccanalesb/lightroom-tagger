# Classical (non-learned) discriminators for blank / black / technically-failed frames

Created using Anthropic Claude. Keep this line on internal versions until a human has reviewed and verified the content.

Scope: what production systems actually use, with their real default thresholds, and whether any of it can separate our two adversarial cases.

---

## 1. Verdict up front

**1.1 — The reusable numbers exist and are decades-tuned, but they are numbers for *broadcast video black*, not for *photographic merit*.** FFmpeg `blackdetect`'s two defaults (`pixel_black_th=0.10`, `picture_black_ratio_th=0.98`) reduce to: *a picture is black when ≥98% of its luma samples are ≤ 10% of the luma range.* On an 8-bit full-range JPEG that is **Y ≤ 25 for ≥98% of pixels**. On limited-range video it is **Y ≤ 37**. These are directly reusable and are the single best-supported numbers in this whole report.

**1.2 — No standard defines "black frame" numerically. Only tools do.** ITU-R BT.709/BT.601/BT.2100, SMPTE and EBU R 103 define *black level* (code value 16 in 8-bit narrow range, 64 in 10-bit) and *signal tolerance*. None of them defines a detection rule — no percentage-of-frame, no duration. Every number in section 2 comes from a tool (FFmpeg, QCTools) not a standard. Treat that as the structural finding: if you want a numeric rule you are picking a tool's tuning, not conforming to a spec.

**1.3 — No single scalar separates the Statue-of-Liberty-at-night frame from the crescent-moon-only frame.** This is the honest answer, and it is not a shortfall of the search. Every classical scalar collapses the two cases:

- Mean/median luminance: both ≈ 0. Identical.
- Standard deviation / RMS contrast: both low and dominated by the same term (a tiny bright region against black). Identical to within a factor set by area, which is the *one* thing that does differ — so it is not an independent signal.
- Histogram entropy: both very low, both ≈ the entropy of "one huge black bin plus a thin tail". Identical.
- Upper-percentile luminance (P99, P99.5, P99.9): both have a bright tail. The *only* thing the percentile curve encodes is **at what percentile the luminance takes off**, and that is algebraically `1 − nonblack_fraction`. Percentiles are a reparameterisation of area, not new information.
- Laplacian variance and every gradient-energy focus measure: both are low, for the same reason (most of the frame has zero gradient), and both are low *for reasons unrelated to focus*. This metric is actively misleading on dark frames.

**1.4 — The one axis that does differ is AREA of the non-black region, and it separates the *typical* instances by 1–2 orders of magnitude but overlaps at the extremes.** A Statue frame described as "~95% black" has `nonblack_fraction ≈ 0.05`. A crescent moon on a 24 MP frame is `≈ 2e-4` at 50 mm and `≈ 7e-4` at 200 mm — a 70–250× gap. But at 600 mm a crescent reaches `≈ 6e-3`, and a Statue shot small in frame can fall to `≈ 5e-3`. **The distributions touch.** Area is your best classical axis and it is still not a safe auto-reject axis.

**1.5 — Therefore the correct architecture is two-tier, and the classical layer must not make the keep/reject call.**

- **Tier A (classical, high precision, safe to auto-reject):** answers *"is there any light-bearing content at all?"* — lens cap, black-out frame, unexposed frame, all-noise frame, blown-white frame. This tier rejects neither of our two cases; the crescent moon **passes** Tier A because it has a genuine bright tail. That is correct behaviour: "there is something there" is a signal question; "the something is only a moon" is not.
- **Tier B (subject-level, learned):** the crescent-moon reject is a *subject identity* judgement. A caption/CLIP/VLM signal ("night sky, moon, no subject" vs "Statue of Liberty, monument, night") is the only thing that makes it. Do not try to build a moon detector out of blob circularity — see §5.7 for why the shape route is a trap.

**1.6 — Your pipeline has a specific hazard that invalidates absolute luminance thresholds on RAW-derived images.** `lightroom_tagger/core/analyzer/image_prep.py:89` calls `raw.postprocess(use_camera_wb=True, half_size=True)`. rawpy's `no_auto_bright` defaults to **`False`**, so LibRaw's automatic brightness stretch is applied, targeting `auto_bright_thr = 0.01` (1% of pixels clipped). **A 95%-black night frame gets brightened by LibRaw until ~1% of its pixels clip.** Every absolute threshold in this report will read differently on a RAW-derived preview than on a camera JPEG of the same scene. See §6.

**1.7 — Dependency reality for this repo: NumPy, SciPy and Pillow are available; OpenCV is not.** `uv.lock` contains `numpy`, `scipy` (via `ImageHash` and `scikit-learn`), `pillow` and `rawpy`; there is no `opencv-python` entry. So `scipy.ndimage` morphology and connected components **are** available, which is enough for every metric proposed in §7 without adding a dependency.

---

## 2. FFmpeg and broadcast QC: published algorithms and exact defaults

This section is verified against filter source in `libavfilter` at FFmpeg master, plus the official filter documentation. Put these numbers first because they are the only ones in this report with real production provenance.

### 2.1 `blackdetect` — the canonical rule (most reusable)

Docs: <https://ffmpeg.org/ffmpeg-filters.html#blackdetect_002c-blackdetect_005fvulkan>
Source: <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_blackdetect.c> and <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_blackdetect.h>

**Algorithm (exactly, from source):**

```
per pixel:   is_black = (luma <= pixel_black_th_i)          # NOTE: <=, inclusive
per frame:   picture_black_ratio = nb_black_pixels / (w * h)
frame black  if picture_black_ratio >= picture_black_ratio_th
report       if a contiguous black run lasts >= black_min_duration
```

The per-pixel comparison is literally `counter += src[x] <= threshold;` in `count_pixels8_c()` (`vf_blackdetect.h:41`). Only the **luma plane** is examined (`plane = s->alpha ? 3 : 0`); chroma is ignored entirely.

**Defaults (from `blackdetect_options[]`, `vf_blackdetect.c:64-73`):**

| Option | Alias | Default | Meaning |
|---|---|---|---|
| `pixel_black_th` | `pix_th` | **0.10** | fraction of the luma *range*, not of 255 |
| `picture_black_ratio_th` | `pic_th` | **0.98** | fraction of pixels that must be black |
| `black_min_duration` | `d` | **2.0 s** | minimum run length to log |
| `alpha` | — | 0 | check alpha instead of luma |

**The range scaling — this is the part everyone gets wrong.** From `filter_frame()` (`vf_blackdetect.c:189-195`):

```c
const int full = picref->color_range == AVCOL_RANGE_JPEG ||
                 ff_pixfmt_is_in(picref->format, yuvj_formats) || s->alpha;
s->pixel_black_th_i = full ? s->pixel_black_th * max :
    16 * factor + s->pixel_black_th * (235 - 16) * factor;
```

with `max = (1<<depth)-1` and `factor = 1<<(depth-8)`. The documented form is
`absolute_threshold = luma_minimum_value + pixel_black_th * luma_range_size`.

Because `pixel_black_th_i` is an `unsigned int`, the double result is **truncated**, not rounded:

| Input | Computation at default 0.10 | Effective integer threshold | Rule |
|---|---|---|---|
| 8-bit limited range (BT.601/709 video) | `16 + 0.10 × 219 = 37.9` | **37** | luma ≤ 37 |
| 8-bit full range (JPEG / YUVJ / sRGB preview) | `0.10 × 255 = 25.5` | **25** | luma ≤ 25 |
| 10-bit limited range | `64 + 0.10 × 876 = 151.6` | **151** | luma ≤ 151 |
| 10-bit full range | `0.10 × 1023 = 102.3` | **102** | luma ≤ 102 |

**For our system the relevant line is the full-range one: Y ≤ 25 out of 255.** Our previews are tone-mapped 8-bit sRGB JPEGs, i.e. full range. Anyone who copies "37.9" from a blog post into a JPEG pipeline is using a 50% looser black threshold than FFmpeg would.

**Reusable pair:** *black pixel = Y ≤ 25 (full range, 8-bit); black frame = ≥ 98% of pixels black.*

### 2.2 `blackframe` — the older, simpler, absolute-threshold rule

Docs: <https://ffmpeg.org/ffmpeg-filters.html#blackframe>
Source: <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_blackframe.c>
Lineage: ported from MPlayer `libmpcodecs/vf_blackframe.c`; copyrights go back to Brian J. Murrell 2002. This is the ~24-year-old original that `blackdetect` was "loosely based on".

```
per pixel:  black_pixels_count += p[x] < bthresh;            # NOTE: strict <, and NO range scaling
per frame:  pblack = nblack * 100 / (w * h);                  # integer division
flag        if pblack >= bamount
```

**Defaults (`vf_blackframe.c:132-139`):**

| Option | Default | Meaning |
|---|---|---|
| `amount` | **98** | percent of pixels below threshold |
| `threshold` / `thresh` | **32** | absolute luma code value, no range scaling at all |

Two differences from `blackdetect` that matter if you port either: `<` vs `<=`, and **no full-/limited-range adaptation** — 32 is 32 regardless of format. `pblack` is integer-truncated, so 97.9% reads as 97 and does not trip.

The 98% figure is common to both filters, arrived at independently ~10 years apart (2002 MPlayer → 2012 `blackdetect`). Treat 98% as the genuinely load-bearing consensus number; the pixel threshold (25 / 32 / 37) is the format-dependent one.

### 2.3 `signalstats` — production percentile luminance statistics

Docs: <https://ffmpeg.org/ffmpeg-filters.html#signalstats>
Source: <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_signalstats.c>

**This is the primary-source answer to "does anyone use upper-percentile luminance statistics this way?" — yes, broadcast QC does, and has for over a decade.** But note *which* percentiles they chose:

```c
lowp   = lrint(s->fs * 10 / 100.);     // vf_signalstats.c:706
highp  = lrint(s->fs * 90 / 100.);     // vf_signalstats.c:707
```

Emitted metadata (`vf_signalstats.c:765-798`):

| Key | Definition |
|---|---|
| `YMIN` | luma minimum (first non-empty histogram bin) |
| `YLOW` | **luma 10th percentile** |
| `YAVG` | luma mean |
| `YHIGH` | **luma 90th percentile** |
| `YMAX` | luma maximum |
| `YDIF` | mean absolute frame-to-frame luma difference, `dify / (w*h)` |
| `YBITDEPTH` | effective bit depth from the OR-mask of all values seen |
| `TOUT` | fraction of pixels that are temporal outliers |
| `VREP` | fraction affected by vertical line repetition |
| `BRNG` | fraction of pixels outside broadcast range |

`BRNG`'s out-of-range test is hard-coded (`vf_signalstats.c:236-238`) and is the cleanest primary-source statement of broadcast legal range in code:

```c
const int filt = luma    < 16 || luma    > 235 ||
                 chromau < 16 || chromau > 240 ||
                 chromav < 16 || chromav > 240;
```

`TOUT`'s outlier predicate is also hard-coded, with an in-source admission that the constant is arbitrary (`vf_signalstats.c:284`):

```c
return ((abs(x - y) + abs(z - y)) / 2) - abs(z - x) > 4; // make 4 configurable?
```

**Why 10/90 and not 99.5.** QCTools' documentation of these same values explains the design intent directly: *"instead of looking at the absolute minimum and maximum value for these channels, it looks at the 10th percentile (LOW) and 90th percentile (HIGH) ... An extreme minimum or maximum value could dramatically skew the graph but because they may be outside the viewable broadcast image (or the range of human perception), they may not necessarily be meaningful indicators of a problematic visual image."* — <https://github.com/bavc/qctools/blob/main/docs/filter_descriptions.md>

That is the opposite of what we need. Broadcast QC deliberately chose robust *inner* percentiles to suppress small bright outliers, because in broadcast a handful of hot pixels is noise. **In our problem the small bright region is the subject.** So we should take the *technique* (percentile luminance) from broadcast QC but invert the choice: we want P99.9 / P99.99 / max, precisely the outliers they discard. I found no production QC tool using upper percentiles above 90 for this purpose, so §5.3's use of P99.5+ should be treated as our own construction rather than as inherited practice.

### 2.4 `freezedetect` — stuck-frame / duplicate detection

Docs: <https://ffmpeg.org/ffmpeg-filters.html#freezedetect>
Source: <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_freezedetect.c>

Defaults (`vf_freezedetect.c:54-61`):

| Option | Default | Meaning |
|---|---|---|
| `noise` / `n` | **0.001** | SAD noise tolerance, as a fraction of full scale |
| `duration` / `d` | **2 s** (`2000000` µs) | minimum frozen run |

Mechanism: scene SAD (`ff_scene_sad_fn`) against a held reference frame. Note the same 2-second minimum duration as `blackdetect` — the pairing of a per-frame test with a temporal-persistence requirement is the standard broadcast QC shape, and is the part we *cannot* borrow because we grade single stills.

### 2.5 `entropy` — histogram entropy, with a normalised variant

Docs: <https://ffmpeg.org/ffmpeg-filters.html#entropy>
Source: <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_entropy.c>

Exact computation (`vf_entropy.c:137-156`), per plane, over a full `1<<depth`-bin histogram:

```c
// mode=normal (default)
if (histogram[y]) { float p = histogram[y] / total; entropy += -log2(p) * p; }

// emitted:
lavfi.entropy.entropy.normal.Y             = entropy                       // bits
lavfi.entropy.normalized_entropy.normal.Y  = entropy / log2(1 << depth)    // 0..1
```

So **normalised entropy is divided by the bit depth** (8 for 8-bit), giving a clean 0–1 scale. `mode=diff` instead takes entropy over `|hist[y] - hist[y-1]|`, i.e. histogram roughness rather than histogram spread.

There is **no threshold option** — the filter only reports. QCTools states the endpoints and nothing more: *"A color channel with only a single shade will have entropy of 0, while a channel using all shades will be 1."* (<https://github.com/bavc/qctools/blob/main/docs/filter_descriptions.md>). **No production tool I found publishes a numeric entropy threshold separating flat from textured.** If you use entropy you are choosing the number yourself.

### 2.6 `blurdetect` — the production blur metric, and note what it is *not*

Docs: <https://ffmpeg.org/ffmpeg-filters.html#blurdetect-1>
Source: <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_blurdetect.c>

Worth flagging because QCTools' "Blurriness" plot is exactly this filter at defaults, so this is *the* blur metric in archival video QC. **It is not variance-of-Laplacian.** The source header states the implementation target:

> Marziliano, Pina, et al. "A no-reference perceptual blur metric." ICIP 2002, vol. 3.
> <https://infoscience.epfl.ch/record/111802/files/14%20A%20no-reference%20perceptual%20blur%20metric.pdf>

i.e. **edge-width based**: Canny edges, then measure the spatial width of each edge's intensity ramp, then pool. Defaults (`vf_blurdetect.c:73-82`):

| Option | Default | Meaning |
|---|---|---|
| `high` | **30/255 ≈ 0.1176** | Canny high hysteresis threshold |
| `low` | **15/255 ≈ 0.0588** | Canny low hysteresis threshold |
| `radius` | **50** | search radius for edge-ramp maxima |
| `block_pct` | **80** | percentile used when pooling block blurriness |
| `planes` | 1 | luma only |

**Why this matters for our constraint:** an edge-width metric measures sharpness *only where edges exist*. On a 95%-black frame it silently restricts itself to the subject — which is exactly the masked behaviour §5.6 argues for. That is a strong argument that the production answer to "measure focus on a mostly-black frame" is *edge-localised*, not *global-variance*. Conversely, on a frame with **no** edges above the Canny threshold it has nothing to pool and the value is meaningless rather than low — so it cannot double as a blank detector.

### 2.7 What the standards actually say (and do not)

| Source | What it defines | Numeric black | Defines a *detection rule*? |
|---|---|---|---|
| ITU-R BT.601 / BT.709 / BT.2100 | quantisation levels for the video signal | 8-bit narrow range black = **16**, white = **235**; 10-bit black = **64**, white = **940** | **No** |
| EBU R 103 "Video Signal Tolerance in Digital Television Systems" (<https://tech.ebu.ch/docs/r/r103.pdf>) | tolerance bands for how far a signal may exceed nominal range | expressed as tolerance around the BT. levels | **No** |
| FADGI / Metamorfoze / ISO 19264-1 (still-image preservation) | tone response, black/white point, clipping | Metamorfoze: black clip = any RGB channel at 8-bit **0**; highlight clip = any channel at **255**; hard cap L\* ≤ 98 | **No blank-page test at all** |
| FFmpeg `blackdetect` | *detection* | Y ≤ 25 (full) / 37 (limited), ≥ 98% of pixels, ≥ 2.0 s | **Yes** |
| FFmpeg `blackframe` | *detection* | Y < 32, ≥ 98% of pixels | **Yes** |

The generalisation, which holds on both the video and the scanned-document side: **standards specify levels; tools specify detection.** Archival still-image standards (FADGI 2023, Metamorfoze 2.0, ISO 19264-1) contain no blankness test whatsoever. The closest analogue anywhere in a preservation standard is FADGI 2023's *Noise (Lower Limit) > 0.25 std-dev of L\**, which flags an image as **too flat** — and it is aimed at a calibration target, treating flatness as a *system fault*, not as a blank page. Document-scanning blank-page detection is likewise all vendor-side (TWAIN byte-size, ABBYY object counts, Kofax eVRS edge-count 75 / black-pixel-count 450, Dynamsoft std-dev ≤ 1 at a 128 split) and notably **no document tool defaults to the percentage-of-black-pixels rule** — the opposite of video practice.

*Not verified:* I could not confirm any published black-frame parameter defaults for commercial QC products (Interra BATON, Telestream Vidchecker, Venera Pulsar, Tektronix Aurora); their parameter documentation is behind customer portals. Netflix Photon is an IMF/XML validation library and contains no pixel-domain black-frame test. Treat any specific vendor number you see quoted elsewhere as unverified.

---

## 3. Metric summary table

Assume an 8-bit array `Y` (0–255) of luma from a tone-mapped sRGB preview. "Separates?" means: does this metric alone distinguish **A = Statue of Liberty, ~95% black, keep** from **B = crescent moon only, reject**?

| Metric | Formula | NumPy-only? | Robust to | Fails on | Separates A/B? |
|---|---|---|---|---|---|
| Mean luma | `Y.mean()` | yes | nothing much | any dark image | **No** — both ≈ 0 |
| Median luma | `np.median(Y)` | yes | bright outliers (by design) | *deliberately* blind to small subjects | **No** — both ≈ 0 |
| Non-black fraction (FFmpeg) | `(Y > 25).mean()` | yes | scene content, gamma choice is the only knob | knife-edge when sky sits near 25 | **Partially** — 0.05 vs 2e-4…6e-3; ranges touch |
| P50 / P90 (broadcast `YLOW`/`YHIGH`) | `np.percentile(Y,[10,90])` | yes | hot pixels, sensor noise | blind to the subject in a 95%-black frame | **No** |
| P99.5 / P99.9 / P99.99 | `np.percentile(Y,99.9)` | yes | isolated hot pixels (at 99.5) | pure reparameterisation of area | **No** (equivalent to area) |
| Max luma | `Y.max()` | yes | nothing — single-pixel sensitive | one stuck hot pixel defeats it | **No** — both high |
| Std dev | `Y.std()` | yes | — | scales with subject area × brightness | **No** |
| RMS contrast | `Y.std() / Y.mean()` (see §5.8) | yes | overall gain | **divide-by-≈0 on near-black frames** | **No** — unstable |
| Michelson contrast | `(Ymax-Ymin)/(Ymax+Ymin)` | yes | — | saturates at ≈1 for any frame with black and a highlight | **No** — both ≈ 1.0 |
| Shannon entropy (256 bins) | `-Σ p log2 p` | yes | geometry, rotation | one dominant black bin pins it low | **No** — both low |
| Normalised entropy | `H / 8` | yes | bit depth | same as above | **No** |
| Laplacian variance | `Var(conv(Y, L))` | yes (`scipy.ndimage.laplace`, or a 4-line NumPy slice-sum) | — | **scales with contrast/energy: a dark but perfectly sharp frame scores low** | **No**, and misleading |
| Masked Laplacian variance | same, restricted to `Y > 25` | yes | frame-level darkness | needs enough mask pixels; noisy masks | **No** (both sharp) |
| Tenengrad | `Σ (Gx² + Gy²)` over `> T` | yes | noise better than Laplacian | still energy-scaled | **No** |
| Brenner gradient | `Σ (Y[i+2]-Y[i])²` | yes | trivial to compute | very noise-sensitive | **No** |
| Normalised variance (Groen) | `Var(Y) / mean(Y)²` | yes | **illumination gain** — this is the contrast-invariance fix | **explodes as mean → 0** | **No** — worse on dark frames |
| FFT high-frequency energy | `Σ|F|² outside a radius / Σ|F|²` | yes (`np.fft.fft2`) | absolute brightness (if ratio-normalised) | ringing from the black/subject boundary itself | **No** |
| Edge-width (Marziliano / `blurdetect`) | mean edge ramp width | **no** (needs Canny) | frame-level darkness (edge-localised) | undefined when no edges pass threshold | **No** |
| Non-black largest-blob area fraction | `label(open(Y>25))`, max area / N | **SciPy** (`scipy.ndimage`) | hot pixels (killed by opening) | halo/glow merges blobs | **Partially** — same axis as area, slightly cleaner |
| Non-black component count | `label(...)` → count ≥ min area | **SciPy** | hot pixels | an isolated Statue is also 1 blob | **No** |
| Blob shape (circularity, solidity, aspect) | see §5.7 | SciPy + hand-rolled | — | it is a bespoke moon detector; brittle | Nominally yes — **do not ship it** |

Nothing in that table has a "yes" in the last column. That is the finding.

---

## 4. Per-metric detail — the level statistics

### 4.1 Mean / median luminance, and why they are insufficient alone

Mean luma is what `signalstats` calls `YAVG` (`vf_signalstats.c:767`, `1.0 * toty / s->fs`). QCTools' own guidance is the clearest published statement of the naive rule and its limits: *"A picture with well-balanced light levels will have an average, or mid-range Y Channel value of around 128 (Y AVG). Graph readings outside of that range will indicate a picture that is either too bright or too dark."* (<https://github.com/bavc/qctools/blob/main/docs/filter_descriptions.md>)

Read that sentence against our constraint and the failure is total: our best photographs have `YAVG` far below 128 **by artistic intent**. Mean luma is a *legality* statistic for broadcast, where the expected content genuinely is mid-grey on average. It is not a quality statistic for photography.

The deeper reason mean is insufficient is that it is a first moment: it is invariant to *where* the light is. A uniform Y=12 fog frame, a 95%-black frame with a 5% bright subject at Y=230, and a 50/50 split at Y=24 can all share a mean. Median is worse for us, not better: the median is by construction insensitive to anything occupying less than 50% of the frame, so for **any** night photograph the median reports the sky and nothing else. Both of our test cases have a median of ~0 to ~5.

**Practical consequence: neither mean nor median should appear with a lower bound anywhere in a reject rule.** They are only safe as *upper*-bounded checks (e.g. `mean > 250` → blown-white frame).

### 4.2 Fraction of pixels above a luminance floor

This is FFmpeg `blackdetect` exactly, and §2.1 gives its precise form. Restating in our terms:

```python
BLACK_TH = 25                    # full-range 8-bit, FFmpeg default 0.10 x 255, truncated
nonblack_frac = float((Y > BLACK_TH).mean())      # = 1 - picture_black_ratio
```

**Robust to:** scene content, subject position, subject shape, rotation, resolution (it is a ratio). It is the only metric in this report with 20+ years of independent production tuning behind both of its constants.

**Failure mode:** it is a hard threshold on a soft quantity. A night sky in a tone-mapped preview commonly lands at Y = 8–30, straddling 25. Push the sky from Y=24 to Y=26 with a small exposure or gamma change and `nonblack_frac` jumps from ~0.05 to ~1.0. **The metric is stable for genuinely black backgrounds and unstable for dim-but-not-black ones**, which is precisely the regime our night photographs live in. Mitigate by reporting the whole curve `nonblack_frac(T)` for `T ∈ {8, 16, 25, 32, 48}` rather than one number, and requiring the reject condition to hold across the sweep.

**On our two cases:** this is the best single axis and still not sufficient — see §1.4 for the area arithmetic.

### 4.3 Histogram percentile spread and upper percentiles

Broadcast QC's use is real but is *inner*-percentile (10/90) and deliberately discards the bright tail — §2.3, with the QCTools rationale quoted. I found **no** production tool using P99+ luminance as a blankness or content discriminator. So the following is a construction, not inherited practice.

The useful percentile facts for our problem:

```python
p = np.percentile(Y, [50, 90, 99, 99.5, 99.9, 99.99])
```

- **The P99.9–P50 gap is a "there is a highlight" detector, not a "there is a subject" detector.** Both of our cases have a large gap. A single stuck hot pixel in an otherwise dead-black frame also produces a large `max - P50` gap, though not a large `P99.5 - P50` gap on a multi-megapixel frame (99.5% of 24 MP is 120,000 pixels, so P99.5 is immune to anything smaller than that).
- **The percentile at which luminance takes off *is* the area, restated.** If the subject occupies fraction `a` of the frame and is much brighter than the background, then `P_q` is background for `q < 100(1-a)` and subject for `q > 100(1-a)`. So the "takeoff percentile" is `100(1-a)`. Statue at a=0.05 → takeoff at P95. Crescent moon at a=2e-4 → takeoff at P99.98. **This is genuinely informative — it is just not independent of §4.2.** Choose one parameterisation; do not count it as two pieces of evidence.
- **The one place percentiles beat a threshold count:** robustness against hot pixels and sensor noise *without* needing morphology. `P99.9` on a 24 MP frame is the 24,000th-brightest pixel; no amount of shot noise or a few dozen hot pixels can move it. If you want a "is there any real light in this frame" test that cannot be fooled by a single defective sensel, `P99.9` is the NumPy one-liner that does it, and it is a strictly better choice than `Y.max()`.

**Recommendation:** use `P99.9` as the *presence* test (Tier A) and `nonblack_frac` as the *extent* measure (Tier B input). Do not use `max`.

### 4.4 Standard deviation and RMS contrast

`Y.std()` is a second moment about the mean and inherits the same blindness as the mean: it cannot tell *where* the variance is. For a two-level frame (background `b` on fraction `1-a`, subject `s` on fraction `a`) the standard deviation is exactly

```
std = (s - b) * sqrt(a * (1 - a))
```

so for small `a` it goes as `(s-b)·√a`. Statue: `(230-5)·√0.05 ≈ 50`. Crescent moon: `(240-2)·√2e-4 ≈ 3.4`. That is a real 15× gap — but it is `√area` again. **Std dev is the third reparameterisation of area in this report.** It is not new evidence, and because it takes a square root it is a *less* discriminative version of the same signal than `nonblack_frac`.

RMS contrast in the commonly cited form is `σ / Ī` (normalised RMS contrast). Two cautions:

1. **Attribution.** The `σ/Ī` form is routinely credited to Peli, "Contrast in complex images", JOSA A 7(10):2032–2040, 1990 (<https://doi.org/10.1364/JOSAA.7.002032>). Peli's actual contribution is a *band-limited local* contrast measure for complex images, arguing that a single global number is inadequate; he does not introduce `σ/Ī` as the definition. Cite Peli for "global contrast is the wrong model for complex images" — which supports our argument — not for the formula.
2. **It is numerically unusable here.** `Ī → 0` on a near-black frame, so `σ/Ī` diverges. Statue: `50/16 ≈ 3.1`. Crescent moon: `3.4/0.05 ≈ 68`. The moon scores **higher** contrast than the Statue. If you use normalised RMS contrast with an upper bound to reject "flat" frames you will reject the wrong ones, and with a lower bound you will reject the Statue. **Do not use normalised RMS contrast on near-black frames.**

Michelson contrast `(Y_max − Y_min)/(Y_max + Y_min)` (<https://en.wikipedia.org/wiki/Contrast_(vision)#Michelson_contrast>, original: Michelson, *Studies in Optics*, 1927) saturates at ~1.0 for **any** frame containing both a black region and a highlight. Both cases score ≈ 1.0. Useless here.

### 4.5 Shannon entropy of the luminance histogram

Formula, exactly as FFmpeg computes it (§2.5):

```python
h = np.bincount(Y.ravel(), minlength=256).astype(np.float64)
p = h[h > 0] / Y.size
H = float(-(p * np.log2(p)).sum())      # bits, 0 .. 8 for 8-bit
H_norm = H / 8.0                        # FFmpeg's normalized_entropy
```

Range: `H = 0` for a single-valued frame; `H = 8` for a perfectly uniform 256-bin histogram. FFmpeg divides by `log2(1<<depth)` (`vf_entropy.c:155`) so the normalised value is bit-depth-independent.

**What entropy is robust to:** geometry entirely. Rotate, flip, shuffle the pixels — entropy is unchanged. It is a pure histogram statistic and carries no spatial information whatsoever. That makes it a good *blank* detector and a poor *content* detector.

**Published value ranges separating flat from textured: none that I could verify.** QCTools states only the endpoints (0 = one shade, 1 = all shades). FFmpeg's filter has no threshold option. Every "entropy < 0.5 means blank" number in circulation is blog-tier. If you use entropy you own the constant.

**Empirical expectation for our cases** (stated as reasoning, not as a measured result — this needs validating on your actual collection):
- Uniform black lens-cap frame with read noise: histogram concentrated in ~4–8 bins near 0 → `H ≈ 1–2.5 bits`, `H_norm ≈ 0.13–0.31`.
- Crescent-moon frame: ~99.98% in the bottom few bins, a thin tail across the rest. Entropy is dominated by the black mass: `-p log2 p` for `p = 0.9998` contributes ~0.0003 bits, and the 2e-4 of tail mass spread over ~200 bins contributes at most `2e-4 × log2(...)` ≈ a few thousandths of a bit. **`H ≈ 0.5–2 bits`** — nearly indistinguishable from the lens cap.
- Statue frame at a = 0.05: the 5% tail can contribute up to `0.05 × log2(1/0.05·200) ≈ 0.6` bits plus the black-mass term. **`H ≈ 1–3 bits`.**

So entropy compresses a 250× area difference into maybe a 2× entropy difference, and puts the moon frame in the same band as a lens cap. **Entropy cannot separate our two cases and should not be the primary axis.** Its legitimate use is as a *corroborating* signal in Tier A: `H_norm < 0.10` is strong evidence of a genuinely degenerate frame (single-shade or near-single-shade), and neither of our cases reaches it.

### 4.6 Why `entropy=diff` mode is the more interesting variant

`mode=diff` (`vf_entropy.c:143-147`) takes the entropy of `|hist[y] − hist[y−1]|`, i.e. of the histogram's own roughness. QCTools uses the frame-to-frame delta of this for detecting damaged tape and digital manipulation. For single stills it has no obvious use, but it is worth knowing it exists because it is the one production entropy variant that is sensitive to histogram *shape* rather than histogram *spread* — a spiky, comb-like histogram (the signature of an over-stretched or heavily posterised preview) scores differently from a smooth one of the same spread. That could be a genuinely useful "this preview has been mangled" signal, separate from the blank question.

---

## 5. Per-metric detail — the spatial and focus metrics

### 5.1 Variance of the Laplacian: the actual formula, which is not what everyone implements

**Original source.** J. L. Pech-Pacheco, G. Cristóbal, J. Chamorro-Martínez, J. Fernández-Valdivia, "Diatom autofocusing in brightfield microscopy: a comparative study", *Proc. 15th ICPR*, Barcelona, 2000, vol. 3, pp. 314–317. DOI: <https://doi.org/10.1109/ICPR.2000.903548>. No open-access version of record exists; the authors' camera-ready preprint is archived at <https://web.archive.org/web/20040116202018/http://www.iv.optica.csic.es/papers/icpr2k.pdf>.

**Their §3.3, eqs. 10–13:**

```
mask L = (1/6) * [[ 0, -1,  0],
                  [-1,  4, -1],
                  [ 0, -1,  0]]            # positive centre, scaled by 1/6

LAP(I)     = Σ_m Σ_n |L(m,n)|                          (11)
LAP_VAR(I) = Σ_m Σ_n [ |L(m,n)| - L_bar ]^2            (12)
L_bar      = (1/(N*M)) * Σ_m Σ_n |L(m,n)|              (13)
```

**Three ways the popular implementation differs from the paper.** `cv2.Laplacian(gray, cv2.CV_64F).var()`:
1. uses the **signed** Laplacian, whereas eq. 12 takes variance of the **absolute** Laplacian, and `Var(|x|) ≠ Var(x)`;
2. divides by `N·M` (it is a variance), whereas eq. 12 is an **unnormalised sum of squared deviations**, so the paper's value scales with image size;
3. uses a differently signed/scaled kernel — the paper's `1/6` factor makes `LAP_VAR` `1/36` of an unnormalised-kernel version.

The paper also defines grey-level local variance `VAR`, Tenengrad `TEN`, and their own new `SOB_VAR`; and **it does not recommend variance-of-Laplacian as the winner.** The "variance of Laplacian" name attached to this paper is a downstream convention. The popularisation is Adrian Rosebrock, "Blur detection with OpenCV" (<https://pyimagesearch.com/2015/09/07/blur-detection-with-opencv/>), which is where the widely copied `threshold ≈ 100` comes from — and that post explicitly flags the threshold as scene-dependent and requiring per-dataset tuning. **There is no published, dataset-independent Laplacian-variance threshold.**

**NumPy-only implementation (no OpenCV needed):**

```python
def lap_var(Y):  # Y float64 2-D
    lap = (-4.0 * Y[1:-1, 1:-1]
           + Y[:-2, 1:-1] + Y[2:, 1:-1] + Y[1:-1, :-2] + Y[1:-1, 2:])
    return float(lap.var())
# or: scipy.ndimage.laplace(Y).var()
```

### 5.2 The documented failure mode: Laplacian variance measures contrast, not focus

This is the most important negative result in the report for our purposes.

The Laplacian is a linear operator. Scale the image by `k` (a pure exposure/contrast change) and the Laplacian scales by `k`, so its variance scales by `k²`. **Laplacian variance is therefore quadratically proportional to image contrast and only incidentally related to focus.** A perfectly focused frame that is 95% black at Y≈3 with a subject at Y≈230 has almost all of its area contributing exactly zero to the Laplacian; the variance is dominated by the fraction of pixels near the subject's edges, and the resulting number is small *because the frame is dark and mostly empty*, not because it is out of focus.

Supporting primary sources:

- **Groen, Young, Ligthart, "A comparison of different focus functions for use in autofocus algorithms", *Cytometry* 6(2):81–91, 1985** (<https://doi.org/10.1002/cyto.990060202>). This is the paper that identifies the problem and gives the standard fix: **normalised variance**, dividing the grey-level variance by the *square* of the mean:

  ```
  F_normvar = (1 / (H*W)) * Σ (Y(i,j) - Ȳ)^2 / Ȳ^2
  ```

  The `Ȳ²` (not `Ȳ`) denominator is what makes the measure invariant to a multiplicative illumination change, because both numerator and denominator then scale as `k²`. **But this fix is useless to us**: `Ȳ → 0` on a near-black frame, so normalised variance *diverges* exactly where we need it. It is a fix for microscopy, where the field is uniformly illuminated.

- **Pertuz, Puig, Garcia, "Analysis of focus measure operators for shape-from-focus", *Pattern Recognition* 46(5):1415–1432, 2013** (<https://doi.org/10.1016/j.patcog.2012.11.011>). The standard broad comparison (~36 operators across noise, contrast and saturation conditions). Its central conclusion is that **no operator dominates across conditions** — the ranking changes with noise level, contrast and saturation, so any single operator plus fixed threshold is a bet on one operating regime. Use this as the citation for "the choice is condition-dependent and low contrast is one of the conditions that changes the answer". *(My own mechanistic gloss, not a quotation from the paper: gradient-based operators should degrade more gracefully under noise than Laplacian-based ones, since the Laplacian is a second derivative and amplifies noise twice. Verify against the paper's tables before citing that specific claim.)*

- **Marziliano et al., ICIP 2002** (<https://infoscience.epfl.ch/record/111802/files/14%20A%20no-reference%20perceptual%20blur%20metric.pdf>) is the practical counter-design and the one FFmpeg shipped (§2.6): measure the *width* of edge ramps rather than the *energy* of derivatives. Edge width is dimensionless in intensity and therefore intrinsically contrast-invariant — which is why an edge-width metric is the right shape of tool for dark frames and a variance metric is the wrong one.

**Direct consequence for our system: never apply a global Laplacian-variance blur threshold to a collection containing night photography.** Every good night photograph will fail it. If you want a focus signal on these frames it must be computed *inside* a content mask (§5.6), and even then it will not separate our two cases because both a statue and a lunar limb are sharp.

### 5.3 Tenengrad and Brenner

**Tenengrad** derives from Tenenbaum's 1970 Stanford PhD thesis ("Accommodation in computer vision") and is given its usual thresholded form by **Krotkov, "Focusing", *IJCV* 1(3):223–237, 1987** (<https://doi.org/10.1007/BF00127822>). The standard modern statement is

```
TEN = Σ_{(i,j) : S(i,j) > T} S(i,j)     where S(i,j) = Gx(i,j)^2 + Gy(i,j)^2
```

with `Gx, Gy` Sobel responses and `T` a discard threshold. Note that Tenenbaum's original formulation sums the gradient magnitude, not its square; the squared-and-thresholded form is the later convention. NumPy-expressible in a few slice operations; no OpenCV required.

**Brenner gradient** — Brenner et al., "An automated microscope for cytologic research: a preliminary evaluation", *J. Histochem. Cytochem.* 24(1):100–111, 1976 (<https://doi.org/10.1177/24.1.1254907>):

```
BREN = Σ_{i,j} ( Y(i, j+2) - Y(i, j) )^2      for pixel pairs at distance 2
```

Trivially NumPy-expressible (`((Y[:, 2:] - Y[:, :-2])**2).sum()`). Cheapest of all the focus measures and the most noise-sensitive, because it is an unfiltered finite difference.

**Both are energy measures and both inherit §5.2's failure exactly.** They are quadratic in contrast. Neither separates our two cases. Tenengrad's advantage over Laplacian variance is noise robustness (a first derivative rather than a second), and its thresholded form gives you a free way to ignore the black region — which makes it the better *building block* for a masked metric.

### 5.4 FFT high-frequency energy

Formula: transform, then take the fraction of spectral power outside a cutoff radius.

```python
F = np.fft.fftshift(np.fft.fft2(Y - Y.mean()))
P = np.abs(F) ** 2
r = np.hypot(*np.indices(Y.shape) - np.array(Y.shape)[:, None, None] // 2)
hf_ratio = P[r > r0].sum() / P.sum()
```

Because it is a **ratio**, it is normalised against overall image energy and so is not defeated by darkness the way raw Laplacian variance is — that is its one genuine advantage. NumPy-only.

Two problems for us. First, **I found no primary source publishing a usable numeric cutoff or threshold**; the technique is folklore-with-a-formula, its most-cited popular form being the same PyImageSearch lineage as §5.1 (<https://pyimagesearch.com/2020/06/15/opencv-fast-fourier-transform-fft-for-blur-detection-in-images-and-video-streams/>), where the threshold is again presented as needing per-dataset tuning. Second, and specific to our case: **a hard black/subject boundary is itself a broadband edge.** A 95%-black frame with a sharply bounded bright subject produces strong high-frequency content from the silhouette alone, regardless of whether the subject's interior is in focus. So `hf_ratio` on our frames is measuring the silhouette, not the focus. It does not separate our two cases (a lunar limb is at least as sharp an edge as a statue's).

### 5.5 Where the classical still-image discriminators actually stand

Rolling §4 and §5 together: the classical toolbox has exactly **three** independent axes on a single still frame.

1. **Level** — where the histogram sits (mean, median, percentiles, non-black fraction, entropy). All of these on a near-black frame reduce to *how much area is above black and how bright it is*.
2. **Local structure energy** — derivative magnitudes (Laplacian, Tenengrad, Brenner, FFT HF). All of these are contrast-scaled and therefore confounded with axis 1 on dark frames.
3. **Spatial organisation** — connected components, blob geometry, morphology. This is the only axis carrying information that axes 1 and 2 discard, and it is the only place a Statue/moon distinction could live.

Our two cases are engineered to be identical on axes 1 and 2 up to a factor of area. So any classical separation must come from axis 3 — see §5.6 and §5.7.

### 5.6 Connected components, morphological opening, and masked metrics

**The opening step is non-negotiable and is the standard fix for hot pixels and sensor noise.** Threshold first, then open with a small structuring element to delete isolated single pixels and thin noise before measuring anything:

```python
from scipy import ndimage as ndi

mask  = Y > 25                                     # FFmpeg-equivalent non-black mask
mask  = ndi.binary_opening(mask, np.ones((3, 3)))  # kills 1-2 px hot pixels / noise specks
lab, n = ndi.label(mask)
if n:
    areas   = np.bincount(lab.ravel())[1:]
    a_max   = areas.max() / Y.size                 # largest-blob area fraction
    n_real  = int((areas >= 64).sum())             # blobs of non-trivial size
```

`scipy.ndimage` is available in this repo (§1.7), so this needs no new dependency and no OpenCV.

**What opening buys you, precisely.** A 3×3 opening removes any connected foreground structure that cannot contain a 3×3 square — every single hot pixel, every 1-px noise speck, every 2-px-wide sensor artefact. This is the difference between a metric you can trust on a 24 MP frame with a few hundred defective sensels and one you cannot. It is also why `largest-blob area` is a strictly better version of `nonblack_fraction`: it is `nonblack_fraction` with the noise contribution structurally removed and the *coherence* requirement added.

**What it does not buy you.** On our two cases:

| | Statue at night | Crescent moon only |
|---|---|---|
| blobs after opening | 1 (or a few, with glow/reflections) | 1 |
| largest-blob area fraction | ~0.02–0.05 | ~2e-4 … 6e-3 |
| blob is coherent, non-noise | yes | yes |

Component **count** does not separate them: the constraint says the Statue is "isolated against complete darkness", i.e. one blob. Largest-blob **area** does separate the typical instances, but it is axis 1 again with better hygiene, and §1.4's overlap still applies.

**The genuinely valuable use of the mask is as a domain for the other metrics.** Compute Laplacian variance, Tenengrad, or entropy *inside* the dilated mask only:

```python
roi   = ndi.binary_dilation(mask, np.ones((9, 9)))
lv_roi = float(lap[roi[1:-1, 1:-1]].var())   # focus of the subject, not of the sky
```

This is the correct way to ask "is the subject sharp?" on a mostly-black frame, and it is what FFmpeg's `blurdetect` does implicitly by only pooling over detected edges (§2.6). It fixes the §5.2 failure mode for the *focus* question. It does not help the Statue/moon question, because both subjects are sharp.

### 5.7 Blob shape — why the tempting route is a trap

The shape metrics that would nominally separate a statue from a moon:

- **Circularity** `4πA/P²` → ~1.0 for a full-moon disc, ~0.2–0.4 for a statue silhouette.
- **Bounding-box aspect ratio** → ~1.0 for a moon, ~2–4 for the Statue with its pedestal.
- **Solidity** `A / A_convexhull` → high for a full moon; **low for a crescent**, which is the case we are actually asked to reject.
- **Extent** `A / A_bbox` → ~0.785 for a perfect disc.

I am flagging these as available and then recommending against them, for four reasons:

1. **You would be building a moon detector.** A rule tuned on discs rejects any circular bright subject: a streetlamp, a firework, a lit porthole, a sun through fog. The false-reject class is not small and is not enumerable.
2. **Solidity points the wrong way for the actual case.** A crescent is strongly non-convex, so a "reject high-solidity discs" rule misses a crescent while catching full moons.
3. **The shape depends on the threshold and the glow.** Atmospheric glow around a bright moon makes the thresholded blob a fuzzy disc with a threshold-dependent radius; changing `BLACK_TH` from 25 to 32 materially changes circularity.
4. **A learned subject signal does this better and generalises.** The distinction "moon in an empty sky" vs "monument at night" is semantic. §1.5's Tier B is the honest place for it.

### 5.8 What the classical layer *can* reject with near-zero false positives

Stated positively, because this is the deliverable value of the classical layer. All of these are safe against our constraint — none of them fires on either the Statue frame or the crescent-moon frame:

- **Dead-black / lens-cap / unexposed**: `P99.9 <= 25` **and** `Y.max() <= 48`. Nothing in the frame is bright anywhere, not even the 24,000th-brightest pixel. The Statue and the moon both have `P99.99 > 200` and sail through.
- **Blown white / flash-fired-at-wall**: `P00.1 >= 230` (the 0.1st percentile is already near white).
- **Uniform single-tone (any level)**: `H_norm < 0.06` **and** `Y.std() < 2.0`. Catches solid-colour frames, fully clipped frames, and rendering failures.
- **All-noise / no coherent content**: `mask = Y > 25` has `nonblack_frac > 0.001` but **zero** blobs survive a 3×3 opening — i.e. every bright pixel is isolated. This is the sensor-noise-only frame.
- **Preview decode failure**: `Y.shape` degenerate, or `Y.std() == 0`.

Each of these is a statement about the *absence of any recoverable content*, which is the only question classical signal processing on a single frame is entitled to answer.

---

## 6. RAW vs tone-mapped preview: this changes the numbers, and there is a live hazard in this repo

Every threshold in §2 is defined on a **display-referred, gamma-encoded** luma signal. That is what FFmpeg sees (BT.709-coded video) and it is what a JPEG preview is. It is *not* what a RAW sensor array is. Three consequences.

**6.1 Absolute thresholds are only meaningful on the tone-mapped side.** RAW values are scene-linear and camera-scaled: black level offset varies by model (typically 0–2048 in a 14-bit raw), and there is no fixed relationship between a raw code value and a display luminance until demosaic + white balance + tone curve have run. `Y ≤ 25/255` has no RAW equivalent. **Compute all of these metrics on the tone-mapped preview, never on the raw array.** For our system that is the right side anyway, since most images have previews and not raw.

**6.2 The tone curve compresses the shadows, which helps us.** rawpy's default gamma is `(2.222, 4.5)` — the BT.709 OETF (<https://github.com/letmaik/rawpy/blob/master/rawpy/_rawpy.pyx>, `Params.__init__` docstring: *"pair (power, slope), default is (2.222, 4.5) for rec. BT.709"*). A power-2.2-ish curve lifts deep shadows substantially, so a scene-linear sky at 0.1% of full scale lands nowhere near code value 0 in the preview. This is *why* night skies in previews sit at Y = 8–30 rather than at Y = 0–2, and it is the direct cause of §4.2's instability around `BLACK_TH = 25`. It also means the preview is the more forgiving domain: shadow detail that would be numerically invisible in linear light is spread across many code values.

**6.3 The hazard: LibRaw's auto-brightness is ON by default in this repo's RAW path.** `lightroom_tagger/core/analyzer/image_prep.py:89`:

```python
rgb = raw.postprocess(use_camera_wb=True, half_size=True)
```

From rawpy's `Params` signature (<https://github.com/letmaik/rawpy/blob/master/rawpy/_rawpy.pyx>, line 1251):

```python
no_auto_bright: bool = False,
auto_bright_thr: Optional[float] = None,   # "Default is 0.01 (1%)"
```

`no_auto_bright=False` means **automatic brightness increase is applied**, stretching the image until approximately 1% of pixels clip. Also default: `output_bps=8`, `output_color=sRGB`, `highlight_mode=Clip`, `bright=1.0`.

For a deliberately dark 95%-black night frame this is an aggressive, scene-dependent exposure change applied silently. Two frames of the same scene — one processed from RAW through this path, one a camera JPEG — will produce materially different `nonblack_frac`, `P99.9`, `Y.std()` and `H`. **Concretely: a correctly-exposed dark night frame gets brightened, moving background sky pixels up across the `BLACK_TH = 25` line and inflating `nonblack_frac`, which makes a night photograph look *less* black than it is; and a genuinely underexposed failure gets brightened too, which makes a failed frame look *more* like content.** Auto-bright works directly against the discrimination we want.

**Recommendation, and it is the highest-leverage single change in this report:** if these metrics are to be computed on RAW-derived previews, pass `no_auto_bright=True` so the thresholds mean something stable, or else record which path produced each preview and never compare thresholds across paths. Note that changing this flag will alter the appearance of every RAW-derived preview, so it is a product decision, not just a metrics one — the alternative is to compute metrics from a second, metrics-only postprocess call with `no_auto_bright=True`.

**6.4 Which luma to use.** Pillow's `Image.convert("L")` uses the ITU-R 601-2 luma transform `L = 0.299R + 0.587G + 0.114B` (<https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.convert>). BT.709 luma is `Y = 0.2126R + 0.7152G + 0.0722B` (ITU-R BT.709-6, <https://www.itu.int/rec/R-REC-BT.709>). The difference matters for coloured subjects: a deep-red subject scores ~40% higher under 601 than under 709. Since our previews are sRGB (709 primaries), **BT.709 coefficients are the technically correct choice**, but the practical advice is simply to **pick one and record it with the thresholds** — the thresholds are only valid for the luma definition they were tuned against. `Image.convert("L")` is fine and is the cheapest option; just do not mix.

---

## 7. Proposed composite rule, with the reasoning behind each number

Written for Pillow + NumPy + SciPy, which is what this repo already has (§1.7). No OpenCV.

### 7.1 Feature extraction

```python
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

BLACK_TH = 25          # FFmpeg blackdetect default 0.10 x 255, truncated (full-range 8-bit)
MAX_SIDE = 1024        # downscale for speed; area fractions are scale-invariant

def features(path):
    im = Image.open(path)
    im.draft("L", (MAX_SIDE, MAX_SIDE))        # JPEG-native fast downscale, luma only
    im = im.convert("L")
    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.BOX)
    Y = np.asarray(im, dtype=np.uint8)
    N = Y.size

    # --- level ---
    pct = np.percentile(Y, [0.1, 50, 90, 99, 99.9, 99.99])
    f = {
        "p001": pct[0], "p50": pct[1], "p90": pct[2],
        "p99": pct[3], "p999": pct[4], "p9999": pct[5],
        "ymax": int(Y.max()), "mean": float(Y.mean()), "std": float(Y.std()),
    }

    # --- non-black fraction, swept (see 4.2: report the curve, not one number) ---
    for T in (8, 16, 25, 32, 48):
        f[f"nbf{T}"] = float((Y > T).mean())

    # --- entropy, exactly as FFmpeg computes it ---
    h = np.bincount(Y.ravel(), minlength=256).astype(np.float64)
    p = h[h > 0] / N
    f["H"] = float(-(p * np.log2(p)).sum())
    f["H_norm"] = f["H"] / 8.0

    # --- spatial: opening kills hot pixels before we measure anything ---
    mask = ndi.binary_opening(Y > BLACK_TH, np.ones((3, 3)))
    lab, n = ndi.label(mask)
    if n:
        areas = np.bincount(lab.ravel())[1:]
        f["blob_max_frac"] = float(areas.max()) / N
        f["blob_count"] = int((areas >= 64).sum())
    else:
        f["blob_max_frac"], f["blob_count"] = 0.0, 0

    # --- masked focus: sharpness of the SUBJECT, not of the sky (5.6) ---
    Yf = Y.astype(np.float64)
    lap = (-4.0 * Yf[1:-1, 1:-1] + Yf[:-2, 1:-1] + Yf[2:, 1:-1]
           + Yf[1:-1, :-2] + Yf[1:-1, 2:])
    roi = ndi.binary_dilation(mask, np.ones((9, 9)))[1:-1, 1:-1]
    f["lap_var_global"] = float(lap.var())
    f["lap_var_roi"] = float(lap[roi].var()) if roi.sum() > 256 else None
    return f
```

### 7.2 Tier A — auto-reject. High precision. Must never fire on either test case.

| Rule | Condition | Why this number |
|---|---|---|
| **A1 dead black** | `p999 <= 25` **and** `ymax <= 48` | `25` is FFmpeg's own black level for full-range 8-bit (§2.1) — the most defensible constant available. `P99.9` not `max` so a handful of hot pixels cannot mask a genuinely black frame (§4.3). `ymax <= 48` is a belt-and-braces second gate at roughly 2× the black level, so the rule needs the frame to be dark *everywhere*, including its single brightest pixel. **Statue: `p9999 > 200` → does not fire. Moon: `p9999 > 200` → does not fire.** Correct. |
| **A2 blown white** | `p001 >= 230` | `230` is just under BT.709 nominal white (235) in narrow range; if even the 0.1st percentile is there, the frame is clipped everywhere. Symmetric counterpart to A1. |
| **A3 uniform single tone** | `H_norm < 0.06` **and** `std < 2.0` | `H_norm` is FFmpeg's `normalized_entropy` (§2.5). `0.06` of 8 bits = 0.48 bits ≈ a two-to-three-bin histogram: a solid colour plus quantisation. The `std < 2.0` conjunct is there because entropy alone is scale-free and I want a second, independent statistic to agree. §4.5 estimates both test cases at `H ≈ 0.5–3 bits` (`H_norm ≈ 0.06–0.38`), so the moon frame is uncomfortably close to this line — **this is the one Tier A rule that needs measuring on your real collection before it ships.** If real near-black frames come in under 0.06, lower the constant until they do not. |
| **A4 noise only** | `nbf25 > 0.001` **and** `blob_count == 0` | The frame has bright pixels but *no* bright pixel survives a 3×3 opening, i.e. every one is isolated (§5.6). This is the signature of read noise with no image. Both test cases produce a large coherent blob → do not fire. |
| **A5 decode failure** | `std == 0.0` or image smaller than 64 px on a side | Structural, not statistical. |

Tier A is a conjunction-heavy design on purpose: every rule requires two independent statistics to agree, because the cost of a false reject in this collection is high and the cost of a false accept is a frame that survives to Tier B.

### 7.3 Tier B — flag for subject-level review. Never auto-reject.

| Signal | Condition | Reasoning |
|---|---|---|
| **B1 tiny isolated subject** | `blob_max_frac < 0.005` **and** `nbf25 < 0.01` **and** `blob_count <= 2` | `0.005` (0.5% of frame) is the midpoint of the overlap zone computed in §1.4: a 200 mm crescent moon sits at ~7e-4 and a 600 mm crescent at ~6e-3, while the Statue frame sits at ~0.02–0.05. It separates the *typical* instances by ~10× and **is expected to misfire on legitimately small-subject night photography**, which is exactly why this is a flag and not a reject. |
| **B2 near-black overall** | `p50 <= 16` **and** `nbf25 < 0.10` | Identifies "this is a near-black frame, route it to the subject model" — a *triage* condition, carrying no quality judgement. `16` is BT.709 narrow-range black. This should fire on the Statue frame; that is correct and desirable. |
| **B3 subject possibly soft** | `lap_var_roi is not None` **and** `lap_var_roi < <calibrate>` | Deliberately left without a number. §5.1 establishes that no dataset-independent Laplacian-variance threshold exists; §5.2 establishes that even the ROI-masked version is contrast-scaled. Calibrate on your own collection or prefer an edge-width metric (§2.6). **Do not ship a global `lap_var_global` threshold at all** — it rejects all good night photography. |
| **B4 threshold instability** | `nbf16` and `nbf32` differ by more than 5× | The `BLACK_TH` sweep from §4.2. A frame whose black fraction is highly sensitive to the threshold has a dim-but-not-black background, so any single-threshold conclusion about it is unreliable. Flag rather than decide. |

### 7.4 The rule that is deliberately absent

There is **no** classical rule proposed for "reject the crescent-moon frame". §1.3 through §1.5 argue this cannot be done with a scalar, and §5.7 argues the shape-based route is a brittle bespoke detector with an unbounded false-reject class. The moon frame is routed by **B1 + B2** to the subject-level signal, which is where a "night sky, moon, no subject of interest" judgement belongs. Attempting it in the classical layer will cost you Statue-of-Liberty frames.

### 7.5 Calibration plan (small, and it removes most of the guesswork)

The constants above that are inherited (25, 32, 98%, 16, 235) are defensible from primary sources. The ones I invented (48, 230, 0.06, 2.0, 0.001, 0.005, 5×) are reasoned but unmeasured. Recommended validation, roughly a day's work:

1. Dump the §7.1 feature vector for the whole collection to a table (metrics are cheap: one `draft`-accelerated JPEG decode per image).
2. Hand-label ~50 frames: 15 known-good night photographs including the Statue case, 15 genuine failures (lens cap, black-out, blown, noise-only), 20 near-black borderline cases including a moon-only frame if one exists.
3. Check Tier A fires on **zero** of the known-good set. If it fires on any, loosen — Tier A must be precision-1.0 by construction.
4. Read the `blob_max_frac` distribution for the good-night vs moon-only groups and set B1's `0.005` at the observed gap rather than at my estimate.
5. Only then consider whether B3 is worth having at all.

---

## 8. Source list

**FFmpeg — filter source (primary):**
- `vf_blackdetect.c` — <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_blackdetect.c>
- `vf_blackdetect.h` (the per-pixel `<=` comparison) — <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_blackdetect.h>
- `vf_blackframe.c` — <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_blackframe.c>
- `vf_signalstats.c` — <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_signalstats.c>
- `vf_freezedetect.c` — <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_freezedetect.c>
- `vf_entropy.c` — <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_entropy.c>
- `vf_blurdetect.c` — <https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_blurdetect.c>

**FFmpeg — official documentation:**
- <https://ffmpeg.org/ffmpeg-filters.html#blackdetect_002c-blackdetect_005fvulkan>
- <https://ffmpeg.org/ffmpeg-filters.html#blackframe>
- <https://ffmpeg.org/ffmpeg-filters.html#signalstats>
- <https://ffmpeg.org/ffmpeg-filters.html#freezedetect>
- <https://ffmpeg.org/ffmpeg-filters.html#entropy>
- <https://ffmpeg.org/ffmpeg-filters.html#blurdetect-1>

**Archival / broadcast QC:**
- QCTools filter descriptions — <https://github.com/bavc/qctools/blob/main/docs/filter_descriptions.md>
- A/V Artifact Atlas — <https://bavc.github.io/avaa/index.html>
- EBU R 103, *Video Signal Tolerance in Digital Television Systems* — <https://tech.ebu.ch/docs/r/r103.pdf>
- EBU R 128 (referenced by QCTools for audio) — <https://tech.ebu.ch/docs/r/r128.pdf>
- ITU-R BT.709 — <https://www.itu.int/rec/R-REC-BT.709>
- FADGI 2016 guidelines (the edition that still carries 8-bit code values) — <https://www.digitizationguidelines.gov/guidelines/FADGI%20Federal%20%20Agencies%20Digital%20Guidelines%20Initiative-2016%20Final_rev1.pdf>
- Metamorfoze Preservation Imaging Guidelines 2.0, April 2025 — <https://www.metamorfoze.nl/sites/default/files/documents/Preservation%20Imaging%20Guidelines%20English%202.0,%20April%202025.pdf>

**Focus / sharpness / contrast literature:**
- Pech-Pacheco et al., ICPR 2000 — <https://doi.org/10.1109/ICPR.2000.903548>; author preprint <https://web.archive.org/web/20040116202018/http://www.iv.optica.csic.es/papers/icpr2k.pdf>
- Groen, Young, Ligthart, *Cytometry* 6(2):81–91, 1985 — <https://doi.org/10.1002/cyto.990060202>
- Krotkov, "Focusing", *IJCV* 1(3):223–237, 1987 — <https://doi.org/10.1007/BF00127822>
- Brenner et al., *J. Histochem. Cytochem.* 24(1):100–111, 1976 — <https://doi.org/10.1177/24.1.1254907>
- Pertuz, Puig, Garcia, *Pattern Recognition* 46(5):1415–1432, 2013 — <https://doi.org/10.1016/j.patcog.2012.11.011>
- Marziliano et al., ICIP 2002 — <https://infoscience.epfl.ch/record/111802/files/14%20A%20no-reference%20perceptual%20blur%20metric.pdf>
- Peli, "Contrast in complex images", *JOSA A* 7(10):2032–2040, 1990 — <https://doi.org/10.1364/JOSAA.7.002032>
- Rosebrock, "Blur detection with OpenCV" (source of the folk threshold ≈100) — <https://pyimagesearch.com/2015/09/07/blur-detection-with-opencv/>
- Rosebrock, "OpenCV FFT for blur detection" — <https://pyimagesearch.com/2020/06/15/opencv-fast-fourier-transform-fft-for-blur-detection-in-images-and-video-streams/>

**Pipeline / library facts:**
- rawpy `Params` defaults (`no_auto_bright=False`, `auto_bright_thr=0.01`, `gamma=(2.222, 4.5)`, `output_bps=8`) — <https://github.com/letmaik/rawpy/blob/master/rawpy/_rawpy.pyx>
- Pillow `convert("L")` uses ITU-R 601-2 luma — <https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.convert>
- This repo's RAW path: `/Users/ccanales/projects/lightroom-tagger/lightroom_tagger/core/analyzer/image_prep.py:89`
- This repo's dependency set: `/Users/ccanales/projects/lightroom-tagger/pyproject.toml`, `/Users/ccanales/projects/lightroom-tagger/uv.lock` (numpy, scipy, pillow, rawpy present; no opencv)

### Unverified / could not confirm

- Commercial QC tools (Interra BATON, Telestream Vidchecker, Venera Pulsar, Tektronix Aurora): **no published black-frame parameter defaults found.** Documentation is behind customer portals.
- Netflix Photon: IMF/XML packaging validation; **no pixel-domain black-frame test.** No Netflix-published black-frame threshold found.
- ISO 19264-1:2021 Level A/B/C numeric tolerances: paywalled annexes, **not verified.**
- Any published numeric entropy threshold separating flat from textured content: **none found in any primary source.**
- Any published, dataset-independent Laplacian-variance blur threshold: **none exists**; the widely copied "100" is from a tutorial that itself calls it scene-dependent.
- Any production QC tool using luminance percentiles above the 90th as a content/blankness discriminator: **none found.** §4.3's use of P99.9 is our own construction.
- The per-case numbers in §4.5 (entropy estimates) and §1.4 (area fractions) are **analytical estimates from stated geometry, not measurements** on this collection. §7.5 is the plan to replace them with measurements.
