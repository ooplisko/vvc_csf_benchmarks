from __future__ import annotations

import pytest

from metrics.image_quality import msssim_luma, msssim_rgb, psnr_rgb, read_yuv


def test_msssim_luma_identity_is_one() -> None:
    width = 16
    height = 16
    reference = [(x + y) / 30.0 for y in range(height) for x in range(width)]

    assert msssim_luma(reference, reference, width, height) == 1.0


def test_msssim_luma_decreases_for_distortion() -> None:
    width = 16
    height = 16
    reference = [(x + y) / 30.0 for y in range(height) for x in range(width)]
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


def test_read_yuv_rejects_incomplete_frame(tmp_path) -> None:
    yuv = tmp_path / "bad.yuv"
    yuv.write_bytes(b"\x00" * 10)

    with pytest.raises(ValueError):
        read_yuv(yuv, width=16, height=16, bit_depth=8, chroma_format="420")
