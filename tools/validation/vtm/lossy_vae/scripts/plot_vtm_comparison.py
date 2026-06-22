"""Render comparison plots for the VTM Kodak validation data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[5]


SERIES_STYLES = {
    "Duan et al. VTM 18.0 Anchor": {"color": "#111111", "marker": "o", "linestyle": "-", "zorder": 9},
    "Local VTM 18.0 (FFmpeg 4:4:4)": {"color": "#1f77b4", "marker": "v", "linestyle": ":", "zorder": 5},
    "Local VTM 18.0 (OpenCV 4:4:4)": {"color": "#d62728", "marker": "s", "linestyle": "--", "linewidth": 3, "zorder": 10},
    "Local VTM 18.0 (OpenCV 4:4:4) [Matches Duan et al. Anchor]": {
        "color": "#d62728",
        "marker": "s",
        "linestyle": "--",
        "linewidth": 3,
        "zorder": 10,
    },
    "Local VTM 23.0 Baseline (FFmpeg 4:4:4)": {"color": "#17becf", "marker": "^", "linestyle": "-", "zorder": 6},
    "Local VTM 23.0 CSF (FFmpeg 4:4:4)": {"color": "#8c564b", "marker": "P", "linestyle": (0, (5, 2)), "zorder": 7},
    "Local VTM 23.0 Baseline (OpenCV 4:4:4)": {"color": "#ff7f0e", "marker": "D", "linestyle": "-", "zorder": 6},
    "Local VTM 23.0 CSF (OpenCV 4:4:4)": {"color": "#9467bd", "marker": "X", "linestyle": "-.", "zorder": 7},
    "Local VVenC (FFmpeg 4:2:0)": {"color": "#2ca02c", "marker": "*", "linestyle": (0, (1, 1)), "zorder": 4},
    "Local VVenC (OpenCV 4:2:0)": {"color": "#7f7f7f", "marker": "h", "linestyle": (0, (3, 1, 1, 1)), "zorder": 4},
}


def plot_bpp_psnr(title: str, series: list[dict], out_path: Path) -> None:
    plt.figure(figsize=(10, 6))

    for item in series:
        name = item["name"]
        data = item["data"]
        linestyle = item.get("linestyle", "-")
        if not data:
            continue
        style = SERIES_STYLES.get(name, {})
        sorted_data = sorted(data, key=lambda row: float(row["bpp"]))
        bpps = [row["bpp"] for row in sorted_data]
        psnrs = [row["psnr"] for row in sorted_data]
        plt.plot(
            bpps,
            psnrs,
            color=style.get("color"),
            marker=style.get("marker", "o"),
            linewidth=style.get("linewidth", 2),
            markersize=style.get("markersize", 8),
            linestyle=style.get("linestyle", linestyle),
            label=name,
            zorder=style.get("zorder", 3),
        )

    plt.title(title, fontsize=14)
    plt.xlabel("BPP (Bits Per Pixel)", fontsize=12)
    plt.ylabel("PSNR-RGB (dB)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.legend(fontsize=9)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def read_reference_points(path: Path, qps: list[int]) -> list[dict[str, float | int]]:
    with path.open("r", encoding="utf-8") as stream:
        ref_data = json.load(stream)
    return [
        {"qp": qp, "bpp": ref_data["bpp"][qp - 15], "psnr": ref_data["psnr"][qp - 15]}
        for qp in qps
    ]


def read_csv_points(path: Path, qps: list[int], mode: str | None = "baseline") -> list[dict[str, float | int]]:
    if not path.exists():
        return []

    frame = pd.read_csv(path)
    if mode is not None and "mode" in frame.columns:
        frame = frame[frame["mode"] == mode]

    data = []
    for qp in qps:
        qp_rows = frame[frame["qp"] == qp]
        if not qp_rows.empty:
            data.append(
                {
                    "qp": qp,
                    "bpp": float(qp_rows["bpp"].mean()),
                    "psnr": float(qp_rows["psnr_rgb"].mean()),
                }
            )
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot VTM/VVenC Kodak validation comparisons.")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "docs" / "vtm_validation")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "vtm_validation" / "lossy-vae")
    parser.add_argument("--baseline-json", type=Path, default=ROOT / "data" / "baselines" / "kodak_vtm.json")
    parser.add_argument("--qps", default="22,27,32,37", help="Comma-separated QP list.")
    args = parser.parse_args()
    args.qps = [int(item) for item in args.qps.split(",") if item.strip()]
    return args


def main() -> int:
    args = parse_args()
    qps = args.qps
    results_dir = args.results_dir
    output_dir = args.output_dir

    reference = read_reference_points(args.baseline_json, qps)
    vvenc_baseline = read_csv_points(results_dir / "vvenc_baseline.csv", qps)
    vtm_ffmpeg = read_csv_points(results_dir / "vtm_ffmpeg.csv", qps)
    vtm_opencv = read_csv_points(results_dir / "vtm_opencv.csv", qps)
    vtm23_ffmpeg_baseline = read_csv_points(results_dir / "vtm23_ffmpeg.csv", qps, mode="baseline")
    vtm23_ffmpeg_csf = read_csv_points(results_dir / "vtm23_ffmpeg.csv", qps, mode="csf")
    vtm23_opencv_baseline = read_csv_points(results_dir / "vtm23_opencv.csv", qps, mode="baseline")
    vtm23_opencv_csf = read_csv_points(results_dir / "vtm23_opencv.csv", qps, mode="csf")
    vvenc_opencv = read_csv_points(results_dir / "vvenc_opencv.csv", qps, mode=None)

    plot_bpp_psnr(
        "Local VTM 18.0 (OpenCV 4:4:4) vs Duan et al. VTM 18.0 Anchor",
        [
            {"name": "Duan et al. VTM 18.0 Anchor", "data": reference, "linestyle": "-"},
            {"name": "Local VTM 18.0 (OpenCV 4:4:4)", "data": vtm_opencv, "linestyle": "--"},
            {"name": "Local VTM 23.0 Baseline (OpenCV 4:4:4)", "data": vtm23_opencv_baseline, "linestyle": "-"},
            {"name": "Local VTM 23.0 CSF (OpenCV 4:4:4)", "data": vtm23_opencv_csf, "linestyle": "-."},
            {"name": "Local VVenC (FFmpeg 4:2:0)", "data": vvenc_baseline, "linestyle": ":"},
            {"name": "Local VVenC (OpenCV 4:2:0)", "data": vvenc_opencv, "linestyle": "-."},
        ],
        output_dir / "rd_psnr_duan_anchor_replication.png",
    )

    plot_bpp_psnr(
        "Rate-Distortion Comparison: Canonical (FFmpeg) vs Full-Range Penalty (OpenCV)",
        [
            {"name": "Local VTM 18.0 (FFmpeg 4:4:4)", "data": vtm_ffmpeg, "linestyle": ":"},
            {"name": "Local VTM 18.0 (OpenCV 4:4:4) [Matches Duan et al. Anchor]", "data": vtm_opencv, "linestyle": "--"},
            {"name": "Local VTM 23.0 Baseline (FFmpeg 4:4:4)", "data": vtm23_ffmpeg_baseline, "linestyle": "-"},
            {"name": "Local VTM 23.0 CSF (FFmpeg 4:4:4)", "data": vtm23_ffmpeg_csf, "linestyle": "-."},
            {"name": "Local VTM 23.0 Baseline (OpenCV 4:4:4)", "data": vtm23_opencv_baseline, "linestyle": "-"},
            {"name": "Local VTM 23.0 CSF (OpenCV 4:4:4)", "data": vtm23_opencv_csf, "linestyle": "-."},
            {"name": "Local VVenC (FFmpeg 4:2:0)", "data": vvenc_baseline, "linestyle": "-"},
            {"name": "Local VVenC (OpenCV 4:2:0)", "data": vvenc_opencv, "linestyle": "-."},
        ],
        output_dir / "rd_psnr_ffmpeg_vs_opencv_penalty.png",
    )

    print(f"Plots generated successfully in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
