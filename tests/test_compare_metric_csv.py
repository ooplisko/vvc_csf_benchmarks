from __future__ import annotations

from pathlib import Path

from tools.reporting.compare_metric_csv import compare_csv


def write_csv(path: Path, value: str) -> None:
    path.write_text(
        "\n".join(
            [
                "image,qp,mode,bpp,psnr_y",
                f"img,32,baseline,0.5,{value}",
            ]
        ),
        encoding="utf-8",
    )


def test_compare_metric_csv_accepts_identical_files(tmp_path: Path) -> None:
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    write_csv(expected, "40.0")
    write_csv(actual, "40.0")

    assert compare_csv(expected, actual, tolerance=1e-9) == []


def test_compare_metric_csv_reports_numeric_delta(tmp_path: Path) -> None:
    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"
    write_csv(expected, "40.0")
    write_csv(actual, "39.9")

    issues = compare_csv(expected, actual, tolerance=1e-9)

    assert issues
    assert "psnr_y" in issues[0]
