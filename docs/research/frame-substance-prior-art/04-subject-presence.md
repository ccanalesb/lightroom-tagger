# Subject presence, not exposure, as the gate for "is this frame worth judging?"

Research note. Every factual claim carries a URL. Claims marked **[INFERENCE]** are my
reasoning, not cited evidence.

Two test cases used throughout:

- **CASE A — crescent moon on black sky.** Tiny bright blob, technically a subject,
  no legible content. **Must be REJECTED.**
- **CASE B — Statue of Liberty lit against total darkness.** Equally dark overall.
  **Must be KEPT.**

---

## Verdict

**Yes — subject presence is a strictly better framing than exposure, and it is a
published, named research problem with human-level results on exactly the case we
care about.**

The problem is called **Salient Object Subitizing (SOS)**: predict *the existence and
the number* of salient objects in an image, with **0** as a first-class output class
(Zhang et al., CVPR 2015 / IJCV 2017, <https://arxiv.org/abs/1607.07525>). Its 0-class
recall is **94%** in the CVPR version, "matching the human accuracy for this category in
our human subitizing test", and ~93% in the IJCV version
(<https://arxiv.org/html/1607.07525v1>, §5). The paper also does precisely the
architectural thing we want — it gates a downstream saliency model on the subitizing
prediction: "**if our SOS method predicts that the image contains zero salient objects,
then we do not apply salient object detection methods on that image**", which yields a
**>35% relative AP increase** on their MSO benchmark
(<https://arxiv.org/html/1607.07525v1>).

There is a second, independent precedent: Jiang et al., "Joint Salient Object Detection
and Existence Prediction" (<https://mmcheng.net/salexist/>), which predicts an
image-level existence label and reports **88.36%** accuracy on a purpose-built set of
6,182 background images.

So the answer to "does anyone treat subject presence as the criterion" is **yes, twice
over, and both treat it as a gate, exactly as we want to.**

The answer to "can we" is **yes, but not by downloading the SOS model** — it is a
2016-era Caffe GoogleNet with no maintained weights (no repo via `gh search repos
"salient object subitizing"`; project page <http://cs-people.bu.edu/jmzhang/sos.html>
404s). What survives is the *labelled data* and the *problem formulation*. One modern
alternative is worth a look before we build: Islam et al., CVPR 2018, "Revisiting Salient
Object Detection: Simultaneous Detection, Ranking, and **Subitizing**"
(<https://arxiv.org/abs/1803.05082>), which has a PyTorch reimplementation
(<https://github.com/MinglangQiao/pytorch-rsdnet-sor>).

**And the central technical finding, which determines everything else:** the crescent
moon and the lit Statue are **structurally near-identical in pixel statistics** — a small
lit region in a vast black field. **Only semantics separate them.** Every low-level
signal we might reach for (exposure, saliency contrast, complexity, compression) is
therefore working with the wrong information, and the literature confirms it: Xia et al.
name "**low objectness**" as a distinct reason a high-contrast region is *not* a salient
object (<https://openaccess.thecvf.com/content_cvpr_2017/html/Xia_What_Is_and_CVPR_2017_paper.html>),
and SOS reports that saliency-map-derived features are *worse* than plain global image
features (HOG, GIST) at predicting existence
(<https://arxiv.org/html/1607.07525v1>). **The instrument has to be semantic.**

### What to prototype, in priority order

1. **A lit-area fraction statistic on a downsampled frame — do this first, it is ~10
   lines and may solve the whole problem.** My own probe (§7) shows it separates Case A
   from Case B by ~16× (0.72% vs 11.38%) and is *completely invariant* to simulated
   sensor noise, which the compressed-file-size trick is not. It measures spatial
   *extent* of legible content, which is precisely the property CLIP is documented to
   discard (§13) — so it is complementary, not redundant.
2. **Train a tiny head on our existing CLIP embeddings against presence labels.** The
   CLIP paper's own Fig. 8 says a linear probe beats zero-shot prompting by **10–25
   points**, and Fig. 7 says it needs a median of **5.4 labelled examples per class** to
   match zero-shot (<https://arxiv.org/html/2103.00020v1>). LAION-Aesthetics V1 is
   `nn.Linear(768, 1)` — **769 parameters** — trained on 5,000 ratings, and it selected
   the Stable Diffusion v1 training set (<https://laion.ai/blog/laion-aesthetics/>). Label
   sources, all existing: the SOS dataset (14K, 0/1/2/3/4+,
   <https://arxiv.org/html/1607.07525v1>); XPIE's 8,598 "no clear object" images
   (<https://openaccess.thecvf.com/content_cvpr_2017/html/Xia_What_Is_and_CVPR_2017_paper.html>);
   **SOC's 2,217 "aurora, sky" non-salient images** — literally our Case A
   (<https://ar5iv.labs.arxiv.org/html/2105.03053>); **SOSB's 6,182 background images**
   (<https://mmcheng.net/salexist/>); AADB's human-rated `object_emphasis` / `content`
   over 10,000 images (<https://ar5iv.labs.arxiv.org/html/1606.01621>). That is well over
   20,000 human-labelled negatives available without us annotating anything.
3. **OWLv2's class-agnostic objectness head** as the one model-based candidate worth a
   spike. It is the only text-free, per-patch presence score in this entire survey,
   requires no class list, is 155 M params and Apache-2.0
   (<https://arxiv.org/abs/2306.09683>, and see §12 for the code references).
4. **CLIP antonym prompt pairs as a zero-shot day-one baseline**, cheap enough to be
   worth running even though I expect it to lose to (2). Published and validated as a
   technique (<https://arxiv.org/html/2207.12396v2>) and shipped in torchmetrics
   (<https://lightning.ai/docs/torchmetrics/stable/multimodal/clip_iqa.html>), but with
   two serious caveats developed in §4 and §13: WP-CLIP measures zero-shot CLIP at
   SRCC 0.06 on the closest art-theoretic axis, and the score saturates near-binary
   because implementations apply CLIP's 100× logit scale.

**And in all cases: fit the threshold to our own score histogram.** Zero-shot CLIP is
documented as miscalibrated (<https://arxiv.org/abs/2303.12748>), and score-based
thresholds are documented to "suffer from threshold sensitivity"
(<https://arxiv.org/abs/2504.14224>, whose training-free Box-Cox + bimodal-GMM recipe is
the right shape for a 42,000-image corpus). Never hardcode a constant from a paper.

**And hold out a dark-frames-only validation slice.** There is **no published measurement
of CLIP accuracy under illumination or exposure corruption at all** (§13) — the CLIP
paper deliberately excludes ImageNet-C-style synthetic shifts. Every dataset in
recommendation (2) is daytime-skewed. The transfer to night photography is the untested
link in every single path in this report, so it is the thing our prototype must measure
rather than assume. A head that scores 0.95 overall and 0.55 on dark frames is useless to
us, and an aggregate number will hide that. **Ready-made dark-frame eval data exists** —
YLLSOD has 3,263 pairs with explicit "extreme darkness" and "uneven illumination" classes
(<https://github.com/ynn1030/YLLSOD>), and NTI-V1 has 577 night images with pixel ground
truth (<https://arxiv.org/abs/2007.16124>). Use them alongside our own hand-labelled
night frames.

### What to *not* prototype

- **Object detection of any kind as the presence gate.** This is the firmest negative
  result in the report and it is quantitative. Detectors trained on well-exposed data
  collapse on dark imagery: **−32.1 points** day→night on identical classes
  (CODaN/CIConv, <https://arxiv.org/abs/2108.05137>), and **Faster-RCNN scores 1.7 mAP**
  on WIDER FACE → DARK FACE (<https://arxiv.org/html/2312.01220v2>, Table 1) against
  90-plus on well-lit data. Low-light enhancement preprocessing buys ≈0.5 mAP or less
  (<https://github.com/cuiziteng/MAET>). **A detector-based gate would systematically
  reject legitimate night photography — exactly our Case B false positive.** Grounding
  DINO is separately unaffordable at 15 s/image on CPU
  (<https://github.com/IDEA-Research/GroundingDINO/issues/31>) ≈ 175 hours.
- **SAM's `predicted_iou` or `stability_score` as a presence signal.** They are
  *inverted* for our purpose: a bright disc on flat black is the easiest possible
  segmentation, so the frame we want to reject scores most confident. SAM's stated design
  goal is "to always predict a valid mask for any prompt even when the prompt is
  ambiguous" (<https://arxiv.org/abs/2304.02643>, §3) — there is no abstain path. Its
  automatic mode is also the most expensive option surveyed.
- **Saliency-map mass, peak or area as a presence score.** No paper uses it as a
  runtime confidence; where it was tried, SOS reports Otsu + connected-components
  counting as "**barely better than chance**" (CVPR 2015 §4). And in U²-Net, BASNet and
  InSPyReNet the statistic is not even *measurable*, because per-image min-max
  normalization (in the demo, in `rembg`, and for InSPyReNet inside
  `forward_inference` itself) destroys the scale — see §14's table for which models
  preserve it and which do not. Itti–Koch and Spectral Residual actively *invert* the
  signal: a bright blob on black is their ideal stimulus by design.
- **Compressed-file-size / JPEG-size complexity.** My probe shows its absolute scale
  is dominated by sensor noise, not content: a pure black frame at simulated ISO 1600
  scores 0.331 vs the crescent's 0.335 — indistinguishable — while the clean versions
  score 0.001 vs 0.001. No fixed threshold survives a mixed-ISO 42,000-image library.
- **Background-removal mask confidence.** RMBG-1.4's own official postprocessing
  min-max normalises the saliency map, which on a near-blank frame **rescales noise to
  full range and manufactures a confident mask out of nothing**
  (<https://huggingface.co/briaai/RMBG-1.4/raw/main/README.md>). Mask *area and geometry*
  read from pre-normalisation logits may be salvageable; confidence is not. Also note
  RMBG-1.4/2.0 are **non-commercial**, and RMBG-2.0 is rembg's silent default.
- **Anything keyed on photographic vocabulary.** CLIP-IQA's own limitations section
  states CLIP fails on "professional terms that are relatively uncommon in human
  conversations, such as *Long exposure*, *Rule of thirds*, *Shallow DOF*"
  (<https://arxiv.org/html/2207.12396v2>, §3.3). "Negative space", "minimalism" and
  "low-key" are the same class of term. Do not write a prompt containing them.
- **Negation in prompts.** VLMs perform "at chance level" on negation
  (<https://arxiv.org/abs/2501.09425>). Phrase the reject pole positively.

---

## Comparison table

| Technique | Output | Separates A from B? | Open weights | Size | 42k on Apple Silicon CPU |
|---|---|---|---|---|---|
| **Salient Object Subitizing (SOS)** | P(0,1,2,3,4+) salient objects | **Yes — this is literally the task**; 0-class recall ~93%, human-level | Data yes, weights no (Caffe-era, dead link) | GoogleNet, ~7M params | Would need retraining; as a CLIP head, ~free |
| **CLIP head trained on presence labels** | scalar / class | **Likely yes** [INFERENCE — but grounded in a validated label set] | n/a (we train it) | ~1k–500k params | **Free** — embeddings already computed |
| **CLIP-IQA `Complex/Simple` prompt pair** | scalar 0–1 | **Probably, weakly.** ~80% human agreement on complex/simple; but zero-shot CLIP SRCC on the art-theoretic multiplicity/unity axis is **0.06** | Yes | 2 text encodes, cached forever | **Free** — dot product against existing embeddings |
| **Lit-area fraction on 8x-downsampled frame** | scalar % | **Yes — 0.72% vs 11.4% in my probe, noise-invariant** | n/a (10 lines) | 0 | Seconds for the whole library |
| **Compressed-size complexity (zip/JPEG)** | ratio 0–1 | **Ordering yes, absolute threshold no** — noise-dominated | n/a | 0 | Minutes; but unusable as a global threshold |
| **MegaDetector (empty-image gate)** | boxes + confidence, animal/person/vehicle | **Partially** — proven "is anything here" gate, but closed vocabulary; would reject the Statue | Yes | YOLOv5-based | **Practical**: 1.85 img/s on M1 MBP → ~6.3h; 4.61 img/s on M3 → ~2.5h |
| **Saliency mass/peak — U²-Net, BASNet, InSPyReNet** | saliency map | **No — not even measurable.** Per-image min-max normalization (and input auto-gain) destroys the scale | Yes, Apache-2.0/MIT | 4.7MB (u2netp) / 176MB (u2net) | Yes, but pointless |
| **Saliency mass/peak — PoolNet, TRACER** | absolute sigmoid map, no stretch | **Measurable but expect it to fail** — trained on DUTS where every image has a subject | Yes, MIT/Apache-2.0 | ResNet-50 / EfficientNet class | Yes |
| **Itti–Koch, Spectral Residual** | relative contrast map | **No — inverts.** A bright blob on black is their *ideal* stimulus | Yes (OpenCV) | zero weights | Trivially fast |
| **Islam et al. rank+subitizing net** | mask + rank + subitizing | **Plausibly yes** — modern PyTorch subitizing | Yes, reimpl available | not established | not established |
| **OWLv2 class-agnostic objectness** | per-patch objectness logit, no class list needed | **Most promising untested candidate** | Yes, Apache-2.0 | 155M (base) / 438M (large) | Untimed on CPU |
| **rembg / BiRefNet / RMBG mask confidence** | mask; soft map if used directly | **No** — high confidence on both; min-max normalisation manufactures masks on blank frames | Yes (RMBG **non-commercial**) | 4.6MB (u2netp) → 1GB (RMBG-2.0) | u2netp yes; RMBG-2.0 ~10h+ |
| **Same models, mask area + shape from pre-normalisation logits** | area, compactness | **Plausibly yes** [INFERENCE] | Yes | as above | Yes with u2netp/BiRefNet-lite |
| **SAM `predicted_iou` / `stability_score`** | mask quality scores | **No — inverted.** The emptiest frame scores best | Yes, Apache-2.0 | 38.8MB (MobileSAM) → 2.4GB (ViT-H) | Automatic mode ~175× YOLO11n cost — no |
| **SAM mask count + area histogram** | count | Plausibly yes [INFERENCE] but unaffordable | Yes | as above | No |
| **COCO detector (YOLO11n, DETR) detection count** | boxes | **No — rejects both.** −32pt day→night gap | Yes (Ultralytics **AGPL-3.0**; DETR Apache-2.0) | 2.6M–41.6M | **Yes, ~39 min** for 42k (YOLO11n CPU ONNX) |
| **Grounding DINO** | boxes | Ruled out on cost | Yes, Apache-2.0 | 172M–233M | **No** — 15 s/img on CPU ≈ 175 hours |
| **IC9600 / ICNet complexity** | scalar 0–1 + complexity map | Plausible but untested on dark frames [INFERENCE] | Weights on Google Drive, dataset by application | ResNet18 dual-branch | Practical (ResNet18-class) |
| **Negative-space / minimalism / low-key classifier** | — | **Does not exist.** See negative findings | — | — | — |

---

## Per-technique detail

### 1. Salient Object Subitizing — the one that is actually about this

**Zhang, Ma, Sameki, Sclaroff, Betke, Lin, Shen, Price, Mech.** "Salient Object
Subitizing." CVPR 2015; extended IJCV 2017. <https://arxiv.org/abs/1607.07525> ·
<https://openaccess.thecvf.com/content_cvpr_2015/html/Zhang_Salient_Object_Subitizing_2015_CVPR_paper.html>

The abstract states the task directly: "predicting **the existence** and the number of
salient objects in an image using holistic cues … we achieve prediction accuracy
comparable to human performance in identifying images with **zero** or one salient
object" (<https://arxiv.org/abs/1607.07525>).

Facts that matter to us, all from <https://arxiv.org/html/1607.07525v1>:

- **Dataset:** SOS, ~14K everyday images (expanded from ~7K in the CVPR version),
  drawn from SUN, VOC07, COCO and ImageNet, each labelled 0/1/2/3/4+ by AMT workers
  (§3). SUN was deliberately capped at 5,000 images "because most images in this
  dataset do not contain obviously salient objects, and we do not want the images from
  this dataset to dominate the category for background images" (§3) — i.e. the empty
  case is a curated, balanced class, not an afterthought.
- **The 0 class is real and reliable.** Human offline subitizing agreement with the AMT
  labels is 90% for category 0 (§3); the CNN's recall on category 0 is "about 93% …
  close to the human accuracy for these categories" (§5). Category-0 AP is
  ~93.6–93.8% (§5, Table 3).
- **Ambiguous images were excluded**, not forced: "A few images do not have a clear
  notion about what should be counted as an individual salient object, and labels on
  those images tend to be divergent… We exclude images with fewer than four consensus
  labels" (§3). Relevant to us: human raters themselves disagree on marginal presence,
  so a hard binary gate will always have a contested band. Design for a
  three-way *reject / uncertain / judge* outcome rather than a threshold.
- **It was used as a gate.** "For salient object detection, our SOS model can
  effectively suppress false object detections on background images and estimate a
  proper number of detections. By leveraging the SOS model, we attain an absolute
  increase of about 4% in F-measure" (§1). This is a published precedent for the exact
  pipeline shape we want: presence gate → judge.
- **Architecture:** fine-tuned GoogleNet, 5-way softmax head (§4). AlexNet is
  "significantly worse"; VGG16 ≈ GoogleNet (§5, Table 4).
- **Synthetic pre-training works and cuts label needs.** Cut-and-paste synthetic images
  (N cutouts pasted on SUN backgrounds) pre-trained then fine-tuned gives +2% AP on the
  2/3/4+ classes and lets 25% of the real data reach 76% mAP (§4.1, §5, Table 5).
  **[INFERENCE]** For us this means a presence head can be bootstrapped cheaply — and
  we could synthesise our own dark-frame training pairs (crescent-on-black vs
  lit-subject-on-black) at near-zero cost.

**Does it separate A from B?** This is the task definition, so by construction: a
crescent moon is one bright blob with no object structure and, per the SUN-derived
"background image" notion, is the paradigm 0-case; a lit statue is the paradigm
1-salient-object case. **[INFERENCE]** — I found no evaluation of SOS on night
photography specifically, so I cannot cite this. The risk is that the model was trained
on well-exposed everyday images and may simply score all dark frames as 0.

**Follow-ons worth knowing:**
- He, Jiao, Zhang, Han, Lau. "Delving Into Salient Object Subitizing and Detection."
  ICCV 2017. <https://openaccess.thecvf.com/content_iccv_2017/html/He_Delving_Into_Salient_ICCV_2017_paper.html>
- "Weakly-Supervised Saliency Detection via Salient Object Subitizing", TCSVT,
  <https://arxiv.org/pdf/2101.00932.pdf>

### 2. "What is and what is not a salient object?" — XPIE

**Xia, Li, Chen, Wang, Duan.** CVPR 2017.
<https://openaccess.thecvf.com/content_cvpr_2017/html/Xia_What_Is_and_CVPR_2017_paper.html>

Its XPIE dataset was annotated in two stages: stage one assigns a **binary label for
whether the image contains a clear object at all**, yielding 21,002 "yes" and **8,598
"no"** images out of ~29,600; only the "yes" subset (10,000 images) got masks
(dataset card: <https://github.com/lartpang/awesome-segmentation-saliency-dataset>).

That 8,598-image "no clear object" set is a second, independent source of
negative labels for a presence head, and it is a *human* judgement of presence rather
than a derived statistic.

### 3. SOC — the benchmark that admits the empty case exists

**Fan, Cheng, Liu, Gao, Hou, Borji.** "Salient Objects in Clutter: Bringing Salient
Object Detection to the Foreground." ECCV 2018.
<https://arxiv.org/abs/1803.06091>

The abstract is the citation we want for *why the exposure framing and the standard SOD
framing both fail us*: "Our analysis identifies a serious design bias of existing SOD
datasets which assumes that each image contains at least one clearly outstanding
salient object in low clutter. The design bias has led to a saturated high performance
for state-of-the-art SOD models when evaluated on existing datasets. The models,
however, still perform far from being satisfactory when applied to real-world daily
scenes… our SOC (Salient Objects in Clutter) dataset, includes images with salient
**and non-salient** objects from daily object categories."
(<https://arxiv.org/abs/1803.06091>)

So the entire SOD benchmark tradition *assumes* a subject exists. Any off-the-shelf SOD
model is therefore trained and tuned under that assumption, which is a strong prior
reason to distrust its output on our Case A. See §10 below for the per-model
consequences.

**The extended TPAMI version is the better citation and it contains a detail that is
almost too on-the-nose for us.** <https://arxiv.org/abs/2105.03053> (TPAMI 2022) restates
the bias — "a serious design bias of existing salient object detection (SOD) datasets,
which unrealistically assume that each image should contain at least one clear and
uncluttered salient object" — and then describes how SOC's **non-salient half** was
constructed (<https://ar5iv.labs.arxiv.org/html/2105.03053>):

> non-salient = "images without salient objects or images with 'stuff' categories…
> (a) densely distributed similar objects, (b) fuzzy shapes, and (c) regions without
> semantics"

built from "**783 texture images from the DTD dataset**" plus "**2,217 images including
aurora, sky, crowds, store and many other kinds of realistic scenes**", giving a 3,000
non-salient / 3,000 salient split.

**"Aurora, sky" is our Case A.** A published SOD benchmark has already decided that a
sky frame contains no salient object, and has 2,217 such images labelled. That is both a
validation of our framing and a directly usable negative-label source for the presence
head recommended above. It also means these images are a *held-out corrective set* —
the shipped SOD/matting models did not train on them.

### 4. CLIP-IQA antonym prompt pairs

**Wang, Chan, Loy.** "Exploring CLIP for Assessing the Look and Feel of Images."
AAAI 2023. <https://arxiv.org/abs/2207.12396> · code <https://github.com/IceClear/CLIP-IQA>

This is the load-bearing citation for "prompt-pair comparison on CLIP embeddings is a
documented, validated technique". Method, from <https://arxiv.org/html/2207.12396v2> §2.1:

- A single prompt's absolute cosine similarity is unreliable because of linguistic
  ambiguity — their examples: "a *clean* image" could mean noise-free or literally
  cleaned; "a *rich* image" could mean rich content or wealth. "using CLIP with a
  single prompt shows poor correlation with human perception on common IQA datasets."
- Fix: take an antonym pair `t1`, `t2`, compute cosine similarity `s_i` for each, and
  softmax over the two:

  ```
  s̄ = e^{s1} / (e^{s1} + e^{s2})
  ```

  "the ambiguity of one prompt is reduced by its antonym as the task is now cast as a
  **binary classification**, where the final score is regarded as a **relative
  similarity**."

  **Important implementation detail the paper's equation hides: every real
  implementation multiplies the cosines by CLIP's ~100× logit scale first.** Verified in
  all three:
  torchmetrics — `logits_per_image = 100 * img_features @ anchors.t()`
  (<https://raw.githubusercontent.com/Lightning-AI/torchmetrics/master/src/torchmetrics/functional/multimodal/clip_iqa.py>);
  piq — `self.logit_scale = self.feature_extractor.logit_scale.exp()`
  (<https://raw.githubusercontent.com/photosynthesis-team/piq/master/piq/clip_iqa.py>);
  IQA-PyTorch — `logit_scale = self.logit_scale.exp()`
  (<https://raw.githubusercontent.com/chaofengc/IQA-PyTorch/main/pyiqa/archs/clip_model.py>).
  CLIP's trained temperature is pinned at that ceiling — it was "clipped to prevent
  scaling the logits by more than 100" (<https://arxiv.org/html/2103.00020v1>, §2.5),
  independently confirmed as τ = 1/100 by
  <https://ar5iv.labs.arxiv.org/html/2203.02053>.

  **Consequence, and it is the opposite of what I initially assumed.** The score is
  `σ(100·Δcos)`. Arithmetic (mine, not cited): Δcos = 0.005 → 0.62; 0.01 → 0.73;
  0.02 → 0.88; 0.05 → 0.99; 0.10 → 0.99995. **The failure mode is near-binary
  saturation, not compression toward 0.5** — the score is effectively a hard `sign()` of
  a tiny, backbone-dependent, prompt-dependent cosine difference, hypersensitive to
  ~0.01 of noise. There is no usable middle of the scale in which to place a cut. This
  makes a hardcoded absolute threshold *worse*, not better.
- Second modification: remove the learnable positional embedding so arbitrary-sized
  inputs are accepted, and use the **ResNet-50** CLIP variant (the ViT variant "shows
  better performance than the ResNet variant *with* the positional embedding" but drops
  significantly when it is removed) (§3.2). **Practically important for us:** since we
  already have standard ViT embeddings computed at 224×224 with positional embeddings
  intact, we are in the configuration the paper says is the *stronger* one for ViT — we
  just don't get resolution sensitivity, which we don't need.

Validated prompt pairs (§Appendix Table 3/4): brightness `["Bright photo.", "Dark
photo."]`, noisiness `["Clean photo.", "Noisy photo."]`, colorfulness, sharpness,
contrast; and five abstract attributes including **complex/simple `["Complex photo.",
"Simple photo."]`**, natural/synthetic, happy/sad, scary/peaceful, new/old.

**The complex/simple result is the directly relevant one.** §2.3: for each of the five
abstract attributes they ran a user study — 15 image pairs per attribute, 25 subjects
each, subjects asked which image better matches the description — and "CLIP-IQA
achieves an accuracy of about 80% on all five attributes". Fig. 6's caption calls out
`"Complex/Simple"` by name as evidence CLIP-IQA "is able to understand abstract
perception".

Reported quality numbers for context: zero-shot CLIP-IQA is "comparable to BRISQUE and
surpasses all other non-learning methods" on KonIQ-10k, LIVE-itW and SPAQ, and beats
CNNIQA which *was* trained on annotations; CoOp-tuned CLIP-IQA+ reaches SROCC/PLCC
0.895/0.909 (KonIQ-10k), 0.805/0.832 (LIVE-itW), 0.864/0.866 (SPAQ) (§2.2, Table 1).

**Prompt brittleness is documented and material.** §3.1: the template matters —
`"[text] photo."` vs `"A photo of [text]."` vs `"There is [text] in the photo."` give
"noticeable differences"; and the adjective matters — `Good/Bad` beats `High
quality/Low quality` and `High definition/Low definition`, from which they conjecture
"poorer performance of uncommon adjectives". §3.3 lists prompt sensitivity as
limitation #1 and, limitation #2, that CLIP cannot handle professional photographic
terms — "*Long exposure*", "*Rule of thirds*", "*Shallow DOF*".

**Library support:** torchmetrics ships this as
`CLIPImageQualityAssessment` /
`clip_image_quality_assessment`
(<https://lightning.ai/docs/torchmetrics/stable/multimodal/clip_iqa.html>). Its source
(<https://raw.githubusercontent.com/Lightning-AI/torchmetrics/master/src/torchmetrics/functional/multimodal/clip_iqa.py>)
contains the full built-in `_PROMPTS` dict — including
`"complexity": ("Complex photo.", "Simple photo.")` — and `_clip_iqa_format_prompts`
accepts **arbitrary user-defined 2-tuples**, documented in its own docstring:

```python
>>> _clip_iqa_format_prompts(("quality", ("Super good photo.", "Super bad photo.")))
(['Good photo.', 'Bad photo.', 'Super good photo.', 'Super bad photo.'],
 ['quality', 'user_defined_0'])
```

so custom presence pairs need no new code. Selectable backbones include
`openai/clip-vit-base-patch16`, `-patch32`, `clip-vit-large-patch14` — likely already
matching whatever we computed.

**The serious caveat: WP-CLIP.** Ghildyal, Wang et al. "WP-CLIP: Leveraging CLIP to
Predict Wölfflin's Principles in Visual Art." ICCV 2025 Workshops.
<https://arxiv.org/abs/2508.12668> · <https://github.com/abhijay9/wpclip>

They explicitly test CLIP-IQA's antonym-pair method on Wölfflin's five art-theoretic
axes, one of which — **Multiplicity vs Unity** — is the art-theory version of "how many
distinct things are in this frame". Result (Table 2, SRCC,
<https://arxiv.org/html/2508.12668v1>):

| Axis | CLIP | CLIP-IQA | WP-CLIP (fine-tuned) |
|---|---|---|---|
| Absolute-Relative | -0.06 | -0.02 | 0.54 |
| Closed-Open | -0.04 | -0.04 | 0.39 |
| Linear-Painterly | 0.05 | -0.10 | 0.57 |
| **Multiplicity-Unity** | **0.06** | **-0.04** | **0.30** |
| Planar-Recessional | 0.06 | 0.06 | 0.33 |

Their conclusion: "these principles are not inherently captured in the data that CLIP
was trained on… Despite being a foundation model trained on a large-scale vision and
language dataset, CLIP shows **no correlation** with Wölfflin's pairs" (§3.3). And
"**Multiplicity versus Unity was the most challenging principle for both models**" —
worst even after fine-tuning, and worse than Gemini-2.5-pro managed either (§4.2).

**How to reconcile this with the ~80% complex/simple result.** They measure different
things: CLIP-IQA's user study is pairwise-forced-choice on *hand-selected extreme
photo pairs*, whereas WP-CLIP is rank correlation across a *full distribution of
paintings*. **[INFERENCE]** The honest read is that `Complex/Simple` captures a coarse,
real signal at the extremes and essentially nothing in the middle. Our Case A vs Case B
is plausibly an extreme pair — near-empty vs structured — which is the regime where it
works. But it will not give us a calibrated continuous presence score, and it should
not be the sole gate.

**Concrete prompt pairs worth trying**, ranked, all **[INFERENCE]** — nothing is
published for presence (see §13).

The key design principle, which follows directly from the negation and counting
citations: **both poles must positively describe something concrete.** Never phrase the
reject pole as an absence.

1. `("an illuminated building at night", "the moon in the night sky")` — **most likely
   to work**, because it is pure entity discrimination, which is CLIP's core competence.
   But it is bespoke: it solves *this* pair, not legibility in general, and will misfire
   on a lit tree, a campfire, a neon sign.
2. `("a detailed photograph with visible textures and surfaces", "a single small bright
   point of light in darkness")` — **the best general framing.** It reads as scene-type
   discrimination (CLIP is strong on SUN397, 59.6 → 68.4 across backbones,
   <https://arxiv.org/html/2103.00020v1> Table 11) rather than counting, and the reject
   pole names a concrete visual configuration instead of an absence.
3. `("a photograph of a recognizable landmark or structure", "a photograph of the empty
   night sky")` — mid confidence; "empty" edges toward absence.
4. `("Complex photo.", "Simple photo.")` — the only pair with *any* published
   validation (~80% human agreement, §4), but see the WP-CLIP SRCC of −0.04 on the
   multiplicity-unity axis. Include it as a baseline, don't rely on it.
5. **Ensemble 4–6 pairs and average the probabilities**, following IQA-PyTorch's
   documented practice. Single-pair variance is the documented weak point.

**Do not use:**

- `("a photo with a subject", "a photo with no subject")`, `"an empty photo"`, `"a photo
  containing nothing"` — negation and absence prompts, at chance per NegBench.
- `("Good photo.", "Bad photo.")` and the rest of the CLIP-IQA quality ladder — wrong
  axis entirely. Both our frames are technically *well* exposed for what they are.
- Anything containing a number or quantity word — CLEVRCounts/CountBench are the reason.
- Anything containing photographic jargon — CLIP-IQA §3.3 is the reason.

### 5. AADB — human-labelled `object_emphasis`, the best off-the-shelf presence labels

**Kong, Shen, Lin, Mech, Fowlkes.** "Photo Aesthetics Ranking Network with Attributes
and Content Adaptation." ECCV 2016. <https://arxiv.org/abs/1606.01621> ·
<https://github.com/aimerykong/deepImageAestheticsAnalysis>

AADB: 10,000 images (8,500 train / 500 val / 1,000 test), each with an overall
aesthetic score **and eleven human-rated attributes** from five raters each, attributes
chosen "after consulting professional photographers"
(<https://ar5iv.labs.arxiv.org/html/1606.01621>):

`interesting_content`, `object_emphasis`, `good_lighting`, `color_harmony`,
`vivid_color`, `shallow_depth_of_field`, `motion_blur`, `rule_of_thirds`,
`balancing_element`, `repetition`, `symmetry`.

Two of these are presence signals, with the paper's own definitions:

- **"object emphasis" — "whether the image emphasizes foreground objects"**
- **"content" — "whether the image has good/interesting content"**

This is a public, human-rated, per-image regression target for approximately the thing
we want, and it is orthogonal to `good_lighting`, so a model trained on
`object_emphasis` is *by construction* not an exposure detector.

**Does it separate A from B?** **[INFERENCE]** A crescent on black should score low on
both `object_emphasis` and `content`; a lit statue should score high on
`object_emphasis`. Untested — AADB is Flickr Creative Commons imagery and I found no
breakdown by illumination.

Licensing caution: the repo notes "the patent US20170294010A1 discourages
considerations of commercial use" and "all the images are downloaded from flickr with
Creative Commons license, so the dataset is for research purpose only"
(<https://raw.githubusercontent.com/aimerykong/deepImageAestheticsAnalysis/master/README.md>).
Training on it for a personal tool is fine; shipping a model trained on it is a legal
question, not a technical one.

### 6. MegaDetector — the industrial-scale precedent for "is anything here?"

<https://github.com/agentmorris/MegaDetector> ·
<https://microsoft.github.io/MegaDetector/>

Camera-trap ecology has been solving our problem at enormous scale for years. The
README describes MegaDetector as a model that "identifies animals, people, and vehicles
in camera trap images (**which also makes it useful for eliminating blank images**)"
(<https://raw.githubusercontent.com/agentmorris/MegaDetector/main/README.md>). Its whole
value proposition is that reviewers' time "is spent reviewing images they aren't
interested in. This primarily includes **empty images**"
(<https://raw.githubusercontent.com/agentmorris/MegaDetector/main/megadetector.md>).

Reported accuracy from independent evaluations collated in the docs
(<https://raw.githubusercontent.com/agentmorris/MegaDetector/main/megadetector.md>):

- WildEye 2022: MDv5a 99.2% animal recall @ 97.26% precision; MDv5b 99.1% @ 98.76%.
- Pestell et al., *Ecosphere* 2025: 99% precision @ 98% recall for MDv5a.
- Zampetti et al., *MEE* 2024: 98% precision @ 90% recall.
- Fennell et al., *GECCO* 2022: 95% precision @ 92% recall for animals.

**Apple Silicon CPU/GPU feasibility — this is the best hard data I found for our
constraint**, straight from the docs:

- 2024 M3 MacBook Pro (18 GPU cores): **4.61 img/s** → 42,000 images in **~2.5 hours**.
- 2020 M1 MacBook Pro (8 GPU cores): **1.85 img/s** → 42,000 images in **~6.3 hours**.
- Intel i7-13700K, single core: 0.8 img/s (~69,000 images/day).
- Architecture is YOLOv5-based since MDv5 (was Faster-RCNN in MDv4).

**[INFERENCE]** A YOLOv5-class detector at ~2–6 hours for the whole library is
comfortably within budget, and this tells us the *scale* question is settled for any
model of that size — the open question is only accuracy on dark frames.

**Why it isn't our answer directly:** its vocabulary is animal/person/vehicle. It would
reject the Statue of Liberty. It is a precedent and a performance benchmark, not a
candidate. Also note the docs' warning that confidence ranges are not comparable
across versions: "be aware that the range of confidence values produced by MDv5 is very
different from the range of confidence values produced by MDv4! Don't use your MDv4
confidence thresholds with MDv5!" — a general caution against porting thresholds
between models, which applies to every threshold we set.

Night behaviour: MDv4's release notes mention adding "images of humans in both daytime
and **nighttime**" to training, so illumination robustness was explicitly worked on,
but I found **no published per-illumination accuracy breakdown**. Per-dataset results
are at <https://lila.science/megadetector-results-for-camera-trap-datasets/>.

### 7. Image complexity as "enough to judge"

#### IC9600 / ICNet — the modern learned complexity model

**Feng, Zhai, Yang, Liang, Fan, Zhang, Shao, Tao.** "IC9600: A Benchmark Dataset for
Automatic Image Complexity Assessment." IEEE TPAMI 2023, doi
10.1109/TPAMI.2022.3232328. <https://github.com/tinglyfeng/IC9600> ·
<https://ieeexplore.ieee.org/document/9999482>

From the repo README
(<https://raw.githubusercontent.com/tinglyfeng/IC9600/master/README.md>):

- 9,600 images, complexity annotated by **17 annotators** on a 1–5 scale, averaged and
  normalised to [0,1].
- **ICNet** has two branches modified from a **ResNet18** — a detail branch on the
  high-resolution image and a context branch on a smaller image — concatenated into
  two heads: a **complexity map** head and a **scalar score** head, plus a "spatial
  layout attention module (SLAM)".
- Off-the-shelf inference script `gene.py` emits, per image, an `.npy` complexity map
  named with the scalar score, plus a blended visualisation PNG.
- Weights: Google Drive link in the README. Dataset: by application via Google Drive,
  "for academic usage".

**[INFERENCE]** A ResNet18-class dual-branch model is very comfortable on Apple Silicon
CPU for 42,000 images — MegaDetector's YOLOv5 numbers above are the right order of
magnitude. Availability is the friction: Google Drive weights, application-gated
dataset, and no HuggingFace mirror I could find.

**Does it separate A from B?** Plausibly — a near-empty frame is low-complexity by
construction, a lit structure with folds and a crown is not. **[INFERENCE]**: untested
on night imagery, and the complexity map output would tell us *where* the content is,
which is more useful than the scalar. Worth a spike but behind the CLIP options
because the weights are harder to obtain and it needs a real forward pass.

#### The compressed-file-size trick — and why I now think it fails for us

Primary sources for the technique, via the `imagefluency` R package's documentation
(<https://imagefluency.com/reference/img_complexity.html>), which is the cleanest
statement of the method I found:

- "Visual complexity is calculated as **ratio between the compressed and uncompressed
  image file size**… Values can range between almost 0 (virtually completely compressed
  image, thus extremely simple image) and 1 (no compression possible, thus extremely
  complex image)." Algorithms offered: `zip` (deflate, default), `jpg`, `gif`, `png`.
- Worked example in the docs: a `trees.jpg` image scores **0.8949686**; a `sky.jpg`
  image is given as the low-complexity counterexample.
- Note the optional `rotate` argument, because "most compression algorithms do not
  depict horizontal and vertical redundancies equally" — a real methodological wrinkle.
- Cited primary literature: **Donderi, D. C. (2006). "Visual complexity: A Review."
  *Psychological Bulletin*, 132, 73–97**, doi
  <https://doi.org/10.1037/0033-2909.132.1.73>; **Forsythe, Nadal, Sheehy, Cela-Conde
  & Sawey (2011). "Predicting Beauty: Fractal Dimension and Visual Complexity in Art."
  *British Journal of Psychology*, 102, 49–70**, doi
  <https://doi.org/10.1348/000712610X498958>; **Mayer & Landwehr (2018). "Quantifying
  Visual Aesthetics Based on Processing Fluency Theory: Four Algorithmic Measures for
  Antecedents of Aesthetic Preferences." *Psychology of Aesthetics, Creativity, and the
  Arts*, 12(4), 399–431**, doi <https://doi.org/10.1037/aca0000187> — the last is
  cited specifically as "a discussion of different image compression algorithms for
  measuring visual complexity."

I could not retrieve the Donderi or Forsythe abstracts directly (paywalled at PsycNET
and Wiley; `psycnet.apa.org/record/2006-00818-005` and
`bpspsychub.onlinelibrary.wiley.com/doi/10.1348/000712610X498958` both returned nothing
extractable). The `imagefluency` docs are a secondary but authoritative-enough
statement of what those papers established.

#### My own probe: compression ratio does not survive sensor noise; lit-area does

Because the noise confound is the whole question for night photography, I ran it rather
than inferring it. Script:
`scratchpad/complexity_probe.py`. Synthetic 1024×1024 grayscale frames: a flat black
control, a crescent-on-black (Case A), and a "lit structure in darkness" stand-in
(Case B: lit pedestal with stonework lines, tapering robe with sinusoidal folds, head,
raised arm, torch, crown spikes; everything else at value 2). Gaussian noise at σ=0 /
4 / 12 stands in for clean / ISO 1600 / ISO 12800.

Full-resolution statistics:

| case | zip ratio | JPEG q90 KB | histogram entropy | % px > 16 |
|---|---|---|---|---|
| flat_black / clean | 0.0010 | 12.3 | 0.000 | 0.00 |
| flat_black / iso1600 | 0.3311 | 106.1 | 2.141 | 0.00 |
| flat_black / iso12800 | 0.4705 | 293.2 | 3.136 | 9.10 |
| **crescent (A) / clean** | 0.0013 | 15.1 | 0.050 | 0.57 |
| **crescent (A) / iso1600** | 0.3345 | 108.6 | 2.196 | 0.57 |
| **crescent (A) / iso12800** | 0.4753 | 295.7 | 3.198 | 9.62 |
| **lit structure (B) / clean** | 0.0043 | 31.4 | 0.854 | 10.98 |
| **lit structure (B) / iso1600** | 0.4893 | 155.5 | 3.755 | 11.00 |
| **lit structure (B) / iso12800** | 0.5845 | 327.6 | 4.367 | 21.79 |

Same statistics after an 8× box-average downsample (averaging suppresses i.i.d. sensor
noise by ~√64 = 8× while preserving structure):

| case | zip ratio | entropy | % px > 16 |
|---|---|---|---|
| flat_black / clean | 0.0024 | 0.000 | 0.00 |
| flat_black / iso1600 | 0.1669 | 0.998 | 0.00 |
| flat_black / iso12800 | 0.3090 | 1.912 | 0.00 |
| **crescent (A) / clean** | 0.0121 | 0.094 | **0.72** |
| **crescent (A) / iso1600** | 0.1778 | 1.095 | **0.72** |
| **crescent (A) / iso12800** | 0.3207 | 2.003 | **0.72** |
| **lit structure (B) / clean** | 0.0381 | 1.020 | **11.38** |
| **lit structure (B) / iso1600** | 0.2424 | 2.056 | **11.38** |
| **lit structure (B) / iso12800** | 0.4123 | 2.995 | **11.41** |

Readings:

1. **The compression ratio's ordering is right but its absolute scale is
   noise-dominated.** Clean: A = 0.0013, B = 0.0043 — a 3.3× separation, but A is
   within 30% of a totally black frame (0.0010). At ISO 1600: A = 0.3345, flat black =
   0.3311 — **indistinguishable**, and both are 250× their clean values. Any threshold
   calibrated on clean frames labels every noisy black frame "complex". Across a
   42,000-image library shot at mixed ISO, a single global compression threshold cannot
   work. Same story for histogram entropy.
2. **Lit-area fraction is the robust statistic.** `% px > 16` on the downsampled frame
   is **0.72% for Case A and 11.38% for Case B, identical to two decimals at all three
   noise levels** — a ~16× separation that noise cannot touch, because box-averaging
   pulls noise below the threshold before it is counted. This is 10 lines of code and
   runs over the whole library in seconds.
3. **Downsampling first is the general lesson.** It rescues the compression measure's
   separation somewhat (A = 0.1778 vs black 0.1669 vs B = 0.2424 at ISO 1600) but does
   not fix its absolute scale. It fixes the threshold statistic completely.

Honest limitations of this probe: synthetic, grayscale, idealised i.i.d. Gaussian
noise, no demosaic/denoise pipeline, no banding, no real stars or sky gradient, one
instance per class. It establishes the *mechanism* of the noise confound, not the
error rate. And lit-area fraction is not a subject-presence measure — it is a
subject-*extent* measure, which is a refinement of exposure rather than an escape from
it. Its own failure modes, **[INFERENCE]**: a genuinely excellent minimalist frame (one
bird against a vast pale sky, a single lit window) has low lit area, and a Milky Way
astro shot has low lit area with high content. Use it to catch the obvious, not to
adjudicate the interesting.

### 8. Photographic-defect detection — where "intent" is quietly handled

**Yu, Shen, Lin, Mech, Barnes.** "Learning to Detect Multiple Photographic Defects."
WACV 2018. <https://arxiv.org/abs/1612.01635>

Seven defects, chosen "by consulting professional photographers and analyzing a large
amount of image editing data": **bad exposure**, bad white balance, over/under
saturation, noise, haze, undesired blur, **bad composition**
(<https://arxiv.org/html/1612.01635v5>, §1).

The important structural point for us: severity is a **human-annotated regression
target**, not a histogram rule. "we collected a large-scale dataset of user annotations
on seven common photographic defects, which allows us to evaluate algorithms by
measuring their consistency with human judgments… Unlike some existing single-defect
estimation methods that rely on low-level statistics and **may fail in many cases on
natural photographs**, our model is able to understand image contents and quality at a
higher level" (<https://arxiv.org/abs/1612.01635>). They report their model beats "an
average human from our user study".

**[INFERENCE]** This is the closest thing to an intent-aware exposure judgement in the
literature, and it works by *not asking about exposure*. A human annotator shown a
low-key Statue of Liberty rates "bad exposure" severity as low, because the question
was "is this exposure bad", not "is this dark". Our current rubric makes the opposite
mistake in the opposite direction: it asks "is this compositionally clean" and an empty
frame answers "maximally". **The lesson is that the fix may be a labelling fix, not a
model fix** — reframe the rubric question so that emptiness cannot score well, and/or
learn the mapping from human ratings rather than asserting it.

Related, weaker: "Photo Rater: Photographs Auto-Selector with Deep Learning"
(<https://arxiv.org/abs/2211.14420>) chains an IQA net, a blur classifier and an
aesthetics net — note the authors' own comment that they "discovered issues in the code
that produced figures 8 and 9". Not a source to lean on.

### 9. Wölfflin's unity/multiplicity — the art-theory framing of our axis

Worth knowing that our question has a name in art history. The NTIA/ITS Institute for
Telecommunication Sciences published a 2025 note by Margaret Pinson, "A Missing Factor
in NR Metrics: Object Size and Artistic Intent"
(<https://its.ntia.gov/research/qoe/video-quality-research/no-reference-metrics/artistic-intent/>),
reporting from a VQEG meeting that this line of work "presented insights into the value
of NR metrics for assessing **scales that do not assume a spectrum from good to bad**.
This article focuses on one of Wölfflin's factors that extends from **unity (single
object) to multiplicity (multiple objects)**." Her hypothesis: "unity vs multiplicity
(and other artistic factors) influence human perception of video impairments."

That phrase — *scales that do not assume a spectrum from good to bad* — is exactly the
diagnosis of our 9/10 bug. Our "compositional cleanliness" rubric is a good-to-bad
scale applied to something that is not a good-to-bad property.

The implementation is WP-CLIP (§4 above): fine-tuned CLIP-ViT-B/32 on 1,000
human-annotated real paintings (Jha et al.), tested on 800 GAN-generated ones,
per-principle MSE and SRCC reported. Weights/code at
<https://github.com/abhijay9/wpclip>. **Its multiplicity/unity SRCC of 0.30 is the
weakest of its five axes**, so this is a pointer to a vocabulary, not a usable model
for us.

### 10. Background removal / matting — mask area as presence

| Model | Params | Weight file | License |
|---|---|---|---|
| u2netp (rembg lite) | — | **4.57 MB** ONNX | Apache-2.0, <https://github.com/xuebinqin/U-2-Net> |
| silueta | — | 44.2 MB ONNX | as U-2-Net |
| u2net | — | 176.0 MB ONNX | as U-2-Net |
| isnet-general-use | — | 178.6 MB ONNX | <https://github.com/xuebinqin/DIS> |
| BRIA RMBG-1.4 | 44.08 M | ~176 MB fp32 | **non-commercial** |
| BRIA RMBG-2.0 | gated | **1,024 MB** ONNX | **non-commercial** |
| BiRefNet (swin_v1_large) | 220.70 M | 972.7 MB ONNX | **MIT** |
| BiRefNet-lite (swin_v1_tiny) | — | 224.0 MB ONNX | MIT |

Params from the HF API (e.g.
<https://huggingface.co/api/models/ZhengPeng7/BiRefNet>); file sizes from
`content-length` on the rembg release assets, model list at
<https://github.com/danielgatis/rembg#available-models>.

**Licensing landmine:** rembg's *default* model is `bria-rmbg` (RMBG-2.0), which is
non-commercial ("their weights are for only non-commercial use",
<https://github.com/ZhengPeng7/BiRefNet#acknowledgement>;
<https://bria.ai/bria-huggingface-model-license-agreement/>). A naive `rembg` install
silently picks up a non-commercial dependency, and it is ~1 GB. rembg itself is MIT.
BiRefNet is MIT and is the permissive equivalent. Flagging this because if this ever
moves beyond a personal tool the license split is worth a look from whoever owns OSS
review — I am not making a legal call here.

**There is no confidence output through rembg's API.** `remove()` returns a cutout;
`-om` returns the mask; `-ppm` thresholds it binary
(<https://github.com/danielgatis/rembg#rembg-i>). No score, logit or confidence anywhere
in the public surface. Used *directly*, RMBG-1.4/BiRefNet do emit a soft single-channel
probability map, and that raw map is the only quasi-confidence available.

**The most actionable finding in this whole slice: RMBG-1.4's official postprocessing
min-max normalises the map.** From the model card usage code
(<https://huggingface.co/briaai/RMBG-1.4/raw/main/README.md>):

```python
ma = torch.max(result); mi = torch.min(result)
result = (result - mi) / (ma - mi)
```

On a blank or near-blank frame the raw map is uniformly near zero, so this **rescales
noise to full range and manufactures a confident-looking mask out of nothing.** Any
presence heuristic built on these models must read the **pre-normalisation** logits or
it is reading amplified noise. This is the same trap as the compression-ratio noise
confound in §7 — an absolute-scale statistic destroyed by a normalisation step.

**These models have never been supervised on absence.** RMBG-1.4's published training
distribution is "Single main foreground object 51.42% / Multiple objects in the
foreground 48.58%" — summing to 100%
(<https://huggingface.co/briaai/RMBG-1.4/raw/main/README.md>). BRIA describes RMBG-1.4
as "a saliency segmentation model", so SOC's design-bias critique (§3) applies to it
directly. The model has literally never seen a no-subject image labelled as such.

**Nobody discusses the empty case.** Exhaustive `gh search issues` across
`danielgatis/rembg`, `ZhengPeng7/BiRefNet` and `facebookresearch/segment-anything` for
`blank image`, `empty mask`, `no object`, `black image`, `all white`, `hallucinate`,
`returns whole image`, `fully transparent` produced **zero on-point hits**. There is no
folk knowledge to lean on; this is unmapped territory requiring our own calibration.

**CPU feasibility:** rembg has a first-class CPU path (`pip install "rembg[cpu]"`,
<https://github.com/danielgatis/rembg#cpu-support>), but RAM is the binding constraint —
maintainer thread reports the process being killed at 4 GB and peaking at 6.5 GB on a
5000px image (<https://github.com/danielgatis/rembg/issues/175>). BiRefNet publishes only
A100 numbers: SwinL ONNX ~165 ms, SwinT ~93.8 ms at 1024×1024
(<https://github.com/ZhengPeng7/BiRefNet#model-zoo>). **[INFERENCE]** A 20–50× A100→M-series
CPU gap puts BiRefNet-SwinL in seconds per image, i.e. 10+ hours for 42,000, likely
worse. Use u2netp (4.57 MB) or BiRefNet-lite if we go this route at all.

**Does it separate A from B?** **[INFERENCE], and the answer splits by which signal we
read.** A bright blob on a uniform dark field is the textbook maximum-saliency stimulus,
so the moon likely produces a *high-confidence, tiny-area, near-circular* mask and the
statue a *high-confidence, larger, elongated, structurally complex* mask. So **mask
area plus mask geometry (compactness / solidity) plausibly separates them; mask
confidence does not.** The usable discriminator here is geometric, not confidence-based.

### 11. SAM — confidence heads that point the wrong way

**Kirillov et al.** "Segment Anything." <https://arxiv.org/abs/2304.02643>

Precise definitions, from the code:

- **`predicted_iou`** — "The model's own prediction of the mask's quality. This is
  filtered by the `pred_iou_thresh` parameter"
  (<https://github.com/facebookresearch/segment-anything/blob/main/segment_anything/automatic_mask_generator.py>).
  It estimates IoU against the unknown ground truth — a *quality* estimate for a mask
  already assumed to exist, **not** a probability that an object exists.
- **`stability_score`** — exact code at
  <https://github.com/facebookresearch/segment-anything/blob/main/segment_anything/utils/amg.py>:

  ```python
  intersections = (masks > (mask_threshold + threshold_offset)).sum(-1).sum(-1)
  unions        = (masks > (mask_threshold - threshold_offset)).sum(-1).sum(-1)
  return intersections / unions
  ```

  i.e. IoU between the mask thresholded at `+offset` and at `−offset`. Paper wording:
  "we consider a mask stable if thresholding the probability map at 0.5−δ and 0.5+δ
  results in similar masks" (§4).

**`SamAutomaticMaskGenerator` defaults:** `points_per_side=32` (so 1,024 grid points),
`points_per_batch=64`, **`pred_iou_thresh=0.88`**, **`stability_score_thresh=0.95`**,
`stability_score_offset=1.0`, `box_nms_thresh=0.7`, `crop_n_layers=0`,
`min_mask_region_area=0`.

**Masks per image:** SA-1B is "11M images and 1.1B masks" (paper datasheet), so
**exactly 100 masks/image on average** (derived). With filtering removed and a denser
grid the paper reports ~900–950 masks/image, so the default ~100 is an artefact of the
0.88/0.95 filters rather than of image content.

**SAM is architecturally incapable of saying "nothing here."** The paper states the
design goal outright: "**our aim is to always predict a valid mask for any prompt even
when the prompt is ambiguous**" (§3). Every grid point yields three masks; there is no
objectness or abstain path. Also telling — the appendix records that Meta had to add a
filter because "occasionally an automatic mask would cover the entire image. These masks
were generally uninteresting, and we filtered them by removing masks that covered 95% or
more of an image."

**Does it separate A from B? No — it inverts.** **[INFERENCE]**, no citation found: on a
crescent moon SAM should return a *small number of masks with high `predicted_iou` and
very high `stability_score`*, because a bright disc on a flat field is the easiest
possible segmentation. **The emptiest image scores most confident.** Both confidence
heads are actively misleading for this decision. The plausibly-usable signal is **mask
count and the mask-area histogram** after default filtering — moon ⇒ ~1–3 masks (one
tiny, possibly one near-whole-image); statue ⇒ many masks at multiple scales.

**Cost rules it out anyway.** Checkpoints: ViT-H 2.39 GiB, ViT-L 1.16 GiB, ViT-B 358 MiB
(`content-length` on `dl.fbaipublicfiles.com/segment_anything/…`). Lighter variants:
MobileSAM **38.8 MiB**, "more than 60 times smaller yet performs on par", "~10ms per
image", "~5 times faster than the concurrent FastSAM and 7 times smaller", and — the
only first-party CPU claim found anywhere in this survey — "**MobileSAM can run
relatively smoothly on CPU**" (<https://arxiv.org/abs/2306.14289>). EfficientSAM ViT-T
~41 MB; SAM 2.1 hiera-tiny 38.96 M params / 91.2 FPS on A100
(<https://github.com/facebookresearch/sam2#model-description>). SAM and SAM 2 are
Apache-2.0. But automatic mode runs the decoder over 1,024 grid points per image;
**[INFERENCE]** even at MobileSAM's GPU figures this is the most expensive option
surveyed, roughly 175× YOLO11n, and impossible to justify for a binary flag.

**No Apple Silicon / MPS / CPU timings are published for SAM, SAM 2, BiRefNet, OWLv2 or
Grounding DINO.** Only Ultralytics publishes real CPU-ONNX latencies. Our 42k budget is
therefore only *firmly* established for the YOLO family.

### 12. Object detection as a presence test — and the dark-image trap

#### Open-vocabulary detectors

| Model | Params | License | Class-agnostic "any object" mode? |
|---|---|---|---|
| OWL-ViT B/32 | 153.23 M | Apache-2.0 | **No** — `grep -c objectness` on `modeling_owlvit.py` = 0 |
| **OWLv2 B/16 ensemble** | **154.97 M** | Apache-2.0 | **Yes, exposed** |
| OWLv2 L/14 ensemble | 437.61 M | Apache-2.0 | Yes |
| Grounding DINO tiny / base | 172.28 M / 232.81 M | Apache-2.0 | Text prompt always required |
| YOLO-World | — | **GPL-3.0**; Ultralytics packaging **AGPL-3.0** | Vocabulary required |
| DETR-ResNet-50 | 41.63 M | Apache-2.0 | 91-class COCO |

Params from the HF API, e.g.
<https://huggingface.co/api/models/google/owlv2-base-patch16-ensemble>.

**OWLv2's objectness head is real, exposed, and the only text-free per-patch presence
score in this entire survey.** In
<https://raw.githubusercontent.com/huggingface/transformers/main/src/transformers/models/owlv2/modeling_owlv2.py>:
`objectness_logits` of shape `(batch_size, num_patches, 1)`,
`self.objectness_head = Owlv2BoxPredictionHead(config, out_dim=1)`, docstring "Predicts
the probability that each image feature token is an object."

The caveat is in the paper (<https://arxiv.org/abs/2306.09683>), verbatim: "We introduce
an objectness head which predicts the likelihood that an output token actually
represents an object, and compute boxes, class scores, and losses only for the top k
tokens by objectness… **The objectness score predicts the future classification score of
a token and is supervised by the actual classification score of those tokens that end up
being selected**… We select approximately 10% of instances by top objectness during
training in all of our experiments. **During inference, all instances are used.**"

So objectness is *distilled from the text-conditioned classification score*, not
independently supervised on a class-agnostic "is-an-object" label. **[INFERENCE]** It
therefore inherits the vocabulary bias of the self-training pseudo-labels, and a
sky-only frame is out of its supervision distribution. Nonetheless it needs no class
list, is 155 M params, is Apache-2.0, and is **the most promising untested candidate in
this report after the CLIP head.**

**Grounding DINO is ruled out on cost.** No class-agnostic mode is documented (searched
`class agnostic`, `generic prompt`, `detect all objects`, `empty prompt`, `agnostic`,
`everything` in `IDEA-Research/GroundingDINO` — zero on-point hits). CPU is a hard
blocker: <https://github.com/IDEA-Research/GroundingDINO/issues/31> reports "Right now i
am getting **15s average inference time**", answered by maintainers with "we have not
explored it yet"; ONNX export is broken (`Exporting the operator ::__ior_ to ONNX opset
version 13 is not supported`). Further CPU-pain issues: #256, #21, #154, #404 (CPU batch
memory leak). **15 s × 42,000 ≈ 175 hours.**

#### Closed-vocabulary COCO detectors — the only clearly CPU-affordable option

Official Ultralytics CPU-ONNX latencies at 640 px
(<https://docs.ultralytics.com/models/yolo11/>):

| Model | mAP50-95 | **CPU ONNX (ms)** | Params (M) |
|---|---|---|---|
| YOLO11n | 39.5 | **56.1 ± 0.8** | 2.6 |
| YOLO11s | 47.0 | 90.0 ± 1.2 | 9.4 |
| YOLO11m | 51.5 | 183.2 ± 2.0 | 20.1 |
| YOLO11x | 54.7 | 462.8 ± 6.7 | 56.9 |

Derived: YOLO11n at 56.1 ms ⇒ **42,000 images ≈ 39 minutes single-threaded.** This is
the cheapest technique surveyed. But **Ultralytics is AGPL-3.0**; DETR-ResNet-50
(41.6 M, Apache-2.0) is the permissive fallback.

**The vocabulary problem kills it regardless.** COCO's 80 classes cover people, animals,
vehicles and household objects. Landscapes, architecture, sunsets, texture, weather and
astronomy are entirely absent. **[INFERENCE]** "0 detections ⇒ no subject" would reject a
large fraction of legitimate keepers — including the Statue of Liberty — for reasons
having nothing to do with darkness.

#### Detector behaviour on dark images — the false-positive mechanism, quantified

This is the strongest cited evidence in the report against any detector-based gate.

**Root cause.** ExDark (Loh & Chan, CVIU 2019, <https://arxiv.org/abs/1805.11227>):
low-light images are "**less than 2% of the total images**" in PASCAL VOC, ImageNet and
MS-COCO. Their conclusion: "we found that the effects of low-light reaches far deeper
into the features than can be solved by simple 'illumination invariance'."

**Number 1 — same classes, same model, day vs night: −32.1 points.** CODaN (10 classes,
15,500 images) baseline ResNet-18: **day 80.39 ± 0.38% vs night 48.31 ± 1.33%**
(<https://github.com/Attila94/CODaN>). Cleanest possible isolation of the darkness
variable. Best published CODaN night top-1 climbs MAET 56.48 → CIConv 60.32 →
Sim-MinMax 65.87 → DAI-Net 68.44 (<https://arxiv.org/html/2312.01220v2>, Table 3) — so
**even SOTA dark-adapted methods stay ~12 points below the day baseline.**

**Number 2 — the catastrophic case.** WIDER FACE → DARK FACE generalization mAP, i.e.
detectors trained on well-lit data evaluated directly on dark
(<https://arxiv.org/html/2312.01220v2>, Table 1):

| Detector | mAP (%) |
|---|---|
| **Faster-RCNN** | **1.7** |
| SSH | 6.9 |
| RetinaFace | 8.6 |
| PyramidBox | 12.5 |
| DSFD | 16.1 |
| CIConv (zero-shot adapt) | 18.4 |
| Sim-MinMax (ZSDA) | 25.7 |
| DAI-Net (ZSDA) | 28.0 |
| Fine-tuned DSFD (supervised) | 46.0 |
| Fine-tuned DAI-Net (supervised) | 52.9 |

**Faster-RCNN scores 1.7 mAP.** These same architectures score in the 90s on well-lit
WIDER FACE. Fine-tuning on dark data recovers to 46–52.9, so the gap is a *data/domain*
gap and it is nearly total for an off-the-shelf detector.

**Number 3 — COCO-pretrained YOLOv3 on ExDark with no dark adaptation: 62.7 mAP vs 78.3
SOTA** (<https://arxiv.org/html/2312.01220v2>, Table 2).

**Number 4 — low-light enhancement preprocessing barely helps.** MAET's ExDark table,
all YOLOv3 fine-tuned on ExDark (<https://github.com/cuiziteng/MAET>, ICCV 2021,
<https://arxiv.org/abs/2205.03346>): baseline 76.4; KIND 76.3 (**−0.1**); MBLLEN 76.8;
Zero-DCE 76.9; MAET 77.7; DENet 77.3; IAT-YOLO 77.8. **Enhancement buys ≈0.5 mAP or
less, and KIND is net negative.** Important methodological caveat: these are all
*fine-tuned on ExDark*, which is why they sit at ~76 rather than YOLO-N's 62.7 — do not
read MAET's 76.4 "baseline" as an off-the-shelf number.

DAI-Net's abstract states the mechanism plainly: "**detectors trained on well-lit data
exhibit significant performance degradation on low-light data due to low visibility**",
and its §3.2 adds that "training the detector directly on synthetic low-light images
leads to much worse results than training on well-lit images" — which is a caution
against the synthetic-dark-augmentation idea proposed above, and worth heeding: synthesise
carefully, and validate on real dark frames.

If we have RAW originals, the LOD dataset provides paired long/short-exposure RGB **and
RAW** images (<https://bmva-archive.org.uk/bmvc/2021/conference/papers/paper_0085.html>,
<https://github.com/ying-fu/LODDataset>).

**Consequence for us — the requested false positive is confirmed with hard numbers.** A
legitimate night photo (Case B) will be scored by a COCO-pretrained detector roughly as
if it were empty: **−32 points** on identical classes, up to **−90+ points** in the worst
documented case. No confidence-threshold tuning fixes a domain gap of that magnitude,
and enhancement preprocessing is cited as buying ≤0.5 mAP. **A detector-based presence
test will systematically reject legitimate night photography.** Rule it out.

Note also: no literature was found on detection of *small bright objects on uniform dark
backgrounds* (moon, astro), nor on COCO-detector behaviour on near-zero-content images.
Searched; absent.

### 13. CLIP's documented failure modes, and the one that works in our favour

#### CLIP encodes *existence* and discards *cardinality* — which is good news

The single most useful finding about CLIP for this problem. From "Teaching CLIP to Count
to Ten" (<https://arxiv.org/html/2302.12066v1>, §5.4), on baseline off-the-shelf CLIP:

> baseline CLIP "often retrieves the same images for several different requested
> numbers. **This further implies that the baseline model mostly focuses on the
> existence of the described object in the image, and ignores the number in the
> caption.**"

Corroborated by their relevancy maps: "the original model primarily identifies a single
instance of the described object". So **existence is precisely what off-the-shelf CLIP
does encode**; number and extent are what it throws away. That is a good match for
"is there a subject" and a bad match for "is there *enough* subject".

Counting numbers, for completeness. CLEVRCounts is 8-way, chance 12.5%
(<https://arxiv.org/html/2103.00020v1>, Tables 9 and 11):

| Model | CLEVRCounts | ImageNet |
|---|---|---|
| RN50 | 20.3 | 59.6 |
| ViT-B/32 | 24.8 | 63.2 |
| ViT-B/16 | 23.4 | 68.6 |
| ViT-L/14 | 24.3 | 75.3 |
| ViT-L/14@336px | 24.8 | 76.2 |

Counting is flat (20.3 → 24.8) across a ~50× compute scale-up while ImageNet gains 16.6
points — **counting does not scale**, and a linear probe does not rescue it either
(§3.2, same URL). CountBench (9-way, chance 11.1%): off-the-shelf CLIP-B/32 scores
**31.67%** (<https://arxiv.org/html/2302.12066v1>, Table 1).

The CLIP paper's own limitations section (§6, <https://arxiv.org/html/2103.00020v1>):
"CLIP also struggles with more abstract and systematic tasks such as counting the number
of objects in an image… **We are confident that there are still many, many, tasks where
CLIP's zero-shot performance is near chance level.**"

**Practical rule: never phrase our presence question as a count or a quantity.**

#### Negation — do not write "no" into a prompt

"Vision Language Models Do Not Understand Negation" (NegBench, CVPR 2025,
<https://arxiv.org/abs/2501.09425>): 18 task variations, 79k examples across image, video
and medical datasets; "modern VLMs struggle significantly with negation, **often
performing at chance level**". Fine-tuning on millions of synthetic negated captions
recovers +10% recall / +28% MCQ accuracy — i.e. the deficit is real and requires
retraining to fix.

**Rule: phrase the reject pole as a positive description of what the bad frame *does*
contain**, never as the absence of something.

#### Low light — a genuine gap in the literature

**There is no published measurement of CLIP zero-shot accuracy under brightness or
exposure corruption.** The CLIP paper's robustness section (§3.3,
<https://arxiv.org/html/2103.00020v1>) evaluates only seven *natural* distribution shifts
(ImageNetV2, Sketch, YouTube-BB, ImageNet-Vid, ObjectNet, ImageNet-A, ImageNet-R) and
explicitly excludes "synthetic distribution shifts such as ImageNet-C" — which is
exactly where brightness/contrast corruptions live
(<https://arxiv.org/abs/1903.12261>). So CLIP's headline robustness claims **carry zero
information about our dark frames.** Searches across ImageNet-C × CLIP, day-night × CLIP,
nighttime × CLIP found nothing; `lr0.fm` (<https://ucf-crcv.github.io/lr0.fm/>) is
resolution-only; <https://arxiv.org/abs/2310.13040> probes 16 CLIP encoders but only on
ImageNet shifts.

The best available proxies are all CNNs, **not CLIP** — flagging that clearly:

- **CIConv**, ICCV 2021, <https://arxiv.org/abs/2108.05137>, Table 2, on CODaN with
  identical 10 classes where only illumination differs: **day 80.39 ± 0.38 → night
  48.31 ± 1.33** — a **32.1-point absolute / 40% relative** collapse. The best
  colour-invariant recovers only to 59.67.
- **Similarity Min-Max**, ICCV 2023 — note the correct ID is
  **<https://arxiv.org/html/2307.08779v2>**, *not* arXiv:2312.08924, which is an
  unrelated composed-image-retrieval paper. Table 1 on CODaN night: ResNet-18 53.32; six
  low-light *enhancement* front-ends reach only 56.68–58.72; CIConv 60.32; theirs 65.87.
  **Pre-brightening buys ~5 points; it does not fix the representation.**
- **DAI-Net**, AAAI 2024, <https://arxiv.org/html/2312.01220v2> — see §12 for its
  detection numbers.

**[INFERENCE]** A 30–40% relative degradation on *ordinary* night photos is the right
prior. Our two cases are far past CODaN — near-total darkness with one lit region is
out-of-distribution for CLIP in the way MNIST is (CLIP paper §6: "CLIP only achieves 88%
accuracy on MNIST… an embarrassingly simple baseline of logistic regression on raw
pixels outperforms zero-shot CLIP"). **Whatever we build needs its own held-out
dark-frame eval set. We cannot infer this from anything published.**

#### The modality gap and why absolute cosine thresholds are unreliable

"Mind the Gap" (<https://ar5iv.labs.arxiv.org/html/2203.02053>):

- Gap magnitude: **‖Δ_gap‖ = 0.82** Euclidean between the centroids of the image and
  text embedding clouds, on the unit sphere (§3.1).
- Cause 1, the cone effect: within-modality average cosine is 0.56 / 0.47 / 0.51 across
  three trained models (0.99 for a randomly-initialised ResNet). "A cosine similarity of
  0.56 can occupy less than 1/2^512 fraction of the surface area in a unit 512D
  hypersphere."
- Cause 2, the contrastive loss itself: "the default gap distance ‖Δ_gap‖ = 0.82
  **actually achieves the global minimum**, and shifting toward closing the gap
  increases the contrastive loss" at τ = 1/100. The gap is not a bug to be fixed.

**The numeric range of image–text cosine, cited.** CLIPScore
(<https://arxiv.org/html/2104.08718v1>, §B): "While the cosine similarity, in theory, can
range from [−1,1] (1) **we never observed a negative cosine similarity**; and (2) **we
generally observe values ranging from roughly zero to roughly .4**." That is why they
multiply by w = 2.5 to "stretch" the distribution — and they warn the constant is
backbone-specific: "the exact parameters of our rescaling method only apply to CLIP
ViT-B/32… bigger models… could exhibit a different cosine similarity distribution."

**Calibration is a solved-ish problem, and the solution is "fit to your own
histogram".**

- <https://arxiv.org/abs/2303.12748> (LeVine et al.): "we find that **zero-shot inference
  with CLIP is miscalibrated**"; their modified temperature scaling means "a single
  learned temperature generalizes for each specific CLIP model… across inference dataset
  and prompt choice" — one scalar, fit once, transfers.
- <https://arxiv.org/abs/2504.14224> (VLM-OpenXpert) is directly on point for absolute
  thresholds: "existing score-based unknown detectors use **simplistic thresholds and
  suffer from threshold sensitivity**, resulting in sub-optimal performance." Their
  training-free fix — Box-Cox to correct score skew, then a **bimodal Gaussian mixture
  to adaptively estimate the threshold** — works on CLIP/SigLIP/ALIGN. **This is the
  shape of the answer for a 42,000-image corpus: fit the cut to our own score histogram,
  never hardcode a constant.**

**Ensembling mitigates single-pair variance, and this is established practice.**
IQA-PyTorch ensembles five antonym pairs (Good/bad image, Sharp/blurry image,
sharp/blurry edges, High/low resolution image, Noise-free/noisy image) and means the
probabilities — "we assemble multiple prompts to improve the results"
(<https://raw.githubusercontent.com/chaofengc/IQA-PyTorch/main/pyiqa/archs/clipiqa_arch.py>).
Miyata (<https://arxiv.org/abs/2308.13094>) generalises multi-antonym-pair CLIP-IQA.

#### SigLIP — per-pair independence is real, absolute calibration is overclaiming

SigLIP (ICCV 2023 Oral, <https://arxiv.org/abs/2303.15343>): "the sigmoid loss operates
solely on image-text pairs and **does not require a global view of the pairwise
similarities for normalization**"; it "processes every image-text pair **independently**,
effectively turning the learning problem into the **standard binary classification** on
the dataset of all pair combinations."

But the loss carries a learnable bias `b`, and the paper explains why: "at
initialization, the heavy imbalance coming from the many negatives dominates the loss…
we introduce an additional learnable bias term b… We initialize t′ and b to 10 and −10
respectively. **This makes sure the training starts roughly close to the prior**"
(<https://openaccess.thecvf.com/content/ICCV2023/papers/Zhai_Sigmoid_Loss_for_Language_Image_Pre-Training_ICCV_2023_paper.pdf>,
§3.2).

**[INFERENCE]** `b` exists specifically to encode the *pretraining pair prior* — one
positive per batch of up to 32k candidates. So `σ(t·cos + b)` is calibrated to that
prior, not to any real-world rate of "this photo contains legible content". HuggingFace
does print `probs = torch.sigmoid(logits_per_image)  # these are the probabilities`
(<https://huggingface.co/docs/transformers/main/en/model_doc/siglip>), and the per-pair
independence is genuine, but **no experiment in either paper validates absolute
probability calibration.** Treating the sigmoid output as a presence probability is
overclaiming. Its real advantage is architectural: one prompt against one image, no
antonym needed, so we escape the 100×-amplified antonym-difference problem — but the
threshold still has to be fitted empirically.

Sizes: SigLIP 2 (<https://arxiv.org/abs/2502.14786>) ships ViT-B (86M), L (303M),
So400m (400M), g (1B). `google/siglip-so400m-patch14-384` is Apache-2.0
(<https://huggingface.co/google/siglip-so400m-patch14-384>). Quantized ONNX exists for
B-scale (<https://huggingface.co/onnx-community/siglip2-base-patch16-224-ONNX>), so CPU
is practical. **But the real cost is that SigLIP means re-embedding all 42,000 photos —
our existing CLIP embeddings are worthless to it.** That is a big strike against it given
the whole point of this section is to reuse what we have.

#### Nobody has done CLIP prompt-pairs for content presence

Honest negative result. Searches for "CLIP zero-shot object presence", "CLIP image-text
similarity object existence", "open-vocabulary image-level presence absence", "CLIP empty
image / blank frame detection", "photo of nothing", plus `gh search repos`, returned only
generic zero-shot-classification tutorials and *localisation*-based open-vocab detection
(e.g. <https://huggingface.co/docs/transformers/v4.43.4/tasks/zero_shot_object_detection>)
— which answers "where is the cat", not "is anything here worth looking at". The nearest
adjacent works are both quality/OOD rather than presence:
<https://arxiv.org/abs/2308.13094> and <https://arxiv.org/abs/2504.14224>.

**There is no published antonym-prompt method for content presence, emptiness, or "is
there a subject". We would be first, with no baseline and no reported accuracy to anchor
expectations.** That is a reason to prototype and measure, not a reason to trust a prompt.

### 14. Salient object detection as a presence test — the wrong instrument, and the literature says so

#### Normalization is the crux, and it destroys the signal in most models

The obvious idea is to read the saliency map's total mass, peak confidence, or
area-above-threshold as a presence score. **Whether that is even measurable depends
entirely on where each model applies per-image min-max normalization**, and the answer
differs per model. This table is the most operationally useful thing in this section.

| Model | Raw output | Per-image normalization? | Mass/peak usable? |
|---|---|---|---|
| **U²-Net** (<https://arxiv.org/abs/2005.09007>, <https://github.com/xuebinqin/U-2-Net>) | `return F.sigmoid(d0), …` — 7 absolute probability maps at 320×320 | **Not in the model, but twice in the pipeline.** `u2net_test.py` defines `normPRED(d): (d-mi)/(ma-mi)`; and `data_loader.py`'s `ToTensorLab` does `image = image/np.max(image)` **on the input** — a per-image auto-gain before ImageNet mean/std. `rembg`'s `U2netSession.predict` does both too. | **No, as shipped** |
| **BASNet** (CVPR 2019, <https://github.com/xuebinqin/BASNet>) | `F.sigmoid(dout), …` absolute probabilities | Same pattern: `normPRED` in `basnet_test.py`, `np.max(image)` input division in `data_loader.py` | **No, as shipped** |
| **PoolNet** (<https://arxiv.org/abs/1904.09569>, <https://github.com/backseason/PoolNet>) | `solver.py::test` → `torch.sigmoid(preds)` then `255 * pred` | **None anywhere.** Input is fixed BGR mean subtraction: `in_ -= (104.00699, 116.66877, 122.67892)` | **Yes** — the only listed model whose stock pipeline preserves mass *and* peak end to end |
| **TRACER** (<https://arxiv.org/abs/2112.07380>, <https://github.com/Karel911/TRACER>) | `torch.sigmoid(final_map), …` | **No min-max.** `trainer.py` only does `output*255.0 → uint8`; input is fixed `albu.Normalize` | **Yes** |
| **InSPyReNet** (<https://arxiv.org/abs/2209.09475>, <https://github.com/plemeri/InSPyReNet>) | pyramid of raw logits | **Normalization is INSIDE the model.** `lib/InSPyReNet.py`, in *both* `forward_train` and `forward_inference`: `pred = torch.sigmoid(d0); pred = (pred - pred.min()) / (pred.max() - pred.min() + 1e-8)`. `sample['pred']` always has max exactly 1.0. | **No** — recoverable only by taking `sigmoid(sample['saliency'][-1])` yourself |
| **Itti–Koch–Niebur 1998** (TPAMI, doi 10.1109/34.730558, <https://ieeexplore.ieee.org/document/730558>) | scalar map → winner-take-all scanpath | **Normalization is the algorithm's core and is explicitly amplitude-destroying**: the operator `N(·)` "globally promotes maps in which a small number of strong peaks of activity is present"; step 1 is "**normalizing the values in the map to a fixed range [0..M], in order to eliminate modality-dependent amplitude differences**" | **No, by design** |
| **Spectral Residual** (Hou & Zhang CVPR 2007, <https://ieeexplore.ieee.org/document/4270292>) | 64×64 log-spectrum residual, squared, blurred, resized | **Doubly relative.** Paper: `O(x)=1 if S(x) > threshold`, "we set **threshold = E(S(x)) × 3**" — self-referential, so *every* image yields proto-objects. OpenCV additionally divides by the per-image max: `magnitude = magnitude / maxVal` (<https://github.com/opencv/opencv_contrib/blob/4.x/modules/saliency/src/staticSaliencySpectralResidual.cpp>); input force-resized to 64×64; `computeBinaryMap` uses k-means k=5, also relative | **No, by design** |

Sizes/licenses: U²-Net `u2net.pth` **176.3 MB**, `u2netp.pth` **4.7 MB**, Apache-2.0
(the widely-cited 44.02M / 1.13M params is consistent with fp32 size but is **not**
stated in the paper — inference). BASNet MIT. PoolNet MIT. TRACER Apache-2.0.
InSPyReNet MIT, also shipped as the `transparent-background` pip package. Spectral
Residual is in `opencv-contrib-python` as
`cv2.saliency.StaticSaliencySpectralResidual_create()`, Apache-2.0, zero weights.

**None of U²-Net, BASNet, PoolNet, TRACER or InSPyReNet documents its behaviour when no
salient object is present.** A grep of the U²-Net paper for "non-salient" / "no salient
object" / "fail" returns no hits. The only statements come from the critique literature:
SOC ("most models are not optimized for non-salient objects detection"), SOS ("these
methods can output unexpected results for images that contain no salient object"), and
Jiang et al. ("all three state-of-the-art approaches produce unsatisfactory saliency maps
on background images").

#### Is mass / peak / area documented as a presence score anywhere? Essentially no — and where it was tried, it failed

- **Total mass appears only as an *evaluation metric*.** SOC rules out F-measure on
  all-zero ground truth — "the black (all-zero matrix) ground truth is not well defined
  in F-measure when calculating recall and precision… different foreground maps get the
  same result 0, which is apparently unreasonable" — and falls back to pixel-wise
  accuracy ε = normalized MAE
  (<https://www.ecva.net/papers/eccv_2018/papers_ECCV/papers/Deng-Ping_Fan_Salient_Objects_in_ECCV_2018_paper.pdf>,
  §4.1). Since G ≡ 0 on non-salient images, **ε reduces algebraically to the mean of the
  predicted saliency map** — so the "total mass" statistic does exist in the literature,
  but as a *scoring rule for benchmarking*, never as a runtime confidence. (The algebraic
  reduction is my arithmetic, not stated in the paper.) The TPAMI version restates the
  policy: "the GTs of non-salient images in our SOC dataset are all-zero matrices, so
  directly using the traditional F-measure will result in very low and inaccurate scores.
  Thus, we utilize three golden metrics (i.e., MAE, maximum E-measure, and S-measure)"
  (<https://mftp.mmcheng.net/Papers/22TPAMI-SOC.pdf>). No per-subset non-salient-only
  column is published in either version.
- **Area-above-threshold as a presence/count signal is published as *failing*.** SOS
  binarizes a SOTA saliency map with Otsu, drops components smaller than 1/100 of the
  largest, and reports performance "**barely better than chance**" — "Counting based on
  pixel connectivity is only reliable in idealistic cases" (CVPR 2015, §4). This is
  direct published evidence against blob-counting on a saliency map.
- **Saliency-derived features are *worse* than plain global image features for the
  existence question.** SOS reports that "SalPyr [saliency map pyramid] is not as
  effective as HOG and GIST in predicting the existence of salient objects in an image",
  and its model works precisely because it bypasses the map — "without resorting to any
  intermediate saliency map computation" (<https://arxiv.org/html/1607.07525v1>).
- **Where existence *was* predicted from saliency maps, the authors deliberately threw
  away magnitude and kept spatial layout.** Wang et al., CVPR 2012, "Salient object
  detection for searched web images via global saliency"
  (<https://jingdongwang2017.github.io/Pubs/CVPR12-Saliency.pdf>): "our algorithm exploits
  global features from multiple saliency information to **directly predict the
  existence** and the position of the salient object". Their driving observation is
  exactly our problem: "for background images, the salient contents in images are always
  **scattered**, or there's no obvious salient regions. While images containing an object
  generally produce a saliency map with a **compact and closed salient region**." But
  their features are a 30×30 grid of block-mean saliency computed *after* "we normalized
  all the saliency maps into [0,1]" — i.e. **layout, not mass**.

**Conclusion: no paper uses raw saliency total mass or peak sigmoid as a calibrated
presence confidence.** Where the map was used for existence, it was via spatial
compactness; where mass/area was tried, it was reported as near-chance.

#### A second existence-prediction precedent, with a big background-image dataset

**Jiang, Cheng, Li, Borji, Wang.** "Joint Salient Object Detection and Existence
Prediction." *Frontiers of Computer Science* 2018.
<https://mmcheng.net/salexist/> · <http://mftp.mmcheng.net/Papers/JointSalExist.pdf> ·
doi <https://doi.org/10.1007/s11704-017-6613-8>

A structural SVM that jointly outputs an **image-level existence label** and pixel
saliency. Its **SOSB dataset**: "we collected **6,182 background images** from the SUN
dataset, describable texture dataset, Flickr, and Bing image search engines" (5,000 train
/ 1,182 test) plus 5,000 MSRA10K.

Existence accuracy (Table 2): joint SSVM **99.22% / 98.66% / 94.40% / 88.36%** on their
test set / MSRA-B / ECSSD / SOSB, versus the Wang 2012 baseline at 90.64 / 89.26 / 72.50 /
**75.23** — a ~13-point gain on the hard background set from the joint formulation.
Honest limitation stated by the authors: "our approach can not always produce all-black
saliency maps for background images."

**For us this is a third labelled negative set (6,182 background images) and a second
published precedent that presence is worth modelling explicitly.**

#### The modern, PyTorch-available option

**Islam, Kalash, Bruce.** "Revisiting Salient Object Detection: Simultaneous Detection,
Ranking, and **Subitizing** of Multiple Salient Objects." CVPR 2018.
<https://arxiv.org/abs/1803.05082> · PyTorch reimplementation
<https://github.com/MinglangQiao/pytorch-rsdnet-sor>

One network produces mask + saliency rank + subitizing. **This is the closest thing to a
maintained, PyTorch-era subitizing model**, and it is the first place to look if we would
rather adopt than train. Worth a spike before committing to the CLIP-head route.

#### SOD on low-light images — the datasets exist and confirm off-the-shelf failure

- **Xu et al.** "Exploring Image Enhancement for Salient Object Detection in Low Light
  Images." ACM TOMM. <https://arxiv.org/abs/2007.16124>. Dataset **NTI-V1**: 577 low-light
  images with pixel-level human ground truth. The failure is stated plainly: "existing
  salient object detection models are developed based on the assumption that the images
  are captured under a sufficient brightness environment, which is impractical"; "**the
  results of R3Net lose detail information of salient objects and tend to contain
  non-saliency backgrounds** in the degraded low light images"; "we verify that low
  illumination can reduce the performance of SOD."
- **YLLSOD.** Yu et al., "Degradation-removed multiscale fusion for low-light salient
  object detection", *Pattern Recognition* 2024, doi 10.1016/j.patcog.2024.110650,
  <https://github.com/ynn1030/YLLSOD>. 3,263 image pairs at 384×384, categorized by
  salient-object size **and including an explicit "extreme darkness (ED)" class and an
  "uneven illumination (UI)" class**. This is the closest published taxonomy to our
  problem and the best source of real dark-frame eval data I found.
- **LS-SOD / LSPV.** <https://github.com/Shiqin-Wang/LS-SOD> — low-light salient
  pedestrian/vehicle dataset, partial release only.
- **HDNet.** <https://github.com/Ylinyuan/HDNet>
- Telling adjacent signal: **RGB-T SOD / VT5000** (<https://arxiv.org/abs/2007.03262>) is
  motivated by "adverse conditions such as dark environments" — the community's answer to
  darkness is *add a thermal channel*. That is how hard RGB-only night SOD is.

#### Does SOD separate Case A from Case B? No — and for several models it inverts

- **Spectral Residual and Itti–Koch: no, actively harmful.** [cited] Both are pure
  contrast/anomaly detectors with explicitly relative thresholds. A single bright blob on
  black is the *ideal* stimulus for both — it is exactly the "small number of strong peaks
  of activity" configuration that Itti's `N(·)` is *designed to promote*. **[INFERENCE]**
  Both will score the crescent moon at or above the Statue.
- **U²-Net / BASNet as shipped: no.** [cited] The input pipeline divides by the image max
  (`image/np.max(image)`), which auto-exposes a dark frame, and the output pipeline
  min-max-stretches the map. **[INFERENCE]** After input auto-gain a crescent on black
  becomes a maximum-contrast compact blob — the easiest thing U²-Net ever sees — and the
  stretched output is a confident mask with max = 1.0. Both properties push toward
  *keeping* the moon. You can bypass both normalizations, but you are then running the
  network off-distribution from its own training preprocessing.
- **InSPyReNet: no unless patched**, because the stretch is inside `forward_inference`.
- **PoolNet / TRACER: the only two where mass/peak is even measurable**, so
  `mean(p)`, `max(p)`, `area(p > 0.5)` are comparable across images. [cited]
  **[INFERENCE] But nothing in their training objective teaches them to output near-zero
  on a subject-free frame** — they were trained on DUTS, where every image has a salient
  object, so the prior is "something is salient". Expect a confident compact mask on the
  moon.

**The cue we actually need is objectness, not saliency, and the literature says so
directly.** Xia et al.'s third reason for non-salience is precisely "**low objectness** —
Sometimes the most salient region is considered to be not an 'object' due to its semantic
attributes (e.g., the rock and road…)". Their derived definition: "a salient object should
have a limited similar distractors, relatively clear and simple shape and high
objectness". Combined with SOS's finding that saliency features underperform HOG/GIST for
existence, the literature's verdict is: **a saliency map cannot tell you whether a bright
blob is a subject; a semantic/objectness model can.** SOD is the wrong instrument.

**[INFERENCE]** The lit-Statue case and the crescent-moon case are structurally
near-identical in pixel statistics — a small lit region in a vast black field. **Only
semantics separate them.** That is the single most important sentence in this report, and
it is why the recommendation is a semantic head on CLIP embeddings rather than any
low-level saliency, complexity, or exposure statistic. It is also the reason to keep the
lit-area statistic (§7) as a *cheap first-pass filter only*, never as the adjudicator.

Best realistic use of SOD here, **[INFERENCE]**: not as a presence test, but as a
second-stage filter *after* a semantic gate — PoolNet mass plus blob compactness to reject
scattered-texture frames, which is exactly what Wang 2012 uses spatial layout for [cited]
— while accepting that a compact bright blob on black passes every SOD criterion in the
literature.

---

## The CLIP-embeddings-already-exist option — our cheapest path

We already pay for CLIP image embeddings on all 42,000 images. Two distinct things can
be built on top for essentially zero marginal cost. They are not the same thing and
have very different reliability.

### Option 1 — zero-shot antonym prompt pairs (cost: one dot product per image)

Encode two text prompts once (cacheable forever, ~kilobytes), then per image compute
two cosine similarities and the CLIP-IQA softmax `s̄ = e^{s1}/(e^{s1}+e^{s2})`. For
42,000 images this is a single 42,000×512 by 512×2 matrix multiply — milliseconds.

**Status: published, validated, library-supported, and weaker than it looks.**

- Validated: CLIP-IQA (<https://arxiv.org/abs/2207.12396>), ~80% human agreement on
  complex/simple specifically (§2.3).
- Supported: `torchmetrics` with arbitrary custom pairs
  (<https://lightning.ai/docs/torchmetrics/stable/multimodal/clip_iqa.html>).
- Undercut: WP-CLIP measures zero-shot CLIP/CLIP-IQA at SRCC 0.06/-0.04 on the
  multiplicity-unity axis (<https://arxiv.org/html/2508.12668v1>, Table 2).

**Three known failure modes that bear directly on our two cases.** Detailed citations
are in the CLIP slice below; the shape of each:

1. **Negation.** Do not write a prompt containing "no" / "without" / "empty of". "Vision
   Language Models Do Not Understand Negation" (NegBench, CVPR 2025,
   <https://arxiv.org/abs/2501.09425>) finds "modern VLMs struggle significantly with
   negation, **often performing at chance level**" across 18 task variations and 79k
   examples. A prompt pair like `("a photo with a subject", "a photo with no
   subject")` is therefore likely to be near-useless. Prefer positive-vs-positive
   phrasings.
2. **Counting.** We must not phrase presence as a count.
3. **Low light.** Both our cases are dark; CLIP's behaviour under severe
   underexposure is the crux and is the least well-characterised.

**Recommended first experiment**, and it is genuinely a one-hour job:

- Hand-label ~200 frames from our own library into three buckets: clearly-empty
  (should reject), clearly-has-subject (should keep), and specifically the hard dark
  cases (crescent-moon-likes and Statue-of-Liberty-likes).
- Score each with, say, six candidate prompt pairs, including
  `("Complex photo.", "Simple photo.")` and the positive-vs-positive night pair.
- Plot the two distributions per pair and read off whether any pair separates them, and
  where.
- **Do not set a global threshold from published numbers.** CLIP-IQA's own §3.1 shows
  scores move materially with template and adjective choice, so the threshold is a
  property of our prompt and our library, not a transferable constant. Calibrate on
  our own labelled 200.

### Option 2 — a tiny supervised head on the frozen embeddings (cost: minutes to train)

**This is the recommendation, and the CLIP paper itself supplies the quantitative
argument for preferring it over any prompt.**

From <https://arxiv.org/html/2103.00020v1>:

- Fig. 8: "**zero-shot performance mostly shifted 10 to 25 points lower**" than the
  linear probe on the same features. "On only **5** datasets does zero-shot performance
  approach linear probe performance (≤3 point difference)."
- Fig. 7: a linear probe needs a median of **5.4 labeled examples per class** to *match*
  zero-shot (mean 20.8, max 184).

So a few hundred hand-labels should beat every prompt pair we could invent, by 10–25
points, using embeddings we have already computed.

**How small "tiny" really is.** LAION-Aesthetics V1
(<https://raw.githubusercontent.com/LAION-AI/aesthetic-predictor/main/README.md>) is
literally:

```python
if clip_model == "vit_l_14":   m = nn.Linear(768, 1)
elif clip_model == "vit_b_32": m = nn.Linear(512, 1)
```

**769 parameters**, trained on **5,000 image-rating pairs** from SAC on frozen "CLIP
Image embeddings produced with the Open AI CLIP VIT L 14 model"
(<https://laion.ai/blog/laion-aesthetics/>). "Its results were so encouraging, that we
decided to produce 8M and 120M sample subsets of the LAION 5B images."

The V2 `improved-aesthetic-predictor`
(<https://raw.githubusercontent.com/christophschuhmann/improved-aesthetic-predictor/main/train_predictor.py>)
is a ~928k-param MLP (768→1024→128→64→16→1, MSE loss, dropout) trained on ~441k ratings
— **and its ReLUs are commented out in the source**, so it is functionally an affine map.
LAION's own verdict: "**a simple linear model on the top of CLIP ViT/14 produced in our
subjective view the visually most appealing results**… (Even though other MLPs with e.g.
Relu functions produced slightly lower MSE and MAE loss values.)" This predictor's ≥5.0
subset selected the Stable Diffusion v1 training set — a 769-parameter linear head on
frozen CLIP features shaped one of the most-used generative models ever built. The
pattern is not just precedented, it is load-bearing infrastructure.

The reason this is the strongest available option is that **validated labels for our
task already exist**:

| Label source | Size | Target | URL |
|---|---|---|---|
| SOS | ~14K | 0/1/2/3/4+ salient objects — the 0 class is the gate | <https://arxiv.org/html/1607.07525v1> |
| XPIE stage-1 | 8,598 negatives / 21,002 positives | binary "contains a clear object" | <https://openaccess.thecvf.com/content_cvpr_2017/html/Xia_What_Is_and_CVPR_2017_paper.html> |
| SOC | non-salient subset | non-salient vs salient, daily-object categories | <https://arxiv.org/abs/1803.06091> |
| AADB | 10,000 | `object_emphasis`, `content` (human-rated, continuous) | <https://ar5iv.labs.arxiv.org/html/1606.01621> |

Embed 14K–24K of those images once with the *same* CLIP model we already use, fit a
logistic regression or 2-layer MLP, and we have a presence head that runs on our
existing 42,000 embeddings for free and that we can threshold with a real
precision/recall curve instead of a guess.

Two things to add to it, both **[INFERENCE]**:

- **Augment with synthetic dark pairs.** The SOS paper shows cut-and-paste synthetic
  images work well enough to substitute for real data (+5% mAP at 25% real data,
  <https://arxiv.org/html/1607.07525v1> §5, Table 5). We can synthesise our own
  crescent-on-black and lit-subject-on-black pairs at whatever ISO we like and add them
  to training. This is the direct fix for the "trained on well-exposed data" risk, and
  it is the only way I can see to get real evidence about our two cases rather than
  inference.
- **Hold out a dark-frames-only validation slice** from our own library and report
  precision/recall on it separately. A head that scores 0.95 overall and 0.55 on dark
  frames is useless to us, and an aggregate number will hide that.

Caveat on both options: SOS/XPIE/SOC/AADB are all daytime-skewed everyday-photo
datasets, and none of them, as far as I could establish, reports results by
illumination. So the transfer to night photography is the untested link in the chain
for every one of these paths. That is the thing our prototype should measure first.

---

## Negative findings

These matter as much as the positives.

1. **Nobody has published a negative-space, minimalism, or low-key photography
   classifier.** Searching for "negative space detection photography deep learning",
   "minimalist photography classifier", "minimalist photography recognition dataset
   negative space computational aesthetics" returns only photography blogs and how-to
   articles (adobe.com, slrlounge.com, photoworkout.com, visualwilderness.com …), no
   academic work. If a validated minimalism/low-key recogniser existed, it would be the
   obvious answer to our problem; it does not exist.

2. **The AVA dataset's photographic style labels do not include minimalism, negative
   space, high key or low key.** AVA (Murray, Marchesotti, Perronnin, CVPR 2012) is the
   canonical large aesthetics dataset with style annotations, and the actual list is
   exactly 14 styles
   (<https://raw.githubusercontent.com/imfing/ava_downloader/master/AVA_dataset/style_image_lists/styles.txt>):
   `Complementary_Colors`, `Duotones`, `HDR`, `Image_Grain`, `Light_On_White`,
   `Long_Exposure`, `Macro`, `Motion_Blur`, `Negative_Image`, `Rule_of_Thirds`,
   `Shallow_DOF`, `Silhouettes`, `Soft_Focus`, `Vanishing_Point`.
   `Light_On_White` is the nearest neighbour to high-key minimalism and `Silhouettes` to
   low-key, but neither is the concept, and there is no low-key or negative-space
   category at all. **So the standard aesthetics vocabulary itself lacks the label we
   need.** Note also `Negative_Image` means an inverted-tone image, not negative space —
   an easy misreading.

3. **AADB's eleven attributes contain no minimalism or negative-space attribute
   either** — the closest are `object_emphasis` and `content`
   (<https://ar5iv.labs.arxiv.org/html/1606.01621>). This is a second independent
   confirmation of finding 2.

4. **No work explicitly distinguishes intentional underexposure from failed
   underexposure.** Searching "distinguish intentional underexposure artistic intent
   from technical failure image quality assessment", "intentional underexposure
   detection", and "no-reference image quality artistic intent" surfaced exactly one
   on-point primary source — the NTIA/ITS note above
   (<https://its.ntia.gov/research/qoe/video-quality-research/no-reference-metrics/artistic-intent/>)
   — and that note is a 2025 *hypothesis* about object size confounding NR metrics, not
   a solution, and it concerns video compression artefacts rather than exposure. The
   nearest thing to a working approach is the implicit one in defect detection
   (<https://arxiv.org/abs/1612.01635>): stop deriving badness from statistics and
   learn it from human severity ratings. **This is an open problem, and if we solve it
   we will not be re-implementing anyone.**

5. **CLIP does not know photographic vocabulary.** CLIP-IQA §3.3 explicitly names
   "*Long exposure*", "*Rule of thirds*", "*Shallow DOF*" as terms CLIP fails on
   (<https://arxiv.org/html/2207.12396v2>). Any prompt-based approach that reaches for
   compositional jargon will silently fail. Constrain prompts to everyday adjectives —
   which is also what §3.1's `Good/Bad` beating `High definition/Low definition` shows.

6. **The whole SOD benchmark tradition assumes a subject exists**, per SOC's abstract:
   existing datasets carry "a serious design bias… which assumes that each image
   contains at least one clearly outstanding salient object in low clutter"
   (<https://arxiv.org/abs/1803.06091>). Any saliency model we pick up off the shelf
   inherits that assumption, so its behaviour on Case A is out-of-distribution by
   construction and should be measured, never assumed.

7. **No maintained open weights for salient object subitizing.** `gh search repos
   "salient object subitizing"` returns nothing; the project page
   <http://cs-people.bu.edu/jmzhang/sos.html> 404s and
   <http://www.cs.bu.edu/groups/ivc/Subitizing/> only redirects. The task is validated;
   the artifact is gone. Hence the recommendation to rebuild it as a head on our own
   embeddings rather than to hunt for a checkpoint.

8. **Nobody has measured CLIP's accuracy under illumination or exposure corruption.**
   The CLIP paper's robustness section evaluates seven natural distribution shifts and
   *explicitly excludes* synthetic shifts like ImageNet-C, where brightness and contrast
   corruptions live (<https://arxiv.org/html/2103.00020v1> §3.3;
   <https://arxiv.org/abs/1903.12261>). Searches across ImageNet-C × CLIP, day-night ×
   CLIP and nighttime × CLIP found nothing; `lr0.fm` is resolution-only
   (<https://ucf-crcv.github.io/lr0.fm/>); <https://arxiv.org/abs/2310.13040> probes 16
   CLIP encoders but only on ImageNet shifts. **Every low-light number in this report is
   from a CNN, not from CLIP.** So the single most important question for our use case is
   unmeasured in the literature, and we must measure it ourselves.

9. **No published antonym-prompt method for content presence.** See §13. We would be
   first, with no baseline and no reported accuracy to anchor expectations.

10. **The background-removal and SAM communities do not discuss the empty-frame case at
    all.** Exhaustive `gh search issues` across `danielgatis/rembg`,
    `ZhengPeng7/BiRefNet` and `facebookresearch/segment-anything` for `blank image`,
    `empty mask`, `no object`, `black image`, `all white`, `hallucinate`, `returns whole
    image`, `fully transparent` produced zero on-point hits. Nobody uses these tools this
    way, so there is no folk knowledge to borrow and every claim about their blank-frame
    behaviour in this report is inference.

11. **No literature on detecting small bright objects on uniform dark backgrounds**
    (moon, astro), nor on COCO-detector behaviour on near-zero-content images. Searched;
    absent.

12. **No paper uses saliency-map total mass or peak sigmoid as a calibrated presence
    confidence.** Total mass appears only as an evaluation metric (SOC's ε/MAE on
    all-zero ground truth, which reduces to the map mean); area-above-threshold counting
    is published as "barely better than chance" (SOS CVPR 2015 §4); and the one work that
    *did* predict existence from saliency maps explicitly normalized them to [0,1] first
    and used **spatial layout** instead (Wang et al. CVPR 2012,
    <https://jingdongwang2017.github.io/Pubs/CVPR12-Saliency.pdf>). The intuitive idea is
    not merely unvalidated — it has been tried and reported as not working.

13. **No published CPU or Apple Silicon timings for SAM, SAM 2, BiRefNet, OWLv2 or
    Grounding DINO.** Only Ultralytics publishes real CPU-ONNX latencies
    (<https://docs.ultralytics.com/models/yolo11/>) and MegaDetector publishes real
    M1/M3 numbers (<https://raw.githubusercontent.com/agentmorris/MegaDetector/main/megadetector.md>).
    Our 42,000-image budget is therefore only *firmly* established for the YOLO family
    and for MegaDetector-class models; everything else in the table is extrapolation.

---

## Appendix: sources consulted that did not pan out

- `arXiv:2207.00980` is a lattice field theory paper, not IC9600 — the IC9600 paper has
  no arXiv ID I could find; cite the TPAMI DOI 10.1109/TPAMI.2022.3232328 and the repo.
- Donderi (2006) and Forsythe et al. (2011) abstracts were not retrievable from
  PsycNET / Wiley / PubMed with the tooling available; they are cited here as the
  `imagefluency` documentation cites them
  (<https://imagefluency.com/reference/img_complexity.html>).
- `export.arxiv.org/api/query` was unresponsive throughout; arXiv abs/html pages were
  fetched directly instead.
- **Corrected citation:** "Similarity Min-Max" (zero-shot day-night domain adaptation,
  ICCV 2023) is **arXiv:2307.08779**, not arXiv:2312.08924 — the latter is an unrelated
  composed-image-retrieval paper. Worth noting because the wrong ID was in the brief and
  may be circulating elsewhere in this research effort.
- **IC9600 has no arXiv ID** that I could find; cite TPAMI DOI 10.1109/TPAMI.2022.3232328
  and <https://github.com/tinglyfeng/IC9600>.

---

Created using Anthropic Claude. Please keep this note on internal versions until a human
has reviewed and verified the content. Every numeric claim is quoted from the linked
primary source; items marked **[INFERENCE]**, the softmax-saturation arithmetic in §4, and
the synthetic probe in §7 are my own derivation or judgement, not published results, and
should be re-checked before they drive a design decision.
