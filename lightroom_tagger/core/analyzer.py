import os
import tempfile
from typing import Dict, Any, Optional, Tuple
from lightroom_tagger.core.config import load_config

RAW_EXTENSIONS = {'.dng', '.raw', '.cr2', '.cr3', '.nef', '.arw', '.rw2', '.orf', '.raf', '.srw', '.x3f'}

# Vision compression configuration
VISION_MAX_DIMENSION = int(os.environ.get('VISION_MAX_DIMENSION', '1024'))
VISION_COMPRESS_QUALITY = int(os.environ.get('VISION_COMPRESS_QUALITY', '80'))


def get_vision_model() -> str:
    """Get vision model from config or env override."""
    if 'VISION_MODEL' in os.environ:
        return os.environ['VISION_MODEL']
    return load_config().vision_model

VISION_MODEL = os.environ.get('VISION_MODEL', 'gemma3:27b')


def compress_image(input_path: str, max_size: Optional[Tuple[int, int]] = None, quality: Optional[int] = None) -> str:
    """Compress image to reduce file size for vision comparison.

    Returns path to temporary compressed file.
    Caller is responsible for cleaning up the temporary file.

    Args:
        input_path: Path to input image
        max_size: Max (width, height) tuple, defaults to VISION_MAX_DIMENSION
        quality: JPEG quality (1-100), defaults to VISION_COMPRESS_QUALITY

    Returns:
        Path to compressed temporary file, or original path on failure.
    """
    from PIL import Image

    if max_size is None:
        max_size = (VISION_MAX_DIMENSION, VISION_MAX_DIMENSION)
    if quality is None:
        quality = VISION_COMPRESS_QUALITY

    try:
        with Image.open(input_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            # Resize if larger than max_size
            if img.width > max_size[0] or img.height > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Save to temp file with compression
            fd, temp_path = tempfile.mkstemp(suffix='.jpg')
            os.close(fd)
            img.save(temp_path, 'JPEG', quality=quality, optimize=True)

            # Log compression
            original_size = os.path.getsize(input_path) / 1024 # KB
            compressed_size = os.path.getsize(temp_path) / 1024 # KB
            print(f" Compressed: {original_size:.1f}KB -> {compressed_size:.1f}KB", flush=True)

            return temp_path
    except Exception as e:
        print(f" Compression failed: {e}", flush=True)
        return input_path


def convert_raw_to_jpg(raw_path: str) -> Optional[str]:
    """Convert RAW/DNG file to temporary JPG for vision comparison.

    Uses retry logic for network/NAS intermittent failures.

    Returns:
        Path to temporary JPG file, or None if conversion failed.
        Caller is responsible for cleaning up the temporary file.
    """
    import rawpy
    import time

    if not os.path.exists(raw_path):
        return None

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with rawpy.imread(raw_path) as raw:
                rgb = raw.postprocess(use_camera_wb=True, half_size=True)

            from PIL import Image
            img = Image.fromarray(rgb)

            fd, jpg_path = tempfile.mkstemp(suffix='.jpg')
            os.close(fd)

            img.save(jpg_path, 'JPEG', quality=95)

            return jpg_path
        except rawpy._rawpy.LibRawIOError as e:
            # Network/NAS intermittent error - retry
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1)) # Exponential backoff
                continue
            return None
        except rawpy._rawpy.LibRawTooBigError as e:
            # Image too large - can't recover
            return None
        except Exception as e:
            # Other errors - don't retry
            return None

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
            exif = img._getexif() # type: ignore[attr-defined]
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag in ['Make', 'Model', 'DateTime', 'LensModel', 'ISOSpeedRatings',
                               'FNumber', 'ExposureTime', 'GPSInfo']:
                        result[tag.lower()] = str(value)
    except Exception:
        pass
    return result

def describe_image(path: str, agent_type: Optional[str] = None) -> str:
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


def compare_with_vision(local_path: str, insta_path: str, log_callback=None,
                        cached_local_path: Optional[str] = None, compressed_insta_path: Optional[str] = None) -> str:
    """Compare two images using vision model via Ollama with compression.

    Compresses images to max VISION_MAX_DIMENSION pixels before comparison
    to reduce bandwidth and processing time. Supports pre-compressed paths
    to avoid redundant compression.

    Args:
        local_path: Original path to catalog image (for error reporting and RAW conversion)
        insta_path: Original path to Instagram image (for error reporting)
        log_callback: Optional callback for logging
        cached_local_path: Pre-compressed catalog image path (optional, uses cache if available)
        compressed_insta_path: Pre-compressed Instagram image path (optional)

    Returns: 'SAME' | 'DIFFERENT' | 'UNCERTAIN'
    """
    # Track all temp files for cleanup
    temp_files = []
    compressed_local = None
    compressed_insta = None

    try:
        # Step 1: Handle catalog image (local_path)
        if cached_local_path and os.path.exists(cached_local_path):
            # Use pre-compressed cached image
            compressed_local = cached_local_path
            if log_callback:
                log_callback('info', f'Using cached compressed image for {os.path.basename(local_path)}')
        else:
            # Get viewable path (convert RAW/DNG if needed)
            viewable_local = get_viewable_path(local_path)
            if viewable_local != local_path:
                temp_files.append(viewable_local)
                # Log RAW conversion
                if log_callback:
                    ext = os.path.splitext(local_path)[1].lower()
                    if ext in RAW_EXTENSIONS:
                        if viewable_local.lower().endswith(('.jpg', '.jpeg')):
                            sidecar_path = local_path.rsplit('.', 1)[0] + '.JPG'
                            sidecar_path_lower = local_path.rsplit('.', 1)[0] + '.jpg'
                            if os.path.exists(sidecar_path) or os.path.exists(sidecar_path_lower):
                                log_callback('info', f'Using JPG sidecar for {os.path.basename(local_path)}')
                            else:
                                log_callback('info', f'Converted DNG to JPG: {os.path.basename(viewable_local)}')
            else:
                viewable_local = local_path

            # Compress the image
            compressed_local = compress_image(viewable_local)
            if compressed_local != viewable_local:
                temp_files.append(compressed_local)

        # Step 2: Handle Instagram image
        if compressed_insta_path and os.path.exists(compressed_insta_path):
            compressed_insta = compressed_insta_path
        else:
            viewable_insta = get_viewable_path(insta_path)
            if viewable_insta != insta_path:
                temp_files.append(viewable_insta)
            else:
                viewable_insta = insta_path

            compressed_insta = compress_image(viewable_insta)
            if compressed_insta != viewable_insta:
                temp_files.append(compressed_insta)

        # Step 3: Run vision comparison
        result = run_vision_ollama(compressed_local, compressed_insta)

        return result

    finally:
        # Clean up temp files we created (but not cached files)
        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass


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
    return 0.5 # UNCERTAIN
