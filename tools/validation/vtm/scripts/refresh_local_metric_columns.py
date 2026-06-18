"""Refresh local Python metric columns in an existing image_metrics-style CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from metrics.image_quality import calculate_color_metrics, calculate_luma_metrics, msssim_luma, read_luma


LOCAL_METRIC_COLUMNS = (
    "msssim_luma",
    "fsim_luma",
    "haarpsi_luma",
    "psnr_hvs_m_luma",
    "psnr_rgb",
    "msssim_rgb",
)
CORE_METRIC_COLUMNS = ("msssim_luma", "psnr_rgb", "msssim_rgb")


def yuv_path(run_dir: Path, image: str, width: int, height: int) -> Path:
    return run_dir / "yuv" / f"{image}_{width}x{height}_1.yuv"


def recon_path(run_dir: Path, image: str, qp: int, mode: str) -> Path:
    return run_dir / "encoded" / image / f"QP{qp}" / mode / f"{image}_QP{qp}_{mode}_rec.yuv"


def refresh_csv(
    csv_path: Path,
    run_dir: Path,
    output_path: Path,
    chroma_format: str,
    reference_bit_depth: int,
    distorted_bit_depth: int,
    metric_set: str,
) -> None:
    with csv_path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    if not rows:
        raise RuntimeError(f"No rows found in {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames or []

    selected_columns = CORE_METRIC_COLUMNS if metric_set == "core" else LOCAL_METRIC_COLUMNS
    missing_columns = [column for column in selected_columns if column not in fieldnames]
    if missing_columns:
        raise RuntimeError(f"{csv_path} is missing metric columns: {missing_columns}")

    refreshed = []
    for row in rows:
        image = row["image"]
        width = int(row["width"])
        height = int(row["height"])
        qp = int(row["qp"])
        mode = row["mode"]
        original = yuv_path(run_dir, image, width, height)
        reconstruction = recon_path(run_dir, image, qp, mode)
        if metric_set == "all":
            luma_metrics = calculate_luma_metrics(
                original,
                reconstruction,
                width,
                height,
                reference_bit_depth=reference_bit_depth,
                distorted_bit_depth=distorted_bit_depth,
            )
        else:
            reference_luma = read_luma(original, width, height, reference_bit_depth)
            distorted_luma = read_luma(reconstruction, width, height, distorted_bit_depth)
            luma_metrics = {"msssim_luma": msssim_luma(reference_luma, distorted_luma, width, height)}
        color_metrics = calculate_color_metrics(
            original,
            reconstruction,
            width,
            height,
            reference_bit_depth=reference_bit_depth,
            distorted_bit_depth=distorted_bit_depth,
            chroma_format=chroma_format,
        )
        values = {**luma_metrics, **color_metrics}
        row.update({key: f"{values[key]:.15g}" for key in selected_columns})
        refreshed.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(refreshed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh local metric columns from stored YUV reconstructions.")
    parser.add_argument("--csv", type=Path, required=True, help="Input image_metrics-style CSV.")
    parser.add_argument("--run-dir", type=Path, required=True, help="Benchmark run directory containing yuv/ and encoded/.")
    parser.add_argument("--output", type=Path, default=None, help="Output CSV. Defaults to updating --csv in place.")
    parser.add_argument("--chroma-format", choices=("420", "444"), required=True)
    parser.add_argument("--reference-bit-depth", type=int, default=8)
    parser.add_argument("--distorted-bit-depth", type=int, default=10)
    parser.add_argument("--metric-set", choices=("core", "all"), default="core")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    refresh_csv(
        args.csv,
        args.run_dir,
        args.output or args.csv,
        args.chroma_format,
        args.reference_bit_depth,
        args.distorted_bit_depth,
        args.metric_set,
    )
    print(f"Refreshed local metric columns in {args.output or args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
