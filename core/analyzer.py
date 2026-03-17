from typing import Dict, Any, Optional

def analyze_image(path: str) -> Dict[str, Any]:
    """Analyze image and return all matching signals.
    
    Returns:
        {phash, exif: {camera, lens, date_taken, gps, ...}, description}
    """
    phash = compute_phash(path)
    exif = extract_exif(path)
    description = describe_image(path)
    
    return {
        'phash': phash,
        'exif': exif,
        'description': description
    }

def compute_phash(path: str) -> Optional[str]:
    """Placeholder - delegate to existing hasher."""
    from core.hasher import compute_phash as _compute
    try:
        return _compute(path)
    except Exception:
        return None

def extract_exif(path: str) -> Dict[str, Any]:
    """Extract EXIF metadata from image."""
    from PIL import Image
    from PIL.ExifTags import TAGS
    
    result = {}
    try:
        with Image.open(path) as img:
            exif = img._getexif()
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag in ['Make', 'Model', 'DateTime', 'LensModel', 'ISOSpeedRatings', 
                              'FNumber', 'ExposureTime', 'GPSInfo']:
                        result[tag.lower()] = str(value)
    except Exception:
        pass
    return result

def describe_image(path: str, agent_type: str = None) -> str:
    """Generate description using configured agent."""
    if agent_type is None:
        try:
            from core.config import load_config
            config = load_config()
            agent_type = getattr(config, 'agent_type', 'local')
        except Exception:
            agent_type = 'local'
    
    if agent_type == 'local':
        return run_local_agent(path)
    elif agent_type == 'external':
        return run_external_agent(path)
    return ""

def run_local_agent(path: str) -> str:
    """Run local vision model (e.g., LLaVA)."""
    return ""

def run_external_agent(path: str) -> str:
    """Run external API (e.g., Claude, GPT-4V)."""
    return ""
