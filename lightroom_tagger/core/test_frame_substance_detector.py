"""Tests for frame substance detector rules and version hashing."""

from __future__ import annotations

import numpy as np

from lightroom_tagger.core.frame_substance_detector import (
    BLACK_AREA_TH,
    _THRESHOLD_TUPLE,
    classify_verdict,
    compute_statistics_from_greyscale,
    detector_version,
)


def _flat_black(shape: tuple[int, int] = (128, 128)) -> np.ndarray:
    return np.zeros(shape, dtype=np.uint8)


def _flat_white(shape: tuple[int, int] = (128, 128)) -> np.ndarray:
    return np.full(shape, 255, dtype=np.uint8)


def _black_with_bright_cluster(shape: tuple[int, int] = (512, 512)) -> np.ndarray:
    arr = np.zeros(shape, dtype=np.uint8)
    y, x = shape[0] // 2, shape[1] // 2
    arr[y - 2 : y + 2, x - 2 : x + 2] = 255
    return arr


def _blown_illegible(shape: tuple[int, int] = (128, 128)) -> np.ndarray:
    arr = np.full(shape, 250, dtype=np.uint8)
    margin = shape[0] // 8
    arr[margin : shape[0] - margin, margin : shape[1] - margin] = 245
    return arr


def _noisy_mid_grey(shape: tuple[int, int] = (128, 128)) -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.integers(80, 176, size=shape, dtype=np.uint8)


def _below_trigger_grey(shape: tuple[int, int] = (128, 128)) -> np.ndarray:
    arr = np.zeros(shape, dtype=np.uint8)
    total = arr.size
    bright_pixels = int(total * (1.0 - BLACK_AREA_TH)) + 8
    arr.ravel()[:bright_pixels] = 128
    return arr


def test_flat_black_is_void() -> None:
    stats = compute_statistics_from_greyscale(_flat_black())
    assert classify_verdict(stats) == "void"


def test_black_with_bright_cluster_is_illegible() -> None:
    stats = compute_statistics_from_greyscale(_black_with_bright_cluster())
    assert classify_verdict(stats) == "illegible"


def test_noisy_mid_grey_is_ok() -> None:
    stats = compute_statistics_from_greyscale(_noisy_mid_grey())
    assert classify_verdict(stats) == "ok"


def test_flat_white_is_void() -> None:
    stats = compute_statistics_from_greyscale(_flat_white())
    assert classify_verdict(stats) == "void"


def test_blown_near_uniform_frame_is_illegible() -> None:
    stats = compute_statistics_from_greyscale(_blown_illegible())
    assert classify_verdict(stats) == "illegible"


def test_untriggered_image_is_ok_regardless_of_structure_stats() -> None:
    stats = compute_statistics_from_greyscale(_below_trigger_grey())
    assert stats["black_frac_25"] < BLACK_AREA_TH
    assert stats["blown_frac_235"] < BLACK_AREA_TH
    stats["lap_var"] = 0.0
    stats["tile_max"] = 0.0
    stats["entropy"] = 0.0
    assert classify_verdict(stats) == "ok"


def test_detector_version_is_stable_and_changes_with_thresholds(
    monkeypatch,
) -> None:
    stable = detector_version()
    assert stable.startswith("v1-")
    assert detector_version() == stable

    monkeypatch.setattr(
        "lightroom_tagger.core.frame_substance_detector._THRESHOLD_TUPLE",
        _THRESHOLD_TUPLE[:-1] + (_THRESHOLD_TUPLE[-1] + 0.01,),
    )
    assert detector_version() != stable
