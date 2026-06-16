from __future__ import annotations

import argparse
import csv
import logging
import shutil
import sys
from pathlib import Path

from vvenc_csf.config import load_benchmark_config
from vvenc_csf.core import CommandRunner, ffprobe_size, files_equal, platform_executable, repo_path, resolve_project_path


logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
STANDARD_DIR = Path("data/datasets/images/standard_grayscale/png")
SYNTHETIC_DIR = Path("data/datasets/images/synthetic/png")
KODAK_DIR = Path("data/datasets/images/kodak/png")
QPS = "22,27,32,37"
RUNNER = CommandRunner(ROOT)
DEFAULT_BASELINE_ENCODER = platform_executable(Path("binaries/vvenc_default"))
DEFAULT_CSF_ENCODER = platform_executable(Path("binaries/vvenc_csf"))
DEFAULT_DECODER = platform_executable(Path("binaries/vvdecapp"))
DEFAULT_BASELINE_TRACE_ENCODER = platform_executable(Path("binaries/vvenc_default_trace"))
DEFAULT_CSF_TRACE_ENCODER = platform_executable(Path("binaries/vvenc_csf_trace"))


def rel(path: Path) -> str:
    return repo_path(path)


def run(cmd: list[str], label: str, log_file: Path) -> None:
    try:
        RUNNER.run(cmd, log_file)
    except RuntimeError:
        logger.error("FAIL %s (log: %s)", label, rel(log_file))
        raise
    logger.info("PASS %s (log: %s)", label, rel(log_file))


def ensure_yuv(image: Path, output: Path, width: int, height: int, log_file: Path) -> None:
    if output.exists():
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", str(image), "-pix_fmt", "yuv420p", "-frames:v", "1", str(output)], "convert smoke image to YUV", log_file)


def encode(
    encoder: Path,
    yuv: Path,
    width: int,
    height: int,
    qp: int,
    bitstream: Path,
    recon: Path,
    extra_args: list[str],
    label: str,
    log_file: Path,
) -> None:
    bitstream.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(encoder),
        "--InputFile",
        str(yuv),
        "--SourceWidth",
        str(width),
        "--SourceHeight",
        str(height),
        "--FrameRate",
        "1",
        "--FramesToBeEncoded",
        "1",
        "--QP",
        str(qp),
        "--preset",
        "medium",
        "--BitstreamFile",
        str(bitstream),
        "--ReconFile",
        str(recon),
        *extra_args,
    ]
    run(cmd, label, log_file)


