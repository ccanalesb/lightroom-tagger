from typing import Any

from .description import describe_image
from .image_inspect import compute_phash, extract_exif


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


def run_external_agent(path: str) -> str:
    """Run external API (e.g., Claude, GPT-4V)."""
    return ""
