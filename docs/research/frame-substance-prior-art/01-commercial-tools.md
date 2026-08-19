# What commercial culling / DAM tools actually key on when they auto-reject a frame

Created using Anthropic Claude. Keep this line on internal versions until a human has reviewed and verified the content.

Research date: 2026-08-19. Sources are vendor help centres, release notes and granted patents unless marked SECONDARY.

---

## Verdict

1. **Two major vendors now ship exposure-based auto-reject, and both landed in the last 10 months.** Adobe Lightroom Classic 15.0 "Assisted Culling" (Oct 2025) has a reject checkbox literally named **"Exposure issues"**; Capture One 16.8 "Assisted Review" (28 May 2026) advertises that it filters out **"black frames"**. Before these two, no mainstream culler used brightness at all.
2. **Not one of the ten tools documents any protection for intentionally dark, low-key or minimalist work.** This is the headline negative finding. Every creative-intent carve-out that exists in writing is about *closed eyes* or *motion blur* — never exposure.
3. **The tools that would spare a 95%-black night frame are safe by accident, not by design** — either because they never look at brightness (Narrative Select, ON1 Lightpanel, Photo Mechanic, Excire) or because their reject rules are gated on a detected face (Optyx: "only photos with obvious faces are candidates for absolute conditions"). Remove the face-gate or add an exposure check and they would all fail.
4. **The only documented discriminator anywhere that gets our case right is in a patent, not a product**: PhotoSi's US11586669B2 rejects a dark frame on **noise-trimmed contrast**, not on brightness — and its own FIG. 4 is "a dark photograph that is *selected* by the process … as it has sufficient contrast," a work of art in a dark environment lit from within. That is functionally the Statue-of-Liberty-at-night case, and the patent keeps it.
5. **Direct answer to the constraint: brightness/percent-black is the wrong discriminator and every vendor that uses it would reject our best frames. Contrast-with-noise-trim is the right one.** A frame that is 95% black but contains a lit subject has *low mean luminance* and *high trimmed contrast*. Those two signals disagree, and only the second one tracks intent.

---

## Summary table

