from typing import Optional
from core.analyzer import analyze_image
from core.database import store_instagram_image

def crawl_and_analyze(db, username: str, output_dir: str, limit: int = 50) -> dict:
    """Crawl Instagram and analyze images.
    
    Returns:
        {processed: N, skipped: N, errors: N}
    """
    from instagram.scraper import crawl_instagram
    
    posts, url_to_path = crawl_instagram(None, output_dir, limit=limit)
    
    processed = 0
    errors = 0
    
    for post in posts:
        local_paths = url_to_path.get(post.post_url, [])
        for local_path in local_paths:
            try:
                analysis = analyze_image(local_path)
                record = {
                    'post_url': post.post_url,
                    'local_path': local_path,
                    **analysis
                }
                store_instagram_image(db, record)
                processed += 1
            except Exception as e:
                errors += 1
    
    return {
        'processed': processed,
        'skipped': len(posts) - processed,
        'errors': errors
    }
