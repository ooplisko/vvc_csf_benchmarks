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
                "standard_grayscale_dir = data/datasets/images/standard_grayscale/png",
                "synthetic_dir = data/datasets/images/synthetic/png",
                "kodak_dir = data/datasets/images/kodak/png",
                "vvenc_root = ../vvenc",
                "vtm_root = ../VVCSoftware_VTM",
                "",
                "[binaries]",
                "baseline_encoder = binaries/vvenc/vvenc_default",
                "csf_encoder = binaries/vvenc/vvenc_csf",
                "decoder = binaries/vvenc/vvdecapp",
                "vtm_baseline_encoder = binaries/vtm/vtm23/baseline/EncoderApp",
                "vtm_csf_encoder = binaries/vtm/vtm23/csf/EncoderApp",
                "vtm_baseline_decoder = binaries/vtm/vtm23/baseline/DecoderApp",
                "vtm18_encoder = binaries/vtm/vtm18/baseline/EncoderApp",
                "vtm18_decoder = binaries/vtm/vtm18/baseline/DecoderApp",
                "baseline_trace_encoder = binaries/vvenc/vvenc_default_trace",
                "csf_trace_encoder = binaries/vvenc/vvenc_csf_trace",
                "vtm_baseline_trace_encoder = binaries/vtm/vtm23/baseline_trace/EncoderApp",
                "vtm_csf_trace_encoder = binaries/vtm/vtm23/csf_trace/EncoderApp",
                "",
                "[experiment]",
                "codec = vvenc",
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
    assert loaded.standard_grayscale_dir == Path("data/datasets/images/standard_grayscale/png")
    assert loaded.codec == "vvenc"
    assert loaded.vtm_root == Path("../VVCSoftware_VTM")
    assert loaded.baseline_encoder == platform_executable(Path("binaries/vvenc/vvenc_default"))
    assert loaded.vtm_csf_encoder == platform_executable(Path("binaries/vtm/vtm23/csf/EncoderApp"))
    assert loaded.vtm18_encoder == platform_executable(Path("binaries/vtm/vtm18/baseline/EncoderApp"))
    assert loaded.vtm_csf_trace_encoder == platform_executable(Path("binaries/vtm/vtm23/csf_trace/EncoderApp"))
