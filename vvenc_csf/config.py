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
    baseline_encoder: Path
    csf_encoder: Path
    decoder: Path
    baseline_trace_encoder: Path
    csf_trace_encoder: Path
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
        baseline_encoder=platform_executable(Path(parser["binaries"]["baseline_encoder"])),
        csf_encoder=platform_executable(Path(parser["binaries"]["csf_encoder"])),
        decoder=platform_executable(Path(parser["binaries"]["decoder"])),
        baseline_trace_encoder=platform_executable(Path(parser["binaries"]["baseline_trace_encoder"])),
        csf_trace_encoder=platform_executable(Path(parser["binaries"]["csf_trace_encoder"])),
        qps=parser["experiment"]["qps"],
        smoke_qp=parser.getint("experiment", "smoke_qp"),
        partition_qp=parser.getint("experiment", "partition_qp"),
        write_xlsx=parser.getboolean("output", "write_xlsx", fallback=True),
    )
