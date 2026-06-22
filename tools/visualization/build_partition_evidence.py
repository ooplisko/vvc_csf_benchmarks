from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.visualization.parse_vvenc_qp_trace import parse_trace, write_csv as write_partition_csv
from tools.visualization.render_partition_map import render_svg
from vvenc_csf.core import CommandRunner, ffprobe_size, platform_executable
from vvenc_csf.encoding import VTM_ENCODER_CONFIG


def ensure_yuv(image: Path, yuv: Path, width: int, height: int, runner: CommandRunner, pix_fmt: str) -> None:
    if yuv.exists():
        return
    yuv.parent.mkdir(parents=True, exist_ok=True)
    runner.run(["ffmpeg", "-y", "-v", "error", "-i", str(image), "-pix_fmt", pix_fmt, "-frames:v", "1", str(yuv)])


def summarize(rows: list[dict[str, int | str]], image: str, mode: str, width: int, height: int) -> dict[str, object]:
    areas = [int(row["width"]) * int(row["height"]) for row in rows]
    sizes: dict[str, int] = {}
    for row in rows:
        key = f'{row["width"]}x{row["height"]}'
        sizes[key] = sizes.get(key, 0) + 1
    return {
        "image": image,
        "mode": mode,
        "width": width,
        "height": height,
        "cu_count": len(rows),
        "min_area": min(areas),
        "max_area": max(areas),
        "avg_area": sum(areas) / len(areas),
        "dominant_sizes": "; ".join(f"{key}:{value}" for key, value in sorted(sizes.items(), key=lambda item: (-item[1], item[0]))[:6]),
    }


def build_for_image(
    image: Path,
    dataset: str,
    args: argparse.Namespace,
    summary_rows: list[dict[str, object]],
) -> None:
    runner = CommandRunner()
    width, height = ffprobe_size(image, runner)
    name = image.stem
    yuv = args.work_dir / dataset / "yuv" / f"{name}_{width}x{height}_1.yuv"
    ensure_yuv(image, yuv, width, height, runner, "yuv444p" if args.codec == "vtm" else "yuv420p")

    for mode, encoder, extra_args in (
        ("baseline", args.baseline_trace_encoder, []),
        ("csf", args.csf_trace_encoder, ["--CSFScalingList=1"] if args.codec == "vtm" else ["--CSFScalingList", "1"]),
    ):
        run_dir = args.work_dir / dataset / name / mode
        bitstream = run_dir / f"{name}_{mode}.vvc"
        recon = run_dir / f"{name}_{mode}_rec.yuv"
        trace = run_dir / f"{name}_{mode}_d_qp.trace"
        log = run_dir / f"{name}_{mode}.log"
        run_dir.mkdir(parents=True, exist_ok=True)

        if args.codec == "vtm":
            cmd = [
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
                str(args.qp),
                "-b",
                str(bitstream),
                "-o",
                str(recon),
                "--InputChromaFormat=444",
                "--InputBitDepth=8",
                f"--TraceFile={trace}",
                "--TraceRule=D_QP:poc==0",
                *extra_args,
            ]
        else:
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
                str(args.qp),
                "--preset",
                args.preset,
                "--BitstreamFile",
                str(bitstream),
                "--ReconFile",
                str(recon),
                "--tracefile",
                str(trace),
                "--tracerule",
                "D_QP:poc==0",
                *extra_args,
            ]
        runner.run(cmd, log)
        rows = parse_trace(trace, frame=0, mode=mode)
        csv_path = args.work_dir / dataset / name / mode / f"{name}_{mode}.csv"
        svg_path = args.output / dataset / f"{name}_{mode}.svg"
        write_partition_csv(rows, csv_path)
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(render_svg([{key: str(value) for key, value in row.items()} for row in rows], width, height), encoding="utf-8")
        summary_rows.append(summarize(rows, name, mode, width, height))


def write_summary(rows: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class PartitionEvidenceBuilder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args

    def build(self) -> None:
        all_rows: list[dict[str, object]] = []
        for dataset, png_dir in (
            ("synthetic", self.args.synthetic_dir),
            ("kodak", self.args.kodak_dir),
            ("standard_grayscale", self.args.standard_grayscale_dir),
        ):
            images = sorted(png_dir.glob("*.png"))
            if self.args.limit:
                images = images[: self.args.limit]
            if not images:
                raise RuntimeError(f"No PNG images found in {png_dir}")
            dataset_rows: list[dict[str, object]] = []
            for image in images:
                build_for_image(image, dataset, self.args, dataset_rows)
            write_summary(dataset_rows, self.args.output / dataset / "summary.csv")
            all_rows.extend({"dataset": dataset, **row} for row in dataset_rows)

        write_summary(all_rows, self.args.output / "summary.csv")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build D_QP partition maps for VVenC or VTM image datasets.")
    parser.add_argument("--codec", choices=["vvenc", "vtm"], default="vvenc")
    parser.add_argument("--synthetic-dir", type=Path, default=Path("data/datasets/images/synthetic/png"))
    parser.add_argument("--kodak-dir", type=Path, default=Path("data/datasets/images/kodak/png"))
    parser.add_argument("--standard-grayscale-dir", type=Path, default=Path("data/datasets/images/standard_grayscale/png"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--baseline-trace-encoder", type=Path)
    parser.add_argument("--csf-trace-encoder", type=Path)
    parser.add_argument("--qp", type=int, default=32)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--limit", type=int, help="Optional maximum number of images per dataset, useful for smoke checks.")
    args = parser.parse_args()
    if args.output is None:
        args.output = Path("docs/partition_maps") / args.codec
    if args.work_dir is None:
        args.work_dir = Path("results/partition_maps") / args.codec
    if args.baseline_trace_encoder is None:
        args.baseline_trace_encoder = platform_executable(
            Path("binaries/vtm/vtm23/baseline_trace/EncoderApp")
            if args.codec == "vtm"
            else Path("binaries/vvenc/vvenc_default_trace")
        )
    if args.csf_trace_encoder is None:
        args.csf_trace_encoder = platform_executable(
            Path("binaries/vtm/vtm23/csf_trace/EncoderApp")
            if args.codec == "vtm"
            else Path("binaries/vvenc/vvenc_csf_trace")
        )

    PartitionEvidenceBuilder(args).build()
    print(f"Wrote partition evidence to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
