"""Run the VVenC OpenCV Kodak validation pipeline."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from metrics.image_quality import msssim_rgb


def get_bpp(vvc_path: Path, height: int, width: int) -> float:
    return vvc_path.stat().st_size * 8 / (height * width)


def image_msssim_rgb(reference_bgr: np.ndarray, decoded_bgr: np.ndarray) -> float:
    reference_rgb = cv2.cvtColor(reference_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    decoded_rgb = cv2.cvtColor(decoded_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    height, width = reference_rgb.shape[:2]
    return msssim_rgb(
        reference_rgb[:, :, 0].ravel().tolist(),
        reference_rgb[:, :, 1].ravel().tolist(),
        reference_rgb[:, :, 2].ravel().tolist(),
        decoded_rgb[:, :, 0].ravel().tolist(),
        decoded_rgb[:, :, 1].ravel().tolist(),
        decoded_rgb[:, :, 2].ravel().tolist(),
        width,
        height,
    )


def run_opencv_vvenc(image_path: Path, qp: int, vvenc: Path, vvdec: Path) -> tuple[float, float, float]:
    original = cv2.imread(str(image_path))
    if original is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    height, width = original.shape[:2]
    yuv_i420 = cv2.cvtColor(original, cv2.COLOR_BGR2YUV_I420)

    with tempfile.TemporaryDirectory(prefix="vvenc_opencv_") as tmp:
        tmp_dir = Path(tmp)
        input_yuv = tmp_dir / "input.yuv"
        encoded_vvc = tmp_dir / "encoded.vvc"
        decoded_yuv = tmp_dir / "decoded.yuv"
        input_yuv.write_bytes(yuv_i420.tobytes())

        subprocess.run(
            [
                str(vvenc),
                "-i",
                str(input_yuv),
                "-s",
                f"{width}x{height}",
                "-q",
                str(qp),
                "--fps",
                "1",
                "-b",
                str(encoded_vvc),
                "--threads",
                "4",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            check=True,
        )
        bpp = get_bpp(encoded_vvc, height, width)

        subprocess.run(
            [str(vvdec), "-b", str(encoded_vvc), "-o", str(decoded_yuv)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            check=True,
        )
        yuv_data = decoded_yuv.read_bytes()

    decoded_yuv16 = np.frombuffer(yuv_data, dtype=np.uint16).reshape((height * 3 // 2, width))
    decoded_yuv8 = np.clip((decoded_yuv16 + 2) >> 2, 0, 255).astype(np.uint8)
    decoded_bgr = cv2.cvtColor(decoded_yuv8, cv2.COLOR_YUV2BGR_I420)
    return bpp, cv2.PSNR(original, decoded_bgr), image_msssim_rgb(original, decoded_bgr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the VVenC OpenCV Kodak validation pipeline.")
    parser.add_argument("--kodak-dir", type=Path, default=ROOT / "data" / "datasets" / "images" / "kodak" / "png")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "vtm_validation" / "vvenc_opencv.csv")
    parser.add_argument("--vvenc", type=Path, default=ROOT / "binaries" / "vvenc_default.exe")
    parser.add_argument("--vvdec", type=Path, default=ROOT / "binaries" / "vvdecapp.exe")
    parser.add_argument("--qps", default="22,27,32,37", help="Comma-separated QP list.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    qps = [int(item) for item in args.qps.split(",") if item.strip()]
    images = sorted(args.kodak_dir.glob("kodim*.png"))

    if not images:
        raise RuntimeError(f"No images found in {args.kodak_dir}")

    results: list[dict[str, float | int]] = []
    print(f"Running VVenC OpenCV Pipeline on {len(images)} images for QPs {qps}...")
    for qp in qps:
        qp_bpp = 0.0
        qp_psnr = 0.0
        qp_msssim = 0.0

        for image_path in images:
            bpp, psnr, msssim = run_opencv_vvenc(image_path, qp, args.vvenc, args.vvdec)
            qp_bpp += bpp
            qp_psnr += psnr
            qp_msssim += msssim
            print(f"  {image_path.name} (QP {qp}): BPP {bpp:.4f}, PSNR {psnr:.4f}, MS-SSIM {msssim:.6f}")

        avg_bpp = qp_bpp / len(images)
        avg_psnr = qp_psnr / len(images)
        avg_msssim = qp_msssim / len(images)
        print(f"Average for QP {qp}: BPP {avg_bpp:.4f}, PSNR {avg_psnr:.4f}, MS-SSIM {avg_msssim:.6f}\n")
        results.append({"qp": qp, "bpp": avg_bpp, "psnr_rgb": avg_psnr, "msssim_rgb": avg_msssim})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["qp", "bpp", "psnr_rgb", "msssim_rgb"])
        writer.writeheader()
        writer.writerows(results)

    print(f"Results written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
