"""Library database — barrel re-exports from split scaffold (plan 14-01)."""

from .db_init import (
    _backfill_matched_catalog_key_from_validated_matches,
    _deserialize_row,
    _dict_factory,
    _ensure_sqlite_vec_loaded,
    _library_db_file_path,
    _migrate_add_column,
    _migrate_catalog_similarity,
    _migrate_image_clip_embeddings_vec0,
    _migrate_image_descriptions_fts,
    _migrate_image_stacks,
    _migrate_image_text_embeddings_vec0,
    _migrate_images_schema,
    _migrate_unified_image_keys,
    _perspective_seed_description,
    _serialize_json,
    init_database,
    migrate_unified_image_keys,
    seed_perspectives_from_prompts_dir,
)

from .catalog import (
    _LIBRARY_WRITE_LOCK,
    _append_query_catalog_image_filters,
    _non_empty_str_list_for_json_array_filter,
    catalog_key_is_primary_grid_row,
    clear_all,
    delete_image,
    filter_order_keys_in_catalog,
    generate_key,
    get_all_catalog_images,
    get_all_images,
    get_catalog_images_missing_cache,
    get_catalog_images_needing_analysis,
    get_image,
    get_image_count,
    init_catalog_table,
    library_write,
    query_catalog_images,
    query_catalog_images_by_keys,
    resolve_filepath,
    search_by_color_label,
    search_by_date,
    search_by_keyword,
    search_by_rating,
    store_catalog_image,
    store_image,
    store_images_batch,
)

from .instagram import (
    _INSTAGRAM_DUMP_CLIP_VIDEO_GUARD,
    _VIDEO_EXTENSIONS_CLAUSE,
    _instagram_row_key,
    batch_update_hashes,
    get_dump_media_by_hash,
    get_images_without_hash,
    get_instagram_by_date_filter,
    get_instagram_dump_media,
    get_instagram_images_needing_analysis,
    get_unprocessed_dump_media,
    init_instagram_dump_table,
    init_instagram_table,
    mark_dump_media_attempted,
    mark_dump_media_processed,
    search_by_instagram_posted,
    store_instagram_dump_media,
    store_instagram_image,
    update_image_hash,
    update_instagram_status,
)

from .matches import (
    _backfill_instagram_created_at_from_catalog,
    apply_instagram_match_to_stack_members,
    catalog_has_instagram_match_conflict,
    delete_matches_for_insta_key,
    get_rejected_pairs,
    init_matches_table,
    reject_match,
    store_match,
    unvalidate_match,
    validate_match,
)

from .stacks import (
    StackMutationError,
    catalog_image_stack_row_fields,
    list_catalog_stack_member_keys,
    select_stack_representative_key_for_keys,
    stack_merge_into,
    stack_metadata_for_api,
    stack_set_representative,
    stack_split_member_out,
)

from .descriptions import (
    build_description_fts_query,
    build_description_search_document,
    get_all_images_with_descriptions,
    get_image_description,
    get_undescribed_catalog_images,
    get_undescribed_instagram_images,
    init_image_descriptions_table,
    store_image_description,
    _coerce_has_repetition,
    _visual_attr_json,
)

from .scores import (
    delete_perspective,
    get_current_scores_for_image,
    get_perspective_by_slug,
    insert_image_score,
    insert_perspective,
    list_all_scores_for_image,
    list_perspectives,
    list_score_history_for_perspective,
    supersede_previous_current_scores,
    update_perspective,
)

from .embeddings import (
    count_catalog_images_missing_text_embedding,
    list_catalog_keys_for_clip_embed_force,
    list_catalog_keys_for_text_embed_force,
    list_catalog_keys_needing_clip_embedding,
    list_catalog_keys_needing_text_embedding,
    list_instagram_dump_keys_for_clip_embed_force,
    list_instagram_dump_keys_needing_clip_embedding,
    upsert_image_clip_embedding,
    upsert_image_text_embedding,
    _embeddable_catalog_description_sql,
    _instagram_dump_clip_embed_filters,
    _list_catalog_keys_clip_embed_sql_params,
    _list_catalog_keys_text_embed_sql_params,
    _list_instagram_dump_clip_embed_sql_params,
    _sort_catalog_key_rows_newest_first,
)

from .similarity import (
    clear_catalog_similarity_results,
    insert_catalog_similarity_group,
    list_clip_embedded_catalog_keys_newest_first,
)

