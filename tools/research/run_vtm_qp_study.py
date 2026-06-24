from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.reporting.report_vtm_qp_study import main as render_report
from tools.visualization.parse_vvenc_qp_trace import parse_trace, write_csv as write_partition_csv
from tools.visualization.partition_overlay import render_partition_overlay
from vvenc_csf.benchmark import ImageBenchmarkConfig, ImageBenchmarkRunner
from vvenc_csf.core import CommandRunner, ffprobe_size, parse_qps, platform_executable
from vvenc_csf.encoding import ImageConverter, VTM_ENCODER_CONFIG


DEFAULT_BASELINE_ENCODER = platform_executable(Path("binaries/vtm/vtm23/baseline/EncoderApp"))
DEFAULT_CSF_ENCODER = platform_executable(Path("binaries/vtm/vtm23/csf/EncoderApp"))
DEFAULT_DECODER = platform_executable(Path("binaries/vtm/vtm23/baseline/DecoderApp"))
DEFAULT_BASELINE_TRACE_ENCODER = platform_executable(Path("binaries/vtm/vtm23/baseline_trace/EncoderApp"))
DEFAULT_CSF_TRACE_ENCODER = platform_executable(Path("binaries/vtm/vtm23/csf_trace/EncoderApp"))


def convert_bmp_dir_to_png(source: Path, output: Path) -> None:
    """Create a normalized PNG dataset from BMP sources when PNG files are absent."""

    output.mkdir(parents=True, exist_ok=True)
    for bmp in sorted(source.glob("*.bmp")):
        stem = "peppers" if bmp.stem.lower() == "pepper" else bmp.stem
        target = output / f"{stem}.png"
        if target.exists():
            continue
        image = cv2.imread(str(bmp), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise RuntimeError(f"Could not read BMP image: {bmp}")
        if not cv2.imwrite(str(target), image, [cv2.IMWRITE_PNG_COMPRESSION, 3]):
            raise RuntimeError(f"Could not write PNG image: {target}")


def ensure_dataset(label: str, png_dir: Path, bmp_dir: Path | None = None) -> Path:
    if list(png_dir.glob("*.png")):
        return png_dir
    if bmp_dir and bmp_dir.exists():
        convert_bmp_dir_to_png(bmp_dir, png_dir)
    if not list(png_dir.glob("*.png")):
        raise RuntimeError(f"No PNG images found for {label}: {png_dir}")
    return png_dir


def run_benchmark(args: argparse.Namespace, dataset: str, png_dir: Path) -> Path:
    root = args.results / dataset
    csv_path = ImageBenchmarkRunner(
        ImageBenchmarkConfig(
            root=root,
            png_dir=png_dir,
            baseline_encoder=args.baseline_encoder,
            csf_encoder=args.csf_encoder,
            decoder=args.decoder,
            qps=parse_qps(args.qps),
            codec="vtm",
            preset=args.preset,
            conversion=args.conversion,
        )
    ).run()
    return csv_path


def build_partition_overlays(args: argparse.Namespace, dataset: str, png_dir: Path) -> None:
    runner = CommandRunner()
    converter = ImageConverter(runner)
    qps = parse_qps(args.qps)
    summary_rows: list[dict[str, object]] = []

    for image in sorted(png_dir.glob("*.png")):
        width, height = ffprobe_size(image, runner)
        yuv = args.results / "partition_work" / dataset / "yuv" / f"{image.stem}_{width}x{height}_1.yuv"
        if args.conversion == "opencv_444":
            converter.to_yuv444p_opencv(image, yuv)
        else:
            converter.to_yuv444p(image, yuv)

        for qp in qps:
            for mode, encoder, extra_args in (
                ("baseline", args.baseline_trace_encoder, []),
                ("csf", args.csf_trace_encoder, ["--CSFScalingList=1"]),
            ):
                run_dir = args.results / "partition_work" / dataset / image.stem / f"QP{qp}" / mode
                bitstream = run_dir / f"{image.stem}_QP{qp}_{mode}.vvc"
                recon = run_dir / f"{image.stem}_QP{qp}_{mode}_rec.yuv"
                trace = run_dir / f"{image.stem}_QP{qp}_{mode}_d_qp.trace"
                log = run_dir / f"{image.stem}_QP{qp}_{mode}.log"
                run_dir.mkdir(parents=True, exist_ok=True)
                runner.run(
                    [
                        str(encoder),
                        "-c",
                        str(VTM_ENCODER_CONFIG),
                        "-i",
                        str(yuv),
                        "-wdt",
                        str(width),
                        "-hgt",
                        str(height),
                        "-fr",
                        "1",
                        "-f",
                        "1",
                        "-q",
                        str(qp),
                        "-b",
                        str(bitstream),
                        "-o",
                        str(recon),
                        "--InputChromaFormat=444",
                        "--InputBitDepth=8",
                        f"--TraceFile={trace}",
                        "--TraceRule=D_QP:poc==0",
                        *extra_args,
                    ],
                    log,
                )
                rows = parse_trace(trace, frame=0, mode=mode)
                csv_path = run_dir / f"{image.stem}_QP{qp}_{mode}.csv"
                png_path = args.output / "partition_overlays" / dataset / f"QP{qp}" / f"{image.stem}_{mode}.png"
                write_partition_csv(rows, csv_path)
                render_partition_overlay([{key: str(value) for key, value in row.items()} for row in rows], width, height, png_path, image)
                summary_rows.append(summarize(rows, dataset, image.stem, mode, qp, width, height))

    write_partition_summary(args.output / "partition_overlays" / dataset / "summary.csv", summary_rows)


def summarize(rows: list[dict[str, int | str]], dataset: str, image: str, mode: str, qp: int, width: int, height: int) -> dict[str, object]:
    areas = [int(row["width"]) * int(row["height"]) for row in rows]
    sizes: dict[str, int] = {}
    for row in rows:
        key = f'{row["width"]}x{row["height"]}'
        sizes[key] = sizes.get(key, 0) + 1
    return {
        "dataset": dataset,
        "image": image,
        "mode": mode,
        "qp": qp,
        "width": width,
        "height": height,
        "cu_count": len(rows),
        "min_area": min(areas),
        "max_area": max(areas),
        "avg_area": sum(areas) / len(areas),
        "dominant_sizes": "; ".join(f"{key}:{value}" for key, value in sorted(sizes.items(), key=lambda item: (-item[1], item[0]))[:6]),
    }


def write_partition_summary(output: Path, rows: list[dict[str, object]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the focused VTM QP study on standard grayscale and standard color images.")
    parser.add_argument("--results", type=Path, default=Path("results/vtm_qp_study"))
    parser.add_argument("--output", type=Path, default=Path("docs/vtm_qp_study"))
    parser.add_argument("--standard-grayscale-dir", type=Path, default=Path("data/datasets/images/standard_grayscale/png"))
    parser.add_argument("--standard-color-dir", type=Path, default=Path("data/datasets/images/standard_color/png"))
    parser.add_argument("--standard-color-bmp-dir", type=Path, default=Path("data/datasets/images/standart_color/bmp"))
    parser.add_argument("--qps", default="22,27,32,37")
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--conversion", choices=("opencv_444", "ffmpeg_444"), default="opencv_444")
    parser.add_argument("--baseline-encoder", type=Path, default=DEFAULT_BASELINE_ENCODER)
    parser.add_argument("--csf-encoder", type=Path, default=DEFAULT_CSF_ENCODER)
    parser.add_argument("--decoder", type=Path, default=DEFAULT_DECODER)
    parser.add_argument("--baseline-trace-encoder", type=Path, default=DEFAULT_BASELINE_TRACE_ENCODER)
    parser.add_argument("--csf-trace-encoder", type=Path, default=DEFAULT_CSF_TRACE_ENCODER)
    parser.add_argument("--skip-benchmark", action="store_true")
    parser.add_argument("--skip-partitions", action="store_true")
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.clean:
        for path in (args.results, args.output):
            if path.exists():
                shutil.rmtree(path)
    args.results.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)

    datasets = [
        ("standard_grayscale", ensure_dataset("standard_grayscale", args.standard_grayscale_dir)),
        ("standard_color", ensure_dataset("standard_color", args.standard_color_dir, args.standard_color_bmp_dir)),
    ]
    for dataset, png_dir in datasets:
        if not args.skip_benchmark:
            csv_path = run_benchmark(args, dataset, png_dir)
            print(f"Wrote {csv_path}")
        if not args.skip_partitions:
            build_partition_overlays(args, dataset, png_dir)

    report_args = [
        "--results",
        str(args.results),
        "--output",
        str(args.output),
    ]
    old_argv = sys.argv
    try:
        sys.argv = ["report_vtm_qp_study.py", *report_args]
        render_report()
    finally:
        sys.argv = old_argv
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
