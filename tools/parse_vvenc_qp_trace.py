from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


LUMA_CU_RE = re.compile(
    r"^x=(?P<x>\d+),\s*y=(?P<y>\d+),\s*w=(?P<width>\d+),\s*h=(?P<height>\d+),\s*qp=(?P<qp>-?\d+)"
)


def parse_trace(trace_path: Path, frame: int, mode: str) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    with trace_path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            match = LUMA_CU_RE.match(line.strip())
            if not match:
                continue

            x = int(match.group("x"))
            y = int(match.group("y"))
            width = int(match.group("width"))
            height = int(match.group("height"))
            rows.append(
                {
                    "poc": frame,
                    "type": "cu",
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "depth": _depth(width, height),
                    "mode": mode,
                    "qp": int(match.group("qp")),
                }
            )
    return rows


def _depth(width: int, height: int) -> int:
    max_side = max(width, height)
    if max_side >= 128:
        return 0
    if max_side >= 64:
        return 1
    if max_side >= 32:
        return 2
    if max_side >= 16:
        return 3
    if max_side >= 8:
        return 4
    return 5


def write_csv(rows: list[dict[str, int | str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["poc", "type", "x", "y", "width", "height", "depth", "mode", "qp"]
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert VVenC D_QP trace output into partition-map CSV.")
    parser.add_argument("trace", type=Path, help="Trace file produced with --tracerule D_QP:poc==0.")
    parser.add_argument("--output", type=Path, required=True, help="Output CSV path.")
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--mode", default="unknown", help="Mode label stored in the CSV.")
    args = parser.parse_args()

    rows = parse_trace(args.trace, args.frame, args.mode)
    if not rows:
        raise RuntimeError(f"No luma CU entries found in {args.trace}")

    write_csv(rows, args.output)
    print(f"Wrote {args.output} ({len(rows)} luma CUs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
