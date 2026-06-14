from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path


def generate_baseline_reports(root: Path, docs_dir: Path) -> None:
    """Reads image_metrics.csv from dataset directories and generates a baseline average report."""
    # Mapping to rename columns as requested
    col_mapping = {
        "bpp": "bpp",
        "psnr_rgb": "PSNR-RGB",
        "psnr_y": "PSNR-Y",
        "psnr_u": "PSNR-U",
        "psnr_v": "PSNR-V",
        "ssim": "SSIM",
        "xpsnr_y": "XPSNR-Y",
        "vmaf": "VMAF",
        "msssim_luma": "MSSSIM-Luma",
        "fsim_luma": "FSIM-Luma",
        "haarpsi_luma": "HaarPSI-Luma",
        "psnr_hvs_m_luma": "PSNR-HVS-M",
        "msssim_rgb": "MSSSIM-RGB",
        "bitrate_kbps": "Bitrate (kbps)",
        "bitstream_bytes": "Bitstream (bytes)",
        "compression_ratio": "Compression Ratio",
    }

    for dataset_dir in root.glob("image_*"):
        metrics_file = dataset_dir / "image_metrics.csv"
        if not metrics_file.exists():
            continue

        dataset_name = dataset_dir.name

        with open(metrics_file, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            continue

        sums: dict[int, dict[str, float]] = collections.defaultdict(lambda: collections.defaultdict(float))
        counts: dict[int, int] = collections.defaultdict(int)

        # Numeric columns are all keys after 'mode'
        original_cols = list(rows[0].keys())
        mode_idx = original_cols.index("mode") if "mode" in original_cols else -1
        numeric_cols = original_cols[mode_idx + 1 :] if mode_idx != -1 else []

        for row in rows:
            if row.get("mode") == "baseline":
                qp = int(row["qp"])
                counts[qp] += 1
                for col in numeric_cols:
                    if col in row and row[col]:
                        try:
                            sums[qp][col] += float(row[col])
                        except ValueError:
                            pass

        if not counts:
            print(f"No baseline data found for {dataset_name}")
            continue

        out_dir = docs_dir / dataset_name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_csv = out_dir / "baseline.csv"

        fieldnames = ["QP"] + [col_mapping.get(col, col) for col in numeric_cols]

        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for qp in sorted(counts.keys()):
                out_row: dict[str, object] = {"QP": qp}
                n = counts[qp]
                for col in numeric_cols:
                    out_col = col_mapping.get(col, col)
                    out_row[out_col] = sums[qp][col] / n
                writer.writerow(out_row)

        print(f"Generated report for {dataset_name} at {out_csv}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dataset baseline reports from metrics CSVs.")
    parser.add_argument("--root", type=Path, default=Path("results/run_all"), help="Root directory with results.")
    parser.add_argument("--docs-dir", type=Path, default=Path("docs/image_benchmark"), help="Output docs directory.")
    args = parser.parse_args()

    generate_baseline_reports(args.root, args.docs_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