| Tool | Blank/dark detection? (vendor's name) | Stated discriminator | Protects low-key? | Advisory or automatic | Would it reject a 95%-black Statue of Liberty? |
|---|---|---|---|---|---|
| **Lightroom Classic / Lightroom** | **Yes** — "Exposure issues", "Misfires" | Subject/Eye sharpness scores + Eyes Open; exposure & misfire classifiers (undisclosed) | **No** | Advisory badges; opt-in skip-import or permanent delete | **Yes — highest risk.** "Exposure issues" is an explicit reject class with no intent test |
| **Capture One** | **Yes** — "black frames" / "exposure problems" | Closed eyes, missed focus, exposure (no algorithm published) | **No** | Advisory only — tags, never deletes | **Yes — highest risk.** "Black frames" names our frame class directly |
| **Aftershoot** | Partial — "blown exposures" in FAQ copy only; no dark/blank bucket | 1–100 learned score over "30+ scoring factors; sharpness, exposure, blinks, duplicates, facial expressions, composition" | **No** (carve-outs exist only for closed eyes & motion blur) | **Automatic** in AI-Automated mode; writes XMP star+colour; non-destructive | **Probably** — exposure is a scored factor and there is no dark-frame exemption |
| **FilterPixel** | Partial — "misfires" generically; no dark/blank detector | Learned model; DeepCull scores 6 named criteria incl. **"Subject Lighting"** | **Partial, and not for exposure** — a REVIEW bucket exists for "creative choices (intentional blur, motion)" | Advisory — "sorts, not deletes"; XMP | **Likely down-ranked**, probably landing in REVIEW rather than REJECTS |
| **Narrative Select** | **No** | Face-gated Focus Score 1–10, Eye States; scene-relative First Pass | No — but no exposure check to protect against | **Advisory only** — "never deletes photos or makes selections" | **No** — safe by omission |
| **ON1 Photo RAW** | **No** (core app is manual; AI culling is the separate **Lightpanel** plugin) | Lightpanel: focus scoring + closed/blurry eyes + similarity grouping | No — but no exposure check | Advisory, flag-based | **No** — safe by omission |
| **Optyx** | **No** | Face-gated "Absolute Conditions" (Sharp/Adequate/Poor Focus); autogroup by content similarity, time, exposure brackets | **No** intent detector, but **face-gating** exempts frames with no face; "Low Light" focus preset | Advisory; writes XMP `Rating`/`Label`; per-photo locking | **No** — a no-face night frame is not an auto-reject candidate |
| **Excire Foto / Excire Search** | Descriptive only — "Dark"/"Bright" are **searchable keywords, not reject flags** | Aesthetics + sharpness (incl. face/eye) + expression; duplicate similarity | No — but darkness is never a penalty | Advisory; "flag assistant does **not** automatically delete photos" | **No** — safe by omission |
| **Photo Mechanic / Plus** | **No — none at all** | None. Manual stars, tags, 8 colour classes | N/A — no automated judgement exists | 100% manual | **No** — nothing to reject it |

---

## Per-tool detail

### Adobe Lightroom Classic / Lightroom — "Assisted Culling"

- Shipped in **15.0 (Oct 2025)** as Early Access: "Quickly select the best shots from a large set of images with Assisted Culling. This feature is currently available as Early Access." Extended in **15.4 (June 2026)** with a Faces panel: "Review Eye Focus and Eyes Open scores and details for each face in a photo." No culling feature appears in any 14.x entry — https://helpx.adobe.com/lightroom-classic/desktop/introduction-to-lightroom-classic/whats-new.html
- **The reject taxonomy is explicit**: "Choose from the following Reject options to define what to exclude photos from the collection: **Documents and receipts** … **Misfires**: Choose this to reject images captured accidentally. **Exposure issues**: Choose this to reject images with exposure problems." — https://helpx.adobe.com/lightroom-classic/desktop/import-photos/assisted-culling-at-import.html
- Same wording in cloud Lightroom: "Exposure issues: Rejects photos with exposure problems. Misfires: Rejects photos captured accidentally." — https://helpx.adobe.com/lightroom/desktop/organize-photos/assisted-culling.html
- Discriminators exposed to the user are **focus-only**: "Subject Focus: … Drag the slider to adjust the subject focus threshold. Eye Focus: … Drag the slider to adjust the eye focus threshold", with scores for "Subject Sharpness, Eye Sharpness, Eye Open" and a "Can't Tell" bucket. **No slider is documented for the exposure or misfire classifiers** — they are on/off checkboxes. Same URL.
- **Advisory by default, automatic if you opt in.** Badges are shown for review, but LrC import offers "Don't Import Rejected Images to exclude the rejected images from getting imported" (rejects are never seen), and cloud Lightroom's batch actions include "**Delete**: Deletes all the rejected images from your catalog permanently." Same URLs.
- Manual reject is unchanged and unrelated: P/X are keyboard shortcuts, and the only built-in auto-flagging is workflow recycling — "The Refine Photos command causes unflagged photos to be flagged as rejected" — https://helpx.adobe.com/lightroom-classic/desktop/organize-photos-in-lightroom-classic/flag-label-rate-photos.html
- Duplicate detection is **exact-file only**: "Photos are considered duplicates only when they contain the same image data" — https://helpx.adobe.com/lightroom-classic/desktop/organize-photos-in-lightroom-classic/find-and-manage-duplicate-photos.html. Visual-similarity grouping is the separate Auto Stack feature — https://helpx.adobe.com/lightroom-classic/desktop/organize-photos-in-lightroom-classic/auto-stack.html
- **No numeric thresholds published.** Only "drag the slider" language.
- **Low-key protection: none documented**, across the What's New pages and both Assisted Culling articles.

> Would it reject our frame? **Yes, and this is the worst case in the survey** — "Exposure issues" is a binary checkbox with no sensitivity control and no documented intent test, and the reject can be wired to skip import entirely.

### Capture One — "Assisted Review (Beta)"

- **16.8, released 28 May 2026.** Verbatim from the release notes, independently re-fetched and confirmed: "**Assisted Review** (Beta), which helps automatically filter out closed eyes, out-of-focus eyes, and **black frames** without the need for manual sorting." — https://support.captureone.com/hc/en-us/articles/35747427882653-Capture-One-16-8-release-notes
- Same page, feature section: "**Assisted Review** uses AI to automatically flag images with technical issues (closed eyes, missed focus, and exposure problems)."
- **Documentation discrepancy worth noting**: the dedicated feature article never repeats "black frames". It lists only "Closed or out of focus eyes; Exposure issues (bad exposure)" and FAQs "Assisted Review currently flags closed eyes, missed focus, and exposure problems." — https://support.captureone.com/hc/en-us/articles/35841394167837-Assisted-Review-Beta. Read together: **"black frame" is a marketing label for the exposure classifier**, not a separate detector.
- Output is four categorical tags: "Every image receives a tag within the three categories – Need review, Issues Detected & Can't tell", plus "No Issues Detected". **No scores, no sliders, no thresholds.** Same URL.
- **Advisory only, and unusually explicit about it**: "Does Assisted Review automatically remove images? **No. Assisted Review only tags images. You remain in full control of all selection and deletion decisions.**" and "designed to complement your own selection process by highlighting potential issues, not to replace human judgement." Same URL.
- Vendor concedes accuracy limits: "Detection accuracy may vary, and some issues can be missed or flagged incorrectly." Same URL.
- Baseline culling remains manual star/colour tagging — https://support.captureone.com/hc/en-us/articles/7185822431645-Culling-images
- **Low-key protection: none documented.**

> Would it reject our frame? **Yes — it names the class.** Mitigated only by being tag-only and reversible; nothing is deleted or hidden.

### Aftershoot

- Canonical bucket list — no blank/dark/test-shot category exists: "we update ratings to bucket images int[o]: – Selected – Highlights – Closed Eyes – Blur – Duplicates" (https://aftershoot.com/culling-faq/); "it places them into 5 filter groups - Selected, Highlights, Duplicates, Blurry, and Closed Eyes" (https://support.aftershoot.com/en/articles/6508163-setting-your-ai-automated-culling-preferences-in-aftershoot). Plus Warnings and a "Maybe" bucket in Extreme cull (https://aftershoot.com/blog/understanding-filters-in-aftershoot/).
- Exposure appears **once**, in FAQ prose, and is not a toggleable filter: "The AI automatically flags blurry frames, closed eyes, and **blown exposures**, and groups near-identical burst shots" and "analyzes every image across 30+ scoring factors; sharpness, **exposure**, blinks, duplicates, facial expressions, and composition" — https://aftershoot.com/culling-faq/. Note this names *blown* (over-) exposure, not dark frames.
- Learned model with a published scale: "assigns each image a score from 1 to 100 — the higher the score, the better" — https://support.aftershoot.com/en/articles/10601968-technical-answers-about-aftershoot
- Duplicates: "it groups similar images into separate groups and selects the best image for you, out of each group." Same URL.
- **Creative-intent carve-outs exist — but only for eyes and blur, never exposure.** Boudoir: "We recommend turning off the Closed Eyes detection to avoid missing out on shots with artistic decisions and intentionally closed eyes"; New Born: "run it with Closed Eyes off" — https://support.aftershoot.com/en/articles/10570203-aftershoot-culling-genres. Blur: "If you are shooting a specific way as a creative choice (such as dragging the shutter), then adding the images back in using the A key tells Aftershoot to include more of these images in the future" — https://aftershoot.com/blog/understanding-filters-in-aftershoot/
- **Genre scoping is the real answer on intent**: the Culling Genres list is Weddings & Engagements, Portrait & Headshots, Family Portraits, Boudoir, Sports, School Portraits, School Events, New Born, "Something Else". **There is no landscape, night or astro genre.** Same Culling Genres URL.
- Personalised learning is claimed generally, not for dark work: "if you prefer images with more emotions over images with perfect focus, the AI will try to prioritize that" — https://support.aftershoot.com/en/articles/10601968-technical-answers-about-aftershoot
- **Automatic, but reversible**: "the AI adds sidecar files - XMPs - to add Star and Color ratings … You can delete the XMP files to remove Aftershoot's ratings if you wish" and "Aftershoot is non-destructive - it will never delete images unless you do it yourself, even the ones it rejects." Same URL. In AI-Automated mode "Aftershoot makes all the initial selections for you"; AI-Assisted mode leaves "every decision" to the user — https://aftershoot.com/culling-faq/
- Sliders (Duplicates, Blurry, Closed Eyes, Highlights) are qualitative: "the more a slider is to the RIGHT the FEWER images you will be getting" — no numeric scale published.

> Would it reject our frame? **Probably down-rank it.** Exposure is one of the scored factors, no dark-frame exemption is documented, and every shipped genre profile is a people genre.

### FilterPixel

- Three-bucket taxonomy: "**REJECTS** — Probably not, but fully recoverable. Out-of-focus shots, blinks, duplicate angles." — https://filterpixel.com/culling. "Misfires" appear only as a generic goal: "Remove blurry shots, misfires, accidental shutter presses, and images with closed eyes" — https://filterpixel.com/what-is-photo-culling
- Discriminator: "Technical Analysis: Sharpness, **exposure**, noise level, and focus accuracy … Expression & Moment: Eye openness, smile detection … Composition & Context" — https://filterpixel.com/what-is-photo-culling
- **DeepCull publishes per-criterion scores** — six named criteria with example values "Subject Lighting 7 / Background Cleanliness 6 / Narrative Clarity 8 / Brand Safety 8 / Moment Timing 5 / Technical Quality 6" (scale bounds not stated; 0–10 inferred from the examples) — https://filterpixel.com/deepcull
- **The nearest thing in any shipping product to an intent hedge**, though it is about blur, not darkness: "**REVIEW** — Worth a second look … interesting moments that might work, or **creative choices (intentional blur, motion, etc.)**" — https://filterpixel.com/culling
- Genre-scoped away from weddings: DeepCull models for Conferences/Corporate, Sports, Concerts/Live Events, high-volume deadline work — "Every other culling tool was built for weddings. This one wasn't." Same URL. Still no landscape/night genre.
- Advisory and non-destructive: "FilterPixel doesn't delete. It sorts … Every image in REJECTS is 100% recoverable with one click … **The AI suggests. You decide.**" — https://filterpixel.com/culling. DeepCull FAQ: "Will DeepCull delete any of my photos? Never." — https://filterpixel.com/deepcull
- Writes XMP: "writes the results as XMP metadata, and Lightroom picks them up in place" — https://filterpixel.crisp.help/en/article/i-have-already-imported-photos-into-lightroom-how-should-i-use-filterpixel-etjefx/
- "Magic Number" sets a target output count rather than a quality threshold — https://filterpixel.crisp.help/en/article/mastering-filterpixels-magic-number-cull-option-h7zfue/
- Self-reported benchmark ("94.7% keepers / 96.1% rejects flagged correctly" on the vendor's own 2,740-image set) is first-party marketing, not independently audited — https://filterpixel.com/best-ai-photo-culling-software
- **No raw numeric threshold** (no Laplacian-variance or EV cutoff) published anywhere.

> Would it reject our frame? **Likely scored down via "Subject Lighting"**, but the REVIEW bucket makes it recoverable rather than binned. The structural idea — a third "uncertain" bucket — is the most reusable thing in this survey.

### Narrative Select

- Documented assessments are **face-and-focus only**: "Contextual Eye States, Focus Scores, Eye States, Eye State Scores … over 17 different assessments" — https://narrative.so/select/face-assessments; "The ellipse indicates our assessment of their face … The line underneath indicates our assessment of their focus" — https://help.narrative.so/en/articles/7337369-face-and-focus-assessments
- **Focus Score is gated on a detected face**: "Any image that contains at least one detected face will receive a focus score. This score is calculated using several factors including the focus of each individual subject, how important those subjects are within the scene, and the overall context of the image." — https://help.narrative.so/en/articles/7337374-filter-by-focus-score
- Non-face content falls back to sharpness ranking only: "Every image in a scene ranked by sharpness, whether you're shooting portraits, detail shots, florals, or wildlife" — https://narrative.so/select
- **First Pass is explicitly relative, not absolute** — an important design point: "These assessments give you guidance based on relative differences between images in a scene – **they are not an objective rating of a single image.**" First Pass+ (beta) "moves away from purely relative ratings toward more objective ones." — https://help.narrative.so/en/articles/7337372-first-pass-image-assessments
- Strictness setting is Ruthless / Balanced / Cautious, described only in terms of distribution: "Changing this setting shifts how images are distributed across the five categories — it never deletes photos or makes selections." Same URL.
- **Advisory only, confirmed first-party**: same quote above. No page describes Narrative writing XMP ratings or reject flags; the documented handoff is export — "Ship direct to Lightroom" — https://narrative.so/select
- **Published scale is 1–10, not 0–100**: "Focus scores range from 1 (lowest) to 10 (highest)" — https://help.narrative.so/en/articles/7337374-filter-by-focus-score; "Hover over them to see the score out of 10" — https://help.narrative.so/en/articles/7337369-face-and-focus-assessments. The widely repeated "0 to 100" figure comes from a review site (https://shotkit.com/narrative-select-review/) and is **SECONDARY and contradicted by the vendor** — treat as wrong.
- **No exposure, blank-frame or dark-frame detector is named on any page checked.**

> Would it reject our frame? **No.** There is no brightness discriminator at all, and its scene-relative framing means a frame is only ever compared against its own siblings.

### ON1 Photo RAW

- **"Auto Cull" does not exist as an ON1 feature name** — not found on any on1.com page. Core Photo RAW culling is manual: "Speed up your workflow by learning how to quickly sort, rate, and select your best images from a shoot" — https://www.on1.com/videos/culling-photos-quickly/
- ON1's AI culling is a **separate product**, "Lightpanel", an ON1 Pro plugin for **Lightroom Classic**, not part of Photo RAW: "Lightpanel flags photos with closed eyes or blur" / "uses intelligent grouping, facial detection, and focus scoring to flag your best shots—automatically" — https://www.on1.com/products/lightpanel/
- Only two automated criteria plus grouping. Support-article excerpt: "During the second phase of the Analysis, closed and blurry eyes are detected (if enabled in Preferences)" — https://on1pro.zendesk.com/hc/en-us/articles/33753176173581-Culling-Closed-and-Blurry-Eyes (**caveat: retrieved as a search-index excerpt; the page sits behind a Zendesk login wall and could not be fetched in full**).
- **No exposure, dark-frame or blank-frame detection is mentioned anywhere** in ON1's own pages.
- Advisory, flag-based, reversible. No numeric scale published.
- A review site describes an ON1 "Culling Studio" doing blur "Technical Analysis"; this could not be corroborated on any on1.com/on1pro page — **SECONDARY, unverified**.

> Would it reject our frame? **No** — blur and eyes only.

### Optyx (optyx.app)

- Vendor confirmed: native Mac **and Windows** app, docs at blog.optyx.app — https://www.optyx.app/ , https://blog.optyx.app/tutorials/learning-optyx/
- **The face-gate is stated as a hard scope limit, and it is the single most useful sentence in this survey**: "As of Optyx v1.3, **only photos with obvious faces are candidates for absolute conditions**." — https://blog.optyx.app/tutorials/learning-optyx/#absolute-conditions. The three Absolute Conditions (which can eliminate a whole photo) are Sharp Focus / Adequate Focus / Poor Focus, all defined on face sharpness. **A frame with no detectable face cannot be auto-rejected.**
- Broader claim on the homepage: "rate them according to facial expression, sharpness, composition, exposure, and more!" — https://www.optyx.app/ — but no exposure-based reject rule appears in the documented condition list.
- Exposure appears only as a **grouping** input, not a quality signal: Autogroup sliders are "Content Similarity, Time, Exposure Brackets … automatically identify bracketed shots for HDR or exposure stacking" — https://blog.optyx.app/tutorials/learning-optyx/#autogroup
- Selective Conditions: Best Overall, Best Faces, Happiest Faces, Sharpest, Solo Group, Unmatched — https://blog.optyx.app/tutorials/learning-optyx/#conditions
- **Closest thing to a shooting-condition adaptation** (blur tolerance, not intent): "A shot in a studio with high-quality strobe lighting should always be extremely sharp while a photo in a dimly lit church with natural light will naturally be less defined … if you tend to shoot in low-light situations where some amount of blur or soft focus is to be expected, set the threshold to 'Low Light'." — https://blog.optyx.app/tutorials/learning-optyx/#focus-detection
- Per-photo opt-out exists: five "Management Methods" from Unlocked to Completely Locked exempt photos from autocull/autogroup — https://blog.optyx.app/tutorials/learning-optyx/#management-methods-locking
- Writes XMP only: "Optyx saves all metadata to industry-standard XMP sidecars" (https://www.optyx.app/); actions are "Set Color Label" (XMP `Label`) and "Set Rating" (XMP `Rating`) — https://blog.optyx.app/tutorials/learning-optyx/#actions. **No delete action exists.**
- **No aggregate quality/aesthetic score and no CLIP/natural-language search documented.** No numeric thresholds — sliders with qualitative endpoints only.

> Would it reject our frame? **No** — the face-gate exempts it. Note this is scoping, not intent-awareness: Optyx isn't protecting the photo, it simply has no opinion about it.

### Excire Foto / Excire Search

- **Darkness is a searchable descriptor, never a penalty.** The AI keyword vocabulary includes "Dark", "Bright", "High Contrast", "Low Contrast", "Colorless", "Unsaturated" as *filterable keywords* in the Find-by-Keyword panel — https://excire.com/manuals/ExcireFoto2024_Quickstart-EN.pdf (p.20). No "reject if dark" rule is documented.
- Selection discriminator: "Quickly identify your best shots by analyzing **aesthetics, sharpness, and facial expressions**. Cull faster with Smart selection." — https://excire.com/en/excire-foto/. Plugin sibling: "Best-shot detection – Instant AI analysis of sharpness, facial expressions, and/or aesthetics"; feature table lists "Aesthetic ratings" and "Automatic focus checking" — https://excire.com/en/excire-search/
- Sharpness tooling is a review aid, not a gate: "Check sharpness at a glance with intelligent detection and focus peaking" — https://excire.com/en/excire-foto/
- **Advisory and explicitly non-destructive**: "The flag assistant does **not automatically delete photos**, but only marks them with appropriate flags, which can then be used to select for the deletion process." — Quickstart manual p.14. AI keywords are user-editable (p.8).
- Published numbers: keyword confidence **0.01–0.99** (p.8); find-similar distance limit **1–100**, strict→loose (p.21); duplicate similarity slider is qualitative "very strict / strict / medium / loose / very loose" (p.13).
- The often-cited "aesthetic score out of 100" is **SECONDARY only** (https://amateurphotographer.com/review/excire-photo-2025-excire-search-2026-review-organising-photos-has-never-been-easier/) and was not confirmed on any excire.com page.
- Excire Analytics is retrospective gear statistics, not per-photo triage (Quickstart p.24).
- **Low-key protection: none documented** — but also no exposure penalty to protect against.

> Would it reject our frame? **No.** It would tag it "Dark" and "High Contrast" and leave it alone. This is the closest shipping behaviour to what we want: **describe the darkness, don't judge it.**

### Photo Mechanic / Photo Mechanic Plus

- **No automated quality analysis of any kind exists.** The vendor's own feature tour frames it as a fast manual browser: "Plug in your memory cards and start picking winners and deleting rejects almost instantaneously … Cull, rate, and tag them as you go." — https://home.camerabits.com/tour-photo-mechanic/ . The tour covers Ingest, Contact Sheet, Keywords, Variables, Batch Editing, GPS, Export — no AI/quality feature.
- Selection is entirely human: "Tags are simple toggles you can use to help you sort through and cull photos. A photo is either tagged or untagged." — https://docs.camerabits.com/en/support/solutions/articles/48001142232 ; "Photo Mechanic has eight different color classes in addition to 'None' … You can use these to sort, select, and filter your photos." — https://docs.camerabits.com/support/solutions/articles/48001142942
- **Plus adds a catalog layer only** — the Plus documentation category contains "Getting Started", "Catalog Settings and Preferences", "Best Practices", "Catalog Troubleshooting" and no AI/quality section — https://docs.camerabits.com/support/solutions/48000450977
- Exposure and brightness are **never mentioned** in the culling documentation. No thresholds, no scores.

> Would it reject our frame? **No** — there is no automated judgement to reject anything.

---

## Patent literature

Patents state discriminators that marketing hides. Five granted patents were read in full.

### PhotoSi US11586669B2 — "Process for the automatic selection of digital photographs from an archive" (granted 2023-02-21) — **the most important source in this report**
https://patents.google.com/patent/US11586669B2

This is the only primary source found anywhere that explicitly distinguishes a *failed* dark frame from an *intentional* one, and it publishes the parameters.

- The figures state the distinction outright: "**FIG. 2 represents a dark photograph that is rejected** by the process according to the invention" (described in the text as "a night-time landscape") versus "**FIG. 4 represents a dark photograph that is selected** by the process according to the invention **as it has sufficient contrast**" — described as "a photograph … that represents a work of art in a dark environment, illuminated by a source inside the work itself."
- **Two-stage discriminator.** Stage 1 is a brightness screen used only as a *trigger*, never as a verdict: convert to 256-level greyscale, split into five intervals, and count what fraction of pixels sit in the extreme intervals — "if in the initial interval and/or the final interval there is a total percentage of pixels of the photograph greater than … a predetermined threshold, **the contrast is evaluated**." Stage 2 is the actual verdict: "if the contrast of the photograph converted to greyscale is ≤ a predetermined threshold, the photograph is rejected."
- **Contrast is computed noise-trimmed**, which is what makes it work: "the image has 12080256 pixels and 2% is equal to 241605 pixels … we look in the histogram for the highest intensity value for which there are at least 241605 lighter pixels. In our case this is the intensity value 42 … Therefore, the contrast net of the noise, most in line with the contrast perceived by the human eye, is equal to 40."
- **Published parameters**: "parameter_1 e.g. **75%** (potential underexposure and/or overexposure threshold); parameter_2 e.g. **2%** (rejection threshold of pixels that do not fall within the contrast calculation); parameter_3 e.g. **125** (contrast threshold net of noise)."
- Also documented: a blur criterion in greyscale, a best-of-similar-photographs criterion, and a hard floor on file weight in KB / pixel count. Criteria are applied in sequence, each only to photos not already rejected.
- Wording caveat: the text says a *low* contrast value means "the photograph is overexposed", which is a translation artifact — the logic is direction-agnostic (low trimmed contrast = flat frame, whether flat-dark or flat-bright).

> Would it reject our frame? **No — it is designed not to.** 95% black trips the 75% screen, then trimmed contrast between the lit statue (~200+) and the sky (~5) is far above 125, so the frame is **selected**. Note the honest limit: FIG. 2, a genuinely flat *night landscape* with no bright subject, **is** rejected. So this discriminator protects "dark with a lit subject", not "dark" in general.

### Apple US20130058590A1 — "Detecting Image Detail Level" (2013)
https://patents.google.com/patent/US20130058590A1

- Names our exact frame class: "FIG. 5C is a bar chart representing band pass information corresponding to a **substantially blank image**", and lumps causes together: "the lack of detail can result from a photograph being blurry (e.g., out of focus), washed out (e.g., overexposed), distorted (e.g., noisy), or **blank**."
- Discriminator is **multi-scale band-pass detail energy**, not brightness: blur the image with kernels of increasing radius (worked example: radii 1, 2, 4, 8, 16, 32, 64, capped at 25% of the long edge), take successive differences D1…D6, and compute a high-to-low frequency ratio.
- **The blank test is an absolute low-frequency energy floor**: "if the amount of information associated with each of the lower frequency bands is very low, the image can lack sufficient information to effectively represent anything (e.g., being substantially blank)." Implemented via a constant: "C can be a constant value (e.g., **3.0**) … Thus, the max function selecting C can indicate D4, D5, and D6 are all lower than C and that the corresponding image is **substantially blank**."
- Published example ratios: sharp = 0.27, medium = 0.16, unrecognisably blurry = 0.02, blank = a spuriously high 0.5 (which is exactly why the floor is needed). Output scale "e.g., 1-10, 1-1000, or 0.0-1.0".
- Scope matters: this is a **gate on face-recognition reliability**, not an aesthetic reject — "the need to determine whether an image includes sufficient detail to perform an accurate facial recognition process."

> Would it reject our frame? **Yes, if used as a reject gate.** The energy is aggregated globally, so a small bright subject on a large black field falls under the C=3.0 floor and is called "substantially blank". **This is precisely the false-positive mechanism to avoid: a global detail-energy floor cannot tell a void from a spotlit subject.** PhotoSi's trimmed-contrast percentile can.

### Adobe US10521705B2 — "Automatically selecting images using multicontext aware ratings" (2019)
https://patents.google.com/patent/US10521705B2

- Attribute list is the fullest public statement of what Adobe scores: "Attributes can comprise **low-level attributes such as blurriness, sharpness, compression, lighting, color histogram, wavelet**, etc. Attributes can also comprise high-level attributes such as eyes open, face quality, rule of thirds, image aesthetics, facial expression, smiling face, pose." Scores are "a value between zero and one or between zero and one-hundred."
- **Darkness is explicitly a learned negative**: the network learns "an amount of **darkness**, light, contrast … to define higher-level image aesthetics"; image characteristics include "**noise, darkness, contrast, structure**"; and the training target is stated plainly — "train an image-quality classification neural network to classify images having sharpness, high resolution, and **good exposure** as high quality and images having **bad lighting**, blur, and noise as low quality."
- "Low quality faces are faces that have motion blur, are out of focus, have **bad illumination or exposure** …"
- **"Context" means subject category, not creative intent.** Context probabilities (selfie, group portrait, landscape, action…) select per-context attribute weights. And the worked landscape example runs the wrong way for us: the system assigns "a landscape context-specific score for the image 120 that is lower … **due to the building in the image 120 being in shadow** … based at least on the darker building."

> Would it reject our frame? **Yes, it would down-rank it.** Adobe's own patent uses shadow/darkness as evidence of low quality in the landscape context — the closest thing to intent-modelling in the Adobe portfolio still penalises dark subjects.

### Adobe US9817847B2 — "Neural network image curation control" (2017)
https://patents.google.com/patent/US9817847B2

- Curation = "calculating a score based on **image and face aesthetics, jointly**, for each of the plurality of images through processing by a neural network, ranking the plurality of images based on respective scores, and selecting one or more … based on the ranking **and a determination that the one or more said images are not visually similar to images that have already been selected**."
- Purely relative and diversity-aware — it picks representatives from a repository rather than rejecting failures, and greedy selection enforces dissimilarity. No exposure rule, no absolute threshold.

> Would it reject our frame? **Not as a failure.** It could omit it from a representative set, but omission from a highlight reel is not a reject. The diversity constraint is worth borrowing.

### Apple AU2017261537B2 — "Automated selection of keeper images from a burst photo captured set"
https://patents.google.com/patent/AU2017261537B2

- **Notable for what it does *not* use: brightness plays no role in the keep/discard decision.** Pipeline is a UV-chroma 2D colour histogram (used for scene/action similarity, not exposure), a sharpness measure ("sum of adjacent pixel differences", or from the camera's AF/AE systems), and a Haar-wavelet blur estimate.
- **The reject rule is relative, not absolute**, and the ratio is published: "if the quality metric of an image is smaller than the maximum quality metric value of the image set multiplied by a ratio, the image may be regarded as too blurry to use (e.g., a **ratio of between 0.6 and 0.9**)."
- Category-conditional logic: bursts are classified portrait / action / other, and each is judged differently ("For a portrait burst, the approach may select one image with the most smiling, non-blinking faces").
- Tight compute budget: "35-55 milliseconds for data collection, processing and analysis."

> Would it reject our frame? **No** — nothing keys on brightness, and the sharpness test is only ever against co-captured siblings. **The relative-to-best-sibling design is the safest pattern in the survey**: a frame is never condemned on its own absolute numbers.

### Google US10891485B2 — "Image archival based on image categories" (2021)
https://patents.google.com/patent/US10891485B2

- The one shipped-scale auto-hide system that keys on **semantics, not quality**: "the image category for archival includes one or more of **document, meme, and/or screenshot**", via "an image classifier trained to classify input images as a document, meme, and/or screenshot", with "a confidence score … for each of the plurality of categories" against "a confidence threshold".
- **It models intent explicitly** — and by content type, not by pixel statistics: "a technical problem in image management is to recognize image content and **determine user intent to capture or store an image**."
- **Advisory and reversible by construction**: archival requires "first user input to archive at least one of the one or more images of the subset", and archive hides from a view rather than deleting.
- Related Google filings on selective retention (https://patents.google.com/patent/US9836484B1, https://patents.google.com/patent/US10732809B2) concern on-device storage triage at capture time, not post-hoc culling of a library.

> Would it reject our frame? **No.** Google's shipped auto-hide never asks "is this too dark" — it asks "is this a utility artifact rather than a photograph". That reframing is the most transferable idea here: **a night photograph and a lens-cap misfire differ in *kind*, not in *brightness*.**

---

## Negative findings — what nobody does

1. **No tool, in any documentation, distinguishes an intentionally dark photograph from a failed one.** Ten tools, ~40 vendor pages. Every vendor that judges exposure (Adobe, Capture One, Aftershoot, FilterPixel) applies it unconditionally; every vendor that spares dark frames does so because it never looks at brightness at all.
2. **Creative-intent language exists, but never for exposure.** Aftershoot documents intent carve-outs for *closed eyes* (boudoir, newborn) and *motion blur* (dragging the shutter); FilterPixel's REVIEW bucket names "intentional blur, motion". Searches for dark/silhouette/low-key/night intent language returned nothing on any vendor site. The industry has accepted that blur and closed eyes can be deliberate. **It has not yet accepted that darkness can be deliberate.**
3. **No vendor publishes a single numeric exposure threshold.** Adobe ships an "Exposure issues" checkbox with no slider; Capture One ships four categorical tags with no scores. Every published number in this report is either a *score scale* (Aftershoot 1–100, Narrative 1–10, Excire 0.01–0.99, FilterPixel ~0–10) or comes from a patent, never from a shipping exposure detector.
4. **"Blank frame" is barely a named concept in products, and heavily named in patents.** No vendor has a bucket called blank, black, void, empty, test shot or lens cap. Capture One's "black frames" is a marketing gloss on its exposure classifier. Meanwhile Apple's patent says "substantially blank image" outright and gives it a constant.
5. **No tool has a genre profile for night, astro, landscape or minimalist work.** Aftershoot's nine genres are all people genres; Narrative markets Weddings/Family/Portrait; Optyx and ON1 gate on faces; FilterPixel targets conferences/sports/concerts. Our collection is outside every documented target genre — which is why "safe by omission" is fragile: these tools are all actively adding coverage.
6. **Advisory is the industry norm, and the exceptions are opt-in.** Capture One, Narrative, FilterPixel, Excire, ON1 and Optyx never delete. Aftershoot auto-selects but writes reversible XMP. **Only Adobe documents paths to irreversible action** — "Don't Import Rejected Images" (rejects never enter the catalog) and cloud Lightroom's "Delete: Deletes all the rejected images from your catalog permanently."
7. **Research limitation, stated rather than papered over:** Google Patents' query endpoint began rate-limiting mid-session, so two targeted searches for patents on *intent-aware* or *intentional-underexposure* quality assessment could not be completed. I therefore **cannot** claim no such patent exists — that specific question is unresolved. All five patents cited above were fetched and read in full before the limit hit. One ON1 support page (on1pro.zendesk.com) sits behind a login wall and is cited from a search-index excerpt only.

---

## Implications for our detector

- **Do not use mean/median luminance or percent-black.** Every vendor discriminator that would destroy our night photographs is a brightness or global-detail-energy test. Adobe's own patent penalises "the building … being in shadow"; Apple's blank test is a global detail floor that a spotlit subject on black cannot clear.
- **Use noise-trimmed contrast as the verdict and brightness only as a trigger.** PhotoSi US11586669B2 is a working, patented, numerically specified template: percent-of-pixels-in-extreme-bins (75%) decides *whether to look further*; percentile-trimmed dynamic range (2% trim, threshold 125/255) decides *keep or reject*. Our Statue of Liberty passes; a genuine lens-cap frame does not.
- **Prefer relative-to-sibling over absolute judgements** (Apple's 0.6–0.9 ratio against the best frame in the set). A frame condemned only relative to a near-identical sibling can never be condemned for being the only frame of its kind.
- **Classify by kind, not by degree** (Google US10891485B2). "Is this a misfire/test frame?" is a different and safer question than "is this too dark?" — and it is the question that actually matches our failure mode.
- **Ship a three-bucket output, not two** (FilterPixel KEEPERS/REVIEW/REJECTS, Capture One's "Can't tell"). Uncertainty about intent should route to review, never to reject.
- **Stay advisory and reversible.** The industry consensus is tags/XMP, never deletion. Given that a false positive here costs us our best work, advisory is not just polite, it is the only defensible default.
