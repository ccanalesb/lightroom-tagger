"""Parse a vision-model comparison response into a structured verdict."""

from __future__ import annotations

import json as _json


def parse_vision_response(raw: str) -> dict:
    """Parse vision model response into structured result.

    Expects JSON: {"confidence": 0-100, "reasoning": "..."}
    Falls back to legacy SAME/DIFFERENT/UNCERTAIN parsing.
    """
    raw = raw.strip()

    try:
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        data = _json.loads(raw)
        confidence = int(data.get('confidence', 50))
        confidence = max(0, min(100, confidence))
        if confidence >= 70:
            verdict = 'SAME'
        elif confidence <= 30:
            verdict = 'DIFFERENT'
        else:
            verdict = 'UNCERTAIN'
        return {'confidence': confidence, 'verdict': verdict, 'reasoning': data.get('reasoning', '')}
    except (TypeError, ValueError, KeyError, _json.JSONDecodeError):
        pass

    upper = raw.upper()
    if upper.startswith('SAME') and 'DIFFERENT' not in upper[:20]:
        return {'confidence': 100, 'verdict': 'SAME', 'reasoning': ''}
    elif 'DIFFERENT' in upper[:50]:
        return {'confidence': 0, 'verdict': 'DIFFERENT', 'reasoning': ''}
    return {'confidence': 50, 'verdict': 'UNCERTAIN', 'reasoning': ''}
