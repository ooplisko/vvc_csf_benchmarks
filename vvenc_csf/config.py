from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from vvenc_csf.core import platform_executable


@dataclass(frozen=True)
class BenchmarkConfig:
    """INI-backed defaults for the image benchmark command-line tools."""

    run_root: Path
    standard_grayscale_dir: Path
    synthetic_dir: Path
    kodak_dir: Path
    vvenc_root: Path
    vtm_root: Path
    baseline_encoder: Path
    csf_encoder: Path
    decoder: Path
    vtm_baseline_encoder: Path
    vtm_csf_encoder: Path
    vtm_baseline_decoder: Path
    vtm18_encoder: Path
    vtm18_decoder: Path
    baseline_trace_encoder: Path
    csf_trace_encoder: Path
    vtm_baseline_trace_encoder: Path
    vtm_csf_trace_encoder: Path
    codec: str
    qps: str
    smoke_qp: int
    partition_qp: int
    write_xlsx: bool


def load_benchmark_config(path: Path) -> BenchmarkConfig:
    parser = configparser.ConfigParser()
    read_files = parser.read(path, encoding="utf-8")
    if not read_files:
        raise FileNotFoundError(f"Benchmark config not found: {path}")

    return BenchmarkConfig(
        run_root=Path(parser["paths"]["run_root"]),
        standard_grayscale_dir=Path(parser["paths"]["standard_grayscale_dir"]),
        synthetic_dir=Path(parser["paths"]["synthetic_dir"]),
        kodak_dir=Path(parser["paths"]["kodak_dir"]),
        vvenc_root=Path(parser["paths"]["vvenc_root"]),
        vtm_root=Path(parser["paths"].get("vtm_root", "../VVCSoftware_VTM")),
        baseline_encoder=platform_executable(Path(parser["binaries"]["baseline_encoder"])),
        csf_encoder=platform_executable(Path(parser["binaries"]["csf_encoder"])),
        decoder=platform_executable(Path(parser["binaries"]["decoder"])),
        vtm_baseline_encoder=platform_executable(Path(parser["binaries"].get("vtm_baseline_encoder", "binaries/vtm/vtm23/baseline/EncoderApp"))),
        vtm_csf_encoder=platform_executable(Path(parser["binaries"].get("vtm_csf_encoder", "binaries/vtm/vtm23/csf/EncoderApp"))),
        vtm_baseline_decoder=platform_executable(Path(parser["binaries"].get("vtm_baseline_decoder", "binaries/vtm/vtm23/baseline/DecoderApp"))),
        vtm18_encoder=platform_executable(Path(parser["binaries"].get("vtm18_encoder", "binaries/vtm/vtm18/baseline/EncoderApp"))),
        vtm18_decoder=platform_executable(Path(parser["binaries"].get("vtm18_decoder", "binaries/vtm/vtm18/baseline/DecoderApp"))),
        baseline_trace_encoder=platform_executable(Path(parser["binaries"]["baseline_trace_encoder"])),
        csf_trace_encoder=platform_executable(Path(parser["binaries"]["csf_trace_encoder"])),
        vtm_baseline_trace_encoder=platform_executable(Path(parser["binaries"].get("vtm_baseline_trace_encoder", "binaries/vtm/vtm23/baseline_trace/EncoderApp"))),
        vtm_csf_trace_encoder=platform_executable(Path(parser["binaries"].get("vtm_csf_trace_encoder", "binaries/vtm/vtm23/csf_trace/EncoderApp"))),
        codec=parser["experiment"].get("codec", "vvenc"),
        qps=parser["experiment"]["qps"],
        smoke_qp=parser.getint("experiment", "smoke_qp"),
        partition_qp=parser.getint("experiment", "partition_qp"),
        write_xlsx=parser.getboolean("output", "write_xlsx", fallback=True),
    )
