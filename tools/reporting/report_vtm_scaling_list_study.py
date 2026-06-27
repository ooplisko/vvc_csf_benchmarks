from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from metrics.registry import METRIC_CHART_LABELS, METRIC_LABELS
from tools.reporting.report_image_benchmark import f, read_rows, write_csv


COLOR_METRICS = ("psnr_rgb", "msssim_rgb", "psnr_hvs_m_luma", "haarpsi_luma")
GRAYSCALE_METRICS = ("psnr_y", "msssim_luma", "psnr_hvs_m_luma", "haarpsi_luma")
DATASETS = (
    ("standard_grayscale", "Standard Grayscale", GRAYSCALE_METRICS),
    ("standard_color", "Standard Color", COLOR_METRICS),
)
DEFAULT_REPORT_IMAGES = ("baboon", "goldhill", "peppers")


def write_dataset_report(metrics_csv: Path, output_dir: Path, metrics: tuple[str, ...]) -> None:
    rows = read_rows(metrics_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "image_metrics.csv", rows)
    write_csv(output_dir / "per_image_summary.csv", per_image_summary(rows, metrics))
    render_qp_charts(rows, output_dir / "qp_charts", metrics)


def per_image_summary(rows: list[dict[str, str]], metrics: tuple[str, ...]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["image"]].append(row)

    output = []
    for image, image_rows in sorted(grouped.items()):
        item: dict[str, object] = {
            "image": image,
            "qp_points": len(image_rows),
            "bpp_mean": _mean(image_rows, "bpp"),
            "bitstream_bytes_mean": _mean(image_rows, "bitstream_bytes"),
        }
        for metric in metrics:
            item[f"{metric}_mean"] = _mean(image_rows, metric)
        output.append(item)
    return output


def render_qp_charts(rows: list[dict[str, str]], output_dir: Path, metrics: tuple[str, ...]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["image"]].append(row)

    for image, image_rows in sorted(grouped.items()):
        image_dir = output_dir / _safe_name(image)
        image_dir.mkdir(parents=True, exist_ok=True)
        for metric in metrics:
            points = sorted(
                [{"qp": int(row["qp"]), "quality": f(row, metric)} for row in image_rows],
                key=lambda point: int(point["qp"]),
            )
            _render_single_mode_chart(image, metric, points, image_dir / f"qp_{metric}.png")


