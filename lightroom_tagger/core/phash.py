
import imagehash


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
