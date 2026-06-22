"""Run the local VTM Kodak benchmark and compare it with the pinned baseline."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def run_benchmark(args: argparse.Namespace) -> Path:
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "benchmarking" / "image_csf_benchmark.py"),
        "--root",
        str(args.run_dir),
        "--png-dir",
        str(args.kodak_dir),
        "--qps",
        ",".join(str(qp) for qp in args.qps),
        "--baseline-encoder",
        str(args.vtm_encoder),
        "--csf-encoder",
        str(args.vtm_encoder),
        "--decoder",
        str(args.vtm_decoder),
        "--codec",
        "vtm_validation",
        "--conversion",
        "opencv_444",
    ]

    print("Running VTM Benchmark...", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return args.run_dir / "image_metrics.csv"


def compare_results(csv_file: Path, baseline_json: Path, qps: list[int]) -> None:
    with baseline_json.open("r", encoding="utf-8") as stream:
        ref_data = json.load(stream)

    ref_bpp = ref_data["bpp"]
    ref_psnr = ref_data["psnr"]
    aggregated: defaultdict[int, dict[str, float]] = defaultdict(
        lambda: {"bpp": 0.0, "psnr_rgb": 0.0, "psnr_y": 0.0, "count": 0.0}
    )

    with csv_file.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            qp = int(row["qp"])
            aggregated[qp]["bpp"] += float(row["bpp"])
            aggregated[qp]["psnr_rgb"] += float(row["psnr_rgb"])
            aggregated[qp]["psnr_y"] += float(row["psnr_y"])
            aggregated[qp]["count"] += 1.0

    results = {
        qp: {
            "bpp": data["bpp"] / data["count"],
            "psnr_rgb": data["psnr_rgb"] / data["count"],
            "psnr_y": data["psnr_y"] / data["count"],
        }
        for qp, data in aggregated.items()
        if data["count"] > 0
    }

    print("\n--- VTM 18.0 Kodak Validation ---")
    print(f"{'QP':<5} | {'Ref BPP':<10} | {'Rep BPP':<10} | {'Ref PSNR':<10} | {'Rep PSNR-RGB':<12} | {'Rep PSNR-Y':<12}")
    print("-" * 75)

    for qp in qps:
        if qp not in results:
            print(f"{qp:<5} | MISSING IN RESULTS")
            continue

        ref_index = qp - 15
        print(
            f"{qp:<5} | "
            f"{ref_bpp[ref_index]:<10.5f} | "
            f"{results[qp]['bpp']:<10.5f} | "
            f"{ref_psnr[ref_index]:<10.5f} | "
            f"{results[qp]['psnr_rgb']:<12.5f} | "
            f"{results[qp]['psnr_y']:<12.5f}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local VTM Kodak metrics against the pinned baseline JSON.")
    parser.add_argument("--run-dir", type=Path, default=ROOT / "results" / "image_kodak_vtm")
    parser.add_argument("--kodak-dir", type=Path, default=ROOT / "data" / "datasets" / "images" / "kodak" / "png")
    parser.add_argument("--baseline-json", type=Path, default=ROOT / "data" / "baselines" / "kodak_vtm.json")
    parser.add_argument("--vtm-encoder", type=Path, default=ROOT / "binaries" / "vtm" / "vtm18" / "baseline" / "EncoderApp.exe")
    parser.add_argument("--vtm-decoder", type=Path, default=ROOT / "binaries" / "vtm" / "vtm18" / "baseline" / "DecoderApp.exe")
    parser.add_argument("--qps", default="22,27,32,37", help="Comma-separated QP list.")
    args = parser.parse_args()
    args.qps = [int(item) for item in args.qps.split(",") if item.strip()]
    return args


def main() -> int:
    args = parse_args()
    csv_out = run_benchmark(args)
    compare_results(csv_out, args.baseline_json, args.qps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
