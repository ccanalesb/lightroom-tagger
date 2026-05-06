from lightroom_tagger.core.analyzer import compute_phash, describe_image, extract_exif
from lightroom_tagger.core.database import store_instagram_image


def crawl_and_analyze(db, username: str, output_dir: str, limit: int = 50) -> dict:
    """Crawl Instagram and analyze images.

    Returns:
        {processed: N, skipped: N, errors: N}
    """
    from lightroom_tagger.instagram.scraper import crawl_instagram

    posts, url_to_path = crawl_instagram(None, output_dir, limit=limit)

    processed = 0
    errors = 0

    for post in posts:
        local_paths = url_to_path.get(post.post_url, [])
        for local_path in local_paths:
            try:
                phash = compute_phash(local_path)
                exif = extract_exif(local_path)
                structured = describe_image(local_path)
                analysis = {
                    'phash': phash,
                    'exif': exif,
                    'description': structured.get('summary', ''),
                    'structured_description': structured,
                }
                record = {
                    'post_url': post.post_url,
                    'local_path': local_path,
                    **analysis
                }
                store_instagram_image(db, record)
                processed += 1
            except Exception:
                errors += 1

    return {
        'processed': processed,
        'skipped': len(posts) - processed,
        'errors': errors
    }
