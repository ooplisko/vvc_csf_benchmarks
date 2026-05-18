from __future__ import annotations

import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    DECODER_BASELINE,
    DECODER_CSF,
    ENCODER_BASELINE,
    ENCODER_CSF,
    QP_SWEEP_FRAMES,
    QP_SWEEP_QP_POINTS,
    SEQUENCES,
    VVENC_CFG,
    VVENC_PRESET,
)
from utils.checker import assert_files_identical, assert_log_clean, md5_file
from utils.console import print_table
from utils.results import make_run_dir
from utils.runner import run_decoder, run_encoder


def _select_sequences(names: list[str] | None) -> dict:
    if not names:
        return SEQUENCES

    selected = {}
    for name in names:
        if name not in SEQUENCES:
            raise KeyError(f"Unknown sequence '{name}'. Available: {', '.join(SEQUENCES)}")
        selected[name] = SEQUENCES[name]
    return selected


def run_qp_sweep_test(
    sequence_names: list[str] | None = None,
    qp_points: list[int] | None = None,
    frames: int = QP_SWEEP_FRAMES,
    run_dir: Path | None = None,
) -> bool:
    print("\n" + "=" * 72)
    print("QP SWEEP: local sequences, baseline vs CSF")
    print("=" * 72)

    out_dir = run_dir or make_run_dir("sweep")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"  output: {out_dir}")

    sequences = _select_sequences(sequence_names)
    if not sequences:
        print("  FAIL no sequence files found in sequences/")
        return False

    qps = qp_points or QP_SWEEP_QP_POINTS
    total = len(sequences) * len(qps) * 2
    print(f"  runs: {len(sequences)} sequences x {len(qps)} QPs x 2 modes = {total}")
    print("\n  sequence coverage")
    print_table(
        ["Sequence", "Class", "Size", "FPS", "Bit depth", "File"],
        [
            [
                name,
                seq["class"],
                f"{seq['width']}x{seq['height']}",
                seq["fps"],
                seq["bit_depth"],
                seq["file"].name,
            ]
            for name, seq in sequences.items()
        ],
    )

    rows = []
    all_ok = True
    index = 0

    modes = [
        ("baseline", ENCODER_BASELINE, DECODER_BASELINE, None),
        ("csf", ENCODER_CSF, DECODER_CSF, True),
    ]

    for seq_name, seq in sequences.items():
        for qp in qps:
            for mode, encoder, decoder, csf_flag in modes:
                index += 1
                tag = f"{seq_name}_QP{qp}_{mode}"
                mode_dir = out_dir / seq_name / f"QP{qp}" / mode

                bitstream = mode_dir / f"{tag}.bin"
                recon = mode_dir / f"{tag}_rec.yuv"
                decoded = mode_dir / f"{tag}_dec.yuv"
                enc_log = mode_dir / f"{tag}_enc.log"
                dec_log = mode_dir / f"{tag}_dec.log"

                print(f"\n[{index}/{total}] {tag}")
                enc_ret = run_encoder(
                    encoder,
                    seq["file"],
                    seq["width"],
                    seq["height"],
                    seq["fps"],
                    frames,
                    qp,
                    bitstream,
                    recon,
                    enc_log,
                    preset=VVENC_PRESET,
                    cfg_file=VVENC_CFG,
                    csf_enabled=csf_flag,
                    input_bit_depth=seq["bit_depth"],
                )

                dec_ret = run_decoder(decoder, bitstream, decoded, dec_log) if enc_ret == 0 else 1

                enc_log_ok = assert_log_clean(enc_log, f"{tag} encode") if enc_ret == 0 else False
                dec_log_ok = assert_log_clean(dec_log, f"{tag} decode") if dec_ret == 0 else False
                md5_ok = assert_files_identical(recon, decoded, f"{tag} rec==dec") if dec_ret == 0 else False
                run_ok = enc_ret == 0 and dec_ret == 0 and enc_log_ok and dec_log_ok and md5_ok
                all_ok = all_ok and run_ok

                rows.append(
                    {
                        "sequence": seq_name,
                        "class": seq["class"],
                        "qp": qp,
                        "mode": mode,
                        "frames": frames,
                        "encoder_ok": enc_ret == 0,
                        "decoder_ok": dec_ret == 0,
                        "rec_dec_md5_ok": md5_ok,
                        "bitstream_bytes": bitstream.stat().st_size if bitstream.exists() else 0,
                        "recon_md5": md5_file(recon) if recon.exists() else "",
                        "decoded_md5": md5_file(decoded) if decoded.exists() else "",
                        "enc_log": str(enc_log),
                        "dec_log": str(dec_log),
                    }
                )

    summary_csv = out_dir / "qp_sweep_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    print(f"\n  summary: {summary_csv}")
    print(f"{'PASS' if all_ok else 'FAIL'} QP sweep")
    return all_ok


if __name__ == "__main__":
    raise SystemExit(0 if run_qp_sweep_test() else 1)
