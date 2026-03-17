import os
from pathlib import Path
from typing import Optional

from PIL import Image

from lightroom_tagger.core.phash import find_matches


def compute_phash(image_path: str, hash_size: int = 8) -> Optional[str]:
    """Compute perceptual hash of an image.
    
    Args:
        image_path: Path to the image file
        hash_size: Size of hash (default 8 = 64-bit hash)
    
    Returns:
        Hex string of pHash, or None if error
    """
    try:
        img = Image.open(image_path)
        import imagehash
        hash_val = imagehash.phash(img, hash_size=hash_size)
        return str(hash_val)
    except Exception as e:
        return None


def compute_multiple_hashes(image_path: str) -> dict:
    """Compute multiple types of hashes for an image.
    
    Returns:
        dict with 'phash', 'ahash', 'dhash', 'whash' keys
    """
    import imagehash
    hashes = {}
    try:
        img = Image.open(image_path)
        hashes['phash'] = str(imagehash.phash(img))
        hashes['ahash'] = str(imagehash.average_hash(img))
        hashes['dhash'] = str(imagehash.dhash(img))
        hashes['whash'] = str(imagehash.whash(img))
    except Exception as e:
        pass
    
    return hashes


def batch_compute_hashes(image_paths: list[str], hash_size: int = 8) -> dict[str, str]:
    """Compute pHash for multiple images.
    
    Args:
        image_paths: List of image file paths
        hash_size: Size of hash
    
    Returns:
        Dict mapping filepath to hash
    """
    results = {}
    
    for path in image_paths:
        if not os.path.exists(path):
            continue
        
        hash_val = compute_phash(path, hash_size)
        if hash_val:
            results[path] = hash_val
    
    return results
