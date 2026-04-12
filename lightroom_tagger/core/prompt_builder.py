"""Assemble multi-perspective image description prompts from DB perspective rows."""

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
- **Time of day** if discernible: (dawn, morning, midday, afternoon, golden_hour, blue_hour, night, unknown)"""


def build_description_user_prompt(
    perspective_rows: list[dict],
    *,
    composition_block: bool = True,
    technical_block: bool = True,
) -> str:
    """Build the text user message for a structured multi-perspective description call.

    *perspective_rows* dicts should include ``slug``, ``display_name``, and ``prompt_markdown``
    (as returned from the ``perspectives`` table / :func:`list_perspectives`).
    """
    n = len(perspective_rows)
    slug_list = [str(r["slug"]) for r in perspective_rows]
    best_alternatives = "|".join(slug_list)

    intro = (
        "You are an experienced photo editor reviewing images for a photography portfolio. "
        "Be direct and constructive. State clearly what works and what doesn't — no flattery, "
        "no sugarcoating, but also no performative negativity. Every image has strengths and "
        "weaknesses; identify both with specifics.\n\n"
        f"Analyze this photograph from {n} expert perspectives and return a structured JSON "
        "response.\n\n"
        "Each perspective below gets its own score — an image can be strong in one lens and weak "
        "in another. Also choose which single perspective fits this image best (best_perspective)."
    )

    parts: list[str] = [intro]

    for row in perspective_rows:
        display_name = str(row["display_name"])
        slug = str(row["slug"])
        body = str(row.get("prompt_markdown", "")).strip()
        parts.append(f"### Perspective: {display_name} ({slug})\n{body}")

    if composition_block:
        parts.append(_COMPOSITION_BLOCK)

    if technical_block:
        parts.append(_TECHNICAL_BLOCK)

    persp_json_lines: list[str] = []
    for row in perspective_rows:
        slug = str(row["slug"])
        persp_json_lines.append(
            f'    "{slug}": {{\n'
            '      "analysis": "2-3 sentences — what works, what doesn\'t, what would improve it",\n'
            '      "score": 1-10\n'
            "    }"
        )
    perspectives_inner = ",\n".join(persp_json_lines)

    json_template = f"""## Required JSON format (respond with ONLY this JSON, no other text):
{{
  "summary": "1-2 sentence objective description of the image content",
  "composition": {{
    "layers": ["foreground: <description>", "midground: <description>", "background: <description>"],
    "techniques": ["technique1", "technique2"],
    "problems": ["specific issue 1", "specific issue 2"],
    "depth": "shallow|moderate|deep",
    "balance": "symmetric|asymmetric|radial"
  }},
  "perspectives": {{
{perspectives_inner}
  }},
  "technical": {{
    "dominant_colors": ["#hex1", "#hex2"],
    "mood": "one_word",
    "lighting": "lighting_type",
    "time_of_day": "time_period"
  }},
  "subjects": ["subject1", "subject2"],
  "best_perspective": "{best_alternatives}"
}}"""

    parts.append(json_template)
    return "\n\n".join(parts)
