from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vvenc_csf.benchmark import ImageBenchmarkConfig, ImageBenchmarkRunner, KodakDownloader
from vvenc_csf.core import parse_qps, platform_executable


def main() -> int:
    parser = argparse.ArgumentParser(description="Run image-only CSF benchmark on PNG images.")
    parser.add_argument("--root", type=Path, default=Path("results/image_kodak"), help="Run directory.")
    parser.add_argument("--codec", choices=["vvenc", "vtm", "vtm_validation"], default="vvenc", help="Codec command dialect to use.")
    parser.add_argument("--baseline-encoder", type=Path, default=platform_executable(Path("binaries/vvenc/vvenc_default")))
    parser.add_argument("--csf-encoder", type=Path, default=platform_executable(Path("binaries/vvenc/vvenc_csf")))
    parser.add_argument("--decoder", type=Path, default=platform_executable(Path("binaries/vvenc/vvdecapp")))
    parser.add_argument("--png-dir", type=Path, default=None, help="Directory with input PNG images.")
    parser.add_argument("--download-kodak", action="store_true", help="Download the Kodak PNG suite.")
    parser.add_argument("--qps", default="22,27,32,37", help="Comma-separated QP list.")
    parser.add_argument("--preset", default="medium", help="VVenC preset used for both encoders.")
    parser.add_argument("--conversion", default="ffmpeg_420", choices=["ffmpeg_420", "ffmpeg_444", "opencv_444"], help="Conversion mode for PNG to YUV.")
    args = parser.parse_args()

    png_dir = args.png_dir or (args.root / "png")
    if args.download_kodak:
        KodakDownloader().download(png_dir)

    csv_path = ImageBenchmarkRunner(
        ImageBenchmarkConfig(
            root=args.root,
            png_dir=png_dir,
            baseline_encoder=args.baseline_encoder,
            csf_encoder=args.csf_encoder,
            decoder=args.decoder,
            qps=parse_qps(args.qps),
            codec=args.codec,
            preset=args.preset,
            conversion=args.conversion,
        )
    ).run()
    print(f"Wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
