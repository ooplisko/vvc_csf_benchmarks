from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    ENCODER_BASELINE,
    ENCODER_CSF,
    SEQUENCES,
    SMOKE_FRAMES,
    SMOKE_QP,
    SMOKE_SEQUENCE,
    VVENC_CFG,
    VVENC_PRESET,
)
from utils.checker import assert_files_identical, assert_log_clean
from utils.results import make_run_dir
from utils.runner import run_encoder


def run_regression_test(run_dir: Path | None = None) -> bool:
    print("\n" + "=" * 72)
    print("REGRESSION TEST: --CSFScalingList 0 is bit-identical to baseline")
    print("=" * 72)

    out_dir = run_dir or make_run_dir("regression")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"  output: {out_dir}")

    seq = SEQUENCES[SMOKE_SEQUENCE]

    baseline_bin = out_dir / "baseline.bin"
    baseline_rec = out_dir / "baseline_rec.yuv"
    baseline_log = out_dir / "baseline_enc.log"

    csf_off_bin = out_dir / "csf_off.bin"
    csf_off_rec = out_dir / "csf_off_rec.yuv"
    csf_off_log = out_dir / "csf_off_enc.log"

    baseline_ret = run_encoder(
        ENCODER_BASELINE,
        seq["file"],
        seq["width"],
        seq["height"],
        seq["fps"],
        SMOKE_FRAMES,
        SMOKE_QP,
        baseline_bin,
        baseline_rec,
        baseline_log,
        preset=VVENC_PRESET,
        cfg_file=VVENC_CFG,
        csf_enabled=None,
        input_bit_depth=seq["bit_depth"],
    )

    csf_off_ret = run_encoder(
        ENCODER_CSF,
        seq["file"],
        seq["width"],
        seq["height"],
        seq["fps"],
        SMOKE_FRAMES,
        SMOKE_QP,
        csf_off_bin,
        csf_off_rec,
        csf_off_log,
        preset=VVENC_PRESET,
        cfg_file=VVENC_CFG,
        csf_enabled=False,
        input_bit_depth=seq["bit_depth"],
    )

    checks = [
        baseline_ret == 0,
        csf_off_ret == 0,
        assert_log_clean(baseline_log, "baseline encode"),
        assert_log_clean(csf_off_log, "csf off encode"),
        assert_files_identical(baseline_bin, csf_off_bin, "baseline.bin == csf_off.bin"),
        assert_files_identical(baseline_rec, csf_off_rec, "baseline_rec.yuv == csf_off_rec.yuv"),
    ]

    all_ok = all(checks)
    print(f"\n{'PASS' if all_ok else 'FAIL'} regression test")
    return all_ok


if __name__ == "__main__":
    raise SystemExit(0 if run_regression_test() else 1)
