from __future__ import annotations

import argparse
from pathlib import Path

from tools.validation.vtm.scripts.run_vtm23_kodak import benchmark_command, selected_runs


def test_selected_runs_maps_both_conversions_to_vtm23_csvs(tmp_path: Path) -> None:
    args = argparse.Namespace(conversion="both", root=tmp_path / "results", output_dir=tmp_path / "docs")

    runs = selected_runs(args)

    assert [run.conversion for run in runs] == ["ffmpeg_444", "opencv_444"]
    assert [run.output_csv.name for run in runs] == ["vtm23_ffmpeg.csv", "vtm23_opencv.csv"]


def test_benchmark_command_uses_vtm23_binary_set(tmp_path: Path) -> None:
    args = argparse.Namespace(
        baseline_encoder=Path("binaries/vtm/vtm23/baseline/EncoderApp.exe"),
        csf_encoder=Path("binaries/vtm/vtm23/csf/EncoderApp.exe"),
        decoder=Path("binaries/vtm/vtm23/baseline/DecoderApp.exe"),
        png_dir=Path("data/datasets/images/kodak/png"),
        qps="22,27",
        download_kodak=False,
    )
    run = selected_runs(argparse.Namespace(conversion="ffmpeg_444", root=tmp_path / "results", output_dir=tmp_path / "docs"))[0]

    cmd = benchmark_command(args, run)

    assert "tools/benchmarking/image_csf_benchmark.py" in cmd
    assert "--codec" in cmd and "vtm" in cmd
    assert "--conversion" in cmd and "ffmpeg_444" in cmd
    assert str(Path("binaries/vtm/vtm23/baseline/EncoderApp.exe")) in cmd
    assert str(Path("binaries/vtm/vtm23/csf/EncoderApp.exe")) in cmd
    assert str(Path("binaries/vtm/vtm23/baseline/DecoderApp.exe")) in cmd
