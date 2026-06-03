from __future__ import annotations

from pathlib import Path

from vvenc_csf.config import load_benchmark_config
from vvenc_csf.core import platform_executable


def test_load_benchmark_config_reads_paths_and_qps(tmp_path: Path) -> None:
    config = tmp_path / "benchmark.ini"
    config.write_text(
        "\n".join(
            [
                "[paths]",
                "run_root = results/run_all",
                "standard_grayscale_dir = image_sets/standard_grayscale/png",
                "synthetic_dir = image_sets/synthetic/png",
                "kodak_dir = image_sets/kodak/png",
                "vvenc_root = ../vvenc",
                "",
                "[binaries]",
                "baseline_encoder = binaries/vvenc_default",
                "csf_encoder = binaries/vvenc_csf",
                "decoder = binaries/vvdecapp",
                "baseline_trace_encoder = binaries/vvenc_default_trace",
                "csf_trace_encoder = binaries/vvenc_csf_trace",
                "",
                "[experiment]",
                "qps = 22,27,32,37",
                "smoke_qp = 32",
                "partition_qp = 32",
                "",
                "[output]",
                "write_xlsx = true",
            ]
        ),
        encoding="utf-8",
    )

    loaded = load_benchmark_config(config)

    assert loaded.qps == "22,27,32,37"
    assert loaded.smoke_qp == 32
    assert loaded.write_xlsx is True
    assert loaded.standard_grayscale_dir == Path("image_sets/standard_grayscale/png")
    assert loaded.baseline_encoder == platform_executable(Path("binaries/vvenc_default"))
