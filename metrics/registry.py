"""Single source of truth for benchmark metric keys, labels, provenance, and chart paths.

Adding a new metric requires only one change: append a tuple to
``_METRIC_DEFS`` below.  The ``METRICS`` list, label dictionaries,
column definitions, and chart paths are all derived automatically.
"""
from __future__ import annotations

# (csv_key, short_label_for_tables, chart_axis_label_with_unit, provenance)
_METRIC_DEFS: list[tuple[str, str, str, str]] = [
    ("psnr_y", "PSNR-Y", "PSNR-Y, dB", "codec log"),
    ("ssim", "SSIM", "SSIM index", "ffmpeg filter"),
    ("xpsnr_y", "XPSNR-Y", "XPSNR-Y, dB", "ffmpeg filter"),
    ("vmaf", "VMAF", "VMAF score", "ffmpeg libvmaf"),
    ("msssim_luma", "MS-SSIM luma", "MS-SSIM luma index", "Wang et al. algorithm"),
    ("fsim_luma", "FSIM luma approx", "FSIM luma approximation", "local approximation"),
    ("haarpsi_luma", "HaarPSI luma", "HaarPSI luma index", "authors' Python/NumPy implementation"),
    ("psnr_hvs_m_luma", "PSNR-HVS-M luma", "PSNR-HVS-M luma, dB", "NumPy/SciPy port of authors' MATLAB implementation"),
    ("psnr_rgb", "PSNR-RGB", "PSNR-RGB, dB", "local implementation, externally cross-checked"),
    ("msssim_rgb", "MS-SSIM-RGB", "MS-SSIM-RGB index", "local implementation, protocol/RD cross-checked"),
]

METRICS: list[str] = [key for key, _, _, _ in _METRIC_DEFS]
"""Ordered metric keys as they appear in CSV columns and chart filenames."""

METRIC_LABELS: dict[str, str] = {key: short for key, short, _, _ in _METRIC_DEFS}
"""Short display names for table headers (e.g. ``"PSNR-Y"``)."""

METRIC_CHART_LABELS: dict[str, str] = {key: chart for key, _, chart, _ in _METRIC_DEFS}
"""Full display names with units for chart axes (e.g. ``"PSNR-Y, dB"``)."""

METRIC_PROVENANCE: dict[str, str] = {key: provenance for key, _, _, provenance in _METRIC_DEFS}
"""Implementation provenance for scientific reporting."""

METRIC_COLUMNS: list[tuple[str, str]] = [
    (f"{key}_delta_mean", short) for key, short, _, _ in _METRIC_DEFS
]
"""Per-image summary column keys paired with short labels."""

CHARTS: list[tuple[str, str]] = [
    (chart, f"rd_{key}.png")
    for key, _, chart, _ in _METRIC_DEFS
]
"""Chart display labels paired with generated PNG filenames."""
