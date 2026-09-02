"""Frame substance per-image read and mutation routes."""

from __future__ import annotations

from flask import jsonify
from spectree import Response
from utils.db import with_db
from utils.lr_catalog_write import (
    describe_lr_catalog_write_status,
    read_cull_keyword_present,
    remove_cull_keyword,
    write_cull_keyword,
)
from utils.responses import error_bad_request, error_not_found, error_server_error

from api.openapi import spec
from api.schemas.frame_substance import (
    CullKeywordMutationResponse,
    FrameSubstanceInstrument,
    FrameSubstanceOverrideResponse,
    FrameSubstanceResponse,
)
from api.schemas.jobs import ErrorBody
from lightroom_tagger.core.database import (
    delete_frame_substance_override,
    get_frame_substance_verdict,
    get_image,
    get_latest_finished_frame_substance_run,
    has_excusal_channel_hint,
    has_frame_substance_override,
    insert_frame_substance_override,
    is_frame_substance_flagged,
    is_frame_substance_verdict_stale,
    library_write,
)

from .catalog import catalog_bp


def _build_frame_substance_response(db, image_key: str) -> dict:
    verdict_row = get_frame_substance_verdict(db, image_key)
    has_run = get_latest_finished_frame_substance_run(db) is not None
    catalog_status = describe_lr_catalog_write_status()

    instrument: FrameSubstanceInstrument | None = None
    restore_tier: str | None = None
    verdict_value = None
    unknown_reason = None
    detector_version = None
    judged_at = None

    if verdict_row is not None:
        verdict_value = str(verdict_row.get("verdict") or "")
        unknown_reason = str(verdict_row.get("unknown_reason") or "") or None
        detector_version = str(verdict_row.get("detector_version") or "") or None
        judged_at = str(verdict_row.get("judged_at") or "") or None
        if verdict_value in ("void", "illegible"):
            tier = "A" if verdict_value == "void" else "B"
            instrument = FrameSubstanceInstrument(
                kind="pixel_detector",
                verdict=verdict_value,
                tier=tier,
                advisory=False,
            )
            restore_tier = tier
    if instrument is None and has_excusal_channel_hint(db, image_key):
        instrument = FrameSubstanceInstrument(
            kind="excusal_channel",
            verdict=None,
            tier=None,
            advisory=True,
        )

    has_cull_keyword = None
    if catalog_status.available:
        has_cull_keyword = read_cull_keyword_present(image_key)

    return FrameSubstanceResponse(
        image_key=image_key,
        has_detection_run=has_run,
        verdict=verdict_value,
        unknown_reason=unknown_reason,
        detector_version=detector_version,
        judged_at=judged_at,
        is_stale=is_frame_substance_verdict_stale(
            db, image_key, verdict_row=verdict_row
        ),
        has_override=has_frame_substance_override(db, image_key),
        flagged=is_frame_substance_flagged(db, image_key),
        has_cull_keyword=has_cull_keyword,
        instrument=instrument,
        restore_tier=restore_tier,
        catalog_write_available=catalog_status.available,
        catalog_write_unavailable_reason=catalog_status.reason,
    ).model_dump()


@catalog_bp.route("/<path:image_key>/frame-substance", methods=["GET"])
@with_db
@spec.validate(
    resp=Response(HTTP_200=FrameSubstanceResponse, HTTP_404=ErrorBody),
    tags=['images-catalog'],
)
def get_catalog_frame_substance(db, image_key: str):
    try:
        if not get_image(db, image_key):
            return error_not_found("image")
        return jsonify(_build_frame_substance_response(db, image_key))
    except Exception as e:
        return error_server_error(str(e))


@catalog_bp.route("/<path:image_key>/frame-substance/override", methods=["POST"])
@with_db
@spec.validate(
    resp=Response(HTTP_200=FrameSubstanceOverrideResponse, HTTP_404=ErrorBody),
    tags=['images-catalog'],
)
def post_catalog_frame_substance_override(db, image_key: str):
    try:
        if not get_image(db, image_key):
            return error_not_found("image")
        with library_write(db):
            insert_frame_substance_override(db, image_key)
        return jsonify({"image_key": image_key, "has_override": True})
    except Exception as e:
        return error_server_error(str(e))


@catalog_bp.route("/<path:image_key>/frame-substance/override", methods=["DELETE"])
@with_db
@spec.validate(
    resp=Response(HTTP_200=FrameSubstanceOverrideResponse, HTTP_404=ErrorBody),
    tags=['images-catalog'],
)
def delete_catalog_frame_substance_override(db, image_key: str):
    try:
        if not get_image(db, image_key):
            return error_not_found("image")
        with library_write(db):
            delete_frame_substance_override(db, image_key)
        return jsonify({"image_key": image_key, "has_override": False})
    except Exception as e:
        return error_server_error(str(e))


@catalog_bp.route("/<path:image_key>/cull-keyword", methods=["POST"])
@with_db
@spec.validate(
    resp=Response(
        HTTP_200=CullKeywordMutationResponse,
        HTTP_400=ErrorBody,
        HTTP_404=ErrorBody,
    ),
    tags=['images-catalog'],
)
def post_catalog_cull_keyword(db, image_key: str):
    try:
        if not get_image(db, image_key):
            return error_not_found("image")
        try:
            result = write_cull_keyword(image_key)
        except RuntimeError as exc:
            return error_bad_request(str(exc))
        return jsonify({"image_key": image_key, "result": result})
    except Exception as e:
        return error_server_error(str(e))


@catalog_bp.route("/<path:image_key>/cull-keyword", methods=["DELETE"])
@with_db
@spec.validate(
    resp=Response(
        HTTP_200=CullKeywordMutationResponse,
        HTTP_400=ErrorBody,
        HTTP_404=ErrorBody,
    ),
    tags=['images-catalog'],
)
def delete_catalog_cull_keyword(db, image_key: str):
    try:
        if not get_image(db, image_key):
            return error_not_found("image")
        try:
            result = remove_cull_keyword(image_key)
        except RuntimeError as exc:
            return error_bad_request(str(exc))
        return jsonify({"image_key": image_key, "result": result})
    except Exception as e:
        return error_server_error(str(e))
