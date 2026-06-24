"""PSNR-HVS-M port of Nikolay Ponomarenko's published MATLAB implementation.

The original source is available from https://www.ponomarenko.info/psnrhvsm.htm.
This NumPy/SciPy port preserves its 8x8 DCT, CSF coefficients, masking
coefficients, block traversal, and default window step.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.fft import dctn


CSF = np.asarray(
    [
        [1.608443, 2.339554, 2.573509, 1.608443, 1.072295, 0.643377, 0.504610, 0.421887],
        [2.144591, 2.144591, 1.838221, 1.354478, 0.989811, 0.443708, 0.428918, 0.467911],
        [1.838221, 1.979622, 1.608443, 1.072295, 0.643377, 0.451493, 0.372972, 0.459555],
        [1.838221, 1.513829, 1.169777, 0.887417, 0.504610, 0.295806, 0.321689, 0.415082],
        [1.429727, 1.169777, 0.695543, 0.459555, 0.378457, 0.236102, 0.249855, 0.334222],
        [1.072295, 0.735288, 0.467911, 0.402111, 0.317717, 0.247453, 0.227744, 0.279729],
        [0.525206, 0.402111, 0.329937, 0.295806, 0.249855, 0.212687, 0.214459, 0.254803],
        [0.357432, 0.279729, 0.270896, 0.262603, 0.229778, 0.257351, 0.249855, 0.259950],
    ],
    dtype=np.float64,
)

MASK = np.asarray(
    [
        [0.390625, 0.826446, 1.000000, 0.390625, 0.173611, 0.062500, 0.038447, 0.026874],
        [0.694444, 0.694444, 0.510204, 0.277008, 0.147929, 0.029727, 0.027778, 0.033058],
        [0.510204, 0.591716, 0.390625, 0.173611, 0.062500, 0.030779, 0.021004, 0.031888],
        [0.510204, 0.346021, 0.206612, 0.118906, 0.038447, 0.013212, 0.015625, 0.026015],
        [0.308642, 0.206612, 0.073046, 0.031888, 0.021626, 0.008417, 0.009426, 0.016866],
        [0.173611, 0.081633, 0.033058, 0.024414, 0.015242, 0.009246, 0.007831, 0.011815],
        [0.041649, 0.024414, 0.016437, 0.013212, 0.009426, 0.006830, 0.006944, 0.009803],
        [0.019290, 0.011815, 0.011080, 0.010412, 0.007972, 0.010000, 0.009426, 0.010203],
    ],
    dtype=np.float64,
)


def psnr_hvs_m(reference: np.ndarray, distorted: np.ndarray, step: int = 8) -> float:
    """Return PSNR-HVS-M for two luma images whose samples are in [0, 255]."""

    if reference.shape != distorted.shape:
        raise ValueError(f"PSNR-HVS-M inputs have different shapes: {reference.shape} != {distorted.shape}")
    if reference.ndim != 2 or min(reference.shape) < 8:
        raise ValueError("PSNR-HVS-M requires two-dimensional images of at least 8x8 pixels")
    if step <= 0:
        raise ValueError("PSNR-HVS-M window step must be positive")

    total = 0.0
    samples = 0
    height, width = reference.shape
    for y in range(0, height - 7, step):
        for x in range(0, width - 7, step):
            ref_block = reference[y : y + 8, x : x + 8].astype(np.float64, copy=False)
            dis_block = distorted[y : y + 8, x : x + 8].astype(np.float64, copy=False)
            ref_dct = dctn(ref_block, type=2, norm="ortho")
            dis_dct = dctn(dis_block, type=2, norm="ortho")
            masking = max(_masking_effect(ref_block, ref_dct), _masking_effect(dis_block, dis_dct))

            difference = np.abs(ref_dct - dis_dct)
            threshold = masking / MASK
            masked_difference = np.maximum(difference - threshold, 0.0)
            masked_difference[0, 0] = difference[0, 0]
            total += float(np.sum((masked_difference * CSF) ** 2))
            samples += 64

    if samples == 0:
        raise ValueError("PSNR-HVS-M did not process any 8x8 blocks")
    mean_error = total / samples
    return 100000.0 if mean_error == 0.0 else 10.0 * math.log10(255.0**2 / mean_error)


def _masking_effect(block: np.ndarray, block_dct: np.ndarray) -> float:
    weighted_energy = float(np.sum((block_dct**2) * MASK) - (block_dct[0, 0] ** 2) * MASK[0, 0])
    population = _matlab_variance_energy(block)
    if population != 0.0:
        quadrants = (
            _matlab_variance_energy(block[:4, :4])
            + _matlab_variance_energy(block[:4, 4:])
            + _matlab_variance_energy(block[4:, 4:])
            + _matlab_variance_energy(block[4:, :4])
        )
        population = quadrants / population
    return math.sqrt(max(weighted_energy * population, 0.0)) / 32.0


def _matlab_variance_energy(values: np.ndarray) -> float:
    flattened = values.reshape(-1)
    if flattened.size <= 1:
        return 0.0
    return float(np.var(flattened, ddof=1) * flattened.size)
