from __future__ import annotations

import csv
from pathlib import Path

from tools.report_image_benchmark import ImageBenchmarkReportBuilder
from vvenc_csf.neutral import Neutral16ControlReport


METRIC_KEYS = [
    "psnr_y",
    "ssim",
    "xpsnr_y",
    "vmaf",
    "msssim_luma",
    "fsim_luma",
    "haarpsi_luma",
    "psnr_hvs_m_luma",
]


def _metric_row(image: str, qp: int, mode: str, bpp: float, value: float) -> dict[str, object]:
    row: dict[str, object] = {
        "image": image,
        "width": 16,
        "height": 16,
        "qp": qp,
        "mode": mode,
        "bitstream_bytes": 64,
        "compression_ratio": 6.0,
        "bpp": bpp,
        "bitrate_kbps": 1.0,
        "psnr_u": 0.0,
        "psnr_v": 0.0,
    }
    for key in METRIC_KEYS:
        row[key] = value
    return row


def test_image_report_builder_writes_summaries_and_charts(tmp_path: Path) -> None:
    metrics_csv = tmp_path / "image_metrics.csv"
    rows = [
        _metric_row("img", 22, "baseline", 1.0, 40.0),
        _metric_row("img", 22, "csf", 1.1, 39.5),
        _metric_row("img", 32, "baseline", 0.5, 35.0),
        _metric_row("img", 32, "csf", 0.55, 34.5),
    ]
    with metrics_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    output = tmp_path / "report"
    ImageBenchmarkReportBuilder(metrics_csv, output).build()

    assert (output / "same_qp_summary.csv").exists()
    assert (output / "per_image_summary.csv").exists()
    assert (output / "charts" / "rd_psnr_y.svg").exists()
    assert (output / "qp_charts" / "img" / "qp_psnr_y.svg").exists()


def test_neutral_control_report_links_verification_and_csv(tmp_path: Path) -> None:
    report = tmp_path / "neutral.md"
    csv_path = tmp_path / "neutral.csv"
    rows = [
        {
            "image": "baboon",
            "qp": 32,
            "baseline_bitstream_bytes": 123,
            "bitstream_identical": True,
            "reconstruction_identical": True,
        }
    ]

    Neutral16ControlReport().write(report, csv_path, rows)
    text = report.read_text(encoding="utf-8")

    assert "neutral_16_verification.md" in text
    assert "LOG2_SCALING_LIST_NEUTRAL_VALUE = 4" in text
    assert "neutral_16_control.csv" in text
