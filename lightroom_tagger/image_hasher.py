import os

import imagehash
from PIL import Image


def compute_phash(image_path: str, hash_size: int = 8) -> str | None:
    """Compute perceptual hash of an image.

    Args:
        image_path: Path to the image file
        hash_size: Size of hash (default 8 = 64-bit hash)

    Returns:
        Hex string of pHash, or None if error
    """
    try:
        img = Image.open(image_path)
        hash_val = imagehash.phash(img, hash_size=hash_size)
        return str(hash_val)
    except Exception as e:
        print(f"Error computing hash for {image_path}: {e}")
        return None


def compute_multiple_hashes(image_path: str) -> dict:
    """Compute multiple types of hashes for an image.

    Returns:
        dict with 'phash', 'ahash', 'dhash', 'whash' keys
    """
    hashes = {}
    try:
        img = Image.open(image_path)
        hashes['phash'] = str(imagehash.phash(img))
        hashes['ahash'] = str(imagehash.average_hash(img))
        hashes['dhash'] = str(imagehash.dhash(img))
        hashes['whash'] = str(imagehash.whash(img))
    except Exception as e:
        print(f"Error computing hashes for {image_path}: {e}")

    return hashes


def hamming_distance(hash1: str, hash2: str) -> int:
    """Calculate Hamming distance between two hash strings.

    Args:
        hash1: First hash (hex string)
        hash2: Second hash (hex string)

    Returns:
        Number of differing bits
    """
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
    except Exception:
        return 32


def compare_hashes(hash1: str, hash2: str, threshold: int = 5) -> bool:
    """Compare two hashes and return True if they're similar within threshold.

    Args:
        hash1: First hash (hex string)
        hash2: Second hash (hex string)
        threshold: Maximum Hamming distance (default 5)

    Returns:
        True if hashes are similar enough
    """
    distance = hamming_distance(hash1, hash2)
    return distance <= threshold


def find_matches(local_images: list[dict], insta_images: list[dict], threshold: int = 5) -> list[dict]:
    """Find matches between local and Instagram images using perceptual hashing.

    Args:
        local_images: List of local image records with 'filepath' and 'image_hash'
        insta_images: List of Instagram images with 'local_path' and 'image_hash'
        threshold: Maximum Hamming distance for match (default 5)

    Returns:
        List of match dicts with local and insta image info
    """
    matches = []

    for local in local_images:
        if not local.get('image_hash'):
            continue

        for insta in insta_images:
            if not insta.get('image_hash'):
                continue

            if compare_hashes(local['image_hash'], insta['image_hash'], threshold):
                matches.append({
                    'local_key': local.get('key'),
                    'local_filepath': local.get('filepath'),
                    'local_id': local.get('id'),
                    'insta_url': insta.get('url'),
                    'insta_local_path': insta.get('local_path'),
                    'hash_distance': hamming_distance(local['image_hash'], insta['image_hash']),
                })

    return matches


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


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python image_hasher.py <image_path>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"Computing hash for: {path}")

    hash_val = compute_phash(path)
    if hash_val:
        print(f"pHash: {hash_val}")

        hashes = compute_multiple_hashes(path)
        for htype, hval in hashes.items():
            print(f"{htype}: {hval}")
    else:
        print("Failed to compute hash")
