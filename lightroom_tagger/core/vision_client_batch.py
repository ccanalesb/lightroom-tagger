"""Batch compare helpers loaded after :mod:`vision_client` to avoid import cycles."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, cast

import openai as openai_sdk

LogCallback = Callable[[str, str], None] | None


def compare_images_batch(
    client: openai_sdk.OpenAI,
    model: str,
    reference_path: str,
    candidates: list[tuple[int, str]],
    log_callback: LogCallback = None,
    max_tokens: int = 4096,
) -> dict[int, float]:
    import lightroom_tagger.core.vision_client as vc

    if not candidates:
        return {}

    ref_b64 = vc._encode_image(reference_path)

    candidate_info = "\n".join([f"Candidate {cid}: (image attached)" for cid, _ in candidates])

    batch_prompt = (
        "CRITICAL: You MUST respond with ONLY valid JSON. No explanations, no prose, ONLY JSON.\n\n"
        "Task: Compare the FIRST image (reference) against the remaining candidate images.\n"
        "For each candidate, determine if it depicts the SAME photograph as the reference.\n\n"
        f"Reference image: First image\n"
        f"Candidates to compare:\n{candidate_info}\n\n"
        "REQUIRED OUTPUT FORMAT (copy this structure exactly):\n"
        '{"results": [{"id": 1, "confidence": 85}, {"id": 2, "confidence": 10}, ...]}\n\n'
        "Rules:\n"
        "- confidence: 0-100, where 0=completely different, 100=definitely same photo\n"
        "- Compare semantic content: subject, scene, composition, angle\n"
        "- Ignore: crops, quality, filters, color vs B&W\n"
        "- Include ALL candidate IDs in results\n\n"
        "RESPOND WITH ONLY THE JSON OBJECT. DO NOT ADD ANY OTHER TEXT."
    )

    content_parts: list[dict[str, Any]] = [
        {"type": "text", "text": batch_prompt},
        vc._image_url_part(ref_b64),
    ]

    for _cid, cand_path in candidates:
        cand_b64 = vc._encode_image(cand_path)
        content_parts.append(vc._image_url_part(cand_b64))

    kwargs: dict[str, Any] = {}
    if "claude" in model.lower():
        kwargs["extra_body"] = {"reasoning_effort": "none"}

    try:
        response = client.chat.completions.create(
            model=model,
            messages=cast(
                Any,
                [
                    {
                        "role": "system",
                        "content": "You are a JSON-only API. You respond exclusively with valid JSON. Never include explanations or prose.",
                    },
                    {
                        "role": "user",
                        "content": content_parts,
                    },
                ],
            ),
            max_tokens=max_tokens,
            temperature=0.1,
            **kwargs,
        )
    except Exception as exc:
        raise vc._map_openai_error(
            exc, provider=getattr(client, "_provider_id", None), model=model
        ) from exc

    raw = response.choices[0].message.content or "{}"

    if log_callback:
        log_callback("debug", f"[vision_batch] Raw response length: {len(raw)} chars")
        log_callback("debug", f"[vision_batch] Raw response (first 500 chars): {raw[:500]}")
        if len(raw) > 500:
            log_callback("debug", f"[vision_batch] Raw response (last 200 chars): ...{raw[-200:]}")

    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw)
        results_list = parsed.get("results", [])

        if log_callback:
            log_callback("debug", f"[vision_batch] Parsed JSON: results_list={results_list}")

        result_map: dict[int, float] = {}
        for item in results_list:
            cid = item.get("id")
            conf = item.get("confidence", 0)
            if cid is not None:
                result_map[cid] = float(conf)

        if log_callback:
            ref_name = os.path.basename(reference_path)
            log_callback(
                "debug",
                f"[vision_batch] {ref_name} vs {len(candidates)} candidates -> {len(result_map)} results",
            )

        return result_map

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        if log_callback:
            log_callback("warning", f"[vision_batch] JSON parse error: {e}, raw={raw[:100]}")
        return {cid: 0.0 for cid, _ in candidates}


def compare_descriptions_batch(
    client: openai_sdk.OpenAI,
    model: str,
    reference_text: str,
    candidates: list[tuple[int, str]],
    log_callback: LogCallback = None,
    max_tokens: int = 4096,
) -> dict[int, float]:
    import lightroom_tagger.core.vision_client as vc

    if not candidates:
        return {}

    candidate_info = "\n".join(
        [f"Candidate {cid}:\n{text}" for cid, text in candidates]
    )

    batch_prompt = (
        "CRITICAL: You MUST respond with ONLY valid JSON. No explanations, no prose, ONLY JSON.\n\n"
        "Task: Rate text semantic similarity between the reference summary and each candidate summary.\n"
        "For each candidate, output how well the candidate summary matches the reference in meaning "
        "(subject, scene, intent), not wording overlap.\n\n"
        f"Reference summary:\n{reference_text}\n\n"
        f"Candidate summaries:\n{candidate_info}\n\n"
        "REQUIRED OUTPUT FORMAT (copy this structure exactly):\n"
        '{"results": [{"id": 1, "confidence": 85}, {"id": 2, "confidence": 10}, ...]}\n\n'
        "Rules:\n"
        "- confidence: 0-100, where 0=completely unrelated, 100=essentially the same content\n"
        "- Include ALL candidate IDs in results\n\n"
        "RESPOND WITH ONLY THE JSON OBJECT. DO NOT ADD ANY OTHER TEXT."
    )

    content_parts: list[dict[str, Any]] = [
        {"type": "text", "text": batch_prompt},
    ]

    kwargs: dict[str, Any] = {}
    if "claude" in model.lower():
        kwargs["extra_body"] = {"reasoning_effort": "none"}

    try:
        response = client.chat.completions.create(
            model=model,
            messages=cast(
                Any,
                [
                    {
                        "role": "system",
                        "content": "You are a JSON-only API. You respond exclusively with valid JSON. Never include explanations or prose.",
                    },
                    {
                        "role": "user",
                        "content": content_parts,
                    },
                ],
            ),
            max_tokens=max_tokens,
            temperature=0.1,
            **kwargs,
        )
    except Exception as exc:
        raise vc._map_openai_error(
            exc, provider=getattr(client, "_provider_id", None), model=model
        ) from exc

    raw = response.choices[0].message.content or "{}"

    if log_callback:
        log_callback("debug", f"[desc_batch] Raw response length: {len(raw)} chars")
        log_callback("debug", f"[desc_batch] Raw response (first 500 chars): {raw[:500]}")
        if len(raw) > 500:
            log_callback("debug", f"[desc_batch] Raw response (last 200 chars): ...{raw[-200:]}")

    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw)
        results_list = parsed.get("results", [])

        if log_callback:
            log_callback("debug", f"[desc_batch] Parsed JSON: results_list={results_list}")

        result_map: dict[int, float] = {}
        for item in results_list:
            cid = item.get("id")
            conf = item.get("confidence", 0)
            if cid is not None:
                result_map[cid] = float(conf)

        if log_callback:
            log_callback(
                "debug",
                f"[desc_batch] reference vs {len(candidates)} candidates -> {len(result_map)} results",
            )

        return result_map

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        if log_callback:
            log_callback("warning", f"[desc_batch] JSON parse error: {e}, raw={raw[:100]}")
        return {cid: 0.0 for cid, _ in candidates}
