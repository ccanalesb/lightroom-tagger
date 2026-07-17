"""Assemble prose-only image description prompts and per-perspective scoring prompts."""

from __future__ import annotations

_COMPOSITION_BLOCK = """## Composition Analysis
Identify:
- **Layers**: List distinct depth layers (foreground, midground, background) and what occupies each. Note if layers are weak or missing.
- **Techniques**: Which composition techniques are present (rule_of_thirds, leading_lines, symmetry, framing, diagonal, golden_ratio, negative_space, repetition).
- **Problems**: Specific composition weaknesses (cluttered, no clear subject, awkward crop, distracting elements, missed focus). Empty list if none.
- **Depth**: shallow, moderate, or deep
- **Balance**: symmetric, asymmetric, or radial"""

_TECHNICAL_BLOCK = """## Technical Analysis
- **Dominant colors**: Up to 5 hex codes
- **Mood**: One word (contemplative, energetic, melancholic, joyful, tense, serene, dramatic, mysterious, flat, dull, chaotic, intimate, raw, quiet)
- **Lighting**: (natural_front, natural_side, natural_back, golden_hour, blue_hour, overcast, artificial, mixed, low_light, high_key, low_key)
- **Time of day** if discernible: (dawn, morning, midday, afternoon, golden_hour, blue_hour, night, unknown)

**Indexing fields (also at JSON root, see format below):** Top-level `dominant_colors`, `mood_tags`, and `has_repetition` take precedence for database indexing; keep `technical.dominant_colors` and `technical.mood` consistent with them when possible."""


def build_description_user_prompt(
    *,
    composition_block: bool = True,
    technical_block: bool = True,
) -> str:
    """Build the text user message for a prose-only structured description call."""
    intro = (
        "You are an experienced photo editor reviewing images for a photography portfolio. "
        "Be direct and constructive. State clearly what works and what doesn't — no flattery, "
        "no sugarcoating, but also no performative negativity. Every image has strengths and "
        "weaknesses; identify both with specifics.\n\n"
        "Analyze this photograph and return a structured JSON response with descriptive and "
        "technical fields only — do not score the image."
    )

    parts: list[str] = [intro]

    if composition_block:
        parts.append(_COMPOSITION_BLOCK)

    if technical_block:
        parts.append(_TECHNICAL_BLOCK)

    json_template = """## Required JSON format (respond with ONLY this JSON, no other text):
{
  "summary": "1-2 sentence objective description of the image content",
  "dominant_colors": ["#RRGGBB", "#RRGGBB"],
  "mood_tags": ["tag", "tag2"],
  "has_repetition": false,
  "composition": {
    "layers": ["foreground: <description>", "midground: <description>", "background: <description>"],
    "techniques": ["technique1", "technique2"],
    "problems": ["specific issue 1", "specific issue 2"],
    "depth": "shallow|moderate|deep",
    "balance": "symmetric|asymmetric|radial"
  },
  "technical": {
    "dominant_colors": ["#hex1", "#hex2"],
    "mood": "one_word",
    "lighting": "lighting_type",
    "time_of_day": "time_period"
  },
  "subjects": ["subject1", "subject2"]
}

**Root visual fields (required keys, use empty arrays or false if unknown):**
- `dominant_colors`: the 2–5 most salient colors as hex strings (`#RRGGBB`).
- `mood_tags`: short evocative tags (e.g. melancholic, tense) — not a paragraph.
- `has_repetition`: `true` if obvious repeating patterns, textures, or motifs; else `false`."""

    parts.append(json_template)
    return "\n\n".join(parts)


def build_scoring_user_prompt(perspective_row: dict) -> str:
    """Build the user message for a single-perspective numeric score (vision) call.

    Expects a ``perspectives``-shaped dict: ``slug``, ``display_name``, ``prompt_markdown``.
    The model must return **only** JSON matching :class:`~lightroom_tagger.core.structured_output.ScoreResponse`
    (not the prose-only describe schema from :func:`build_description_user_prompt`).
    """
    slug = str(perspective_row["slug"])
    display_name = str(perspective_row["display_name"])
    body = str(perspective_row.get("prompt_markdown", "")).strip()
    optional = bool(perspective_row.get("optional") or 0)

    contract_lines = [
        "Respond with ONLY a single JSON object and no other text. Keys must be exactly:",
        '- "perspective_slug" (string, must equal this slug verbatim)',
        '- "score" (integer from 1 through 10 inclusive)',
        '- "rationale" (concise plain string; no markdown code fences)',
    ]
    if optional:
        contract_lines.append(
            '- "not_attempted" (boolean): set true ONLY when this technique is '
            "genuinely absent from the photograph (not merely executed weakly), so "
            "the perspective is excused from the overall judgment instead of counted. "
            "Still provide a numeric score and a rationale explaining the absence. "
            "When unsure whether the technique is present, score low rather than "
            "setting not_attempted."
        )
    contract_lines.append(
        "Use the full rubric honestly; most images land between 4–6."
    )
    json_contract = "\n".join(contract_lines)

    return (
        "You are scoring one photograph for a single critical perspective. "
        "Apply the rubric below; be direct and specific.\n\n"
        f"## Perspective: {display_name} ({slug})\n{body}\n\n"
        f"{json_contract}"
    )
