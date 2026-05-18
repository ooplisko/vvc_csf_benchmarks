from __future__ import annotations

import subprocess
from pathlib import Path


def _check_input(path: Path, label: str) -> bool:
    if path.exists():
        return True

    print(f"  FAIL [{label}] not found: {path}")
    return False


def run_encoder(
    encoder_bin: Path,
    input_yuv: Path,
    width: int,
    height: int,
    fps: int,
    frames: int,
    qp: int,
    output_bin: Path,
    output_rec: Path,
    log_file: Path,
    preset: str = "medium",
    cfg_file: Path | None = None,
    csf_enabled: bool | None = None,
    input_bit_depth: int = 8,
    extra_args: list[str] | None = None,
) -> int:
    if not _check_input(encoder_bin, "encoder"):
        return 127
    if not _check_input(input_yuv, "sequence"):
        return 2

    output_bin.parent.mkdir(parents=True, exist_ok=True)
    output_rec.parent.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [str(encoder_bin)]
    if cfg_file and cfg_file.exists():
        cmd += ["-c", str(cfg_file)]

    cmd += [
        "--InputFile",
        str(input_yuv),
        "--SourceWidth",
        str(width),
        "--SourceHeight",
        str(height),
        "--FrameRate",
        str(fps),
        "--InputBitDepth",
        str(input_bit_depth),
        "--FramesToBeEncoded",
        str(frames),
        "--QP",
        str(qp),
        "--BitstreamFile",
        str(output_bin),
        "--ReconFile",
        str(output_rec),
        "--preset",
        preset,
    ]

    if csf_enabled is True:
        cmd += ["--CSFScalingList", "1"]
    elif csf_enabled is False:
        cmd += ["--CSFScalingList", "0"]

    if extra_args:
        cmd += extra_args

    mode = "csf=on" if csf_enabled is True else "csf=off" if csf_enabled is False else "baseline"
    print(f"  ENCODE {mode:<8} QP={qp:<2} frames={frames:<3} -> {output_bin.name}")
    with log_file.open("w", encoding="utf-8", errors="replace") as log:
        log.write("[COMMAND] " + " ".join(cmd) + "\n\n")
        result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, text=True)

    if result.returncode == 0:
        print(f"  PASS encode ({output_bin.stat().st_size:,} bytes)")
    else:
        print(f"  FAIL encode code={result.returncode}; see {log_file}")
    return result.returncode


def run_decoder(
    decoder_bin: Path,
    input_bin: Path,
    output_yuv: Path,
    log_file: Path,
) -> int:
    if not _check_input(decoder_bin, "decoder"):
        return 127
    if not _check_input(input_bin, "bitstream"):
        return 2

    output_yuv.parent.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [str(decoder_bin), "-b", str(input_bin), "-o", str(output_yuv)]

    print(f"  DECODE {input_bin.name} -> {output_yuv.name}")
    with log_file.open("w", encoding="utf-8", errors="replace") as log:
        log.write("[COMMAND] " + " ".join(cmd) + "\n\n")
        result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, text=True)

    if result.returncode == 0:
        print(f"  PASS decode")
    else:
        print(f"  FAIL decode code={result.returncode}; see {log_file}")
    return result.returncode
