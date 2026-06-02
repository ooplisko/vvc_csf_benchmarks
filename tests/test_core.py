from __future__ import annotations

from pathlib import Path

from vvenc_csf.core import files_equal, parse_qps, repo_path, write_csv


def test_parse_qps_skips_empty_items() -> None:
    assert parse_qps("22,27,,32,37") == [22, 27, 32, 37]


def test_files_equal_detects_identical_and_different_files(tmp_path: Path) -> None:
    left = tmp_path / "left.bin"
    right = tmp_path / "right.bin"
    other = tmp_path / "other.bin"
    left.write_bytes(b"abc")
    right.write_bytes(b"abc")
    other.write_bytes(b"abcd")

    assert files_equal(left, right)
    assert not files_equal(left, other)


def test_write_csv_creates_parent_directory(tmp_path: Path) -> None:
    csv_path = tmp_path / "nested" / "rows.csv"
    write_csv(csv_path, [{"name": "baboon", "qp": 32}])

    assert csv_path.read_text(encoding="utf-8").splitlines() == ["name,qp", "baboon,32"]


def test_repo_path_returns_project_relative_path() -> None:
    assert repo_path(Path("README.md")).endswith("README.md")
