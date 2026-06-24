from __future__ import annotations

import math

import numpy as np
import pytest

from metrics.image_quality import haarpsi_luma, msssim_luma, msssim_rgb, psnr_hvs_m_luma, psnr_rgb, read_yuv
from metrics.psnr_hvs_m import psnr_hvs_m


def test_msssim_luma_identity_is_one() -> None:
    width = 176
    height = 176
    reference = [(x + y) / 350.0 for y in range(height) for x in range(width)]

    assert msssim_luma(reference, reference, width, height) == 1.0


def test_msssim_luma_decreases_for_distortion() -> None:
    width = 176
    height = 176
    reference = [(x + y) / 350.0 for y in range(height) for x in range(width)]
    distorted = [min(1.0, value + 0.1) for value in reference]

    assert msssim_luma(reference, distorted, width, height) < 1.0


def test_msssim_rgb_identity_is_one() -> None:
    width = 8
    height = 8
    red = [0.25] * (width * height)
    green = [0.50] * (width * height)
    blue = [0.75] * (width * height)

    assert msssim_rgb(red, green, blue, red, green, blue, width, height) == 1.0


def test_psnr_rgb_identity_uses_cap_value() -> None:
    samples = [0.0, 0.5, 1.0]

    assert psnr_rgb(samples, samples, samples, samples, samples, samples) == 99.0


def test_reference_luma_metrics_identity() -> None:
    width = 176
    height = 176
    samples = [(x + y) / 350.0 for y in range(height) for x in range(width)]

    assert haarpsi_luma(samples, samples, width, height) == pytest.approx(1.0)
    assert psnr_hvs_m_luma(samples, samples, width, height) == 100000.0


def test_reference_luma_metrics_regression() -> None:
    width = 256
    height = 256
    y, x = np.mgrid[0:height, 0:width]
    reference = ((3 * x + 5 * y + (x * y) % 37) % 256).astype(np.uint8)
    distorted = np.clip(reference.astype(np.int16) + ((x % 9) - 4), 0, 255).astype(np.uint8)
    ref_samples = (reference / 255.0).ravel().tolist()
    dis_samples = (distorted / 255.0).ravel().tolist()

    assert msssim_luma(ref_samples, dis_samples, width, height) == pytest.approx(0.9980908180234471, abs=1e-12)
    assert haarpsi_luma(ref_samples, dis_samples, width, height) == pytest.approx(0.9523704665310944, abs=1e-12)
    assert psnr_hvs_m_luma(ref_samples, dis_samples, width, height) == pytest.approx(36.89445526873182, abs=1e-12)


def test_psnr_hvs_m_matches_octave_reference_goldens() -> None:
    gradient = np.asarray([[96 + ((x * 2 + y * 3) % 64) for x in range(64)] for y in range(64)], dtype=np.float64)
    solid = np.full((64, 64), 128.0)
    texture = np.asarray(
        [
            [
                _rust_round(min(247.0, max(8.0, 128.0 + 70.0 * math.sin(x * 0.42) * math.cos(y * 0.31) + 25.0 * ((x ^ y) % 13))))
                for x in range(64)
            ]
            for y in range(64)
        ],
        dtype=np.float64,
    )

    cases = [
        (gradient, _distort_fixture(gradient, 10.0), 38.018849),
        (gradient, _distort_fixture(gradient, 40.0), 23.581020),
        (solid, _distort_fixture(solid, 5.0), 40.924111),
        (texture, _distort_fixture(texture, 20.0), 33.602163),
    ]
    for reference, distorted, expected in cases:
        assert psnr_hvs_m(reference, distorted) == pytest.approx(expected, abs=1e-6)


def _distort_fixture(reference: np.ndarray, amplitude: float) -> np.ndarray:
    return np.asarray(
        [
            [
                _rust_round(min(255.0, max(0.0, reference[y, x] + amplitude * _fixture_delta(x, y))))
                for x in range(reference.shape[1])
            ]
            for y in range(reference.shape[0])
        ],
        dtype=np.float64,
    )


def _fixture_delta(x: int, y: int) -> float:
    mask = 0xFFFFFFFF
    value = ((x * 0x9E3779B1) & mask) ^ ((y * 0x85EBCA77) & mask)
    value ^= value >> 15
    value = (value * 0x2545F491) & mask
    value ^= value >> 13
    return (value % 20001) / 10000.0 - 1.0


def _rust_round(value: float) -> float:
    return math.floor(value + 0.5)


def test_read_yuv_rejects_incomplete_frame(tmp_path) -> None:
    yuv = tmp_path / "bad.yuv"
    yuv.write_bytes(b"\x00" * 10)

    with pytest.raises(ValueError):
        read_yuv(yuv, width=16, height=16, bit_depth=8, chroma_format="420")