from ._legacy import (
    VISION_CACHE_OVERSIZED_SENTINEL,
    get_cache_stats,
    get_vision_cached_image,
    get_vision_comparison,
    init_vision_cache_table,
    init_vision_comparisons_table,
    is_vision_cache_valid,
    store_vision_cached_image,
    store_vision_comparison,
)

__all__ = ('StackMutationError', 'VISION_CACHE_OVERSIZED_SENTINEL', '_INSTAGRAM_DUMP_CLIP_VIDEO_GUARD', '_LIBRARY_WRITE_LOCK', '_VIDEO_EXTENSIONS_CLAUSE', '_append_query_catalog_image_filters', '_backfill_instagram_created_at_from_catalog', '_backfill_matched_catalog_key_from_validated_matches', '_coerce_has_repetition', '_deserialize_row', '_dict_factory', '_embeddable_catalog_description_sql', '_ensure_sqlite_vec_loaded', '_instagram_dump_clip_embed_filters', '_instagram_row_key', '_library_db_file_path', '_list_catalog_keys_clip_embed_sql_params', '_list_catalog_keys_text_embed_sql_params', '_list_instagram_dump_clip_embed_sql_params', '_migrate_add_column', '_migrate_catalog_similarity', '_migrate_image_clip_embeddings_vec0', '_migrate_image_descriptions_fts', '_migrate_image_stacks', '_migrate_image_text_embeddings_vec0', '_migrate_images_schema', '_migrate_unified_image_keys', '_non_empty_str_list_for_json_array_filter', '_perspective_seed_description', '_serialize_json', '_sort_catalog_key_rows_newest_first', '_visual_attr_json', 'apply_instagram_match_to_stack_members', 'batch_update_hashes', 'build_description_fts_query', 'build_description_search_document', 'catalog_has_instagram_match_conflict', 'catalog_image_stack_row_fields', 'catalog_key_is_primary_grid_row', 'clear_all', 'clear_catalog_similarity_results', 'count_catalog_images_missing_text_embedding', 'delete_image', 'delete_matches_for_insta_key', 'delete_perspective', 'filter_order_keys_in_catalog', 'generate_key', 'get_all_catalog_images', 'get_all_images', 'get_all_images_with_descriptions', 'get_cache_stats', 'get_catalog_images_missing_cache', 'get_catalog_images_needing_analysis', 'get_current_scores_for_image', 'get_dump_media_by_hash', 'get_image', 'get_image_count', 'get_image_description', 'get_images_without_hash', 'get_instagram_by_date_filter', 'get_instagram_dump_media', 'get_instagram_images_needing_analysis', 'get_perspective_by_slug', 'get_rejected_pairs', 'get_undescribed_catalog_images', 'get_undescribed_instagram_images', 'get_unprocessed_dump_media', 'get_vision_cached_image', 'get_vision_comparison', 'init_catalog_table', 'init_database', 'init_image_descriptions_table', 'init_instagram_dump_table', 'init_instagram_table', 'init_matches_table', 'init_vision_cache_table', 'init_vision_comparisons_table', 'insert_catalog_similarity_group', 'insert_image_score', 'insert_perspective', 'is_vision_cache_valid', 'library_write', 'list_all_scores_for_image', 'list_catalog_keys_for_clip_embed_force', 'list_catalog_keys_for_text_embed_force', 'list_catalog_keys_needing_clip_embedding', 'list_catalog_keys_needing_text_embedding', 'list_catalog_stack_member_keys', 'list_clip_embedded_catalog_keys_newest_first', 'list_instagram_dump_keys_for_clip_embed_force', 'list_instagram_dump_keys_needing_clip_embedding', 'list_perspectives', 'list_score_history_for_perspective', 'mark_dump_media_attempted', 'mark_dump_media_processed', 'migrate_unified_image_keys', 'query_catalog_images', 'query_catalog_images_by_keys', 'reject_match', 'resolve_filepath', 'search_by_color_label', 'search_by_date', 'search_by_instagram_posted', 'search_by_keyword', 'search_by_rating', 'seed_perspectives_from_prompts_dir', 'select_stack_representative_key_for_keys', 'stack_merge_into', 'stack_metadata_for_api', 'stack_set_representative', 'stack_split_member_out', 'store_catalog_image', 'store_image', 'store_image_description', 'store_images_batch', 'store_instagram_dump_media', 'store_instagram_image', 'store_match', 'store_vision_cached_image', 'store_vision_comparison', 'supersede_previous_current_scores', 'unvalidate_match', 'update_image_hash', 'update_instagram_status', 'update_perspective', 'upsert_image_clip_embedding', 'upsert_image_text_embedding', 'validate_match')
