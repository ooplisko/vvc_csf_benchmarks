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


def plot_bpp_psnr(title: str, results: dict[str, list[dict[str, float | int]]], out_path: Path) -> None:
    plt.figure(figsize=(10, 6))

    for name, data in results.items():
        if not data:
            continue
        sorted_data = sorted(data, key=lambda row: float(row["bpp"]))
        bpps = [row["bpp"] for row in sorted_data]
        psnrs = [row["psnr"] for row in sorted_data]
        plt.plot(bpps, psnrs, marker="o", linewidth=2, markersize=8, label=name)

    plt.title(title, fontsize=14)
    plt.xlabel("BPP (Bits Per Pixel)", fontsize=12)
    plt.ylabel("PSNR-RGB (dB)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.legend(fontsize=11)
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


def read_csv_points(path: Path, qps: list[int], require_baseline_mode: bool = True) -> list[dict[str, float | int]]:
    if not path.exists():
        return []

    frame = pd.read_csv(path)
    if require_baseline_mode and "mode" in frame.columns:
        frame = frame[frame["mode"] == "baseline"]

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
    vvenc_opencv = read_csv_points(results_dir / "vvenc_opencv.csv", qps, require_baseline_mode=False)

    plot_bpp_psnr(
        "VTM 18.0 Replication (OpenCV 4:4:4) vs VVenC (4:2:0)",
        {
            "VTM 18.0 (Duan et al. Repo)": reference,
            "Replicated VTM (OpenCV 4:4:4)": vtm_opencv,
            "Replicated VVenC (OpenCV 4:2:0)": vvenc_opencv,
        },
        output_dir / "plot_replication.png",
    )

    plot_bpp_psnr(
        "Canonical (FFmpeg) vs Full-Range Penalty (OpenCV)",
        {
            "VTM Canonical (FFmpeg 4:4:4)": vtm_ffmpeg,
            "VTM OpenCV 4:4:4 (Duan et al.)": vtm_opencv,
            "VVenC Canonical (FFmpeg 4:2:0)": vvenc_baseline,
            "VVenC OpenCV 4:2:0": vvenc_opencv,
        },
        output_dir / "plot_canonical.png",
    )

    print(f"Plots generated successfully in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
