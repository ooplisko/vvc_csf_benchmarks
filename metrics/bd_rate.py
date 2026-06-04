from __future__ import annotations

import math
from collections.abc import Sequence


# ====================================================================================================================
# Bjontegaard delta metrics
# ====================================================================================================================


def bd_rate(
    ref_bpp: Sequence[float],
    ref_metric: Sequence[float],
    test_bpp: Sequence[float],
    test_metric: Sequence[float],
) -> float | None:
    """Returns Bjontegaard Delta Rate in percent.

    Negative values mean the test curve uses fewer bits than the reference curve
    at the same quality level. `None` means the curves do not have a usable
    overlapping quality range.

    Parameters
    ----------
    ref_bpp : Sequence[float]
        Bits per pixel values for the reference encoder.
    ref_metric : Sequence[float]
        Quality metric values for the reference encoder.
    test_bpp : Sequence[float]
        Bits per pixel values for the test encoder.
    test_metric : Sequence[float]
        Quality metric values for the test encoder.

    Returns
    -------
    float | None
        The BD-Rate difference in percent, or None if the curves do not overlap.

    Examples
    --------
    >>> bd_rate([1.0, 2.0], [30.0, 35.0], [0.9, 1.8], [30.0, 35.0])
    -10.211892990698188
    """

    ref = _prepare_curve(ref_metric, [math.log(max(value, 1e-12)) for value in ref_bpp])
    test = _prepare_curve(test_metric, [math.log(max(value, 1e-12)) for value in test_bpp])
    overlap = _overlap(ref.xs, test.xs)
    if overlap is None:
        return None

    average_log_delta = _average_delta(ref, test, overlap[0], overlap[1])
    return (math.exp(average_log_delta) - 1.0) * 100.0


def bd_psnr(
    ref_bpp: Sequence[float],
    ref_metric: Sequence[float],
    test_bpp: Sequence[float],
    test_metric: Sequence[float],
) -> float | None:
    """Returns average quality delta at equal bitrate.

    Positive values mean the test curve has higher quality than the reference
    curve at the same bitrate. `None` means the curves do not have a usable
    overlapping bitrate range.

    Parameters
    ----------
    ref_bpp : Sequence[float]
        Bits per pixel values for the reference encoder.
    ref_metric : Sequence[float]
        Quality metric values for the reference encoder.
    test_bpp : Sequence[float]
        Bits per pixel values for the test encoder.
    test_metric : Sequence[float]
        Quality metric values for the test encoder.

    Returns
    -------
    float | None
        The BD-PSNR difference in the metric's units, or None if the curves do not overlap.

    Examples
    --------
    >>> bd_psnr([1.0, 2.0], [30.0, 35.0], [1.0, 2.0], [31.0, 36.0])
    1.0
    """

    ref = _prepare_curve([math.log(max(value, 1e-12)) for value in ref_bpp], ref_metric)
    test = _prepare_curve([math.log(max(value, 1e-12)) for value in test_bpp], test_metric)
    overlap = _overlap(ref.xs, test.xs)
    if overlap is None:
        return None

    return _average_delta(ref, test, overlap[0], overlap[1])


# ====================================================================================================================
# Piecewise cubic interpolation
# ====================================================================================================================


class _Curve:
    def __init__(self, xs: list[float], ys: list[float], slopes: list[float]) -> None:
        self.xs = xs
        self.ys = ys
        self.slopes = slopes


def _prepare_curve(xs: Sequence[float], ys: Sequence[float]) -> _Curve:
    if len(xs) != len(ys):
        raise ValueError("Bjontegaard curves must have matching x/y lengths")
    pairs = sorted((float(x), float(y)) for x, y in zip(xs, ys))
    deduped: list[tuple[float, float]] = []
    for x, y in pairs:
        if deduped and abs(x - deduped[-1][0]) < 1e-12:
            deduped[-1] = (x, (deduped[-1][1] + y) / 2.0)
        else:
            deduped.append((x, y))

    if len(deduped) < 2:
        raise ValueError("Bjontegaard curves need at least two distinct points")

    clean_xs = [x for x, _y in deduped]
    clean_ys = [y for _x, y in deduped]
    return _Curve(clean_xs, clean_ys, _pchip_slopes(clean_xs, clean_ys))


def _pchip_slopes(xs: list[float], ys: list[float]) -> list[float]:
    count = len(xs)
    if count == 2:
        slope = (ys[1] - ys[0]) / (xs[1] - xs[0])
        return [slope, slope]

    h = [xs[index + 1] - xs[index] for index in range(count - 1)]
    delta = [(ys[index + 1] - ys[index]) / h[index] for index in range(count - 1)]
    slopes = [0.0] * count

    for index in range(1, count - 1):
        if delta[index - 1] == 0.0 or delta[index] == 0.0 or (delta[index - 1] < 0.0) != (delta[index] < 0.0):
            slopes[index] = 0.0
        else:
            w1 = 2.0 * h[index] + h[index - 1]
            w2 = h[index] + 2.0 * h[index - 1]
            slopes[index] = (w1 + w2) / (w1 / delta[index - 1] + w2 / delta[index])

    slopes[0] = _endpoint_slope(h[0], h[1], delta[0], delta[1])
    slopes[-1] = _endpoint_slope(h[-1], h[-2], delta[-1], delta[-2])
    return slopes


def _endpoint_slope(h0: float, h1: float, delta0: float, delta1: float) -> float:
    slope = ((2.0 * h0 + h1) * delta0 - h0 * delta1) / (h0 + h1)
    if slope == 0.0 or (slope < 0.0) != (delta0 < 0.0):
        return 0.0
    if (delta0 < 0.0) != (delta1 < 0.0) and abs(slope) > abs(3.0 * delta0):
        return 3.0 * delta0
    return slope


def _evaluate(curve: _Curve, x: float) -> float:
    xs = curve.xs
    if x <= xs[0]:
        index = 0
    elif x >= xs[-1]:
        index = len(xs) - 2
    else:
        index = 0
        for candidate in range(len(xs) - 1):
            if xs[candidate] <= x <= xs[candidate + 1]:
                index = candidate
                break

    h = xs[index + 1] - xs[index]
    t = (x - xs[index]) / h
    y0 = curve.ys[index]
    y1 = curve.ys[index + 1]
    m0 = curve.slopes[index]
    m1 = curve.slopes[index + 1]
    h00 = (2.0 * t**3) - (3.0 * t**2) + 1.0
    h10 = t**3 - (2.0 * t**2) + t
    h01 = (-2.0 * t**3) + (3.0 * t**2)
    h11 = t**3 - t**2
    return h00 * y0 + h10 * h * m0 + h01 * y1 + h11 * h * m1


def _overlap(left: Sequence[float], right: Sequence[float]) -> tuple[float, float] | None:
    low = max(min(left), min(right))
    high = min(max(left), max(right))
    if high <= low:
        return None
    return low, high


def _average_delta(ref: _Curve, test: _Curve, low: float, high: float) -> float:
    samples = sorted({low, high, *[x for x in ref.xs if low < x < high], *[x for x in test.xs if low < x < high]})
    area = 0.0
    for x0, x1 in zip(samples, samples[1:]):
        mid = (x0 + x1) / 2.0
        area += (x1 - x0) / 6.0 * (
            _delta(ref, test, x0) + 4.0 * _delta(ref, test, mid) + _delta(ref, test, x1)
        )
    return area / (high - low)


def _delta(ref: _Curve, test: _Curve, x: float) -> float:
    return _evaluate(test, x) - _evaluate(ref, x)
