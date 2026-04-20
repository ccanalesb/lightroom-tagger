import json
import os
import re
import sqlite3
from collections import OrderedDict
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file
from utils.db import with_db
from utils.responses import (
    error_bad_request,
    error_not_found,
    error_server_error,
    success_paginated,
)

from lightroom_tagger.core.database import (
    get_image,
    get_image_description,
    get_instagram_dump_media,
    query_catalog_images,
    reject_match,
    unvalidate_match,
    validate_match,
)
from lightroom_tagger.core.identity_service import (
    compute_single_image_aggregate_scores,
)

_CATALOG_SCORE_PERSPECTIVE_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

bp = Blueprint('images', __name__)

_DESC_JSON_COLS = ('composition', 'perspectives', 'technical', 'subjects')


def _deserialize_description(row: dict) -> dict:
    """Deserialize JSON columns in an image_descriptions row."""
    out = dict(row)
    for col in _DESC_JSON_COLS:
        val = out.get(col)
        if isinstance(val, str):
            try:
                out[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return out


def _enrich_instagram_media(media_items, model_lookup=None, desc_lookup=None):
    """Transform database media items to API response format."""
    model_lookup = model_lookup or {}
    desc_lookup = desc_lookup or {}
    enriched = []
    for media in media_items:
        file_path = media.get('file_path', '')
        source_folder = _extract_source_folder(file_path)

        exif_data = media.get('exif_data')
        if isinstance(exif_data, str):
            try:
                exif_data = json.loads(exif_data)
            except (json.JSONDecodeError, TypeError):
                pass

        media_key = media['media_key']
        ai_desc = desc_lookup.get((media_key, 'instagram'))

        enriched.append({
            'key': media_key,
            'local_path': file_path,
            'filename': media.get('filename', ''),
            'instagram_folder': media.get('date_folder', ''),
            'date_folder': media.get('date_folder', ''),  # Add explicit date_folder for frontend
            'created_at': media.get('created_at'),  # Add created_at timestamp
            'source_folder': source_folder,
            'image_hash': media.get('image_hash'),
            'description': ai_desc.get('summary', '') if ai_desc else '',  # AI description
            'caption': media.get('caption', ''),  # Instagram caption
            'crawled_at': media.get('added_at', ''),
            'image_index': 1,
            'total_in_post': 1,
            'post_url': media.get('post_url'),
            'exif_data': exif_data,
            'processed': bool(media.get('processed')),
            'matched_catalog_key': media.get('matched_catalog_key'),
            'matched_model': model_lookup.get(media_key),
        })
    return enriched


def _canonical_path(path: str) -> str | None:
    if not path or not str(path).strip():
        return None
    try:
        return os.path.realpath(os.path.expanduser(str(path).strip()))
    except OSError:
        return None


def _parent_dir_if_exists(path: str) -> str | None:
    base = _canonical_path(path)
    if not base:
        return None
    parent = os.path.dirname(base)
    if parent and os.path.isdir(parent):
        return parent
    return None


def _is_path_under_allowed_roots(file_path: str, roots: list[str]) -> bool:
    if not file_path or not roots:
        return False
    try:
        real_file = os.path.realpath(file_path)
    except OSError:
        return False
    for root in roots:
        if not root:
            continue
        if real_file == root:
            return True
        prefix = root + os.sep
        if real_file.startswith(prefix):
            return True
    return False


def _instagram_thumbnail_roots() -> list[str]:
    from lightroom_tagger.core.config import load_config

    cfg = load_config()
    dump = (cfg.instagram_dump_path or "").strip()
    if not dump:
        return []
    root = _canonical_path(dump)
    if root and os.path.isdir(root):
        return [root]
    return []


def _catalog_thumbnail_roots() -> list[str]:
    from lightroom_tagger.core.config import load_config

    cfg = load_config()
    roots: list[str] = []
    vc = _canonical_path(cfg.vision_cache_dir)
    if vc:
        roots.append(vc)
    mp = (cfg.mount_point or "").strip()
    if mp:
        mp_real = _canonical_path(mp)
        if mp_real and os.path.isdir(mp_real):
            roots.append(mp_real)
    for p in (cfg.catalog_path, cfg.small_catalog_path):
        par = _parent_dir_if_exists(p)
        if par and par not in roots:
            roots.append(par)
    seen: set[str] = set()
    out: list[str] = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _extract_source_folder(file_path):
    """Extract source folder (posts, archived_posts) from file path."""
    if '/media/' in file_path:
        parts = file_path.split('/media/')
        if len(parts) > 1:
            subpath = parts[1].split('/')
            if len(subpath) > 0:
                return subpath[0]
    return 'unknown'


def _clamp_pagination(limit, offset, default_limit=50):
    if limit is None:
        limit = default_limit
    else:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = default_limit
    limit = max(1, min(500, limit))
    if offset is None:
        offset = 0
    else:
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = 0
    offset = max(0, offset)
    return limit, offset


def _filter_by_date(images, date_folder, date_from, date_to):
    """Filter images by date parameters."""
    if date_folder:
        return [img for img in images if img['instagram_folder'] == date_folder]

    if date_from:
        images = [img for img in images if img['instagram_folder'] and img['instagram_folder'] >= date_from]
    if date_to:
        images = [img for img in images if img['instagram_folder'] and img['instagram_folder'] <= date_to]

    return images


@bp.route('/instagram', methods=['GET'])
@with_db
def list_instagram_images(db):
    """List Instagram images with filtering and pagination."""
    try:
        media_items = db.execute("SELECT * FROM instagram_dump_media").fetchall()

        model_lookup = {}
        try:
            for row in db.execute("SELECT insta_key, model_used FROM matches").fetchall():
                model_lookup[row['insta_key']] = row['model_used']
        except sqlite3.OperationalError:
            pass

        desc_lookup = {}
        try:
            for desc in db.execute("SELECT * FROM image_descriptions WHERE image_type = 'instagram'").fetchall():
                key = (desc.get('image_key'), desc.get('image_type'))
                desc_lookup[key] = _deserialize_description(desc)
        except sqlite3.OperationalError:
            pass

        enriched_images = _enrich_instagram_media(media_items, model_lookup, desc_lookup)

        # Get filter parameters
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        date_folder = request.args.get('date_folder', '')

        # Apply filters
        enriched_images = _filter_by_date(enriched_images, date_folder, date_from, date_to)

        sort_date_raw = (request.args.get('sort_by_date') or '').strip().lower()
        if sort_date_raw and sort_date_raw not in ('newest', 'oldest'):
            return error_bad_request('sort_by_date must be newest or oldest')
        sort_reverse = sort_date_raw != 'oldest'

        # Sort by date folder (month). Tiebreak by key (set by
        # ``_enrich_instagram_media`` from the underlying ``media_key``) so
        # rows within the same month have a deterministic order matching the
        # chosen direction.
        enriched_images.sort(
            key=lambda x: (x.get('instagram_folder') or '', x.get('key') or ''),
            reverse=sort_reverse,
        )

        # Pagination
        limit, offset = _clamp_pagination(
            request.args.get('limit', 50, type=int),
            request.args.get('offset', 0, type=int),
        )
        total = len(enriched_images)

        paginated = enriched_images[offset:offset+limit]

        # Build custom response with 'images' key for backward compatibility
        success_paginated(paginated, total, offset, limit)
        # success_paginated returns (response, status) tuple, need to modify the response
        # Let's construct manually for compatibility
        return jsonify({
            'total': total,
            'images': paginated,
            'pagination': {
                'offset': offset,
                'limit': limit,
                'current_page': (offset // limit) + 1,
                'total_pages': (total + limit - 1) // limit,
                'has_more': (offset + limit) < total,
            }
        })
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/instagram/months', methods=['GET'])
@with_db
def get_instagram_months(db):
    """Get unique months available in Instagram images."""
    try:
        media_items = db.execute("SELECT * FROM instagram_dump_media").fetchall()
        months = set()
        for media in media_items:
            date_folder = media.get('date_folder', '')
            if date_folder:
                months.add(date_folder)
        return jsonify({'months': sorted(months, reverse=True)})
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/instagram/<path:image_key>/thumbnail', methods=['GET'])
@with_db
def get_instagram_thumbnail(db, image_key):
    """Get thumbnail for Instagram image."""
    try:
        media_items = db.execute(
            "SELECT * FROM instagram_dump_media WHERE media_key = ?",
            (image_key,),
        ).fetchall()

        if not media_items:
            return error_not_found('image')

        media = media_items[0]
        local_path = media.get('file_path')

        if not local_path or not os.path.exists(local_path):
            return error_not_found('file')

        allowed_insta = _instagram_thumbnail_roots()
        if not allowed_insta or not _is_path_under_allowed_roots(
            local_path, allowed_insta
        ):
            return error_not_found('file')

        return send_file(local_path, mimetype='image/jpeg')
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/catalog/<path:image_key>/thumbnail', methods=['GET'])
@with_db
def get_catalog_thumbnail(db, image_key):
    """Get thumbnail for catalog image, creating cache if needed."""
    try:
        images = db.execute(
            "SELECT * FROM images WHERE key = ?",
            (image_key,),
        ).fetchall()

        if not images:
            return error_not_found('image')

        image = images[0]
        allowed_cat = _catalog_thumbnail_roots()

        # Check vision cache first
        cached = db.execute(
            "SELECT compressed_path FROM vision_cache WHERE key = ?",
            (image_key,),
        ).fetchone()
        if cached and cached.get('compressed_path') and os.path.exists(cached['compressed_path']):
            cp = cached['compressed_path']
            if not _is_path_under_allowed_roots(cp, allowed_cat):
                return error_not_found('file')
            return send_file(cp, mimetype='image/jpeg')

        # Resolve original path
        from lightroom_tagger.core.path_utils import resolve_catalog_path
        filepath = resolve_catalog_path(image.get('filepath', ''))

        if not filepath or not os.path.exists(filepath):
            return error_not_found('file')

        if not _is_path_under_allowed_roots(filepath, allowed_cat):
            return error_not_found('file')

        # Generate cache on-the-fly for missing thumbnails
        try:
            from lightroom_tagger.core.vision_cache import get_or_create_cached_image
            cached_path = get_or_create_cached_image(db, image_key, filepath)
            if cached_path and os.path.exists(cached_path):
                if not _is_path_under_allowed_roots(cached_path, allowed_cat):
                    return error_not_found('file')
                return send_file(cached_path, mimetype='image/jpeg')
        except Exception as cache_err:
            # If cache generation fails, log but don't break the request
            print(f"Cache generation failed for {image_key}: {cache_err}")

        # Last resort: send original (may not be browser-compatible)
        return send_file(filepath, mimetype='image/jpeg')
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/catalog/months', methods=['GET'])
@with_db
def get_catalog_months(db):
    """Get available year-months from catalog images based on date_taken."""
    try:
        rows = db.execute("""
            SELECT DISTINCT strftime('%Y%m', date_taken) as month
            FROM images
            WHERE date_taken IS NOT NULL
            ORDER BY month DESC
        """).fetchall()
        months = [row['month'] for row in rows if row['month']]
        return jsonify({'months': months})
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/catalog', methods=['GET'])
@with_db
def list_catalog_images(db):
    """List catalog images with optional filtering and SQL-level pagination."""
    try:
        posted_raw = request.args.get('posted')
        if posted_raw == 'true':
            posted_filter = True
        elif posted_raw == 'false':
            posted_filter = False
        else:
            posted_filter = None

        analyzed_raw = request.args.get('analyzed')
        if analyzed_raw == 'true':
            analyzed_filter = True
        elif analyzed_raw == 'false':
            analyzed_filter = False
        else:
            analyzed_filter = None

        month = request.args.get('month')
        keyword = request.args.get('keyword', '')
        min_rating = request.args.get('min_rating', type=int)
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        color_label = request.args.get('color_label', '')

        score_perspective = (request.args.get('score_perspective') or '').strip()
        if score_perspective and not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(score_perspective):
            return error_bad_request('invalid score_perspective slug')

        sort_raw = (request.args.get('sort_by_score') or '').strip().lower()
        sort_by_score = None
        if sort_raw:
            if sort_raw not in ('asc', 'desc'):
                return error_bad_request('sort_by_score must be asc or desc')
            sort_by_score = sort_raw

        if sort_by_score and not score_perspective:
            return error_bad_request('sort_by_score requires score_perspective')

        sort_date_raw = (request.args.get('sort_by_date') or '').strip().lower()
        sort_by_date = None
        if sort_date_raw:
            if sort_date_raw not in ('newest', 'oldest'):
                return error_bad_request('sort_by_date must be newest or oldest')
            sort_by_date = sort_date_raw

        min_score = None
        if 'min_score' in request.args:
            min_score_raw = request.args.get('min_score')
            if min_score_raw is None or str(min_score_raw).strip() == '':
                min_score = None
            else:
                try:
                    min_score = int(min_score_raw)
                except (TypeError, ValueError):
                    return error_bad_request('min_score must be an integer')
                if min_score < 1 or min_score > 10:
                    return error_bad_request('min_score must be between 1 and 10')

        if min_score is not None and not score_perspective:
            return error_bad_request('min_score requires score_perspective')

        limit, offset = _clamp_pagination(
            request.args.get('limit', 50, type=int),
            request.args.get('offset', 0, type=int),
        )

        score_perspective_arg = score_perspective or None
        try:
            rows, total = query_catalog_images(
                db,
                posted=posted_filter,
                month=month,
                keyword=keyword.strip() or None,
                min_rating=min_rating,
                date_from=date_from or None,
                date_to=date_to or None,
                color_label=color_label.strip() or None,
                analyzed=analyzed_filter,
                score_perspective=score_perspective_arg,
                min_score=min_score,
                sort_by_score=sort_by_score,
                sort_by_date=sort_by_date,
                limit=limit,
                offset=offset,
            )
        except ValueError as err:
            return error_bad_request(str(err))

        score_join_active = bool(score_perspective_arg)

        images = []
        for row in rows:
            out = dict(row)
            desc_summary = out.pop('description_summary', None)
            desc_best = out.pop('description_best_perspective', None)
            desc_perspectives_json = out.pop('description_perspectives_json', None)

            if score_join_active:
                cps = out.pop('catalog_perspective_score', None)
                out['catalog_perspective_score'] = int(cps) if cps is not None else None
                out['catalog_score_perspective'] = score_perspective_arg

            ai_analyzed = desc_summary is not None
            out['ai_analyzed'] = ai_analyzed
            if ai_analyzed:
                out['description_summary'] = desc_summary or ''
                out['description_best_perspective'] = desc_best or ''
                if desc_perspectives_json:
                    try:
                        out['description_perspectives'] = json.loads(desc_perspectives_json)
                    except (json.JSONDecodeError, TypeError):
                        out['description_perspectives'] = {}
                else:
                    out['description_perspectives'] = {}
            else:
                out['description_summary'] = None
                out['description_best_perspective'] = None
                out['description_perspectives'] = None

            rid = out.get('id')
            if rid is not None and str(rid).strip().isdigit():
                out['id'] = int(rid)
            else:
                out['id'] = None
            images.append(out)

        return jsonify({
            'total': total,
            'images': images,
        })
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/dump-media', methods=['GET'])
@with_db
def list_dump_media(db):
    """List dump media with optional filtering."""
    try:
        processed = request.args.get('processed')
        matched = request.args.get('matched')
        limit, offset = _clamp_pagination(
            request.args.get('limit', 50, type=int),
            request.args.get('offset', 0, type=int),
        )

        if processed == 'true':
            media = db.execute(
                "SELECT * FROM instagram_dump_media WHERE processed = 1"
            ).fetchall()
        elif processed == 'false':
            media = db.execute(
                "SELECT * FROM instagram_dump_media WHERE processed = 0"
            ).fetchall()
        elif matched == 'true':
            media = db.execute(
                "SELECT * FROM instagram_dump_media WHERE matched_catalog_key IS NOT NULL"
            ).fetchall()
        elif matched == 'false':
            media = db.execute(
                "SELECT * FROM instagram_dump_media WHERE matched_catalog_key IS NULL"
            ).fetchall()
        else:
            media = db.execute("SELECT * FROM instagram_dump_media").fetchall()

        total = len(media)
        paginated = media[offset:offset+limit]

        return jsonify({
            'total': total,
            'media': paginated,
        })
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/matches', methods=['GET'])
@with_db
def list_matches(db):
    """List matches grouped by Instagram image."""
    try:
        matches = db.execute(
            "SELECT * FROM matches ORDER BY insta_key, COALESCE(rank, 1), total_score DESC"
        ).fetchall()

        # Build lookup tables for images (avoid N+1 queries)
        instagram_lookup = {}
        for img in db.execute("SELECT * FROM instagram_images").fetchall():
            instagram_lookup[img.get('key')] = img

        catalog_lookup = {}
        for img in db.execute("SELECT * FROM images").fetchall():
            catalog_lookup[img.get('key')] = img

        desc_lookup = {}
        try:
            for desc in db.execute("SELECT * FROM image_descriptions").fetchall():
                key = (desc.get('image_key'), desc.get('image_type'))
                desc_lookup[key] = _deserialize_description(desc)
        except sqlite3.OperationalError:
            pass

        model_lookup = {}
        try:
            for row in db.execute("SELECT insta_key, model_used FROM matches").fetchall():
                model_lookup[row['insta_key']] = row['model_used']
        except sqlite3.OperationalError:
            pass

        insta_keys = {m.get('insta_key') for m in matches if m.get('insta_key')}
        dump_instagram_by_key = {}
        if insta_keys:
            keys_list = list(insta_keys)
            chunk_size = 500
            dump_rows = []
            for i in range(0, len(keys_list), chunk_size):
                chunk = keys_list[i:i + chunk_size]
                placeholders = ','.join('?' * len(chunk))
                dump_rows.extend(
                    db.execute(
                        f"SELECT * FROM instagram_dump_media WHERE media_key IN ({placeholders})",
                        chunk,
                    ).fetchall()
                )
            enriched_dump_list = _enrich_instagram_media(
                dump_rows, model_lookup, desc_lookup
            )
            dump_instagram_by_key = {row['key']: row for row in enriched_dump_list}

        groups = OrderedDict()
        all_enriched = []

        for match in matches:
            insta_key = match.get('insta_key')
            catalog_key = match.get('catalog_key')

            enriched = {
                **match,
                'instagram_key': insta_key,
                'score': match.get('total_score', 0),
            }

            resolved_insta = None
            if insta_key:
                resolved_insta = instagram_lookup.get(insta_key) or dump_instagram_by_key.get(insta_key)
            if resolved_insta:
                enriched['instagram_image'] = resolved_insta
            if catalog_key and catalog_key in catalog_lookup:
                enriched['catalog_image'] = catalog_lookup[catalog_key]

            enriched['catalog_description'] = desc_lookup.get((catalog_key, 'catalog')) if catalog_key else None
            enriched['insta_description'] = desc_lookup.get((insta_key, 'instagram')) if insta_key else None

            groups.setdefault(insta_key, []).append(enriched)
            all_enriched.append(enriched)

        match_groups = []
        for insta_key, candidates in groups.items():
            best = max((c.get('score') or 0) for c in candidates) if candidates else 0
            match_groups.append({
                'instagram_key': insta_key,
                'instagram_image': instagram_lookup.get(insta_key) or dump_instagram_by_key.get(insta_key),
                'candidates': candidates,
                'best_score': best,
                'candidate_count': len(candidates),
                'has_validated': any(c.get('validated_at') for c in candidates),
                'all_rejected': False if len(candidates) > 0 else True,
            })

        insta_keys_with_matches = frozenset(groups.keys())

        try:
            rejected_inst_keys = [
                row['insta_key']
                for row in db.execute("SELECT DISTINCT insta_key FROM rejected_matches").fetchall()
                if row.get('insta_key')
            ]
        except sqlite3.OperationalError:
            rejected_inst_keys = []

        tombstone_only_keys = []
        for ik in rejected_inst_keys:
            if ik in insta_keys_with_matches:
                continue
            still_has = db.execute(
                "SELECT 1 FROM matches WHERE insta_key = ? LIMIT 1", (ik,)
            ).fetchone()
            if not still_has:
                tombstone_only_keys.append(ik)

        if tombstone_only_keys:
            keys_to_enrich = [
                k for k in tombstone_only_keys
                if k not in dump_instagram_by_key and k not in instagram_lookup
            ]
            if keys_to_enrich:
                chunk_size = 500
                extra_dump_rows = []
                for i in range(0, len(keys_to_enrich), chunk_size):
                    chunk = keys_to_enrich[i:i + chunk_size]
                    placeholders = ','.join('?' * len(chunk))
                    extra_dump_rows.extend(
                        db.execute(
                            f"SELECT * FROM instagram_dump_media WHERE media_key IN ({placeholders})",
                            chunk,
                        ).fetchall()
                    )
                for row in _enrich_instagram_media(extra_dump_rows, model_lookup, desc_lookup):
                    dump_instagram_by_key[row['key']] = row

        for ik in tombstone_only_keys:
            match_groups.append({
                'instagram_key': ik,
                'instagram_image': instagram_lookup.get(ik) or dump_instagram_by_key.get(ik),
                'candidates': [],
                'best_score': 0.0,
                'candidate_count': 0,
                'has_validated': False,
                'all_rejected': True,
            })

        def _parse_ts(ts):
            if not ts:
                return None
            s = str(ts).replace('Z', '+00:00')
            try:
                return datetime.fromisoformat(s).timestamp()
            except ValueError:
                return None

        def _photo_ts_float(group_dict):
            ig = group_dict.get('instagram_image') or {}
            if isinstance(ig, dict):
                ts = _parse_ts(ig.get('created_at'))
                if ts is not None:
                    return ts
            best_cat_ts = None
            for c in group_dict.get('candidates') or []:
                cat = c.get('catalog_image') or {}
                dt = cat.get('date_taken')
                t = _parse_ts(dt)
                if t is not None and (best_cat_ts is None or t > best_cat_ts):
                    best_cat_ts = t
            return best_cat_ts

        sort_date_raw = (request.args.get('sort_by_date') or '').strip().lower()
        if sort_date_raw and sort_date_raw not in ('newest', 'oldest'):
            return error_bad_request('sort_by_date must be newest or oldest')
        # Default behaviour (no param): newest first within each bucket.
        oldest_first = sort_date_raw == 'oldest'

        def _match_group_sort_key(g):
            # Bucket 0 = actionable (unvalidated, not all-rejected tombstone); 1 = reviewed bucket.
            sort_bucket = 1 if (g.get('all_rejected') or g.get('has_validated')) else 0
            photo_ts = _photo_ts_float(g)
            if photo_ts is None:
                return (sort_bucket, 1, 0.0)
            # Invert when sorting ascending within the bucket.
            return (sort_bucket, 0, photo_ts if oldest_first else -photo_ts)

        match_groups.sort(key=_match_group_sort_key)

        limit, offset = _clamp_pagination(
            request.args.get('limit', 50, type=int),
            request.args.get('offset', 0, type=int),
        )
        paginated_groups = match_groups[offset:offset+limit]
        paginated_matches = []
        for grp in paginated_groups:
            paginated_matches.extend(grp['candidates'])

        total_groups = len(match_groups)
        total_matches = len(all_enriched)

        return jsonify({
            'total': total_groups,
            'total_groups': total_groups,
            'total_matches': total_matches,
            'match_groups': paginated_groups,
            'matches': paginated_matches,
        })
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/matches/<path:catalog_key>/<path:insta_key>/validate', methods=['PATCH'])
@with_db
def toggle_match_validation(db, catalog_key, insta_key):
    """Toggle human validation on a match."""
    try:
        match_row = db.execute(
            "SELECT validated_at FROM matches WHERE catalog_key = ? AND insta_key = ?",
            (catalog_key, insta_key),
        ).fetchone()
        if not match_row:
            return error_not_found('match')

        if match_row['validated_at']:
            unvalidate_match(db, catalog_key, insta_key)
            return jsonify({'validated': False})
        else:
            validate_match(db, catalog_key, insta_key)
            return jsonify({'validated': True})
    except Exception as e:
        return error_server_error(str(e))


@bp.route('/matches/<path:catalog_key>/<path:insta_key>/reject', methods=['PATCH'])
@with_db
def reject_match_endpoint(db, catalog_key, insta_key):
    """Reject a match: delete it and blocklist the pair."""
    try:
        match_row = db.execute(
            "SELECT validated_at FROM matches WHERE catalog_key = ? AND insta_key = ?",
            (catalog_key, insta_key),
        ).fetchone()
        if not match_row:
            return error_not_found('match')
        if match_row['validated_at']:
            return jsonify({
                'error': 'Match has been validated; un-validate it before rejecting.',
                'rejected': False,
            }), 409

        reject_match(db, catalog_key, insta_key)
        return jsonify({'rejected': True})
    except Exception as e:
        return error_server_error(str(e))
_DETAIL_IMAGE_TYPES = ('catalog', 'instagram')


def _build_catalog_detail(db, image_key, score_perspective):
    """Build the catalog detail payload; returns (payload_dict, 404_flag)."""
    row = get_image(db, image_key)
    if not row:
        return None, True

    out = dict(row)
    out['image_type'] = 'catalog'

    desc_row = get_image_description(db, image_key)
    if desc_row and desc_row.get('image_type') == 'catalog':
        out['ai_analyzed'] = True
        out['description_summary'] = desc_row.get('summary') or ''
        out['description_best_perspective'] = desc_row.get('best_perspective') or ''
        persp = desc_row.get('perspectives')
        out['description_perspectives'] = persp if isinstance(persp, dict) else {}
    else:
        out['ai_analyzed'] = False
        out['description_summary'] = None
        out['description_best_perspective'] = None
        out['description_perspectives'] = None

    # Identity aggregate (may be None when no scores yet).
    identity = compute_single_image_aggregate_scores(db, image_key)
    if identity is not None:
        out['identity_aggregate_score'] = identity['aggregate_score']
        out['identity_perspectives_covered'] = identity['perspectives_covered']
        out['identity_eligible'] = identity['eligible']
        out['identity_per_perspective'] = identity['per_perspective']
    else:
        out['identity_aggregate_score'] = None
        out['identity_perspectives_covered'] = 0
        out['identity_eligible'] = False
        out['identity_per_perspective'] = []

    # Per-slug catalog score (same semantics as list endpoint).
    if score_perspective:
        score_row = db.execute(
            "SELECT score FROM image_scores "
            "WHERE image_key = ? AND image_type = 'catalog' "
            "AND perspective_slug = ? AND is_current = 1",
            (image_key, score_perspective),
        ).fetchone()
        out['catalog_perspective_score'] = (
            int(score_row['score']) if score_row else None
        )
        out['catalog_score_perspective'] = score_perspective
    else:
        out['catalog_perspective_score'] = None
        out['catalog_score_perspective'] = None

    # Every persisted current score perspective for this image (drives modal picker).
    slug_rows = db.execute(
        "SELECT DISTINCT perspective_slug FROM image_scores "
        "WHERE image_key = ? AND image_type = 'catalog' AND is_current = 1 "
        "ORDER BY perspective_slug",
        (image_key,),
    ).fetchall()
    out['available_score_perspectives'] = [
        str(r['perspective_slug']) for r in slug_rows
    ]

    rid = out.get('id')
    if rid is not None and str(rid).strip().isdigit():
        out['id'] = int(rid)
    else:
        out['id'] = None

    return out, False


def _build_instagram_detail(db, image_key):
    """Build the instagram detail payload; returns (payload_dict, 404_flag)."""
    row = get_instagram_dump_media(db, image_key)
    if not row:
        return None, True

    out = dict(row)
    out['image_type'] = 'instagram'
    # Normalize to the same ``key`` alias catalog uses.
    out['key'] = row.get('media_key') or image_key
    # Parity with ``_enrich_instagram_media`` so the detail modal renders
    # the same folder / source fields the list tiles would have.
    out['instagram_folder'] = row.get('date_folder') or ''
    out['source_folder'] = _extract_source_folder(row.get('file_path') or '')
    out['local_path'] = row.get('file_path') or ''
    out['processed'] = bool(row.get('processed'))
    out['matched_catalog_key'] = row.get('matched_catalog_key')

    desc_row = get_image_description(db, image_key)
    if desc_row and desc_row.get('image_type') == 'instagram':
        out['ai_analyzed'] = True
        out['description_summary'] = desc_row.get('summary') or ''
        out['description_best_perspective'] = desc_row.get('best_perspective') or ''
        persp = desc_row.get('perspectives')
        out['description_perspectives'] = persp if isinstance(persp, dict) else {}
    else:
        out['ai_analyzed'] = False
        out['description_summary'] = None
        out['description_best_perspective'] = None
        out['description_perspectives'] = None

    # Instagram rows have no identity scoring (catalog-only by design).
    out['identity_aggregate_score'] = None
    out['identity_perspectives_covered'] = 0
    out['identity_eligible'] = False
    out['identity_per_perspective'] = []
    out['catalog_perspective_score'] = None
    out['catalog_score_perspective'] = None
    out['available_score_perspectives'] = []

    return out, False


@bp.route('/<string:image_type>/<path:image_key>', methods=['GET'])
@with_db
def get_image_detail(db, image_type, image_key):
    """Single-image detail payload — used by the consolidated image-view modal."""
    if image_type not in _DETAIL_IMAGE_TYPES:
        return error_bad_request(
            f"invalid image_type; expected one of {_DETAIL_IMAGE_TYPES}"
        )

    score_perspective = (request.args.get('score_perspective') or '').strip()
    if score_perspective and not _CATALOG_SCORE_PERSPECTIVE_SLUG_RE.match(score_perspective):
        return error_bad_request('invalid score_perspective slug')
    if score_perspective and image_type != 'catalog':
        return error_bad_request('score_perspective is only valid for catalog images')

    try:
        if image_type == 'catalog':
            payload, not_found = _build_catalog_detail(
                db, image_key, score_perspective or None
            )
        else:
            payload, not_found = _build_instagram_detail(db, image_key)
        if not_found:
            return error_not_found('image')
        return jsonify(payload)
    except Exception as e:
        return error_server_error(str(e))
