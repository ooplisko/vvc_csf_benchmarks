from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path


KODAK_URL = "https://r0k.us/graphics/kodak/kodak/kodim{index:02d}.png"
ENC_RE = re.compile(r"\s*1\s+a\s+(?P<bitrate>[0-9.]+)\s+(?P<y>[0-9.]+)\s+(?P<u>[0-9.]+)\s+(?P<v>[0-9.]+)")
SSIM_RE = re.compile(r"All:(?P<all>[0-9.]+)")
XPSNR_RE = re.compile(r"XPSNR\s+y:\s*(?P<y>[0-9.]+)")
VMAF_RE = re.compile(r"VMAF score:\s*(?P<vmaf>[0-9.]+)")


def run(cmd: list[str], log_file: Path | None = None) -> str:
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(result.stdout, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stdout}")
    return result.stdout


def ffprobe_size(path: Path) -> tuple[int, int]:
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path)])
    width, height = out.strip().split("x")
    return int(width), int(height)


def download_kodak(png_dir: Path) -> None:
    png_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, 25):
        out = png_dir / f"kodim{index:02d}.png"
        if out.exists() and out.stat().st_size > 0:
            continue
        run(["curl.exe", "-L", KODAK_URL.format(index=index), "-o", str(out)])


def parse_encoder_log(text: str) -> dict[str, float]:
    match = ENC_RE.search(text)
    if not match:
        return {"bitrate_kbps": 0.0, "psnr_y": 0.0, "psnr_u": 0.0, "psnr_v": 0.0}
    return {
        "bitrate_kbps": float(match.group("bitrate")),
        "psnr_y": float(match.group("y")),
        "psnr_u": float(match.group("u")),
        "psnr_v": float(match.group("v")),
    }


def visual_metrics(original_yuv: Path, recon_yuv: Path, width: int, height: int) -> dict[str, float]:
    common = [
        "ffmpeg",
        "-v",
        "info",
        "-s",
        f"{width}x{height}",
        "-pix_fmt",
        "yuv420p",
        "-i",
        str(original_yuv),
        "-s",
        f"{width}x{height}",
        "-pix_fmt",
        "yuv420p10le",
        "-i",
        str(recon_yuv),
    ]
    metrics: dict[str, float] = {}

    ssim_out = run(common + ["-lavfi", "ssim", "-f", "null", "-"])
    match = SSIM_RE.search(ssim_out)
    metrics["ssim"] = float(match.group("all")) if match else 0.0

    xpsnr_out = run(common + ["-lavfi", "xpsnr", "-f", "null", "-"])
    match = XPSNR_RE.search(xpsnr_out)
    metrics["xpsnr_y"] = float(match.group("y")) if match else 0.0

    try:
      vmaf_out = run(common + ["-lavfi", "libvmaf", "-f", "null", "-"])
      match = VMAF_RE.search(vmaf_out)
      metrics["vmaf"] = float(match.group("vmaf")) if match else 0.0
    except RuntimeError:
      metrics["vmaf"] = 0.0

    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Run image-only CSF benchmark on PNG images.")
    parser.add_argument("--root", type=Path, default=Path("results/image_kodak"), help="Run directory.")
    parser.add_argument("--encoder", type=Path, default=Path("binaries/vvencFFapp.exe"))
    parser.add_argument("--decoder", type=Path, default=Path("binaries/vvdecapp.exe"))
    parser.add_argument("--download-kodak", action="store_true", help="Download the Kodak PNG suite.")
    parser.add_argument("--qps", default="22,27,32,37", help="Comma-separated QP list.")
    args = parser.parse_args()

    root = args.root
    png_dir = root / "png"
    yuv_dir = root / "yuv"
    enc_dir = root / "encoded"
    qps = [int(item) for item in args.qps.split(",") if item.strip()]

    if args.download_kodak:
        download_kodak(png_dir)

    images = sorted(png_dir.glob("*.png"))
    if not images:
        raise RuntimeError(f"No PNG files found in {png_dir}")

    rows: list[dict] = []
    for image in images:
        width, height = ffprobe_size(image)
        name = image.stem
        yuv = yuv_dir / f"{name}_{width}x{height}_1.yuv"
        if not yuv.exists():
            yuv.parent.mkdir(parents=True, exist_ok=True)
            run(["ffmpeg", "-y", "-v", "error", "-i", str(image), "-pix_fmt", "yuv420p", "-frames:v", "1", str(yuv)])

        raw_bytes = width * height * 3 // 2
        for qp in qps:
            for mode, flag in (("baseline", "0"), ("csf", "1")):
                out_dir = enc_dir / name / f"QP{qp}" / mode
                bitstream = out_dir / f"{name}_QP{qp}_{mode}.vvc"
                recon = out_dir / f"{name}_QP{qp}_{mode}_rec.yuv"
                decoded = out_dir / f"{name}_QP{qp}_{mode}_dec.yuv"
                enc_log = out_dir / f"{name}_QP{qp}_{mode}_enc.log"
                dec_log = out_dir / f"{name}_QP{qp}_{mode}_dec.log"
                out_dir.mkdir(parents=True, exist_ok=True)

                text = run(
                    [
                        str(args.encoder),
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
                        "--CSFScalingList",
                        flag,
                        "--BitstreamFile",
                        str(bitstream),
                        "--ReconFile",
                        str(recon),
                    ],
                    enc_log,
                )
                run([str(args.decoder), "-b", str(bitstream), "-o", str(decoded)], dec_log)
                parsed = parse_encoder_log(text)
                metrics = visual_metrics(yuv, recon, width, height)
                bytes_out = bitstream.stat().st_size
                rows.append(
                    {
                        "image": name,
                        "width": width,
                        "height": height,
                        "qp": qp,
                        "mode": mode,
                        "bitstream_bytes": bytes_out,
                        "compression_ratio": raw_bytes / bytes_out if bytes_out else 0,
                        "bpp": (bytes_out * 8) / (width * height),
                        **parsed,
                        **metrics,
                    }
                )

    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / "image_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
