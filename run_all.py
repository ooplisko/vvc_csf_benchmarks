from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STANDARD_DIR = Path("image_sets/standard_grayscale/png")
SYNTHETIC_DIR = Path("image_sets/synthetic/png")
KODAK_DIR = Path("image_sets/kodak/png")
QPS = "22,27,32,37"


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def run(cmd: list[str], label: str, log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w", encoding="utf-8", errors="replace") as log:
        log.write("[COMMAND] " + " ".join(cmd) + "\n\n")
        result = subprocess.run(cmd, cwd=ROOT, text=True, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        print(f"FAIL {label} (log: {rel(log_file)})")
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")
    print(f"PASS {label} (log: {rel(log_file)})")


def capture(cmd: list[str]) -> str:
    result = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stdout}")
    return result.stdout


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def files_equal(left: Path, right: Path) -> bool:
    return left.exists() and right.exists() and left.stat().st_size == right.stat().st_size and file_md5(left) == file_md5(right)


def ffprobe_size(path: Path) -> tuple[int, int]:
    out = capture(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=s=x:p=0",
            str(path),
        ]
    )
    width, height = out.strip().split("x")
    return int(width), int(height)


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
    print(f"{'PASS' if ok else 'FAIL'} {name}")
    if not ok:
        raise RuntimeError(name)


def smoke_check(args: argparse.Namespace) -> None:
    print("\n== Smoke encode/decode ==")
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
    print("\n== Neutral 16 checks ==")
    logs = args.root / "logs"
    run(
        [
            sys.executable,
            "tools/verify_neutral_scaling.py",
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
            "tools/neutral_16_control.py",
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
        "tools/image_csf_benchmark.py",
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
    run(
        [
            sys.executable,
            "tools/report_image_benchmark.py",
            str(metrics_csv),
            "--output",
            f"docs/image_benchmark/{name}",
        ],
        f"{name} CSV summaries and RD charts",
        args.root / "logs" / f"report_{name}.log",
    )


def regenerate_reports(metric_csvs: list[Path], args: argparse.Namespace) -> None:
    run(
        [
            sys.executable,
            "tools/merge_image_metrics.py",
            *[str(path) for path in metric_csvs],
            "--output",
            "docs/image_benchmark/combined_image_metrics.csv",
        ],
        "merge image metrics",
        args.root / "logs" / "merge_image_metrics.log",
    )
    run(
        [sys.executable, "tools/report_image_benchmark.py", "docs/image_benchmark/combined_image_metrics.csv", "--output", "docs/image_benchmark/combined"],
        "combined CSV summaries and RD charts",
        args.root / "logs" / "report_combined.log",
    )
    run([sys.executable, "tools/render_readme.py"], "render README and benchmark report", args.root / "logs" / "render_readme.log")


def generate_partition_maps(args: argparse.Namespace) -> None:
    run(
        [
            sys.executable,
            "tools/build_partition_evidence.py",
            "--qp",
            str(args.partition_qp),
            "--standard-grayscale-dir",
            str(STANDARD_DIR),
            "--synthetic-dir",
            str(SYNTHETIC_DIR),
            "--kodak-dir",
            str(KODAK_DIR),
            "--baseline-trace-encoder",
            str(args.baseline_trace_encoder),
            "--csf-trace-encoder",
            str(args.csf_trace_encoder),
        ],
        "partition-map evidence",
        args.root / "logs" / "partition_maps.log",
    )
    run([sys.executable, "tools/render_readme.py"], "render README and benchmark report", args.root / "logs" / "render_readme_after_partitions.log")


def print_summary(csv_path: Path) -> None:
    if not csv_path.exists():
        return
    print("\n== Same-QP summary ==")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            print(f"{row['metric']}: mean={float(row['mean']):+.6f}, min={float(row['min']):+.6f}, max={float(row['max']):+.6f}")


def project_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the image-only VVenC CSF checks and report generators.")
    parser.add_argument("suite", nargs="?", default="quick", choices=["quick", "full"], help="quick runs console sanity checks. full runs all image benchmarks and regenerates docs.")
    parser.add_argument("--root", type=Path, default=Path("results/run_all"))
    parser.add_argument("--qps", default=QPS)
    parser.add_argument("--smoke-dir", type=Path, default=STANDARD_DIR)
    parser.add_argument("--smoke-qp", type=int, default=32)
    parser.add_argument("--partition-qp", type=int, default=32)
    parser.add_argument("--vvenc-root", type=Path, default=ROOT.parent / "vvenc")
    parser.add_argument("--baseline-encoder", type=Path, default=Path("binaries/vvenc_default.exe"))
    parser.add_argument("--csf-encoder", type=Path, default=Path("binaries/vvenc_csf.exe"))
    parser.add_argument("--decoder", type=Path, default=Path("binaries/vvdecapp.exe"))
    parser.add_argument("--baseline-trace-encoder", type=Path, default=Path("binaries/vvenc_default_trace.exe"))
    parser.add_argument("--csf-trace-encoder", type=Path, default=Path("binaries/vvenc_csf_trace.exe"))
    parser.add_argument("--clean", action="store_true", help="Remove the run directory before starting.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for name in (
        "root",
        "smoke_dir",
        "vvenc_root",
        "baseline_encoder",
        "csf_encoder",
        "decoder",
        "baseline_trace_encoder",
        "csf_trace_encoder",
    ):
        setattr(args, name, project_path(getattr(args, name)))

    if args.clean and args.root.exists():
        shutil.rmtree(args.root)
    args.root.mkdir(parents=True, exist_ok=True)

    smoke_check(args)
    neutral_check(args)

    if args.suite == "full":
        run([sys.executable, "tools/generate_synthetic_images.py", "--output", str(SYNTHETIC_DIR)], "generate synthetic images", args.root / "logs" / "generate_synthetic_images.log")
        named_metric_csvs = [
            ("standard_grayscale", benchmark(args, "standard_grayscale", STANDARD_DIR)),
            ("synthetic", benchmark(args, "synthetic", SYNTHETIC_DIR)),
            ("kodak", benchmark(args, "kodak", KODAK_DIR, ["--download-kodak"])),
        ]
        for name, metrics_csv in named_metric_csvs:
            write_image_report(name, metrics_csv, args)
        regenerate_reports([metrics_csv for _name, metrics_csv in named_metric_csvs], args)
        generate_partition_maps(args)
        print_summary(Path("docs/image_benchmark/combined/same_qp_summary.csv"))

    print("\nPASS run_all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
