from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


METRICS = [
    "psnr_y",
    "ssim",
    "xpsnr_y",
    "vmaf",
    "msssim_luma",
    "fsim_luma",
    "haarpsi_luma",
    "psnr_hvs_m_luma",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def f(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "0") or 0)
    except ValueError:
        return 0.0


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def same_qp_deltas(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    by_key: dict[tuple[str, int], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        by_key[(row["image"], int(row["qp"]))][row["mode"]] = row

    output = []
    for (image, qp), modes in sorted(by_key.items()):
        if "baseline" not in modes or "csf" not in modes:
            continue
        base = modes["baseline"]
        csf = modes["csf"]
        out: dict[str, object] = {
            "image": image,
            "qp": qp,
            "baseline_bpp": f(base, "bpp"),
            "csf_bpp": f(csf, "bpp"),
            "bpp_delta_pct": _pct(f(csf, "bpp"), f(base, "bpp")),
            "compression_ratio_delta_pct": _pct(f(csf, "compression_ratio"), f(base, "compression_ratio")),
        }
        for metric in METRICS:
            out[f"{metric}_delta"] = f(csf, metric) - f(base, metric)
        output.append(out)
    return output


def equal_bpp_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    by_image: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_image[row["image"]][row["mode"]].append(row)

    output = []
    for image, modes in sorted(by_image.items()):
        baseline = sorted(modes["baseline"], key=lambda row: f(row, "bpp"))
        csf = sorted(modes["csf"], key=lambda row: f(row, "bpp"))
        if len(baseline) < 2 or len(csf) < 2:
            continue

        low = max(f(csf[0], "bpp"), f(baseline[0], "bpp"))
        high = min(f(csf[-1], "bpp"), f(baseline[-1], "bpp"))
        samples = [row for row in baseline if low <= f(row, "bpp") <= high]
        out: dict[str, object] = {"image": image, "sample_count": len(samples)}
        for metric in METRICS:
            deltas = []
            for base_row in samples:
                csf_metric = _interp_metric(csf, f(base_row, "bpp"), metric)
                if csf_metric is not None:
                    deltas.append(csf_metric - f(base_row, metric))
            out[f"{metric}_equal_bpp_delta"] = sum(deltas) / len(deltas) if deltas else 0.0
        output.append(out)
    return output


def per_image_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_image: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_image[str(row["image"])].append(row)

    output = []
    for image, items in sorted(by_image.items()):
        out: dict[str, object] = {
            "image": image,
            "qp_points": len(items),
            "bpp_delta_pct_mean": _mean(items, "bpp_delta_pct"),
            "compression_ratio_delta_pct_mean": _mean(items, "compression_ratio_delta_pct"),
        }
        for metric in METRICS:
            out[f"{metric}_delta_mean"] = _mean(items, f"{metric}_delta")
        output.append(out)
    return output


def aggregate_summary(rows: list[dict[str, object]], output: Path) -> None:
    metric_keys = [key for key in rows[0] if key.endswith("_delta") or key.endswith("_equal_bpp_delta")]
    summary = []
    for key in metric_keys:
        values = [float(row[key]) for row in rows]
        summary.append(
            {
                "metric": key,
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
            }
        )
    write_csv(output, summary)


def render_metric_charts(rows: list[dict[str, str]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for metric in METRICS:
        points: dict[str, list[tuple[float, float]]] = {"baseline": [], "csf": []}
        grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            grouped[(row["mode"], int(row["qp"]))].append(row)
        for (mode, _qp), group in grouped.items():
            bpp = sum(f(row, "bpp") for row in group) / len(group)
            quality = sum(f(row, metric) for row in group) / len(group)
            points[mode].append((bpp, quality))
        for mode in points:
            points[mode].sort()
        (output_dir / f"rd_{metric}.svg").write_text(_svg_chart(metric, points), encoding="utf-8")


def _pct(new_value: float, old_value: float) -> float:
    return ((new_value - old_value) / old_value * 100.0) if old_value else 0.0


def _mean(rows: list[dict[str, object]], key: str) -> float:
    values = [float(row[key]) for row in rows]
    return sum(values) / len(values) if values else 0.0


def _interp_metric(rows: list[dict[str, str]], bpp: float, metric: str) -> float | None:
    x = math.log(max(bpp, 1e-12))
    points = [(math.log(max(f(row, "bpp"), 1e-12)), f(row, metric)) for row in rows]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if min(x0, x1) <= x <= max(x0, x1):
            if x0 == x1:
                return y0
            ratio = (x - x0) / (x1 - x0)
            return y0 + ratio * (y1 - y0)
    return None


def _svg_chart(metric: str, points: dict[str, list[tuple[float, float]]]) -> str:
    width = 760
    height = 440
    pad = 58
    all_points = points["baseline"] + points["csf"]
    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)
    if min_y == max_y:
        min_y -= 0.01
        max_y += 0.01

    def sx(value: float) -> float:
        return pad + (value - min_x) / (max_x - min_x) * (width - 2 * pad)

    def sy(value: float) -> float:
        return height - pad - (value - min_y) / (max_y - min_y) * (height - 2 * pad)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{pad}" y="28" font-family="Arial" font-size="18" fill="#111827">{metric}: average RD curve</text>',
        f'<line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#374151"/>',
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#374151"/>',
        f'<text x="{width/2-30}" y="{height-16}" font-family="Arial" font-size="13" fill="#374151">bpp</text>',
        f'<text x="12" y="{height/2}" font-family="Arial" font-size="13" fill="#374151" transform="rotate(-90 12 {height/2})">{metric}</text>',
    ]
    for mode, color in (("baseline", "#2563eb"), ("csf", "#dc2626")):
        path = " ".join(("M" if index == 0 else "L") + f"{sx(x):.2f},{sy(y):.2f}" for index, (x, y) in enumerate(points[mode]))
        lines.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.2"/>')
        for x, y in points[mode]:
            lines.append(f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="4" fill="{color}"/>')
        lines.append(f'<text x="{width-pad-110}" y="{pad + (18 if mode == "baseline" else 38)}" font-family="Arial" font-size="13" fill="{color}">{mode}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create summary CSVs and SVG charts for image CSF benchmark metrics.")
    parser.add_argument("metrics_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/image_benchmark"))
    args = parser.parse_args()

    rows = read_rows(args.metrics_csv)
    same_qp = same_qp_deltas(rows)
    equal_bpp = equal_bpp_summary(rows)
    write_csv(args.output / "same_qp_deltas.csv", same_qp)
    write_csv(args.output / "per_image_summary.csv", per_image_summary(same_qp))
    write_csv(args.output / "equal_bpp_summary.csv", equal_bpp)
    if same_qp:
        aggregate_summary(same_qp, args.output / "same_qp_summary.csv")
    if equal_bpp:
        aggregate_summary(equal_bpp, args.output / "equal_bpp_metric_summary.csv")
    render_metric_charts(rows, args.output / "charts")
    print(f"Wrote image benchmark report files to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
