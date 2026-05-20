from __future__ import annotations

import argparse
import csv
from pathlib import Path


CSF_8X8 = [
    [16, 16, 16, 19, 22, 26, 32, 40],
    [16, 16, 17, 20, 24, 30, 38, 48],
    [16, 17, 19, 23, 28, 35, 45, 58],
    [19, 20, 23, 28, 34, 43, 56, 72],
    [22, 24, 28, 34, 43, 55, 71, 92],
    [26, 30, 35, 43, 55, 71, 92, 119],
    [32, 38, 45, 56, 71, 92, 119, 155],
    [40, 48, 58, 72, 92, 119, 155, 200],
]

SCALING_LIST_SIZES = [1, 2, 4, 8, 16, 32, 64]
ZERO_OUT_THRESHOLD = 32


def interp_csf(row: int, col: int, size: int) -> int:
    scale = 7.0 / float(size - 1)
    y = row * scale
    x = col * scale
    y0 = int(y)
    x0 = int(x)
    y1 = min(y0 + 1, 7)
    x1 = min(x0 + 1, 7)
    dy = y - y0
    dx = x - x0
    value = (
        CSF_8X8[y0][x0] * (1.0 - dx) * (1.0 - dy)
        + CSF_8X8[y0][x1] * dx * (1.0 - dy)
        + CSF_8X8[y1][x0] * (1.0 - dx) * dy
        + CSF_8X8[y1][x1] * dx * dy
    )
    return round(value)


def csf_matrix(width: int, height: int) -> list[list[int]]:
    values: list[list[int]] = []
    size_x = SCALING_LIST_SIZES.index(width)
    size_y = SCALING_LIST_SIZES.index(height)
    for y in range(height):
        row: list[int] = []
        for x in range(width):
            if y >= ZERO_OUT_THRESHOLD or x >= ZERO_OUT_THRESHOLD:
                row.append(0)
                continue
            if width == height:
                size_num = min(width, 8)
                ratio = width // size_num
                coeff_x = x // ratio
                coeff_y = y // ratio
            else:
                large_side_id = max(size_x, size_y)
                size_num = 8 if large_side_id >= SCALING_LIST_SIZES.index(8) else 4
                ratio_wh = height // width if height > width else width // height
                ratio_h = height // size_num if height // size_num else size_num // height
                ratio_w = width // size_num if width // size_num else size_num // width
                if height > width:
                    coeff_y = y // ratio_h
                    coeff_x = (x * ratio_wh) // ratio_h
                else:
                    coeff_y = (y * ratio_wh) // ratio_w
                    coeff_x = x // ratio_w
            row.append(interp_csf(coeff_y, coeff_x, 8))
        values.append(row)
    return values


def flat_matrix(width: int, height: int) -> list[list[int]]:
    return [[16 for _x in range(width)] for _y in range(height)]


def write_csv(path: Path, matrix: list[list[int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerows(matrix)


def render_matrix(matrix: list[list[int]]) -> str:
    return "\n".join(",".join(f"{value:3d}" for value in row) for row in matrix)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump neutral and CSF scaling matrices used by the VVenC CSF branch.")
    parser.add_argument("--output", type=Path, default=Path("docs/matrices"), help="Output directory.")
    parser.add_argument(
        "--sizes",
        nargs="*",
        default=["4x4", "8x8", "16x16", "32x32", "32x16", "16x32"],
        help="Matrix sizes to dump, e.g. 8x8 16x16 32x16.",
    )
    args = parser.parse_args()

    out_dir = args.output
    lines = [
        "# CSF scaling matrices",
        "",
        "Neutral/default scaling matrix is value 16 for every coefficient.",
        "The CSF matrix is generated from the 8x8 CSF table and follows the same coefficient mapping as `Quant::xSetCSFScalingList`.",
        "",
    ]

    for spec in args.sizes:
        width_text, height_text = spec.lower().split("x", 1)
        width = int(width_text)
        height = int(height_text)
        if width not in SCALING_LIST_SIZES or height not in SCALING_LIST_SIZES:
            raise ValueError(f"Unsupported scaling-list size: {spec}")

        default = flat_matrix(width, height)
        custom = csf_matrix(width, height)
        write_csv(out_dir / f"default_{width}x{height}.csv", default)
        write_csv(out_dir / f"csf_{width}x{height}.csv", custom)

        lines.extend(
            [
                f"## {width}x{height}",
                "",
                "Default:",
                "",
                "```text",
                render_matrix(default),
                "```",
                "",
                "CSF:",
                "",
                "```text",
                render_matrix(custom),
                "```",
                "",
            ]
        )

    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote matrices to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
