from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    DECODER_BASELINE,
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
from utils.runner import run_decoder, run_encoder


def run_cross_check_test(run_dir: Path | None = None) -> bool:
    print("\n" + "=" * 72)
    print("CROSS CHECK: baseline decoder reads CSF bitstream")
    print("=" * 72)

    out_dir = run_dir or make_run_dir("cross")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"  output: {out_dir}")

    seq = SEQUENCES[SMOKE_SEQUENCE]

    csf_bin = out_dir / "csf.bin"
    csf_rec = out_dir / "csf_rec.yuv"
    csf_enc_log = out_dir / "csf_enc.log"
    cross_dec = out_dir / "csf_crosscheck.yuv"
    cross_log = out_dir / "crosscheck_dec.log"

    enc_ret = run_encoder(
        ENCODER_CSF,
        seq["file"],
        seq["width"],
        seq["height"],
        seq["fps"],
        SMOKE_FRAMES,
        SMOKE_QP,
        csf_bin,
        csf_rec,
        csf_enc_log,
        preset=VVENC_PRESET,
        cfg_file=VVENC_CFG,
        csf_enabled=True,
        input_bit_depth=seq["bit_depth"],
    )

    dec_ret = run_decoder(DECODER_BASELINE, csf_bin, cross_dec, cross_log)

    checks = [
        enc_ret == 0,
        dec_ret == 0,
        assert_log_clean(csf_enc_log, "csf encode"),
        assert_log_clean(cross_log, "baseline decoder"),
        assert_files_identical(csf_rec, cross_dec, "csf_rec.yuv == baseline_decoder.yuv"),
    ]

    all_ok = all(checks)
    print(f"\n{'PASS' if all_ok else 'FAIL'} cross check")
    return all_ok


if __name__ == "__main__":
    raise SystemExit(0 if run_cross_check_test() else 1)
