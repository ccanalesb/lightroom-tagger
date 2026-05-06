# Research Questions

## 2026-05-06: Where do missed image matches fail?

Use a read-only HTML comparison-pool report to classify missed Instagram-to-catalog matches before changing prompts.

Question: For unmatched Instagram images, is the expected catalog match absent from the comparison pool, present but scored/ranked poorly by the image comparison prompt, or present with evidence that downstream ranking/thresholding hides it?

Evidence to collect:

1. Unmatched Instagram image identifier and preview.
2. Actual catalog comparison pool for that Instagram image.
3. Candidate identifiers, scores, ranks, and model reasons when available.
4. Human judgment from inspection: expected match present, expected match absent, or no obvious match.

Why it matters: prompt tuning only helps if the expected catalog image reaches the prompt/comparison stage. If the pool generation is dropping candidates, the retrieval strategy needs work first.
