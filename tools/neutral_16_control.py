from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vvenc_csf.core import parse_qps, platform_executable
from vvenc_csf.neutral import Neutral16ControlConfig, Neutral16ControlRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a neutral-16 control for default VVenC vs CSF-off VVenC.")
    parser.add_argument("--root", type=Path, default=Path("results/neutral_16_control"), help="Temporary run directory.")
    parser.add_argument("--png-dir", type=Path, default=Path("image_sets/synthetic/png"), help="Input PNG directory.")
    parser.add_argument("--baseline-encoder", type=Path, default=platform_executable(Path("binaries/vvenc_default")))
    parser.add_argument("--csf-encoder", type=Path, default=platform_executable(Path("binaries/vvenc_csf")))
    parser.add_argument("--qps", default="22,27,32,37", help="Comma-separated QP list.")
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--csv", type=Path, default=Path("docs/matrices/neutral_16_control.csv"))
    parser.add_argument("--report", type=Path, default=Path("docs/matrices/neutral_16_control.md"))
    args = parser.parse_args()

    Neutral16ControlRunner(
        Neutral16ControlConfig(
            root=args.root,
            png_dir=args.png_dir,
            baseline_encoder=args.baseline_encoder,
            csf_encoder=args.csf_encoder,
            qps=parse_qps(args.qps),
            preset=args.preset,
            csv_path=args.csv,
            report_path=args.report,
        )
    ).run()
    print(f"Wrote {args.csv}")
    print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
