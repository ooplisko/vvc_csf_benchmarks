from __future__ import annotations

import argparse
import csv
from pathlib import Path


COLORS = {
    "ctu": "#6b7280",
    "cu": "#2563eb",
    "tu": "#16a34a",
    "pu": "#9333ea",
}


def _row_int(row: dict[str, str], name: str, default: int = 0) -> int:
    value = row.get(name, "")
    return int(value) if value not in ("", None) else default


def _matches_frame(row: dict[str, str], frame: int) -> bool:
    if "poc" in row and row["poc"] not in ("", None):
        return int(row["poc"]) == frame
    if "frame" in row and row["frame"] not in ("", None):
        return int(row["frame"]) == frame
    return frame == 0


def load_blocks(csv_path: Path, frame: int) -> list[dict[str, str]]:
    with csv_path.open("r", newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return [row for row in reader if _matches_frame(row, frame)]


def infer_canvas(blocks: list[dict[str, str]], width: int | None, height: int | None) -> tuple[int, int]:
    if width and height:
        return width, height

    max_x = max((_row_int(row, "x") + _row_int(row, "width")) for row in blocks)
    max_y = max((_row_int(row, "y") + _row_int(row, "height")) for row in blocks)
    return width or max_x, height or max_y


def render_svg(blocks: list[dict[str, str]], width: int, height: int) -> str:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#f8fafc"/>',
    ]
    for row in blocks:
        kind = row.get("type", "cu").lower()
        color = COLORS.get(kind, "#111827")
        x = _row_int(row, "x")
        y = _row_int(row, "y")
        block_width = _row_int(row, "width")
        block_height = _row_int(row, "height")
        depth = _row_int(row, "depth")
        stroke_width = 1.0 if kind != "ctu" else 1.6
        opacity = max(0.28, 0.9 - depth * 0.08)
        parts.append(
            f'<rect x="{x}" y="{y}" width="{block_width}" height="{block_height}" '
            f'fill="none" stroke="{color}" stroke-width="{stroke_width}" opacity="{opacity:.2f}"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a CU/TU partition CSV into an SVG block map.")
    parser.add_argument("csv", type=Path, help="CSV with frame/poc,type,x,y,width,height columns.")
    parser.add_argument("--output", type=Path, default=None, help="Output SVG path.")
    parser.add_argument("--frame", type=int, default=0, help="POC/frame to render.")
    parser.add_argument("--width", type=int, default=None, help="Picture width. Inferred from blocks when omitted.")
    parser.add_argument("--height", type=int, default=None, help="Picture height. Inferred from blocks when omitted.")
    args = parser.parse_args()

    blocks = load_blocks(args.csv, args.frame)
    if not blocks:
        raise RuntimeError(f"No blocks for frame {args.frame} in {args.csv}")

    width, height = infer_canvas(blocks, args.width, args.height)
    output = args.output or args.csv.with_suffix(".svg")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_svg(blocks, width, height), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
