"""Run Kodak benchmarks for clean and CSF-modified VTM 23.0 binaries."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]

sys.path.insert(0, str(ROOT))

from vvenc_csf.core import platform_executable  # noqa: E402


@dataclass(frozen=True)
class ConversionRun:
    """One VTM 23.0 Kodak benchmark output target."""

    name: str
    conversion: str
    run_dir: Path
    output_csv: Path


def selected_runs(args: argparse.Namespace) -> list[ConversionRun]:
    """Return the conversion runs requested by the CLI."""

    conversions = ("ffmpeg_444", "opencv_444") if args.conversion == "both" else (args.conversion,)
    suffixes = {"ffmpeg_444": "ffmpeg", "opencv_444": "opencv"}
    return [
        ConversionRun(
            name=suffixes[conversion],
            conversion=conversion,
            run_dir=args.root / f"vtm23_{suffixes[conversion]}",
            output_csv=args.output_dir / f"vtm23_{suffixes[conversion]}.csv",
        )
        for conversion in conversions
    ]


def benchmark_command(args: argparse.Namespace, run: ConversionRun) -> list[str]:
    """Build the image benchmark command for one VTM 23.0 conversion run."""

    cmd = [
        sys.executable,
        "tools/benchmarking/image_csf_benchmark.py",
        "--root",
        str(run.run_dir),
        "--codec",
        "vtm",
        "--baseline-encoder",
        str(args.baseline_encoder),
        "--csf-encoder",
        str(args.csf_encoder),
        "--decoder",
        str(args.decoder),
        "--png-dir",
        str(args.png_dir),
        "--qps",
        args.qps,
        "--conversion",
        run.conversion,
    ]
    if args.download_kodak:
        cmd.append("--download-kodak")
    return cmd


def run_benchmark(args: argparse.Namespace, run: ConversionRun) -> None:
    """Execute one benchmark run and publish its CSV into docs/vtm_validation."""

    subprocess.run(benchmark_command(args, run), cwd=ROOT, check=True)
    source_csv = run.run_dir / "image_metrics.csv"
    if not source_csv.exists():
        raise FileNotFoundError(f"Expected benchmark CSV was not produced: {source_csv}")
    run.output_csv.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_csv, run.output_csv)
    print(f"Wrote {run.output_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Kodak VTM 23.0 baseline/CSF validation benchmarks.")
    parser.add_argument("--conversion", choices=("ffmpeg_444", "opencv_444", "both"), default="both")
    parser.add_argument("--qps", default="22,27,32,37", help="Comma-separated QP list.")
    parser.add_argument("--root", type=Path, default=ROOT / "results" / "vtm_validation")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "vtm_validation")
    parser.add_argument("--png-dir", type=Path, default=ROOT / "data" / "datasets" / "images" / "kodak" / "png")
    parser.add_argument("--download-kodak", action="store_true", help="Download Kodak images if --png-dir is empty/missing.")
    parser.add_argument(
        "--baseline-encoder",
        type=Path,
        default=platform_executable(ROOT / "binaries" / "vtm" / "vtm23" / "baseline" / "EncoderApp"),
    )
    parser.add_argument(
        "--csf-encoder",
        type=Path,
        default=platform_executable(ROOT / "binaries" / "vtm" / "vtm23" / "csf" / "EncoderApp"),
    )
    parser.add_argument(
        "--decoder",
        type=Path,
        default=platform_executable(ROOT / "binaries" / "vtm" / "vtm23" / "baseline" / "DecoderApp"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for run in selected_runs(args):
        run_benchmark(args, run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
