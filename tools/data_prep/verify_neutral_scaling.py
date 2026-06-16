from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vvenc_csf.core import ROOT
from vvenc_csf.neutral import NeutralScalingVerifier


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify that scaling-list value 16 is neutral in VVenC.")
    parser.add_argument("--vvenc-root", type=Path, default=ROOT.parent / "vvenc")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/matrices/neutral_16_verification.md")
    args = parser.parse_args()

    NeutralScalingVerifier(args.vvenc_root).write_report(args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
