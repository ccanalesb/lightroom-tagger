from lightroom_tagger.core.analyzer import analyze_image
from lightroom_tagger.core.database import get_catalog_images_needing_analysis, store_catalog_image


def enrich_catalog_images(db, catalog_path: str = None, limit: int = None) -> dict:
    """Analyze and store metadata for catalog images.

    Returns:
        {processed: N, skipped: N, errors: N}
    """
    images_needing_analysis = get_catalog_images_needing_analysis(db)

    if limit:
        images_needing_analysis = images_needing_analysis[:limit]

    processed = 0
    errors = 0

    for record in images_needing_analysis:
        filepath = record.get('filepath')
        if not filepath:
            continue

        try:
            analysis = analyze_image(filepath)
            record.update(analysis)
            store_catalog_image(db, record)
            processed += 1
        except Exception:
            errors += 1

    return {
        'processed': processed,
        'skipped': len(images_needing_analysis) - processed,
        'errors': errors
    }
