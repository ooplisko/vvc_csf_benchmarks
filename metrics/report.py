from __future__ import annotations

import csv
import html
from collections import defaultdict
from pathlib import Path

from utils.console import print_section


def write_analysis_report(metrics_csv: Path | None, output_dir: Path) -> bool:
    print_section("ANALYSIS REPORT")
    if metrics_csv is None or not metrics_csv.exists():
        print("  SKIP analysis report: metrics.csv not found")
        return False

    rows = _load_rows(metrics_csv)
    if not rows:
        print(f"  SKIP analysis report: no rows in {metrics_csv}")
        return False

    output_dir.mkdir(parents=True, exist_ok=True)
    by_sequence: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_sequence[row["sequence"]].append(row)

    chart_paths = []
    for sequence, sequence_rows in sorted(by_sequence.items()):
        chart_path = output_dir / f"rd_{_safe_name(sequence)}.svg"
        if _write_rd_chart(sequence, sequence_rows, chart_path):
            chart_paths.append(chart_path)

    report_path = output_dir / "report.md"
    report_path.write_text(_render_markdown(metrics_csv, rows, chart_paths), encoding="utf-8")
    print(f"  PASS report written: {report_path}")
    if chart_paths:
        print(f"  PASS charts written: {len(chart_paths)} SVG file(s)")
    return True


def _load_rows(metrics_csv: Path) -> list[dict]:
    rows = []
    with metrics_csv.open("r", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            try:
                rows.append(
                    {
                        **row,
                        "qp": int(row["qp"]),
                        "bitrate_kbps": float(row["bitrate_kbps"]),
                        "psnr_y": float(row["psnr_y"]),
                        "elapsed_seconds": float(row.get("elapsed_seconds") or 0),
                    }
                )
            except (KeyError, ValueError):
                continue
    return rows


def _render_markdown(metrics_csv: Path, rows: list[dict], chart_paths: list[Path]) -> str:
    lines = [
        "# VVenC CSF Test Analysis",
        "",
        f"- Metrics CSV: `{metrics_csv}`",
        f"- Encoded points: {len(rows)}",
        "",
        "## CSF vs Baseline",
        "",
        "| Sequence | QP | Bitrate delta | Y-PSNR delta | Time delta |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    for row in _delta_rows(rows):
        lines.append(
            "| {sequence} | {qp} | {bitrate_delta:+.2f}% | {psnr_delta:+.3f} dB | {time_delta:+.2f}% |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Result Notes",
            "",
            "- Bitrate may rise or fall by roughly 1-10%; larger changes deserve manual review.",
            "- PSNR-Y can drop because this is a perceptual quantization experiment, not a PSNR optimizer.",
            "- Time should stay close to baseline; a large increase suggests CSF work moved into a hot loop.",
            "- Decoder compatibility is checked separately by the rec==dec and cross-check tests.",
            "",
            "## Charts",
            "",
        ]
    )

    for chart_path in chart_paths:
        lines.append(f"- `{chart_path.name}`")

    return "\n".join(lines) + "\n"


def _delta_rows(rows: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, int], dict[str, dict]] = {}
    for row in rows:
        by_key.setdefault((row["sequence"], row["qp"]), {})[row["mode"]] = row

    deltas = []
    for (sequence, qp), modes in sorted(by_key.items()):
        baseline = modes.get("baseline")
        csf = modes.get("csf")
        if not baseline or not csf:
            continue
        deltas.append(
            {
                "sequence": sequence,
                "qp": qp,
                "bitrate_delta": _percent_delta(csf["bitrate_kbps"], baseline["bitrate_kbps"]),
                "psnr_delta": csf["psnr_y"] - baseline["psnr_y"],
                "time_delta": _percent_delta(csf["elapsed_seconds"], baseline["elapsed_seconds"]),
            }
        )
    return deltas


