from __future__ import annotations

import math
from pathlib import Path


def read_luma(path: Path, width: int, height: int, bit_depth: int) -> list[float]:
    sample_count = width * height
    data = path.read_bytes()
    if bit_depth <= 8:
        values = data[:sample_count]
        scale = 255.0
        return [value / scale for value in values]

    values: list[float] = []
    scale = float((1 << bit_depth) - 1)
    for index in range(sample_count):
        offset = index * 2
        values.append(int.from_bytes(data[offset : offset + 2], "little") / scale)
    return values


def msssim_luma(reference: list[float], distorted: list[float], width: int, height: int) -> float:
    weights = [0.0448, 0.2856, 0.3001, 0.2363, 0.1333]
    score = 1.0
    ref = reference
    dis = distorted
    w = width
    h = height
    for weight in weights:
        score *= max(_ssim_global(ref, dis), 1e-9) ** weight
        if w < 2 or h < 2:
            break
        ref, w, h = _downsample2(ref, w, h)
        dis, _w2, _h2 = _downsample2(dis, w * 2, h * 2)
    return score


def fsim_luma(reference: list[float], distorted: list[float], width: int, height: int) -> float:
    ref_grad = _gradient_magnitude(reference, width, height)
    dis_grad = _gradient_magnitude(distorted, width, height)
    constant = 0.0026
    weighted_sum = 0.0
    weight_total = 0.0
    for ref_value, dis_value in zip(ref_grad, dis_grad):
        similarity = (2.0 * ref_value * dis_value + constant) / (ref_value * ref_value + dis_value * dis_value + constant)
        weight = max(ref_value, dis_value)
        weighted_sum += similarity * weight
        weight_total += weight
    return weighted_sum / weight_total if weight_total else 1.0


def haarpsi_luma(reference: list[float], distorted: list[float], width: int, height: int) -> float:
    scores = []
    for scale in (1, 2):
        ref_h, ref_v = _haar_coefficients(reference, width, height, scale)
        dis_h, dis_v = _haar_coefficients(distorted, width, height, scale)
        scores.append(_weighted_similarity(ref_h, dis_h))
        scores.append(_weighted_similarity(ref_v, dis_v))
    return sum(scores) / len(scores)


def psnr_hvs_m_luma(reference: list[float], distorted: list[float], width: int, height: int) -> float:
    total = 0.0
    samples = 0
    for y in range(0, height - 7, 8):
        for x in range(0, width - 7, 8):
            ref_block = _block(reference, width, x, y)
            mean = sum(ref_block) / 64.0
            variance = sum((value - mean) ** 2 for value in ref_block) / 64.0
            masking = 1.0 + min(variance * 18.0, 0.45)
            for row in range(8):
                for col in range(8):
                    index = (y + row) * width + x + col
                    freq_weight = 1.0 + 0.08 * math.hypot(row, col)
                    error = (reference[index] - distorted[index]) * freq_weight / masking
                    total += error * error
                    samples += 1
    if total <= 0.0:
        return 99.0
    mse = total / samples
    return 10.0 * math.log10(1.0 / mse)


def calculate_luma_metrics(
    reference_yuv: Path,
    distorted_yuv: Path,
    width: int,
    height: int,
    reference_bit_depth: int = 8,
    distorted_bit_depth: int = 10,
) -> dict[str, float]:
    reference = read_luma(reference_yuv, width, height, reference_bit_depth)
    distorted = read_luma(distorted_yuv, width, height, distorted_bit_depth)
    return {
        "msssim_luma": msssim_luma(reference, distorted, width, height),
        "fsim_luma": fsim_luma(reference, distorted, width, height),
        "haarpsi_luma": haarpsi_luma(reference, distorted, width, height),
        "psnr_hvs_m_luma": psnr_hvs_m_luma(reference, distorted, width, height),
    }


def _ssim_global(reference: list[float], distorted: list[float]) -> float:
    n = len(reference)
    mean_ref = sum(reference) / n
    mean_dis = sum(distorted) / n
    var_ref = sum((value - mean_ref) ** 2 for value in reference) / max(n - 1, 1)
    var_dis = sum((value - mean_dis) ** 2 for value in distorted) / max(n - 1, 1)
    cov = sum((ref - mean_ref) * (dis - mean_dis) for ref, dis in zip(reference, distorted)) / max(n - 1, 1)
    c1 = 0.01 * 0.01
    c2 = 0.03 * 0.03
    return ((2 * mean_ref * mean_dis + c1) * (2 * cov + c2)) / ((mean_ref * mean_ref + mean_dis * mean_dis + c1) * (var_ref + var_dis + c2))


def _downsample2(values: list[float], width: int, height: int) -> tuple[list[float], int, int]:
    next_width = width // 2
    next_height = height // 2
    output = []
    for y in range(next_height):
        row = y * 2 * width
        for x in range(next_width):
            offset = row + x * 2
            output.append((values[offset] + values[offset + 1] + values[offset + width] + values[offset + width + 1]) * 0.25)
    return output, next_width, next_height


def _gradient_magnitude(values: list[float], width: int, height: int) -> list[float]:
    output = [0.0] * (width * height)
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            gx = values[row + x + 1] - values[row + x - 1]
            gy = values[row + width + x] - values[row - width + x]
            output[row + x] = math.sqrt(gx * gx + gy * gy)
    return output


def _haar_coefficients(values: list[float], width: int, height: int, scale: int) -> tuple[list[float], list[float]]:
    horizontal = []
    vertical = []
    step = max(1, scale)
    for y in range(0, height - step, step):
        row = y * width
        next_row = (y + step) * width
        for x in range(0, width - step, step):
            horizontal.append(abs(values[row + x] - values[row + x + step]))
            vertical.append(abs(values[row + x] - values[next_row + x]))
    return horizontal, vertical


def _weighted_similarity(reference: list[float], distorted: list[float]) -> float:
    constant = 0.01
    weighted_sum = 0.0
    weight_total = 0.0
    for ref, dis in zip(reference, distorted):
        similarity = (2.0 * ref * dis + constant) / (ref * ref + dis * dis + constant)
        weight = max(ref, dis)
        weighted_sum += similarity * weight
        weight_total += weight
    return weighted_sum / weight_total if weight_total else 1.0


def _block(values: list[float], width: int, x: int, y: int) -> list[float]:
    return [values[(y + row) * width + x + col] for row in range(8) for col in range(8)]

