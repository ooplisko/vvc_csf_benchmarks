from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    DECODER_BASELINE,
    DECODER_CSF,
    ENCODER_BASELINE,
    ENCODER_CSF,
    SEQUENCES,
    SMOKE_FRAMES,
    SMOKE_QP,
    SMOKE_SEQUENCE,
    VVENC_CFG,
    VVENC_PRESET,
)
from utils.checker import assert_file_nonempty, assert_files_identical, assert_log_clean
from utils.results import make_run_dir
from utils.runner import run_decoder, run_encoder


def run_smoke_test(run_dir: Path | None = None) -> bool:
    print("\n" + "=" * 72)
    print("SMOKE TEST: encode, decode, and rec==dec")
    print("=" * 72)

    out_dir = run_dir or make_run_dir("smoke")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"  output: {out_dir}")

    seq = SEQUENCES[SMOKE_SEQUENCE]
    results: dict[str, bool] = {}

    modes = [
        ("baseline", ENCODER_BASELINE, DECODER_BASELINE, None),
        ("csf", ENCODER_CSF, DECODER_CSF, True),
    ]

    for mode, encoder, _decoder, csf_flag in modes:
        bitstream = out_dir / f"{mode}.bin"
        recon = out_dir / f"{mode}_rec.yuv"
        enc_log = out_dir / f"{mode}_enc.log"

        ret = run_encoder(
            encoder_bin=encoder,
            input_yuv=seq["file"],
            width=seq["width"],
            height=seq["height"],
            fps=seq["fps"],
            frames=SMOKE_FRAMES,
            qp=SMOKE_QP,
            output_bin=bitstream,
            output_rec=recon,
            log_file=enc_log,
            preset=VVENC_PRESET,
            cfg_file=VVENC_CFG,
            csf_enabled=csf_flag,
            input_bit_depth=seq["bit_depth"],
        )

        results[f"{mode}_encode"] = ret == 0
        results[f"{mode}_bitstream"] = assert_file_nonempty(bitstream, f"{mode} bitstream")
        results[f"{mode}_recon"] = assert_file_nonempty(recon, f"{mode} recon")
        results[f"{mode}_log"] = assert_log_clean(enc_log, f"{mode} encode")

    for mode, _encoder, decoder, _csf_flag in modes:
        bitstream = out_dir / f"{mode}.bin"
        recon = out_dir / f"{mode}_rec.yuv"
        decoded = out_dir / f"{mode}_dec.yuv"
        dec_log = out_dir / f"{mode}_dec.log"

        ret = run_decoder(decoder, bitstream, decoded, dec_log)
        results[f"{mode}_decode"] = ret == 0
        results[f"{mode}_rec_eq_dec"] = assert_files_identical(recon, decoded, f"{mode} rec==dec")
        results[f"{mode}_dec_log"] = assert_log_clean(dec_log, f"{mode} decode")

    baseline_size = (out_dir / "baseline.bin").stat().st_size
    csf_size = (out_dir / "csf.bin").stat().st_size
    results["bitstreams_differ"] = baseline_size != csf_size
    print(f"\n  baseline.bin: {baseline_size:,} bytes")
    print(f"  csf.bin:      {csf_size:,} bytes")
    print(f"  {'PASS' if results['bitstreams_differ'] else 'FAIL'} bitstreams differ")

    all_ok = all(results.values())
    print(f"\n{'PASS' if all_ok else 'FAIL'} smoke test")
    return all_ok


if __name__ == "__main__":
    raise SystemExit(0 if run_smoke_test() else 1)
