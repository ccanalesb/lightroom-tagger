import os
import tempfile
from typing import Dict, Any, Optional
from lightroom_tagger.core.config import load_config

RAW_EXTENSIONS = {'.dng', '.raw', '.cr2', '.cr3', '.nef', '.arw', '.rw2', '.orf', '.raf', '.srw', '.x3f'}


def get_vision_model() -> str:
    """Get vision model from config or env override."""
    if 'VISION_MODEL' in os.environ:
        return os.environ['VISION_MODEL']
    return load_config().vision_model

VISION_MODEL = os.environ.get('VISION_MODEL', 'gemma3:27b')


def convert_raw_to_jpg(raw_path: str) -> Optional[str]:
    """Convert RAW/DNG file to temporary JPG for vision comparison.
    
    Returns:
        Path to temporary JPG file, or None if conversion failed.
        Caller is responsible for cleaning up the temporary file.
    """
    import rawpy
    
    try:
        with rawpy.imread(raw_path) as raw:
            rgb = raw.postprocess(use_camera_wb=True, half_size=True)
        
        from PIL import Image
        img = Image.fromarray(rgb)
        
        fd, jpg_path = tempfile.mkstemp(suffix='.jpg')
        os.close(fd)
        
        img.save(jpg_path, 'JPEG', quality=95)
        
        return jpg_path
    except Exception as e:
        print(f"Warning: Failed to convert {raw_path}: {e}")
        return None


def get_viewable_path(image_path: str) -> str:
    """Get a viewable image path, converting RAW/DNG to temporary JPG if needed.
    
    Returns:
        Path to a viewable image (JPG/PNG).
        Returns original path if already viewable.
        Returns temporary JPG path if RAW/DNG (caller should clean up).
    """
    ext = os.path.splitext(image_path)[1].lower()
    
    if ext not in RAW_EXTENSIONS:
        return image_path
    
    jpg_sidecar = image_path.rsplit('.', 1)[0] + '.JPG'
    if os.path.exists(jpg_sidecar):
        return jpg_sidecar
    
    jpg_sidecar_lower = image_path.rsplit('.', 1)[0] + '.jpg'
    if os.path.exists(jpg_sidecar_lower):
        return jpg_sidecar_lower
    
    converted = convert_raw_to_jpg(image_path)
    if converted:
        return converted
    
    return image_path

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
    from lightroom_tagger.core.hasher import compute_phash as _compute
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


def compare_with_vision(local_path: str, insta_path: str) -> str:
    """Compare two images using vision model via Ollama.
    
    Returns: 'SAME' | 'DIFFERENT' | 'UNCERTAIN'
    """
    viewable_local = get_viewable_path(local_path)
    result = run_vision_ollama(viewable_local, insta_path)
    
    if viewable_local != local_path and os.path.exists(viewable_local):
        try:
            os.unlink(viewable_local)
        except Exception:
            pass
    
    return result


def run_vision_ollama(local_path: str, insta_path: str) -> str:
    """Run vision model via Ollama to compare images."""
    import subprocess
    
    prompt = """You are given two images. Determine if they depict the same subject or scene.
Image 1 may be lower quality, compressed, or degraded.
Focus on semantic content, not pixel-level accuracy.

Reply with ONLY: SAME / DIFFERENT / UNCERTAIN"""

    try:
        result = subprocess.run([
            'ollama', 'run', get_vision_model(),
            f'Image 1: {local_path}',
            f'Image 2: {insta_path}',
            prompt
        ], capture_output=True, text=True, timeout=120)
        
        output = result.stdout.strip().upper()
        
        if output.startswith('SAME') and 'DIFFERENT' not in output[:20]:
            return 'SAME'
        elif 'DIFFERENT' in output[:50]:
            return 'DIFFERENT'
        return 'UNCERTAIN'
    except Exception:
        return 'UNCERTAIN'


def vision_score(result: str) -> float:
    """Convert vision result to score."""
    if result == 'SAME':
        return 1.0
    elif result == 'DIFFERENT':
        return 0.0
    return 0.5  # UNCERTAIN