def _write_rd_chart(sequence: str, rows: list[dict], chart_path: Path) -> bool:
    points_by_mode: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        points_by_mode[row["mode"]].append(row)

    points = [row for mode_rows in points_by_mode.values() for row in mode_rows]
    if len(points) < 2:
        return False

    min_rate = min(row["bitrate_kbps"] for row in points)
    max_rate = max(row["bitrate_kbps"] for row in points)
    min_psnr = min(row["psnr_y"] for row in points)
    max_psnr = max(row["psnr_y"] for row in points)
    if min_rate == max_rate or min_psnr == max_psnr:
        return False

    width, height = 760, 460
    left, right, top, bottom = 72, 64, 48, 104
    plot_w = width - left - right
    plot_h = height - top - bottom
    rate_pad = (max_rate - min_rate) * 0.04
    psnr_pad = (max_psnr - min_psnr) * 0.08
    min_rate = max(0.0, min_rate - rate_pad)
    max_rate += rate_pad
    min_psnr -= psnr_pad
    max_psnr += psnr_pad

    def xy(row: dict) -> tuple[float, float]:
        x = left + (row["bitrate_kbps"] - min_rate) * plot_w / (max_rate - min_rate)
        y = top + (max_psnr - row["psnr_y"]) * plot_h / (max_psnr - min_psnr)
        return x, y

    def x_for_rate(value: float) -> float:
        return left + (value - min_rate) * plot_w / (max_rate - min_rate)

    def y_for_psnr(value: float) -> float:
        return top + (max_psnr - value) * plot_h / (max_psnr - min_psnr)

    def clamp_label(x: float, y: float, mode: str) -> tuple[float, float]:
        x = min(max(x + 6, left + 4), width - right - 34)
        offset = -8 if mode == "baseline" else 16
        y = min(max(y + offset, top + 14), height - bottom - 4)
        return x, y

    colors = {"baseline": "#2563eb", "csf": "#dc2626"}
    styles = {
        "baseline": {"width": "3.4", "dash": "", "marker": "circle"},
        "csf": {"width": "2.6", "dash": ' stroke-dasharray="7 5"', "marker": "diamond"},
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="26" font-family="Arial" font-size="18" font-weight="700">{html.escape(sequence)} rate-distortion</text>',
    ]

    for value in _linear_ticks(min_rate, max_rate):
        x = x_for_rate(value)
        parts.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height - bottom}" stroke="#e5e7eb" stroke-width="1"/>'
        )

    for value in _linear_ticks(min_psnr, max_psnr):
        y = y_for_psnr(value)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1"/>'
        )

    parts.extend(
        [
        f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="#111827"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" stroke="#111827"/>',
        f'<text x="{width // 2 - 60}" y="{height - 54}" font-family="Arial" font-size="13">Bitrate, kbps</text>',
        f'<text x="16" y="{height // 2 + 45}" font-family="Arial" font-size="13" transform="rotate(-90 16,{height // 2 + 45})">Y-PSNR, dB</text>',
        ]
    )

    for value in _linear_ticks(min_rate, max_rate):
        x = x_for_rate(value)
        parts.extend(
            [
                f'<line x1="{x:.1f}" y1="{height - bottom}" x2="{x:.1f}" y2="{height - bottom + 5}" stroke="#111827"/>',
                f'<text x="{x:.1f}" y="{height - bottom + 20}" font-family="Arial" font-size="11" fill="#374151" text-anchor="middle">{_format_rate_tick(value)}</text>',
            ]
        )

    for value in _linear_ticks(min_psnr, max_psnr):
        y = y_for_psnr(value)
        parts.extend(
            [
                f'<line x1="{left - 5}" y1="{y:.1f}" x2="{left}" y2="{y:.1f}" stroke="#111827"/>',
                f'<text x="{left - 9}" y="{y + 4:.1f}" font-family="Arial" font-size="11" fill="#374151" text-anchor="end">{_format_psnr_tick(value)}</text>',
            ]
        )

    for mode in ("baseline", "csf"):
        mode_points = sorted(points_by_mode.get(mode, []), key=lambda row: row["bitrate_kbps"])
        if not mode_points:
            continue
        coords = [xy(row) for row in mode_points]
        color = colors[mode]
        style = styles[mode]
        parts.append(
            '<polyline fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round"'
            ' stroke-linejoin="round"{dash} points="{points}"/>'.format(
                color=color,
                width=style["width"],
                dash=style["dash"],
                points=" ".join(f"{x:.1f},{y:.1f}" for x, y in coords),
            )
        )
        for row, (x, y) in zip(mode_points, coords):
            parts.append(_marker_svg(x, y, color, style["marker"]))
            label_x, label_y = clamp_label(x, y, mode)
            parts.append(
                f'<text x="{label_x:.1f}" y="{label_y:.1f}" font-family="Arial" font-size="11" fill="#374151">QP{row["qp"]}</text>'
            )

    parts.extend(
        [
            f'<line x1="{width // 2 - 92}" y1="{height - 26}" x2="{width // 2 - 54}" y2="{height - 26}" stroke="{colors["baseline"]}" stroke-width="{styles["baseline"]["width"]}" stroke-linecap="round"/>',
            _marker_svg(width // 2 - 73, height - 26, colors["baseline"], styles["baseline"]["marker"]),
            f'<text x="{width // 2 - 46}" y="{height - 22}" font-family="Arial" font-size="12">baseline</text>',
            f'<line x1="{width // 2 + 42}" y1="{height - 26}" x2="{width // 2 + 80}" y2="{height - 26}" stroke="{colors["csf"]}" stroke-width="{styles["csf"]["width"]}" stroke-linecap="round" stroke-dasharray="7 5"/>',
            _marker_svg(width // 2 + 61, height - 26, colors["csf"], styles["csf"]["marker"]),
            f'<text x="{width // 2 + 88}" y="{height - 22}" font-family="Arial" font-size="12">csf</text>',
            "</svg>",
        ]
    )
    chart_path.write_text("\n".join(parts), encoding="utf-8")
    return True


def _marker_svg(x: float, y: float, color: str, marker: str) -> str:
    if marker == "diamond":
        return (
            f'<rect x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8" '
            f'transform="rotate(45 {x:.1f} {y:.1f})" fill="#ffffff" stroke="{color}" stroke-width="2"/>'
        )
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#ffffff" stroke="{color}" stroke-width="2"/>'


def _linear_ticks(min_value: float, max_value: float, count: int = 5) -> list[float]:
    if count <= 1 or min_value == max_value:
        return [min_value]
    step = (max_value - min_value) / (count - 1)
    return [min_value + step * index for index in range(count)]


def _format_rate_tick(value: float) -> str:
    return f"{value:,.0f}"


def _format_psnr_tick(value: float) -> str:
    return f"{value:.1f}"


def _percent_delta(value: float, anchor: float) -> float:
    if anchor == 0:
        return 0.0
    return (value - anchor) * 100.0 / anchor


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
