"""Image preparation helpers (RAW/JPEG pipeline, compression, viewable paths)."""

import os
import tempfile

RAW_EXTENSIONS = {'.dng', '.raw', '.cr2', '.cr3', '.nef', '.arw', '.rw2', '.orf', '.raf', '.sr2', '.srw', '.x3f'}
VIDEO_EXTENSIONS = {'.mov', '.mp4', '.avi', '.mkv', '.wmv', '.m4v', '.3gp', '.webm', '.mts', '.m2ts'}

# Vision compression configuration
VISION_MAX_DIMENSION = int(os.environ.get('VISION_MAX_DIMENSION', '1024'))
VISION_COMPRESS_QUALITY = int(os.environ.get('VISION_COMPRESS_QUALITY', '80'))


def compress_image(
    input_path: str,
    max_size: tuple[int, int] | None = None,
    quality: int | None = None,
    *,
    silent: bool = False,
) -> str:
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
            if not silent:
                print(f" Compressed: {original_size:.1f}KB -> {compressed_size:.1f}KB", flush=True)

            return temp_path
    except Exception as e:
        if not silent:
            print(f" Compression failed: {e}", flush=True)
        return input_path


def convert_raw_to_jpg(raw_path: str) -> str | None:
    """Convert RAW/DNG file to temporary JPG for vision comparison.

    Uses retry logic for network/NAS intermittent failures.

    Returns:
        Path to temporary JPG file, or None if conversion failed.
        Caller is responsible for cleaning up the temporary file.
    """
    import time

    import rawpy

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
        except rawpy._rawpy.LibRawIOError:
            # Network/NAS intermittent error - retry
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1)) # Exponential backoff
                continue
            return None
        except rawpy._rawpy.LibRawTooBigError:
            # Image too large - can't recover
            return None
        except Exception:
            # Other errors - don't retry
            return None

    return None


def get_viewable_path(image_path: str) -> str:
    """Get a viewable image path, converting RAW/DNG to temporary JPG if needed.

    Returns:
        Path to a viewable image (JPG/PNG).
        Returns original path if already viewable.
        Returns temporary JPG path if RAW/DNG and no sidecar exists (caller must clean up).
        Returns persistent sidecar JPG path if one exists next to the RAW (caller must NOT delete).

    Use ``get_viewable_path_managed`` when you need to know whether the returned path
    is a temporary file that should be cleaned up vs. a persistent on-disk sidecar.
    """
    path, _ = get_viewable_path_managed(image_path)
    return path


def get_viewable_path_managed(image_path: str) -> tuple[str, bool]:
    """Get a viewable image path with ownership information.

    Returns:
        (path, is_temp) where ``is_temp=True`` means the path is a mkstemp-created
        temporary file that the caller **must** clean up, and ``is_temp=False`` means
        the path is either the original or a persistent on-disk sidecar that must
        **not** be deleted by the caller.
    """
    ext = os.path.splitext(image_path)[1].lower()

    if ext not in RAW_EXTENSIONS:
        return image_path, False

    jpg_sidecar = image_path.rsplit('.', 1)[0] + '.JPG'
    if os.path.exists(jpg_sidecar):
        return jpg_sidecar, False  # persistent sidecar — do not delete

    jpg_sidecar_lower = image_path.rsplit('.', 1)[0] + '.jpg'
    if os.path.exists(jpg_sidecar_lower):
        return jpg_sidecar_lower, False  # persistent sidecar — do not delete

    converted = convert_raw_to_jpg(image_path)
    if converted:
        return converted, True  # mkstemp-created temp — caller must clean up

    return image_path, False
