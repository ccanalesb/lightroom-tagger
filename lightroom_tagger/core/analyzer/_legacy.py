import contextlib
import os
from typing import Any

import ollama

from lightroom_tagger.core.config import get_description_model

from .description import build_description_prompt, describe_image
from .image_inspect import compute_phash, extract_exif
from .image_prep import RAW_EXTENSIONS, compress_image, get_viewable_path


def analyze_image(path: str) -> dict[str, Any]:
    """Analyze image and return all matching signals.

    Returns:
        {phash, exif, description (str summary), structured_description (full dict)}
    """
    phash = compute_phash(path)
    exif = extract_exif(path)
    structured = describe_image(path)

    return {
        'phash': phash,
        'exif': exif,
        'description': structured.get('summary', ''),
        'structured_description': structured,
    }


def run_local_agent(path: str, user_prompt: str | None = None) -> str:
    """Run local vision model (e.g., LLaVA) via Ollama Python client."""
    temp_files: list[str] = []
    viewable = get_viewable_path(path)
    if viewable != path:
        temp_files.append(viewable)

    compressed = compress_image(viewable)
    if compressed != viewable:
        temp_files.append(compressed)

    prompt_text = build_description_prompt()
    if user_prompt is not None and user_prompt.strip():
        prompt_text = user_prompt.strip()

    try:
        response = ollama.chat(
            model=get_description_model(),
            messages=[
                {
                    'role': 'user',
                    'content': prompt_text,
                    'images': [compressed],
                }
            ],
        )
        content = getattr(response.message, 'content', None) if response and response.message else None
        return content or ''
    except Exception as e:
        print(f"  Ollama description failed: {e}", flush=True)
        return ''
    finally:
        for f in temp_files:
            if os.path.exists(f):
                with contextlib.suppress(Exception):
                    os.unlink(f)


def run_external_agent(path: str) -> str:
    """Run external API (e.g., Claude, GPT-4V)."""
    return ""
