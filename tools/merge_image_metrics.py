from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge image benchmark metric CSV files.")
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    fieldnames: list[str] | None = None
    rows: list[dict[str, str]] = []
    for path in args.inputs:
        current_fields, current_rows = read_rows(path)
        if fieldnames is None:
            fieldnames = current_fields
        elif current_fields != fieldnames:
            raise RuntimeError(f"CSV header mismatch in {path}")
        rows.extend(current_rows)

    if not fieldnames:
        raise RuntimeError("No input rows found")

    rows.sort(key=lambda row: (row["image"], int(row["qp"]), row["mode"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {args.output} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
