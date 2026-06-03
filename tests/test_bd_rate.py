from __future__ import annotations

import pytest

from metrics.bd_rate import bd_psnr, bd_rate


def test_bd_rate_is_zero_for_identical_curves() -> None:
    bpp = [1.2, 0.8, 0.5, 0.3]
    quality = [42.0, 39.0, 36.0, 33.0]

    assert bd_rate(bpp, quality, bpp, quality) == pytest.approx(0.0, abs=1e-9)
    assert bd_psnr(bpp, quality, bpp, quality) == pytest.approx(0.0, abs=1e-9)


def test_bd_rate_reports_bitrate_saving_for_scaled_curve() -> None:
    ref_bpp = [1.2, 0.8, 0.5, 0.3]
    test_bpp = [value * 0.9 for value in ref_bpp]
    quality = [42.0, 39.0, 36.0, 33.0]

    assert bd_rate(ref_bpp, quality, test_bpp, quality) == pytest.approx(-10.0, abs=0.05)


def test_bd_rate_returns_none_without_overlap() -> None:
    assert bd_rate([1.0, 0.8], [40.0, 39.0], [0.6, 0.4], [35.0, 34.0]) is None
