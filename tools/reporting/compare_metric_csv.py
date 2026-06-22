from __future__ import annotations

import argparse
import csv
from pathlib import Path


KEY_COLUMNS = ("image", "qp", "mode")


def read_rows(path: Path) -> tuple[list[str], dict[tuple[str, str, str], dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        rows = {tuple(row[column] for column in KEY_COLUMNS): row for row in reader}
    return fields, rows


def compare_csv(expected: Path, actual: Path, tolerance: float) -> list[str]:
    expected_fields, expected_rows = read_rows(expected)
    actual_fields, actual_rows = read_rows(actual)
    issues: list[str] = []

    if expected_fields != actual_fields:
        issues.append(f"header mismatch: {expected_fields} != {actual_fields}")
        return issues

    missing = sorted(set(expected_rows) - set(actual_rows))
    extra = sorted(set(actual_rows) - set(expected_rows))
    if missing:
        issues.append(f"missing rows: {missing[:5]}{'...' if len(missing) > 5 else ''}")
    if extra:
        issues.append(f"extra rows: {extra[:5]}{'...' if len(extra) > 5 else ''}")

    for key in sorted(set(expected_rows) & set(actual_rows)):
        expected_row = expected_rows[key]
        actual_row = actual_rows[key]
        for column in expected_fields:
            if column in KEY_COLUMNS:
                continue
            expected_value = expected_row[column]
            actual_value = actual_row[column]
            if expected_value == actual_value:
                continue
            try:
                delta = abs(float(expected_value) - float(actual_value))
            except ValueError:
                issues.append(f"{key} {column}: {expected_value!r} != {actual_value!r}")
                continue
            if delta > tolerance:
                issues.append(f"{key} {column}: {expected_value} != {actual_value} (delta={delta})")
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two image benchmark metric CSV files.")
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    issues = compare_csv(args.expected, args.actual, args.tolerance)
    if issues:
        print(f"FAIL: {len(issues)} differences found")
        for issue in issues[:50]:
            print(issue)
        return 1
    print("PASS: metric CSV files match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