def build_readme(output: Path, datasets: tuple[tuple[str, str, tuple[str, ...]], ...] = DATASETS, partition_qp: int | None = None) -> str:
    _ = partition_qp
    lines = [
        "# VTM Scaling List Study",
        "",
        "This study isolates the built-in VTM 23.0 default scaling-list mode: `--ScalingList=1`.",
        "It uses only `baboon`, `goldhill`, and `peppers` in the standard grayscale and standard color datasets.",
        "",
        "The main goal is to inspect the behavior of the partitioning scheme as QP changes when the VTM default scaling-list mechanism is explicitly enabled.",
        "",
        "## Reproduce",
        "",
        "```powershell",
        "python tools\\research\\run_vtm_scaling_list_study.py --clean",
        "python tools\\reporting\\report_vtm_scaling_list_study.py",
        "```",
        "",
        "The runner writes long intermediate codec output under `results/vtm_scaling_list_study/`. This README and compact artifacts are stored under `docs/vtm_scaling_list_study/`.",
        "",
    ]

    for dataset, title, metrics in datasets:
        dataset_dir = output / dataset
        metrics_csv = dataset_dir / "image_metrics.csv"
        metric_rows = read_rows(metrics_csv) if metrics_csv.exists() else []
        metric_groups = _rows_by_image(metric_rows)
        partition_groups = _partition_rows_by_image(output / "partition_overlays" / dataset / "summary.csv")
        lines.extend([f"## {title}", ""])
        if not metric_rows:
            lines.extend(["Metrics are not generated yet.", ""])
            continue

        lines.extend(
            [
                f"Metrics CSV: [`{dataset}/image_metrics.csv`]({dataset}/image_metrics.csv)",
                f"Partition CSV: [`partition_overlays/{dataset}/summary.csv`](partition_overlays/{dataset}/summary.csv)",
                "",
            ]
        )

        for image in _ordered_images(metric_groups):
            image_rows = metric_groups[image]
            partition_rows = partition_groups.get(image, [])
            chart_cells = [
                f'**{METRIC_CHART_LABELS.get(metric, metric)}**<br><img src="{dataset}/qp_charts/{_safe_name(image)}/qp_{metric}.png" width="330">'
                for metric in metrics
            ]
            lines.extend(
                [
                    f"### {image.title()}",
                    "",
                    "Mode: VTM 23.0 `--ScalingList=1`.",
                    "",
                    "Metric values by QP:",
                    "",
                    *_markdown_table(
                        ["QP", "BPP", "Bitstream bytes", *[METRIC_LABELS.get(metric, metric) for metric in metrics]],
                        _metric_rows(image_rows, metrics),
                    ),
                    "",
                ]
            )

            if partition_rows:
                lines.extend(
                    [
                        "CU partition statistics by QP:",
                        "",
                        *_markdown_table(
                            ["QP", "CU count", "Min area", "Max area", "Mean area", "Dominant CU sizes"],
                            _partition_table_rows(partition_rows),
                        ),
                        "",
                    ]
                )

            lines.extend(
                [
                    "QP metric curves:",
                    "",
                    *_markdown_table(["QP chart", "QP chart"], _pair_cells(chart_cells)),
                    "",
                    "CU partition-map overlays:",
                    "",
                    *_markdown_table(["Overlay", "Overlay"], _pair_cells(_overlay_cells(output, dataset, image))),
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def _render_single_mode_chart(image: str, metric: str, points: list[dict[str, float | int]], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    qps = [int(point["qp"]) for point in points]
    values = [float(point["quality"]) for point in points]
    fig, ax = plt.subplots(figsize=(7.2, 4.0), dpi=120)
    ax.plot(qps, values, color="#0072B2", linewidth=2.4, marker="o", markersize=5)
    ax.set_title(f"{image}: {METRIC_CHART_LABELS.get(metric, metric)} vs QP", fontsize=11)
    ax.set_xlabel("QP")
    ax.set_ylabel(METRIC_CHART_LABELS.get(metric, metric))
    ax.set_xticks(qps)
    ax.grid(True, color="#d1d5db", linewidth=0.7, alpha=0.8)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output)
    plt.close(fig)


def _rows_by_image(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["image"]].append(row)
    return {image: sorted(items, key=lambda item: int(item["qp"])) for image, items in grouped.items()}


def _partition_rows_by_image(summary_csv: Path) -> dict[str, list[dict[str, str]]]:
    if not summary_csv.exists():
        return {}
    with summary_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return _rows_by_image(rows)


def _ordered_images(groups: dict[str, list[dict[str, str]]]) -> list[str]:
    known = [image for image in DEFAULT_REPORT_IMAGES if image in groups]
    extra = sorted(image for image in groups if image not in DEFAULT_REPORT_IMAGES)
    return known + extra


def _metric_rows(rows: list[dict[str, str]], metrics: tuple[str, ...]) -> list[list[str]]:
    output = []
    for row in rows:
        output.append(
            [
                str(int(row["qp"])),
                _fmt(row["bpp"], 4),
                str(int(float(row["bitstream_bytes"]))),
                *[_metric_fmt(row.get(metric, "")) for metric in metrics],
            ]
        )
    return output


def _partition_table_rows(rows: list[dict[str, str]]) -> list[list[str]]:
    return [
        [
            str(int(row["qp"])),
            str(int(float(row["cu_count"]))),
            str(int(float(row["min_area"]))),
            str(int(float(row["max_area"]))),
            _fmt(row["avg_area"], 2),
            row["dominant_sizes"],
        ]
        for row in rows
    ]


def _overlay_cells(output: Path, dataset: str, image: str) -> list[str]:
    cells = []
    overlay_root = output / "partition_overlays" / dataset
    for qp_dir in sorted(overlay_root.glob("QP*"), key=lambda path: int(path.name.removeprefix("QP"))):
        overlay = qp_dir / f"{image}_scalinglist_default.png"
        if overlay.exists():
            qp = qp_dir.name.removeprefix("QP")
            cells.append(f'**QP {qp}**<br><img src="partition_overlays/{dataset}/QP{qp}/{image}_scalinglist_default.png" width="300">')
    return cells


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(row) + " |" for row in rows],
    ]


def _pair_cells(cells: list[str]) -> list[list[str]]:
    return [[cells[index], cells[index + 1] if index + 1 < len(cells) else ""] for index in range(0, len(cells), 2)]


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)


def _mean(rows: list[dict[str, str]], key: str) -> float:
    values = [float(row[key]) for row in rows]
    return sum(values) / len(values) if values else 0.0


def _fmt(value: object, digits: int) -> str:
    return f"{float(value):.{digits}f}"


def _metric_fmt(value: object) -> str:
    if value in ("", None):
        return ""
    number = float(value)
    return f"{number:.6f}" if abs(number) <= 1.0 else f"{number:.3f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render README and PNG QP charts for the VTM --ScalingList=1 study.")
    parser.add_argument("--results", type=Path, default=Path("results/vtm_scaling_list_study"))
    parser.add_argument("--output", type=Path, default=Path("docs/vtm_scaling_list_study"))
    parser.add_argument("--partition-qp", type=int, default=32)
    args = parser.parse_args()

    for dataset, _title, metrics in DATASETS:
        metrics_csv = args.results / dataset / "image_metrics.csv"
        if metrics_csv.exists():
            write_dataset_report(metrics_csv, args.output / dataset, metrics)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "README.md").write_text(build_readme(args.output, DATASETS, args.partition_qp), encoding="utf-8", newline="\n")
    print(f"Wrote {args.output / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