def decode(decoder: Path, bitstream: Path, output: Path, label: str, log_file: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run([str(decoder), "-b", str(bitstream), "-o", str(output)], label, log_file)


def print_check(name: str, ok: bool) -> None:
    if ok:
        logger.info("PASS %s", name)
    else:
        logger.error("FAIL %s", name)
        raise RuntimeError(name)


def smoke_check(args: argparse.Namespace) -> None:
    logger.info("\n== Smoke encode/decode ==")
    image = sorted(args.smoke_dir.glob("*.png"))[0]
    width, height = ffprobe_size(image)
    root = args.root / "smoke"
    logs = args.root / "logs"
    yuv = root / "yuv" / f"{image.stem}_{width}x{height}_1.yuv"
    ensure_yuv(image, yuv, width, height, logs / "smoke_convert_yuv.log")

    for mode, encoder, extra_args in (
        ("baseline", args.baseline_encoder, []),
        ("csf", args.csf_encoder, ["--CSFScalingList", "1"]),
    ):
        bitstream = root / mode / f"{image.stem}_{mode}.vvc"
        recon = root / mode / f"{image.stem}_{mode}_rec.yuv"
        decoded = root / mode / f"{image.stem}_{mode}_dec.yuv"
        encode(encoder, yuv, width, height, args.smoke_qp, bitstream, recon, extra_args, f"smoke {mode} encode", logs / f"smoke_{mode}_encode.log")
        decode(args.decoder, bitstream, decoded, f"smoke {mode} decode", logs / f"smoke_{mode}_decode.log")
        print_check(f"{mode} bitstream is non-empty", bitstream.exists() and bitstream.stat().st_size > 0)
        print_check(f"{mode} reconstruction equals decoded output", files_equal(recon, decoded))


def neutral_check(args: argparse.Namespace) -> None:
    logger.info("\n== Neutral 16 checks ==")
    logs = args.root / "logs"
    run(
        [
            sys.executable,
            "tools/data_prep/verify_neutral_scaling.py",
            "--vvenc-root",
            str(args.vvenc_root),
            "--output",
            "docs/matrices/neutral_16_verification.md",
        ],
        "neutral 16 source verification",
        logs / "neutral_16_verification.log",
    )
    run(
        [
            sys.executable,
            "tools/data_prep/neutral_16_control.py",
            "--root",
            str(args.root / "neutral_16_control"),
            "--png-dir",
            str(args.smoke_dir),
            "--qps",
            args.qps,
            "--baseline-encoder",
            str(args.baseline_encoder),
            "--csf-encoder",
            str(args.csf_encoder),
        ],
        "neutral 16 CSF-off control",
        logs / "neutral_16_control.log",
    )


def benchmark(args: argparse.Namespace, name: str, png_dir: Path, extra: list[str] | None = None) -> Path:
    run_dir = args.root / f"image_{name}"
    cmd = [
        sys.executable,
        "tools/benchmarking/image_csf_benchmark.py",
        "--root",
        str(run_dir),
        "--png-dir",
        str(png_dir),
        "--qps",
        args.qps,
        "--baseline-encoder",
        str(args.baseline_encoder),
        "--csf-encoder",
        str(args.csf_encoder),
        "--decoder",
        str(args.decoder),
    ]
    if extra:
        cmd.extend(extra)
    run(cmd, f"{name} image benchmark", args.root / "logs" / f"benchmark_{name}.log")
    return run_dir / "image_metrics.csv"


def write_image_report(name: str, metrics_csv: Path, args: argparse.Namespace) -> None:
    cmd = [
        sys.executable,
        "tools/reporting/report_image_benchmark.py",
        str(metrics_csv),
        "--output",
        f"docs/image_benchmark/{name}",
    ]
    if args.write_xlsx:
        cmd.append("--xlsx")
    run(
        cmd,
        f"{name} CSV summaries and RD charts",
        args.root / "logs" / f"report_{name}.log",
    )


def regenerate_reports(metric_csvs: list[Path], args: argparse.Namespace) -> None:
    run(
        [
            sys.executable,
            "tools/reporting/merge_image_metrics.py",
            *[str(path) for path in metric_csvs],
            "--output",
            "docs/image_benchmark/combined_image_metrics.csv",
        ],
        "merge image metrics",
        args.root / "logs" / "merge_image_metrics.log",
    )
    cmd = [sys.executable, "tools/reporting/report_image_benchmark.py", "docs/image_benchmark/combined_image_metrics.csv", "--output", "docs/image_benchmark/combined"]
    if args.write_xlsx:
        cmd.append("--xlsx")
    run(cmd, "combined CSV summaries and RD charts", args.root / "logs" / "report_combined.log")
    run([sys.executable, "tools/reporting/render_readme.py"], "render README and benchmark report", args.root / "logs" / "render_readme.log")


def generate_partition_maps(args: argparse.Namespace) -> None:
    run(
        [
            sys.executable,
            "tools/visualization/build_partition_evidence.py",
            "--qp",
            str(args.partition_qp),
            "--standard-grayscale-dir",
            str(args.smoke_dir),
            "--synthetic-dir",
            str(args.synthetic_dir),
            "--kodak-dir",
            str(args.kodak_dir),
            "--baseline-trace-encoder",
            str(args.baseline_trace_encoder),
            "--csf-trace-encoder",
            str(args.csf_trace_encoder),
        ],
        "partition-map evidence",
        args.root / "logs" / "partition_maps.log",
    )
    run([sys.executable, "tools/reporting/render_readme.py"], "render README and benchmark report", args.root / "logs" / "render_readme_after_partitions.log")


def print_summary(csv_path: Path) -> None:
    if not csv_path.exists():
        return
    logger.info("\n== Same-QP summary ==")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            logger.info("%s: mean=%+.6f, min=%+.6f, max=%+.6f", row['metric'], float(row['mean']), float(row['min']), float(row['max']))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the image-only VVenC CSF checks and report generators.")
    parser.add_argument("suite", nargs="?", default="quick", choices=["quick", "full"], help="quick runs console sanity checks. full runs all image benchmarks and regenerates docs.")
    parser.add_argument("--config", type=Path, default=Path("configs/image_benchmark.ini"))
    parser.add_argument("--root", type=Path, default=Path("results/run_all"))
    parser.add_argument("--qps", default=QPS)
    parser.add_argument("--smoke-dir", type=Path, default=STANDARD_DIR)
    parser.add_argument("--synthetic-dir", type=Path, default=SYNTHETIC_DIR)
    parser.add_argument("--kodak-dir", type=Path, default=KODAK_DIR)
    parser.add_argument("--smoke-qp", type=int, default=32)
    parser.add_argument("--partition-qp", type=int, default=32)
    parser.add_argument("--vvenc-root", type=Path, default=ROOT.parent / "vvenc")
    parser.add_argument("--baseline-encoder", type=Path, default=DEFAULT_BASELINE_ENCODER)
    parser.add_argument("--csf-encoder", type=Path, default=DEFAULT_CSF_ENCODER)
    parser.add_argument("--decoder", type=Path, default=DEFAULT_DECODER)
    parser.add_argument("--baseline-trace-encoder", type=Path, default=DEFAULT_BASELINE_TRACE_ENCODER)
    parser.add_argument("--csf-trace-encoder", type=Path, default=DEFAULT_CSF_TRACE_ENCODER)
    parser.add_argument("--xlsx", dest="write_xlsx", action="store_true", help="Write XLSX reports in addition to CSV and SVG outputs.")
    parser.add_argument("--no-xlsx", dest="write_xlsx", action="store_false", help="Skip XLSX report generation.")
    parser.set_defaults(write_xlsx=None)
    parser.add_argument("--clean", action="store_true", help="Remove the run directory before starting.")
    return parser.parse_args()


class RunAllPipeline:
    """Coordinates smoke checks, benchmarks, report generation, and partition evidence."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args

    def run(self) -> None:
        self.prepare()
        smoke_check(self.args)
        neutral_check(self.args)
        if self.args.suite == "full":
            self.run_full_suite()
        logger.info("\nPASS run_all")

    def prepare(self) -> None:
        self.args.config = resolve_project_path(self.args.config)
        if self.args.config.exists():
            config = load_benchmark_config(self.args.config)
            self.args.root = config.run_root if self.args.root == Path("results/run_all") else self.args.root
            self.args.smoke_dir = config.standard_grayscale_dir if self.args.smoke_dir == STANDARD_DIR else self.args.smoke_dir
            self.args.synthetic_dir = config.synthetic_dir if self.args.synthetic_dir == SYNTHETIC_DIR else self.args.synthetic_dir
            self.args.kodak_dir = config.kodak_dir if self.args.kodak_dir == KODAK_DIR else self.args.kodak_dir
            self.args.vvenc_root = config.vvenc_root if self.args.vvenc_root == ROOT.parent / "vvenc" else self.args.vvenc_root
            self.args.baseline_encoder = config.baseline_encoder if self.args.baseline_encoder == DEFAULT_BASELINE_ENCODER else self.args.baseline_encoder
            self.args.csf_encoder = config.csf_encoder if self.args.csf_encoder == DEFAULT_CSF_ENCODER else self.args.csf_encoder
            self.args.decoder = config.decoder if self.args.decoder == DEFAULT_DECODER else self.args.decoder
            self.args.baseline_trace_encoder = config.baseline_trace_encoder if self.args.baseline_trace_encoder == DEFAULT_BASELINE_TRACE_ENCODER else self.args.baseline_trace_encoder
            self.args.csf_trace_encoder = config.csf_trace_encoder if self.args.csf_trace_encoder == DEFAULT_CSF_TRACE_ENCODER else self.args.csf_trace_encoder
            self.args.qps = config.qps if self.args.qps == QPS else self.args.qps
            self.args.smoke_qp = config.smoke_qp if self.args.smoke_qp == 32 else self.args.smoke_qp
            self.args.partition_qp = config.partition_qp if self.args.partition_qp == 32 else self.args.partition_qp
            self.args.write_xlsx = config.write_xlsx if self.args.write_xlsx is None else self.args.write_xlsx

        if self.args.write_xlsx is None:
            self.args.write_xlsx = False

        for name in (
            "root",
            "smoke_dir",
            "synthetic_dir",
            "kodak_dir",
            "vvenc_root",
            "baseline_encoder",
            "csf_encoder",
            "decoder",
            "baseline_trace_encoder",
            "csf_trace_encoder",
        ):
            setattr(self.args, name, resolve_project_path(getattr(self.args, name)))

        if self.args.clean and self.args.root.exists():
            shutil.rmtree(self.args.root)
        self.args.root.mkdir(parents=True, exist_ok=True)

    def run_full_suite(self) -> None:
        args = self.args
        run([sys.executable, "tools/data_prep/generate_synthetic_images.py", "--output", str(args.synthetic_dir)], "generate synthetic images", args.root / "logs" / "generate_synthetic_images.log")
        named_metric_csvs = [
            ("standard_grayscale", benchmark(args, "standard_grayscale", args.smoke_dir)),
            ("synthetic", benchmark(args, "synthetic", args.synthetic_dir)),
            ("kodak", benchmark(args, "kodak", args.kodak_dir, ["--download-kodak"])),
        ]
        for name, metrics_csv in named_metric_csvs:
            write_image_report(name, metrics_csv, args)
        regenerate_reports([metrics_csv for _name, metrics_csv in named_metric_csvs], args)
        generate_partition_maps(args)
        print_summary(Path("docs/image_benchmark/combined/same_qp_summary.csv"))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    RunAllPipeline(parse_args()).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
