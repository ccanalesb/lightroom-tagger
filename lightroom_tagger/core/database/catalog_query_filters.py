"""Shared WHERE-clause fragments for catalog image listing queries."""

from __future__ import annotations


def _non_empty_str_list_for_json_array_filter(values: list[str] | None) -> list[str] | None:
    """Strip elements, drop blank entries; return None if no filter should apply.

    A list of only whitespace is treated as no filter, matching "empty list" semantics.
    """
    if values is None or len(values) == 0:
        return None
    out = [str(v).strip() for v in values if v is not None and str(v).strip()]
    return out or None


def _append_query_catalog_image_filters(
    clauses: list[str],
    bindings: list,
    *,
    posted: bool | None = None,
    month: str | None = None,
    keyword: str | None = None,
    min_rating: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    color_label: str | None = None,
    analyzed: bool | None = None,
    min_score: int | None = None,
    min_score_on_active: int | None = None,
    burst_stack: bool | None = None,
    description_search: str | None = None,
    dominant_colors: list[str] | None = None,
    mood_tags: list[str] | None = None,
    has_repetition: bool | None = None,
) -> None:
    """Append shared catalog list AND-clauses (incl. stack collapse) to *clauses* / *bindings*.

    Used by :func:`~lightroom_tagger.core.database.catalog_query.query_catalog_images` and
    :func:`~lightroom_tagger.core.database.catalog_query.filter_order_keys_in_catalog`. The
    caller must initialize *clauses* (e.g. ``[\"1=1\"]`` or ``i.key IN (...)``) and *bindings*.
    """
    from .descriptions import build_description_fts_query

    if posted is True:
        clauses.append("i.instagram_posted = 1")
    elif posted is False:
        clauses.append("i.instagram_posted = 0")

    if month and len(month) == 6 and month.isdigit():
        clauses.append("strftime('%Y%m', i.date_taken) = ?")
        bindings.append(month)

    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        clauses.append(
            "("
            "i.keywords LIKE ? COLLATE NOCASE OR "
            "i.filename LIKE ? COLLATE NOCASE OR "
            "i.title LIKE ? COLLATE NOCASE OR "
            "i.description LIKE ? COLLATE NOCASE"
            ")"
        )
        bindings.extend([pattern, pattern, pattern, pattern])

    if min_rating is not None:
        clauses.append("i.rating >= ?")
        bindings.append(min_rating)

    if date_from:
        clauses.append("i.date_taken >= ?")
        bindings.append(date_from)

    if date_to:
        clauses.append("i.date_taken <= ?")
        bindings.append(date_to)

    cl = (color_label or "").strip()
    if cl:
        clauses.append("LOWER(i.color_label) = LOWER(?)")
        bindings.append(cl)

    if analyzed is True:
        clauses.append("d.image_key IS NOT NULL")
    elif analyzed is False:
        clauses.append("d.image_key IS NULL")

    if min_score is not None:
        clauses.append("s.score IS NOT NULL AND s.score >= ?")
        bindings.append(min_score)

    if min_score_on_active is not None:
        if not (1 <= min_score_on_active <= 10):
            raise ValueError("min_score_on_active must be between 1 and 10")
        clauses.append(
            "EXISTS ("
            "SELECT 1 FROM image_scores s_active "
            "INNER JOIN perspectives p_active "
            "  ON p_active.slug = s_active.perspective_slug AND p_active.active = 1 "
            "WHERE s_active.image_key = i.key "
            "  AND s_active.image_type = 'catalog' "
            "  AND s_active.is_current = 1 "
            "  AND s_active.score >= ?"
            ")"
        )
        bindings.append(min_score_on_active)

    if burst_stack is True:
        clauses.append(
            "st.stack_id IS NOT NULL AND st.stack_size > 1 AND i.key = st.representative_key"
        )
    elif burst_stack is False:
        clauses.append(
            "(st.stack_id IS NULL OR st.stack_size <= 1 OR i.key != st.representative_key)"
        )

    if (description_search or "").strip():
        match_str, fts_err = build_description_fts_query(description_search)
        if fts_err:
            raise ValueError(fts_err)
        if match_str is not None:
            clauses.append(
                "i.key IN ("
                "SELECT d2.image_key FROM image_descriptions d2 "
                "INNER JOIN image_descriptions_fts ON image_descriptions_fts.rowid = d2.rowid "
                "WHERE d2.image_type = 'catalog' AND image_descriptions_fts MATCH ?"
                ")"
            )
            bindings.append(match_str)

    dc_tokens = _non_empty_str_list_for_json_array_filter(dominant_colors)
    if dc_tokens:
        dc_ph = ",".join("?" * len(dc_tokens))
        clauses.append(
            "("
            "d.dominant_colors IS NOT NULL AND json_type(d.dominant_colors) = 'array' "
            "AND EXISTS ("
            "SELECT 1 FROM json_each(d.dominant_colors) AS jde "
            f"WHERE jde.value IN ({dc_ph})"
            ")"
            ")"
        )
        bindings.extend(dc_tokens)

    if has_repetition is True:
        clauses.append("d.has_repetition = 1")
    elif has_repetition is False:
        clauses.append("(d.has_repetition IS NULL OR d.has_repetition = 0)")

    mt_tokens = _non_empty_str_list_for_json_array_filter(mood_tags)
    if mt_tokens:
        mt_ph = ",".join("?" * len(mt_tokens))
        clauses.append(
            "("
            "d.mood_tags IS NOT NULL AND json_type(d.mood_tags) = 'array' "
            "AND EXISTS ("
            "SELECT 1 FROM json_each(d.mood_tags) AS jme "
            f"WHERE jme.value IN ({mt_ph})"
            ")"
            ")"
        )
        bindings.extend(mt_tokens)

    clauses.append("(m_st.image_key IS NULL OR i.key = st.representative_key)")
