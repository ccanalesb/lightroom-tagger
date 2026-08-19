# Learned IQA: does anything separate "technically failed" from "intentionally dark"?

*Created using Anthropic Claude. Keep this line on internal versions until a human has reviewed and verified the content.*

Scope: sub-question 02 of the photography-critique research ticket. Every factual claim is
cited to an arXiv paper, an official repo/model card, or the source code of the reference
implementation. Claims that are **measured locally** are labelled `[MEASURED]` with the script
that produced them. Claims that are inference-from-mechanism rather than citation are labelled
`[SPECULATION]`.

Constraint everything is judged against: ~95%-black night frames (Statue of Liberty isolated
against darkness) are among the **best** photographs in this collection. A near-black frame
with a crescent moon in it has a subject but no legible content and must be rejected. A model
that cannot tell those apart is useless as a gate.

---

## VERDICT

**Prototype two things, in this order.**

**1. LIQE (`liqe_mix`, 353 MB) — the only openly-weighted model whose label space actually names
our failure mode.** LIQE predicts a *joint* distribution over (quality level × scene category ×
distortion type) and then marginalises. Its distortion vocabulary is eleven items and two of them
are literally `over-exposure` and `under-exposure`; its scene vocabulary is nine items and one of
them is literally `night scene`
([arXiv:2303.14968 §3](https://ar5iv.labs.arxiv.org/html/2303.14968),
[`liqe_arch.py` L33-56](https://github.com/chaofengc/IQA-PyTorch/blob/main/pyiqa/archs/liqe_arch.py)).
That is structurally the query we want: `scene=night ∧ distortion=others ∧ quality=good` (keeper)
versus `scene=night ∧ distortion=under-exposure ∧ quality=bad` (reject). It is the *only*
candidate in the whole zoo that exposes darkness-as-intent and darkness-as-defect on separate
output heads rather than collapsing them into one scalar. It uses CLIP ViT-B/32 as its visual
encoder — the same backbone this pipeline already runs — so the dependency surface is small.
Cost, measured on this machine: **~84 min CPU / ~46 min MPS for 42k images** (15 crops each).

**2. CLIP-IQA-style antonym prompt pairs on the CLIP embeddings that are already in
`library.db` — cost is effectively zero and one pair works surprisingly well.** `[MEASURED]` Over
all 41,566 stored ViT-B/32 embeddings, the pair
`("a deliberately dark low-key night photograph", "an accidentally underexposed failed photograph")`
ranks the 26 Statue-of-Liberty night frames at **p92** of the library and out-of-focus/illegible
frames at **p63**, giving **AUC 0.862** for SoL-above-illegible. The documented CLIP-IQA
`sharpness` pair (`"Sharp photo."`/`"Blurry photo."`) gives **AUC 0.721**. Total compute: one
41,566×512 @ 512×2 matmul. This is a free baseline that must be beaten before anything heavier is
justified.

**Ruled out with hard local evidence, not argument: the LAION aesthetic predictor.** `[MEASURED]`
Running the official LAION-Aesthetics v1 ViT-B/32 head (3,047 bytes, `nn.Linear(512,1)`) on the
existing embeddings puts **all 26 Statue-of-Liberty night frames in percentile 0–3** of the
41,566-image library (scores 2.15–3.10 against a library median of 4.88). The top of the ranking
is saturated with "person in colourful clothing in front of a green waterfall". It is a
colourfulness-and-saturation detector, and this collection's best work is monochrome and minimal.
This is the single most decision-relevant number in this document.

**And the thing nobody solves.** No candidate separates the *great* minimalist night frame from
the *empty* one. `[MEASURED]` On `intentional_vs_failed`, SoL sits at p92 and the crescent-moon
cohort sits at p91 — indistinguishable. `[SPECULATION, mechanism-based]` This is structural, not a
prompt-tuning failure: at 224×224 with a globally-pooled embedding, a Statue of Liberty occupying
~5% of the frame and a crescent moon occupying ~1% are nearly the same image. Separating them
needs either a cheap pixel statistic (fraction of frame above a luminance threshold; area of the
largest connected bright component) or a VLM call — not a scalar IQA head. See "The gap no learned
IQA model closes" below.

---

## Comparison table

| Model | Predicts | Technical vs aesthetic split | Size on disk | CPU-practical at 42k | Open weights | Separates our two cases? |
|---|---|---|---|---|---|---|
| **LIQE** (`liqe_mix`) | quality∈{bad,poor,fair,good,perfect} **+ scene (incl. `night scene`) + distortion (incl. `under-exposure`)** | Technical only, but *decomposed* — the closest thing to a split that exists | **353.5 MB** | Yes: ~84 min CPU / ~46 min MPS `[MEASURED]` | Yes (pyiqa `liqe`, `liqe_mix`) | **Best shot.** Has the right label space. Untested on our data. `[SPECULATION]` |
| **CLIP-IQA zero-shot** (own reimpl. on existing embeddings) | any antonym pair you write, incl. documented `brightness` = `Bright/Dark photo.` | User-defined; you get as many orthogonal axes as you write pairs | 0 (reuses stored embeddings) | **Free** — <1 s for the whole library `[MEASURED]` | N/A (prompt-only) | Partially: AUC 0.86 SoL-vs-illegible, but SoL p92 vs moon p91 — **fails the moon case** `[MEASURED]` |
| CLIP-IQA+ (learned prompts) | single quality scalar | No | 17 KB (prompt ctx) + RN50 CLIP | Yes, ~1 CLIP pass | Yes | Untested; canonical `Good/Bad` pair is a night-detector here `[MEASURED]` |
| **LAION aesthetic v1** | one aesthetic scalar (~1–10) | Aesthetic only | **3,047 B** (ViT-B/32) / 4,071 B (ViT-L/14) | **Free** on existing embeddings | Yes | **No — catastrophically.** SoL frames at p0–p3 `[MEASURED]` |
| **LAION aesthetic v2** ("improved") | one aesthetic scalar | Aesthetic only | 3.5 MB head, **ViT-L/14 only** | Needs a new ViT-L/14 pass over 42k | Yes | `[SPECULATION]` Same failure as v1 — same AVA/SAC supervision, richer head |
| **NIMA** (paper) | 10-bin score *distribution* → mean + σ | **Yes — two separately trained models**, AVA (aesthetic) and TID2013 (technical) | — | — | **Google never released weights** | Technical head trained on synthetic degradations of 25 daylight Kodak references — no empty frames, no gross underexposure |
| NIMA (pyiqa, what you can actually run) | mean score | `nima`/`nima-vgg16-ava` = **aesthetic (AVA)**; `nima-koniq`, `nima-spaq` = technical. **No TID2013 checkpoint exists** | 58.9 MB (VGG16-AVA) / 218 MB (IncResV2) | Yes | Yes | `[SPECULATION]` AVA head ≈ LAION failure mode; koniq/spaq heads untested |
| **MUSIQ** | one scalar; multi-scale, native resolution | **Yes, via separate checkpoints**: `musiq` (KonIQ, technical), `musiq-spaq`, `musiq-paq2piq` vs `musiq-ava` (aesthetic, range 1–10) | 108.6 MB per checkpoint | Yes (ViT-ish, full-res input → slower than ViT-B/32) | Yes | `[SPECULATION]` No exposure concept in KonIQ/SPAQ label space |
| **TOPIQ** (CFANet) | one scalar | **Yes, via separate checkpoints**: `topiq_nr` (KonIQ, 181 MB) vs `cfanet_iaa_ava_res50` (aesthetic, 294 MB) | 181–508 MB | Yes — ResNet50, ~13% FLOPs of the best FR transformer | Yes | `[SPECULATION]` No |
| **MANIQA** | one scalar | Technical only; tuned for **GAN/synthetic** distortion (PIPAL, NTIRE'22 winner) | **543.3 MB** | Marginal (ViT + Swin) | Yes | No — wrong distortion domain entirely |
| **TReS** | one scalar (+relative ranking loss) | Technical only | **610.3 MB** | Marginal | Yes | `[SPECULATION]` No |
| **Q-Align / OneAlign** | scalar via discrete text levels; **IQA + IAA + VQA in one model** | **Yes — `quality` and `aesthetic` task flags on one model** | **~16.4 GB** (mPLUG-Owl2, fp16, 2 shards) | **No.** ~8B-param LMM per image × 42k | Yes | Plausibly yes (it's a VLM), but this is just "another Ollama vision call" at 42k scale |
| BRISQUE | one scalar, lower=better; SVR on NSS features | Technical only | ~few hundred KB (SVM) | Yes, very fast | Yes | **No** — degenerate on flat frames (see below) |
| NIQE | Mahalanobis distance to pristine MVG; lower=better | Technical only ("completely blind") | tiny (MVG params) | Yes, very fast | Yes | **No** — degenerate on flat frames |
| PIQE | 0–100, lower=better | Technical only | 0 (no learned params) | Yes, very fast | N/A | **No** — returns exactly **100 (worst)** on a uniform frame, by construction |

---

## Per-model detail

### NIMA (Talebi & Milanfar, Google) — the technical head is not the tool you think it is

**What it does.** Predicts the *distribution* of human ratings as a 10-bin histogram with a
squared-EMD loss on top of an ImageNet backbone (VGG16 / Inception-v2 / MobileNet), rather than
regressing the mean; mean and σ are derived from the histogram
([arXiv:1709.05424 abstract](https://arxiv.org/abs/1709.05424), TIP 2018,
[DOI 10.1109/TIP.2018.2831899](https://doi.org/10.1109/TIP.2018.2831899)).

**Two heads, same architecture, different data.** "We train two separate models for aesthetics and
technical quality assessment on AVA, TID2013, and LIVE"
([§IV](https://ar5iv.labs.arxiv.org/html/1709.05424)). The paper's own framing:
"While technical quality assessment deals with measuring low-level degradations such as noise,
blur, compression artifacts, etc., aesthetic assessment quantifies semantic level characteristics
associated with emotions and beauty" (§I).

- **Aesthetic head → AVA.** ~255,000 images from dpchallenge.com, each rated 1–10 by ~200 amateur
  photographers in contest themes; mean ratings concentrate around 5.5 (§I-C).
- **Technical head → TID2013.**

**Exactly what the technical head was trained on.** TID2013 is a **full-reference** database:
25 reference images (crops from the Kodak Lossless True Color Image Suite) × 24 distortion types
× 5 levels = 3,000 distorted images. MOS comes from forced-choice pairwise comparison *with the
reference visible to the rater*, 971 observers, 524,340 comparisons
([Ponomarenko's official TID2013 page](http://www.ponomarenko.info/tid2013.htm);
[Ponomarenko et al., Signal Processing: Image Communication 30 (2015) 57-77](https://doi.org/10.1016/j.image.2014.10.009)).
NIMA §I-D restates this: "3000 images, from 25 reference (clean) images (Kodak images), 24 types
of distortions with 5 levels".

The complete 24-type list, from the official page:

> 1 Additive Gaussian noise · 2 Additive noise in colour components · 3 Spatially correlated noise ·
> 4 Masked noise · 5 High frequency noise · 6 Impulse noise · 7 Quantization noise · 8 Gaussian
> blur · 9 Image denoising · 10 JPEG compression · 11 JPEG2000 compression · 12 JPEG transmission
> errors · 13 JPEG2000 transmission errors · 14 Non eccentricity pattern noise · 15 Local
> block-wise distortions · 16 **Mean shift (intensity shift)** · 17 **Contrast change** · 18 Change
> of colour saturation · 19 Multiplicative Gaussian noise · 20 Comfort noise · 21 Lossy compression
> of noisy images · 22 Image colour quantization with dither · 23 Chromatic aberrations ·
> 24 Sparse sampling and reconstruction

**Answer to the specific question asked: "empty frame" and "gross underexposure" are NOT among
them.** The two closest, #16 mean shift and #17 contrast change, are *global tone perturbations of
a correctly-exposed daylight Kodak reference*, graded relative to that reference. And the ratings
are not monotone in distortion level even for contrast change: NIMA Fig. 5 reports contrast levels
1→5 with MOS 5.67, 6.80, 4.83, 6.69, 3.88 — level 2 and level 4 score *above* level 1. There is no
image in TID2013 that is 95% black, and no image that is an empty frame. The hypothesis in the
brief is correct: **a model trained on this label space has never seen a correctly-exposed
photograph of nothing and has no output that could describe one.**

**The paper itself reports that the TID2013 head does not transfer.** "training on TID2013 results
in poor performance on LIVE and AVA test sets" — training on AVA and testing on LIVE gives
LCC/SRCC 0.552/0.543, while the reverse direction collapses to 0.238/0.200 (§IV, Tables III/IV).
The authors attribute this to AVA being ~250× larger than LIVE. A head fit to 3,000 synthetic
perturbations of 25 scenes should not be expected to generalise to 42,000 real photographs.

**And you cannot run it anyway.** Google published no NIMA weights. The reference implementation
in `pyiqa` ships four checkpoints and **none is TID2013**
([`nima_arch.py` L21-27](https://github.com/chaofengc/IQA-PyTorch/blob/main/pyiqa/archs/nima_arch.py)):
`vgg16-ava`, `inception_resnet_v2-ava`, `inception_resnet_v2-koniq`,
`inception_resnet_v2-spaq`. The model card describes `nima` flatly as "Aesthetic metric trained
with AVA dataset"
([ModelCard.md](https://github.com/chaofengc/IQA-PyTorch/blob/main/docs/ModelCard.md)). Sizes from
the official weight repo
([HF `chaofengc/IQA-PyTorch-Weights`](https://huggingface.co/chaofengc/IQA-PyTorch-Weights)):
`NIMA_VGG16_ava` 58.9 MB, `NIMA_InceptionV2_ava` 218.0 MB, `NIMA_koniq` 218.0 MB, `NIMA-spaq`
218.0 MB.

**Verdict on our two cases.** The AVA head is an aesthetic model with the same supervision family
as the LAION predictor, which is measured below to fail catastrophically. The koniq/spaq heads are
authentic-distortion technical models whose label space has no exposure concept. `[SPECULATION]`
Neither plausibly separates our two cases. Not worth prototyping.

---

### BRISQUE / NIQE / PIQE — the NSS classics are actively harmful on near-black frames

All three model **natural scene statistics**: the empirical regularity that the mean-subtracted,
contrast-normalised (MSCN) coefficients of a natural image follow a stable Gaussian-like
distribution, and that distortions perturb it
([Ruderman 1994, *Network* 5(4)](https://doi.org/10.1088/0954-898X_5_4_006); BRISQUE:
[Mittal, Moorthy & Bovik, IEEE TIP 21(12) 2012](https://doi.org/10.1109/TIP.2012.2214050); NIQE:
[Mittal, Soundararajan & Bovik, IEEE SPL 20(3) 2013](https://doi.org/10.1109/LSP.2012.2227726);
PIQE: [Venkatanath et al., NCC 2015](https://doi.org/10.1109/NCC.2015.7084843)).

**Why a near-uniform black frame is degenerate — code-level, not hand-waving.** The reference
implementation computes MSCN as

```python
# pyiqa/archs/func_util.py L87-99
def normalize_img_with_gauss(img, kernel_size=7, sigma=7.0/6, C=1, padding='same'):
    mu = imfilter(img, kernel)
    sigma = safe_sqrt((imfilter(img**2, kernel) - mu**2).abs())
    return (img - mu) / (sigma + C)
```
([`func_util.py`](https://github.com/chaofengc/IQA-PyTorch/blob/main/pyiqa/archs/func_util.py))

`img` is in the 0–255 range and `C=1` is the stabiliser. On a flat black region `img≈0`, `mu≈0`,
`sigma≈0`, so every MSCN coefficient collapses to `≈0/1 = 0`. BRISQUE then fits a GGD to that
all-zero signal (`estimate_ggd_param` on a zero vector) and NIQE fits an AGGD
(`estimate_aggd_param`). Both are 0/0 in the shape parameter. That the reference NIQE
implementation aggregates block features with `nanmean` / `nancov` rather than `mean` / `cov`
([`niqe_arch.py`](https://github.com/chaofengc/IQA-PyTorch/blob/main/pyiqa/archs/niqe_arch.py))
is direct evidence that degenerate blocks routinely produce NaN features in practice.

For NIQE specifically, the test-time score is a Mahalanobis-type distance between the MVG fitted
to *this image's* 96×96 block features and the MVG of the pristine corpus (Eq. 10 in the paper).
`[SPECULATION, mechanism-based]` A 95%-black frame's block features are dominated by degenerate
flat blocks, so the fitted MVG sits far from the pristine MVG and NIQE reports a large distance,
i.e. "very bad quality" — for both our good night frames and our empty ones.

**PIQE is the clean case: it returns the worst possible score on a uniform frame, arithmetically.**
PIQE gates every block on local activity and divides by the count of active blocks:

```python
# pyiqa/archs/piqe_arch.py — activity_threshold = 0.1
active_blocks = block_var > activity_threshold
...
NHSA = active_blocks.sum(dim=1)
C = 1
score = ((dist_block_scores + C) / (C + NHSA)) * 100
```
([`piqe_arch.py`](https://github.com/chaofengc/IQA-PyTorch/blob/main/pyiqa/archs/piqe_arch.py))

On a uniform frame every `block_var ≈ 0`, so `active_blocks` is all-false, `NHSA = 0`,
`dist_block_scores = 0`, and `score = (0+1)/(1+0) × 100 = **100**`. PIQE is lower-is-better on
0–100 ([ModelCard.md](https://github.com/chaofengc/IQA-PyTorch/blob/main/docs/ModelCard.md)), so an
empty frame scores exactly the worst possible value — and so does any frame whose spatially-active
blocks are a small minority, which is precisely our night work. Also note the pre-scaling step
`img = round(255 * img / img.max())`: on a *pure* black frame `img.max()=0` and the whole thing is
NaN.

**These are the wrong tool.** They are cheap (no learned weights beyond a small SVM/MVG, CPU-fast)
but they conflate "flat" with "broken", and our best photographs are flat by intent. Their one
legitimate use here would be inverted: a very high PIQE combined with a very low count of active
blocks is a *content-emptiness* signal, not a quality signal — which is closer to what we actually
want to measure. Flagging that as a cheap idea, not a recommendation.

Published discussion of the flat/uniform failure mode: the CLIP-IQA authors' own framing is that
NSS methods' "optimality of hand-crafted features is often in doubt, and the correlation to human
perception is inferior in general" ([arXiv:2207.12396 §1](https://ar5iv.labs.arxiv.org/html/2207.12396)),
and the TOPIQ authors state NSS methods "perform well in distinguishing synthetic technical
distortions, [but] struggle with modeling authentic technical distortions and aesthetic quality
assessment" ([arXiv:2308.03060 §2](https://ar5iv.labs.arxiv.org/html/2308.03060)). Neither names
uniform frames specifically. **I did not find a primary source that empirically characterises
NR-IQA output on a blank frame** — the code-level argument above is the best available evidence and
it is mechanism, not measurement.

---

### LIQE — the only model whose vocabulary names under-exposure. Top recommendation.

**What it predicts.** Zhang, Zhai, Wei, Yang & Ma, CVPR 2023, "Blind Image Quality Assessment via
Vision-Language Correspondence: A Multitask Learning Perspective"
([arXiv:2303.14968](https://arxiv.org/abs/2303.14968),
[repo](https://github.com/zwx8981/LIQE)). It builds a textual template

> "a photo of a(n) {scene} with {distortion} artifacts, which is of {quality} quality"

instantiates it over the full cross-product, computes cosine similarities between the CLIP image
embedding and all candidate text embeddings, forms the joint probability, then **marginalises to
get each task's prediction independently** (§3). The vocabularies (§3, and verbatim in
[`liqe_arch.py` L33-56](https://github.com/chaofengc/IQA-PyTorch/blob/main/pyiqa/archs/liqe_arch.py)):

- quality (5): `bad, poor, fair, good, perfect`
- scene (9): `animal, cityscape, human, indoor, landscape, **night**, plant, still_life, others`
- distortion (11): `jpeg2000 compression, jpeg compression, noise, blur, color, contrast,
  **overexposure**, **underexposure**, spatial, quantization, other`

5 × 9 × 11 = 495 text embeddings. The paper is explicit that "the `others` category includes images
with no distortions (i.e. of pristine quality)".

**Why this matters for us.** Every other model in the zoo emits one scalar in which "dark" and
"broken" are entangled. LIQE emits `night` on one axis and `underexposure` on another. The query
`scene=night ∧ distortion=others ∧ quality≥good` is a direct expression of "intentionally dark and
fine", and `scene=night ∧ distortion=underexposure` is a direct expression of "technically failed
in the dark". This is the only candidate where our distinction is *representable in the output*.

**Supervision quality — the caveat.** The scene and distortion labels are not native to the source
datasets; the authors "supplement existing IQA datasets [LIVE, CSIQ, KADID-10k, BID, LIVE
Challenge, KonIQ-10k] with scene category and distortion type labels" (§1). So `underexposure` is a
label the LIQE authors assigned, and its coverage depends on how many genuinely underexposed frames
those six datasets contain. `[SPECULATION]` This is the main risk: the label exists but may be
thinly supervised. It is exactly what a prototype would establish.

**Practicalities.** Visual encoder is CLIP ViT-B/32; text encoder is GPT-2-style, 63M params
(§4.1). Inference crops 15 sub-images of 224×224 at the original aspect ratio (§4.1) — no resize,
which matters for a collection with mixed orientations. Weights are open in the pyiqa zoo:
`liqe_koniq.pt` 353.5 MB and `liqe_mix.pt` 353.5 MB, plus precomputed text features
`liqe_text_feat_mix.pt` at 1.0 MB
([HF weight repo](https://huggingface.co/chaofengc/IQA-PyTorch-Weights)). Only `liqe_mix` is
trained on the multi-dataset mixture and is the one to use.

**Cost, measured on this machine.** `[MEASURED]` Apple M4 (10 cores), torch 2.11.0, macOS 26.4.1:
CLIP ViT-B/32 image tower runs at **124.9 img/s on CPU** and **228.3 img/s on MPS** at 224×224
batch 64. LIQE's 15 crops per image therefore imply **~84 min CPU / ~46 min MPS for 42,000
images**, plus JPEG decode. No CUDA needed. The 495 text embeddings are precomputed once.
(Script: `scratchpad/bench.py`.)

**Verdict.** Prototype this first. `[SPECULATION]` It plausibly separates the SoL frames from
underexposed failures because that distinction is in its label space. It probably does **not**
separate SoL from the crescent-moon frame, because "moon against black sky" is a legitimate
`night` scene with no distortion — the moon frame is not *technically* broken, it is *empty*, and
LIQE has no emptiness output.

---

### CLIP-IQA / CLIP-IQA+ — reimplementable on our existing embeddings, and one pair works

**Method, precisely enough to reimplement.** Wang, Chan & Loy, AAAI 2023, "Exploring CLIP for
Assessing the Look and Feel of Images"
([arXiv:2207.12396](https://arxiv.org/abs/2207.12396),
[repo](https://github.com/IceClear/CLIP-IQA)). Two ingredients:

1. **Antonym prompt pairing.** A single prompt is ambiguous ("a rich image"), so use an antonym
   pair. With image feature `x` and text features `t₁`, `t₂`:

   ```
   s_i = (x · t_i) / (‖x‖ ‖t_i‖),  i ∈ {1,2}     # eq. 2
   s̄   = exp(s₁) / (exp(s₁) + exp(s₂))           # eq. 3, s̄ ∈ [0,1]
   ```

   A larger `s̄` means a closer match to `t₁`. This "casts the task as a binary classification
   where the final score is a relative similarity" (§2.1). Naïve single-prompt cosine gives
   SROCC 0.116–0.214 on KonIQ-10k depending on template; the pair gives 0.695 (Table 2).

2. **Positional-embedding removal**, so CLIP accepts arbitrary-size input instead of a 224 crop
   that would itself alter the quality being measured (§2.1). They use the **RN50** variant
   because ResNets depend less on positional information. This is load-bearing: with pos-emb
   removed, RN50 gets SROCC/PLCC 0.695/0.727 on KonIQ-10k while **ViT-B/32 gets only
   0.391/0.374** (Table 2).

**Documented prompt pairs (paper Tables in §2.2, §2.3 and appendix):**

| axis | pair |
|---|---|
| overall quality | `"Good photo."` / `"Bad photo."` |
| **brightness** | **`"Bright photo."` / `"Dark photo."`** |
| noisiness | `"Clean photo."` / `"Noisy photo."` |
| colourfulness | `"Colorful photo."` / `"Dull photo."` |
| sharpness | `"Sharp photo."` / `"Blurry photo."` |
| abstract | `Complex/Simple`, `Natural/Synthetic`, `Happy/Sad`, `Scary/Peaceful`, `New/Old` |
| abstract (AVA appendix) | `Warm/Cold`, `Real/Abstract`, `Beautiful/Ugly`, `Lonely/Sociable`, `Relaxing/Stressful` |

The template matters a lot: `"[text] photo."` beats `"A photo of [text]."` (0.695 vs 0.116 SROCC)
and `"There is [text] in the photo."` (0.214). Adjective choice matters too: `Good/Bad` beats
`High quality/Low quality` (0.537) and `High definition/Low definition` (Table 2).

**Is `"a photo of a subject"` / `"an empty black frame"` a documented use? No.** The paper's
attribute set is adjectival and perceptual (brightness, noise, sharpness, colour, plus emotional
abstractions). Nothing in the paper, the repo, or the pyiqa reimplementation proposes a
presence-of-content pair. It is also the *worst* template family per Table 2 (`"A photo of ..."`
scores 0.116). So this specific idea is ours, untested upstream — and it does not work, measured
below.

**Documented limitations relevant to us** (§3.3): CLIP-IQA is prompt-sensitive; and it cannot
handle professional photographic vocabulary — the authors name **"Long exposure", "Rule of
thirds", "Shallow DOF"** as terms CLIP does not recognise. That is a direct warning against
writing a rubric in photographer's language and expecting CLIP to score it.

**CLIP-IQA+** keeps all network weights frozen and learns only the 16 context tokens of the two
prompts with CoOp, initialised at `"Good photo."`/`"Bad photo."`, MSE loss on KonIQ-10k, SGD lr
0.002, 100k iters, batch 64 (§2.2). Result: SROCC/PLCC 0.895/0.909 on KonIQ-10k, 0.805/0.832 on
LIVE-itW, 0.864/0.866 on SPAQ — competitive with fully-supervised SOTA, with better cross-dataset
stability. Storage is trivial: `CLIP-IQA+_learned_prompts` is **17,144 bytes**;
`CLIPIQA+_RN50_512` is 316.7 KB; `CLIPIQA+_ViTL14_512` is 474.4 KB
([HF weight repo](https://huggingface.co/chaofengc/IQA-PyTorch-Weights)). The authors highlight
this: "CLIP-IQA+ needs to store only two prompts for each domain" versus training a separate model
per domain the way MUSIQ does.

**Two reimplementation gotchas found in the reference code.**

- pyiqa's `clipiqa` (not `clipiqa+`) does **not** use the paper's single `Good/Bad` pair — it
  ensembles **five** pairs and averages the softmax: `Good/bad image`, `Sharp/blurry image`,
  `sharp/blurry edges`, `High/low resolution image`, `Noise-free/noisy image`, with the header
  noting "we assemble multiple prompts to improve the results"
  ([`clipiqa_arch.py` L160-173, L227-231](https://github.com/chaofengc/IQA-PyTorch/blob/main/pyiqa/archs/clipiqa_arch.py)).
  If you compare your numbers to pyiqa's you are comparing to the ensemble, not the paper.
- **Scale.** The paper's eq. 3 softmaxes *raw* cosine similarities. pyiqa instead softmaxes
  `logits_per_image`, which is `logit_scale.exp() * cos` with `logit_scale.exp() = 100` in the
  released OpenAI CLIP weights
  ([`clip_model.py` L705-707](https://github.com/chaofengc/IQA-PyTorch/blob/main/pyiqa/archs/clip_model.py)).
  `[MEASURED]` Implementing eq. 3 literally gives scores compressed into **0.481–0.505** across
  all 41,566 images — numerically useless as an absolute score, though rank-identical since the
  softmax is monotone in `s₁ − s₂`. **Use `100 × cos`, or just use `s₁ − s₂` and rank.**

**`[MEASURED]` Results on our actual collection.** Implemented eq. 2/3 on the 41,566 stored
ViT-B/32 embeddings + the ViT-B/32 text tower (`scratchpad/probe_clipiqa.py`). Cohort medians as
percentile-within-library; cohorts defined by regex over the existing VLM `summary` field, so they
are noisy but large.

| pair | SoL night (n=26) | crescent-moon (n=130) | out-of-focus/illegible (n=239) | underexposed (n=237) | AUC(SoL > illegible) |
|---|---|---|---|---|---|
| `Good photo./Bad photo.` | p29 | p52 | p16 | **p9** | 0.626 |
| `Bright/Dark photo.` | **p4** | p38 | p19 | **p4** | 0.246 |
| `Sharp/Blurry photo.` | **p74** | p68 | p30 | p32 | **0.721** |
| `Clean/Noisy photo.` | p51 | p37 | p33 | p29 | 0.643 |
| `Complex/Simple photo.` | p21 | p23 | p37 | p34 | 0.385 |
| `a photo of a subject` / `an empty black frame` | p12 | p33 | p18 | p11 | 0.454 |
| `...clear recognisable subject` / `...nothing, an empty dark frame` | p7 | p21 | p19 | p7 | 0.266 |
| `...legible...` / `...illegible...` | p32 | p66 | p31 | p38 | 0.547 |
| **`a deliberately dark low-key night photograph` / `an accidentally underexposed failed photograph`** | **p92** | **p91** | p63 | p61 | **0.862** |
| `a keeper photograph` / `a mistake, a throwaway frame` | p10 | p28 | p21 | p26 | 0.357 |

Readings:

- **The canonical `Good/Bad` pair is a night detector on this collection.** The twelve
  lowest-scoring images are, without exception, night/silhouette/moon/concert-in-the-dark scenes.
  SoL sits at p29. Using it as a reject gate would delete good work — less violently than the LAION
  predictor, but in the same direction.
- **`Bright/Dark` behaves exactly as documented and is therefore useless as a quality axis but
  useful as a *covariate*.** SoL at p4 and underexposed-failures at p4 — it measures darkness, and
  darkness does not distinguish our two cases. Its value is as a conditioning variable ("among dark
  frames only, rank by X").
- **`Sharp/Blurry` is a legitimate reject signal.** AUC 0.721 separating SoL (p74) from
  out-of-focus frames (p30). This is a documented CLIP-IQA pair, costs nothing, and its failure
  mode (long-exposure motion blur used deliberately) is at least an *intelligible* failure mode.
- **The custom "is there content" pairs fail, and fail in the wrong direction.** AUC 0.266 and
  0.454 — they rank SoL *below* illegible frames. The library's lowest scorers on
  `content_vs_nothing` are minimalist B&W seascapes and weathered-wall studies, i.e. deliberate
  work, mixed in with one genuine lens-cap frame (`L1008389`, "Extremely dark underexposed or
  lens-capped frame with no discernible subject"). These pairs are measuring "is this a monochrome
  minimal frame", not "is there content". **Do not ship this idea.**
- **`intentional_vs_failed` is the one that works, and it still can't see the moon.** AUC 0.862
  against illegible frames. But SoL p92 and moon p91 are the same number. It has learned "does this
  look like deliberate night photography", and the crescent-moon frames *do*.

**Cost.** `[MEASURED]` The entire ten-pair sweep over 41,566 images ran in **~1 s of arithmetic**
(the 5 s wall-clock was loading the sentence-transformers model). The embeddings are already in
`library.db` as a `vec0` table `image_clip_embeddings(embedding float[512], image_key TEXT)` and
are already L2-normalised (`encode_images(..., normalize_embeddings=True)` in
`lightroom_tagger/core/clip_embedding_service.py`). Marginal cost of adding this: zero image I/O,
zero model download.

**Caveat on comparability.** Our embeddings come from `clip-ViT-B-32` with standard preprocessing —
**ViT with positional embedding, 224 centre crop** — whereas CLIP-IQA specifies **RN50 with
positional embedding removed** and native resolution. The paper's ablation says ViT-B/32 with
pos-emb removed scores 0.391 vs RN50's 0.695 on KonIQ-10k (Table 2); it does not report ViT-B/32
*with* pos-emb, so I cannot cite a number for our exact configuration. If the free version looks
promising, running the proper RN50-no-pos-emb `clipiqa` from pyiqa is one extra CLIP pass over 42k
(~5.6 min CPU at the measured ViT-B/32 rate; RN50 is in the same order).

---

### LAION aesthetic predictor v1 / v2 — ruled out, with numbers from this collection

**v1: exactly what it takes and outputs.** A single `nn.Linear(768, 1)` for ViT-L/14, or
`nn.Linear(512, 1)` for ViT-B/32, applied to the **L2-normalised** CLIP image embedding
([LAION-AI/aesthetic-predictor README + notebook](https://github.com/LAION-AI/aesthetic-predictor)):

```python
if clip_model == "vit_l_14":  m = nn.Linear(768, 1)
elif clip_model == "vit_b_32": m = nn.Linear(512, 1)
...
image_features = model.encode_image(image)
image_features /= image_features.norm(dim=-1, keepdim=True)
prediction = amodel(image_features)     # -> tensor([[4.0330]])
```

Weight files in the repo: `sa_0_4_vit_b_32_linear.pth` **3,047 bytes**,
`sa_0_4_vit_b_16_linear.pth` 3,047 bytes, `sa_0_4_vit_l_14_linear.pth` **4,071 bytes**
([GitHub contents API](https://api.github.com/repos/LAION-AI/aesthetic-predictor/contents/)).
It is one dot product. Output is an unbounded real that in practice lands on roughly a 1–10 scale.

**v2 ("improved"): the one used for LAION-Aesthetics and diffusion dataset filtering.** An MLP on
CLIP **ViT-L/14 only**, 768-dim input
([christophschuhmann/improved-aesthetic-predictor `simple_inference.py`](https://github.com/christophschuhmann/improved-aesthetic-predictor/blob/main/simple_inference.py)):

```python
self.layers = nn.Sequential(
    nn.Linear(input_size, 1024),  # nn.ReLU(),
    nn.Dropout(0.2),
    nn.Linear(1024, 128),         # nn.ReLU(),
    nn.Dropout(0.2),
    nn.Linear(128, 64),           # nn.ReLU(),
    nn.Dropout(0.1),
    nn.Linear(64, 16),            # nn.ReLU(),
    nn.Linear(16, 1))
model = MLP(768)  # CLIP embedding dim is 768 for CLIP ViT L 14
s = torch.load("sac+logos+ava1-l14-linearMSE.pth")
```

**Note the commented-out ReLUs.** In `eval()` mode dropout is the identity, so this "MLP" is a
composition of five affine maps with no nonlinearity — i.e. **mathematically a single linear
functional on the normalised ViT-L/14 embedding**, same expressive class as v1, just with 3.5 MB of
redundant parameters (`sac+logos+ava1-l14-linearMSE.pth` = 3,714,759 bytes;
`ava+logos-l14-linearMSE.pth` = same;
[contents API](https://api.github.com/repos/christophschuhmann/improved-aesthetic-predictor/contents/)).
Checkpoint names record the supervision: SAC (Simulacra Aesthetic Captions) + LAION-Logos + AVA.
LAION's own writeup of the aesthetics scoring is at
[laion.ai/blog/laion-aesthetics](https://laion.ai/blog/laion-aesthetics/).

**Is it known to score empty/blank images low or high? I found no primary source that states
either way.** So I measured it.

**`[MEASURED]` v1 ViT-B/32 head over all 41,566 stored embeddings** (`scratchpad/probe_aes.py`,
`scratchpad/probe_join.py`; head downloaded from the official repo, 3,047 bytes; embeddings read
directly out of the `vec0` shadow tables; norms verified 1.0000):

Distribution: p0 1.07 · p1 2.62 · p5 3.34 · p25 4.27 · **p50 4.88** · p75 5.49 · p95 6.30 ·
p99 6.84 · p100 8.16.

**The Statue of Liberty night frames — the collection's best work — occupy the absolute bottom:**

| file | score | percentile | description (existing VLM summary, truncated) |
|---|---|---|---|
| L1007428 | 2.15 | **p0** | high-contrast B&W night photograph of the Statue of Liberty… small illuminated figure |
| L1007423 | 2.20 | **p0** | B&W night photograph of the Statue of Liberty illuminated against darkness |
| L1007429 | 2.35 | **p0** | Statue of Liberty isolated against black sky and water |
| L1007422 | 2.55 | p1 | monochrome night photograph… reflection on water |
| L1007431 | 2.55 | p1 | low-key nocturnal view… torch and body the primary light source |
| L1007427 | 2.61 | p1 | nocturnal B&W… isolated against darkness, minimal ambient light |
| L1007430 | 2.78 | p1 | illuminated against darkness, city lights and water reflections |
| L1007419 | 3.10 | p3 | B&W nighttime… viewed from across dark water |

All 26 SoL frames fall in p0–p3.

**It is not a darkness penalty — it is a monochrome-and-minimalism penalty.** `[MEASURED]` The
broad night/dark cohort (n=5,447, regex on `night|darkness|black sky|silhouette|…`) has median
4.81 versus the library's 4.88 — **p46.8, essentially unpenalised.** So dark scenes in general are
fine. What gets crushed is specifically monochrome + low-content + high-black-fraction.

**What it actually ranks.** Top 15: "person in a yellow patterned swimsuit… in a shallow rocky
stream surrounded by dense forest" (8.15), then eleven variants of *a person in a red shirt in
front of a turquoise waterfall* (7.68–8.11). Bottom 15: B&W architectural line studies, interior
hallways, black cats on light floors, monochrome animal tracks in snow — plus, correctly,
"Extremely out-of-focus close-up of human skin, no discernible subject" (1.54), "Severely
out-of-focus photograph of the back of a person's head" (1.62), and "Underexposed, grainy image
showing an indistinct vertical surface" (1.43). **It does find real failures — it just buries them
among the best work.** Precision at the bottom of the ranking is unusable as a gate.

**Correlation with the existing rubric** `[MEASURED]` (Spearman, current scores only):
`environmental-context-legibility` +0.411 (n=40,782), `documentary` +0.282,
`layering` +0.264, `compositional-cleanliness` +0.221, `color_theory` +0.210,
`street` +0.084, `framing` +0.043, `intensity-suggestion` +0.030. It agrees weakly with legibility
and essentially not at all with framing or intensity — it is not measuring what the rubric
measures.

**Verdict: ruled out.** Both versions. v2 would additionally require a full ViT-L/14 pass over
42,000 images to obtain 768-dim embeddings we do not have, in order to run a head with the same
AVA/SAC supervision and (given the missing nonlinearities) the same expressive class.
`[SPECULATION]` I did not measure v2, but there is no mechanism by which it would reverse the sign.

---

### MUSIQ, MANIQA, TReS, TOPIQ, Q-Align — the rest of the modern zoo

**MUSIQ** (Ke et al., ICCV 2021, [arXiv:2108.05997](https://arxiv.org/abs/2108.05997);
[official checkpoints in google-research](https://github.com/google-research/google-research/tree/master/musiq)).
A multi-scale patch transformer that processes **native-resolution** images with a hash-based 2D
spatial embedding plus a scale embedding, so it never resizes or crops — the paper's stated
motivation is that "resizing and cropping can impact image composition or introduce distortions,
thus changing the quality of the image" (§1). SOTA on three **technical** datasets (PaQ-2-PiQ,
KonIQ-10k, SPAQ) and on-par with SOTA on the **aesthetic** dataset AVA (§1). The technical/aesthetic
split is therefore real but implemented as **separate checkpoints, not separate heads**:
pyiqa exposes `musiq` (KonIQ, range ~0–100), `musiq-spaq`, `musiq-paq2piq`, and `musiq-ava`
(range 1–10)
([`default_model_configs.py`](https://github.com/chaofengc/IQA-PyTorch/blob/main/pyiqa/default_model_configs.py)).
Each checkpoint is **108.6 MB**; the ImageNet pretrain is 110.2 MB. CPU-feasible but slower per
image than ViT-B/32 because input is full-resolution.
`[SPECULATION]` Ruled out for our purpose: KonIQ/SPAQ labels are authentic-camera-distortion MOS
with no exposure concept, and `musiq-ava` is an AVA aesthetic model, i.e. the LAION failure family.

**MANIQA** (Yang et al., CVPRW 2022, [arXiv:2204.08958](https://arxiv.org/abs/2204.08958)).
ViT features + Transposed Attention Block + Scale Swin Transformer Block, patch-weighted
prediction. Explicitly built for **GAN-based distortion**: "existing NR-IQA methods are far from
meeting the needs of predicting accurate quality scores on GAN-based distortion images"; won NTIRE
2022 Track 2, evaluated on LIVE/TID2013/CSIQ/KADID-10k. pyiqa ships `maniqa` (KonIQ),
`maniqa-kadid`, `maniqa-pipal`; `MANIQA_PIPAL` is **543.3 MB**. Wrong distortion domain — this is
a super-resolution-artefact detector. Ruled out.

**TReS** (Golestaneh, Dadsetan & Kitani, WACV 2022,
[arXiv:2108.06858](https://arxiv.org/abs/2108.06858)). CNN+transformer with a relative-ranking loss
and a self-consistency loss under image flips. pyiqa: `tres` (KonIQ), `tres-flive`; **610.3 MB**,
the largest non-LMM entry in the zoo. Single technical scalar, no aesthetic split, no exposure
concept. Ruled out on size-to-value.

**TOPIQ / CFANet** (Chen et al., IEEE TIP,
[arXiv:2308.03060](https://arxiv.org/abs/2308.03060) — by the pyiqa author). Top-down
coarse-to-fine attention: high-level semantic features act as queries to select semantically
important low-level distortion features, on a ResNet50 backbone. The efficiency claim is the
selling point: "competitive performance… while being much more efficient (with only ~13% FLOPS of
the current best FR method)" (abstract). It has a genuine technical/aesthetic split by checkpoint:
`topiq_nr` / `cfanet_nr_koniq_res50` **181.2 MB** (technical, KonIQ) versus
`cfanet_iaa_ava_res50` **293.9 MB** and `cfanet_iaa_ava_swin` **507.6 MB** (aesthetic, AVA, trained
with NIMA's EMD distribution loss, §III). Also a face-specific `topiq_nr-face`. The paper's own
framing of the two subtasks is worth quoting because it explains why neither helps us: technical
quality "focuses on technical aspects of the image such as sharpness, brightness, and noise… the
fidelity of an image to the original scene", while aesthetic quality concerns "composition,
lighting, color harmony" (§2). Our question — *is there any legible content* — is in neither
bucket. `[SPECULATION]` Ruled out; the best efficiency/accuracy tradeoff in the zoo, but predicting
the wrong thing.

**Q-Align / OneAlign** (Wu et al., ICML 2024, [arXiv:2312.17090](https://arxiv.org/abs/2312.17090),
[repo](https://github.com/Q-Future/Q-Align)). Teaches an LMM to emit **discrete text-defined rating
levels** ("excellent/good/fair/poor/bad") rather than regressing a score, then converts the level
distribution to a scalar. Unifies IQA + **IAA (aesthetic)** + VQA into one model (OneAlign) — so
this genuinely does have a technical-vs-aesthetic split as *task flags on a single model*, exposed
in pyiqa as `qalign` with `quality` (default) and `aesthetic` options
([ModelCard.md](https://github.com/chaofengc/IQA-PyTorch/blob/main/docs/ModelCard.md)).
**Size: 16.4 GB** — `pytorch_model-00001-of-00002.bin` 9,991,591,698 B +
`pytorch_model-00002-of-00002.bin` 6,417,830,970 B
([HF `q-future/one-align`](https://huggingface.co/q-future/one-align)), i.e. an ~8B-param
mPLUG-Owl2 in fp16. pyiqa also lists newer `qrealign-mini/lite/pro` on a Qwen3.5-VL backbone
(0.8B / 4B / 9B, requires `transformers>=5.0`).

**Q-Align's honest position in our decision.** It is a VLM. This pipeline already runs local Ollama
vision models, so the *capability* exists and the *cost model* is already understood: one VLM
forward pass per image at 42k scale. Adding Q-Align does not buy a new cost regime — it buys a
better-calibrated scoring prompt inside the same regime. `[SPECULATION]` If the answer turns out to
be "only a VLM can tell a Statue of Liberty from a crescent moon" — which the measurements above
suggest — then the right move is a better **prompt** to the existing Ollama model, not a second
16 GB VLM. The `qrealign-mini` 0.8B variant is the one exception worth a look purely on size.

---

## The gap no learned IQA model closes

`[MEASURED]` Every axis tested puts the crescent-moon frames and the Statue-of-Liberty frames in
the same place. On the best-performing pair, SoL p92 / moon p91. On the LAION predictor both are in
the bottom decile. On `Bright/Dark` both are dark.

`[SPECULATION, mechanism-based]` The reason is representational. All these models reduce the image
to a globally-pooled feature at 224×224 (or, for MUSIQ/LIQE, a small set of crops). At that
resolution a Statue of Liberty at ~5% of frame height and a crescent moon at ~1% are both "one
small bright thing on black". The information that distinguishes them — *is the bright region
resolved enough to be a recognisable object* — is destroyed by the pooling. No amount of prompt
engineering on a pooled embedding recovers it.

Two cheap directions that do not require a learned IQA model, offered as leads for the pixel-metrics
sub-question rather than conclusions here:

1. **Luminance-histogram + connected-component statistics.** Fraction of pixels above a threshold;
   number and pixel-area of connected bright components; area of the largest one. A moon is one
   tiny blob; a lit statue plus a shoreline of city lights is a larger blob plus a structured line
   of small ones. This is `numpy` on a downsampled preview, effectively free, and it is measuring
   the thing that actually differs. Note this is the *inverse* of PIQE's active-block count — PIQE
   already computes exactly this statistic (`NHSA`) and then throws it away by dividing by it.
2. **`[MEASURED]` The existing rubric already contains a near-usable axis.** In `image_scores`,
   `environmental-context-legibility` scores **1** for all four crescent-moon frames
   (`_DSF1512`, `_DSF1517`, `_DSF1526`, `_DSF1527`) while the SoL frames get 3–8. The user's
   reported pathology reproduces exactly — `_DSF1526` has
   `compositional-cleanliness = 9` and `environmental-context-legibility = 1` simultaneously. The
   separator may already exist and simply not be gating anything. Caveat: legibility is unstable
   across prompt versions (`L1007429` scored 2 under one `prompt_version` and 7 under another;
   the lens-cap frame `L1008389` scored 1 and 7), so it needs consistency work before it can gate.

---

## Ruled out, and why

| Candidate | Reason |
|---|---|
| **NIMA technical head (TID2013)** | Trained on 3,000 synthetic degradations of 25 daylight Kodak references. Its 24 distortion types contain no empty frame and no gross underexposure; the nearest, mean-shift and contrast-change, are graded against a visible well-exposed reference and are not even monotone in level. The paper reports the TID2013 head transfers poorly (AVA→LIVE 0.552 vs LIVE→AVA 0.238). **And Google never released the weights** — pyiqa has no TID2013 checkpoint. |
| **NIMA aesthetic head (AVA)** | Same supervision family as the LAION predictor, which is measured to put our best 26 frames in p0–p3. |
| **LAION aesthetic v1** | `[MEASURED]` All 26 Statue-of-Liberty night frames land in p0–p3 of 41,566. Top of ranking is saturated with colourful-subject-in-green-forest. Fails the CRITICAL CONSTRAINT outright. |
| **LAION aesthetic v2** | ViT-L/14 only (needs a new 42k embedding pass we don't have); the "MLP" has its ReLUs commented out so in `eval()` it is a linear map — same expressive class as v1, same AVA/SAC supervision. `[SPECULATION]` no mechanism to reverse v1's sign. |
| **BRISQUE / NIQE** | MSCN coefficients collapse to ~0 on flat regions (`(img-mu)/(sigma+1)` with `img≈0`), making the GGD/AGGD shape fits degenerate — the reference NIQE aggregates with `nanmean`/`nancov`, which is itself the tell. They conflate "flat" with "broken"; our best work is flat by intent. |
| **PIQE** | Returns exactly **100 = worst** on a uniform frame by arithmetic: `NHSA=0` ⇒ `score=(0+1)/(1+0)×100`. Pure-black input additionally NaNs on the `255*img/img.max()` prescale. |
| **MANIQA** | Built for GAN/super-resolution artefacts (PIPAL, NTIRE'22). Wrong distortion domain. 543 MB. |
| **TReS** | 610 MB for a single technical scalar with no exposure concept. Worst size-to-value in the zoo. |
| **MUSIQ** | Real technical/aesthetic split but only via separate 108 MB checkpoints; KonIQ/SPAQ label spaces have no exposure concept and `musiq-ava` is the AVA failure family. Keep as a fallback if LIQE's quality head is weak — it is the best-regarded pure technical scalar. |
| **TOPIQ** | Best efficiency/accuracy tradeoff available (ResNet50, ~13% FLOPs of the best FR transformer) and a clean technical/aesthetic checkpoint split — but by the authors' own taxonomy neither subtask covers "is there legible content". |
| **Q-Align / OneAlign** | 16.4 GB, ~8B-param LMM. Does not open a new cost regime relative to the Ollama vision models already in the pipeline; if the answer is "you need a VLM", write a better Ollama prompt instead. `qrealign-mini` (0.8B) is the only variant worth a second look on size. |
| **Custom "content vs nothing" CLIP prompt pairs** | `[MEASURED]` AUC 0.266–0.454 — they rank the good night frames *below* genuinely illegible ones. They measure "monochrome and minimal", not "empty". Also the worst-performing template family in the CLIP-IQA ablation. Do not ship. |

---

## Local cost summary

Measured on this machine: **Apple M4, 10 cores, macOS 26.4.1, torch 2.11.0, MPS available, no
CUDA** (`scratchpad/bench.py`).

| Approach | Download | Per-image work | 42,000 images |
|---|---|---|---|
| CLIP-IQA prompt pairs on **existing** embeddings | 0 | one 512-dim dot product per prompt | **~1 s** `[MEASURED]` |
| LAION aesthetic v1 on **existing** embeddings | 3 KB | one 512-dim dot product | **~1 s** `[MEASURED]` |
| Anything needing one fresh ViT-B/32 pass (CLIP-IQA proper, new embeddings) | ~600 MB CLIP | 1 × 224² ViT-B/32 forward | **~5.6 min CPU / ~3.1 min MPS** `[MEASURED]` |
| **LIQE** (15 × 224² crops, ViT-B/32) | 353 MB + 1 MB text feats | 15 × 224² forwards | **~84 min CPU / ~46 min MPS** `[MEASURED]` |
| TOPIQ NR (ResNet50) | 181 MB | 1 ResNet50 forward | `[SPECULATION]` same order as one CLIP pass, tens of minutes |
| MUSIQ | 109 MB | multi-scale native-resolution transformer | `[SPECULATION]` slower than one ViT-B/32 pass; hours, not minutes |
| BRISQUE / NIQE / PIQE | ~0 | NSS features, no NN | fast, but the outputs are wrong for us |
| Q-Align | **16.4 GB** | one ~8B LMM forward | same regime as the existing Ollama vision pass |

Baseline throughput measured: **CLIP ViT-B/32, 224×224, batch 64 → 124.9 img/s CPU, 228.3 img/s
MPS.** All of these are CPU-practical except Q-Align. Add JPEG/RAW decode time to every row that
touches pixels; the two zero-download rows touch no pixels at all.

---

## Reproduction artefacts

All in `scratchpad/`, all read-only against the database
(`sqlite3` opened `mode=ro&immutable=1`; `vec0` shadow tables read directly since the extension is
not loaded):

| script | what it does |
|---|---|
| `probe_aes.py` | downloads the official 3,047-byte LAION v1 ViT-B/32 head, reads all 41,566 embeddings out of `image_clip_embeddings_vector_chunks00`, verifies norms == 1.0, scores everything, dumps `aes_v1_scores.npy` / `vecs_n.npy` / `aes_keys.txt` |
| `probe_join.py` | joins scores to `images.filename`, `image_descriptions.summary` and `image_scores`; produces the cohort tables and rubric correlations |
| `probe_clipiqa.py` | implements CLIP-IQA eqs. 2-3 over ten antonym pairs on the stored embeddings + the ViT-B/32 text tower; produces the percentile table and the AUC separation test |
| `bench.py` | ViT-B/32 CPU-vs-MPS throughput |
| `pages/` | cached text of every cited paper, repo README, arch source and HF model index |

Cohorts are defined by regex over the existing VLM `summary` text, not by human labels, so cohort
membership is noisy. The Statue-of-Liberty cohort (n=26) is small enough that its p0–p3 result rests
on 26 images — but the effect size is so large (all 26 in the bottom 3%) that noise is not a
plausible explanation.
