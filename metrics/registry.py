"""Single source of truth for benchmark metric keys, labels, and chart paths.

Adding a new metric requires only one change: append a tuple to
``_METRIC_DEFS`` below.  The ``METRICS`` list, label dictionaries,
column definitions, and chart paths are all derived automatically.
"""
from __future__ import annotations

# (csv_key, short_label_for_tables, chart_axis_label_with_unit)
_METRIC_DEFS: list[tuple[str, str, str]] = [
    ("psnr_y", "PSNR-Y", "PSNR-Y, dB"),
    ("ssim", "SSIM", "SSIM index"),
    ("xpsnr_y", "XPSNR-Y", "XPSNR-Y, dB"),
    ("vmaf", "VMAF", "VMAF score"),
    ("msssim_luma", "MS-SSIM", "MS-SSIM luma index"),
    ("fsim_luma", "FSIM approx", "FSIM luma approximation"),
    ("haarpsi_luma", "HaarPSI approx", "HaarPSI luma approximation"),
    ("psnr_hvs_m_luma", "PSNR-HVS-M approx", "PSNR-HVS-M luma approximation, dB"),
    ("psnr_rgb", "PSNR-RGB", "PSNR-RGB, dB"),
    ("msssim_rgb", "MS-SSIM-RGB", "MS-SSIM RGB index"),
]

METRICS: list[str] = [key for key, _, _ in _METRIC_DEFS]
"""Ordered metric keys as they appear in CSV columns and chart filenames."""

METRIC_LABELS: dict[str, str] = {key: short for key, short, _ in _METRIC_DEFS}
"""Short display names for table headers (e.g. ``"PSNR-Y"``)."""

METRIC_CHART_LABELS: dict[str, str] = {key: chart for key, _, chart in _METRIC_DEFS}
"""Full display names with units for chart axes (e.g. ``"PSNR-Y, dB"``)."""

METRIC_COLUMNS: list[tuple[str, str]] = [
    (f"{key}_delta_mean", short) for key, short, _ in _METRIC_DEFS
]
"""Per-image summary column keys paired with short labels."""

CHARTS: list[tuple[str, str]] = [
    (chart, f"rd_{key}.svg")
    for key, _, chart in _METRIC_DEFS
]
"""Chart display labels paired with generated SVG filenames."""
