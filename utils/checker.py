from __future__ import annotations

import hashlib
from pathlib import Path


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_file_nonempty(path: Path, label: str) -> bool:
    if not path.exists():
        print(f"  FAIL [{label}] missing: {path}")
        return False

    size = path.stat().st_size
    if size == 0:
        print(f"  FAIL [{label}] empty: {path}")
        return False

    print(f"  PASS [{label}] {path.name} ({size:,} bytes)")
    return True


def assert_files_identical(file_a: Path, file_b: Path, label: str) -> bool:
    if not file_a.exists():
        print(f"  FAIL [{label}] missing: {file_a}")
        return False
    if not file_b.exists():
        print(f"  FAIL [{label}] missing: {file_b}")
        return False

    md5_a = md5_file(file_a)
    md5_b = md5_file(file_b)
    if md5_a == md5_b:
        print(f"  PASS [{label}] identical (MD5: {md5_a})")
        return True

    print(f"  FAIL [{label}] files differ")
    print(f"       {file_a.name}: {md5_a}")
    print(f"       {file_b.name}: {md5_b}")
    return False


def assert_log_clean(log_file: Path, label: str) -> bool:
    if not log_file.exists():
        print(f"  FAIL [{label}] missing log: {log_file}")
        return False

    text = log_file.read_text(errors="replace")
    bad_tokens = ["ERROR", "Assertion failed", "Segmentation", "Exception"]
    found = [token for token in bad_tokens if token in text]
    if found:
        print(f"  FAIL [{label}] log contains: {', '.join(found)}")
        return False

    print(f"  PASS [{label}] log is clean")
    return True
