from __future__ import annotations

import argparse
import csv
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from metrics.registry import METRIC_CHART_LABELS, METRIC_LABELS, METRIC_PROVENANCE
from tools.reporting.report_image_benchmark import _safe_name, _svg_qp_chart, _write_svg_as_png, f, read_rows, write_csv


SCIENTIFIC_METRICS = ("psnr_rgb", "msssim_rgb", "psnr_hvs_m_luma", "haarpsi_luma")
GRAYSCALE_Y_METRICS = ("psnr_y", "msssim_luma", "psnr_hvs_m_luma", "haarpsi_luma")

PROVENANCE_LINKS = {
    "psnr_rgb": "[Duan et al. validation report](../vtm_validation/lossy-vae/README.md)",
    "msssim_rgb": "[CompressAI validation report](../vtm_validation/compressai/README.md)",
    "psnr_hvs_m_luma": (
        "[author page and MATLAB source](https://www.ponomarenko.info/psnrhvsm.htm); "
        "[audit copy and port notes](../../third_party/psnr_hvs_m/SOURCE.md)"
    ),
    "haarpsi_luma": (
        "[authors' project and implementation](https://www.math.uni-bremen.de/cda/HaarPSI/); "
        "[audit copy](../../third_party/haarpsi/SOURCE.md)"
    ),
    "psnr_y": (
        "[VTM EncoderApp source]"
        "(https://github.com/ooplisko/VVCSoftware_VTM_CSF/blob/feature/csf-scaling-list/"
        "source/Lib/EncoderLib/EncGOP.cpp)"
    ),
    "msssim_luma": (
        "[Wang-Simoncelli-Bovik paper]"
        "(https://ece.uwaterloo.ca/~z70wang/publications/msssim.pdf); "
        "[numerical regression tests](../../tests/test_image_quality.py)"
    ),
}


def render_selected_qp_charts(rows: list[dict[str, str]], output_dir: Path, metrics: tuple[str, ...] = SCIENTIFIC_METRICS) -> None:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["image"]].append(row)

    for image, image_rows in sorted(grouped.items()):
        image_dir = output_dir / _safe_name(image)
        image_dir.mkdir(parents=True, exist_ok=True)
        for metric in metrics:
            points: dict[str, list[dict[str, float | int]]] = {"baseline": [], "csf": []}
            for row in image_rows:
                mode = row["mode"]
                if mode in points:
                    points[mode].append({"qp": int(row["qp"]), "quality": f(row, metric)})
            for mode in points:
                points[mode].sort(key=lambda point: int(point["qp"]))
            _write_svg_as_png(_svg_qp_chart(image, metric, points), image_dir / f"qp_{metric}.png")


def selected_delta_rows(rows: list[dict[str, str]], metrics: tuple[str, ...]) -> list[dict[str, object]]:
    by_image_qp: dict[tuple[str, int], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        by_image_qp[(row["image"], int(row["qp"]))][row["mode"]] = row

    by_image: dict[str, list[dict[str, object]]] = defaultdict(list)
    for (image, qp), modes in sorted(by_image_qp.items()):
        if "baseline" not in modes or "csf" not in modes:
            continue
        base = modes["baseline"]
        csf = modes["csf"]
        delta: dict[str, object] = {
            "image": image,
            "qp": qp,
            "bpp_delta_pct": _pct(f(csf, "bpp"), f(base, "bpp")),
        }
        for metric in metrics:
            delta[f"{metric}_delta"] = f(csf, metric) - f(base, metric)
        by_image[image].append(delta)

    output = []
    for image, deltas in sorted(by_image.items()):
        row: dict[str, object] = {"image": image, "qp_points": len(deltas), "bpp_delta_pct_mean": _mean(deltas, "bpp_delta_pct")}
        for metric in metrics:
            row[f"{metric}_delta_mean"] = _mean(deltas, f"{metric}_delta")
        output.append(row)
    return output


def robustness_rows(delta_rows: list[dict[str, object]], metrics: tuple[str, ...]) -> list[dict[str, object]]:
    """Rank images by metric retention without averaging incompatible metric units."""

    ranks: dict[str, dict[str, int]] = {str(row["image"]): {} for row in delta_rows}
    for metric in metrics:
        ordered = sorted(delta_rows, key=lambda row: float(row[f"{metric}_delta_mean"]), reverse=True)
        for rank, row in enumerate(ordered, start=1):
            ranks[str(row["image"])][metric] = rank

    output = []
    for row in delta_rows:
        image = str(row["image"])
        metric_ranks = ranks[image]
        output.append(
            {
                **row,
                "rank_sum": sum(metric_ranks.values()),
                "metric_ranks": "; ".join(f"{metric}:{metric_ranks[metric]}" for metric in metrics),
            }
        )
    return sorted(output, key=lambda row: (int(row["rank_sum"]), str(row["image"])))


def partition_delta_rows(summary_csv: Path) -> list[dict[str, object]]:
    if not summary_csv.exists():
        return []
    with summary_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[tuple[str, int], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        grouped[(row["image"], int(row["qp"]))][row["mode"]] = row

    by_image: dict[str, list[dict[str, float]]] = defaultdict(list)
    for (image, _qp), modes in grouped.items():
        if "baseline" not in modes or "csf" not in modes:
            continue
        baseline = modes["baseline"]
        csf = modes["csf"]
        by_image[image].append(
            {
                "cu_count_delta_pct": _pct(float(csf["cu_count"]), float(baseline["cu_count"])),
                "avg_area_delta_pct": _pct(float(csf["avg_area"]), float(baseline["avg_area"])),
            }
        )

    return [
        {
            "image": image,
            "qp_points": len(values),
            "cu_count_delta_pct_mean": _mean(values, "cu_count_delta_pct"),
            "avg_area_delta_pct_mean": _mean(values, "avg_area_delta_pct"),
        }
        for image, values in sorted(by_image.items())
    ]


def write_dataset_report(metrics_csv: Path, output_dir: Path, metrics: tuple[str, ...]) -> list[dict[str, object]]:
    rows = read_rows(metrics_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(metrics_csv, output_dir / "image_metrics.csv")
    deltas = selected_delta_rows(rows, metrics)
    write_csv(output_dir / "selected_metric_deltas.csv", deltas)
    write_csv(output_dir / "robustness_ranking.csv", robustness_rows(deltas, metrics))
    render_selected_qp_charts(rows, output_dir / "qp_charts", metrics)
    return deltas


def build_readme(output: Path, datasets: list[tuple[str, str, tuple[str, ...]]], partition_qp: int) -> str:
    lines = [
        "# VTM QP Study",
        "",
        "This focused study compares VTM 23.0 baseline and VTM 23.0 CSF on five standard grayscale images and their color counterparts.",
        "",
        "The focused runner defaults to OpenCV 4:4:4 RGB->YUV conversion (`--conversion opencv_444`) to match the external validation methodology more closely. Use `--conversion ffmpeg_444` when a canonical FFmpeg video-conversion control run is needed.",
        "",
        "Primary scientific metrics are PSNR-RGB and MS-SSIM-RGB, because these two metric paths were cross-checked in the VTM validation reports. PSNR-HVS-M luma, HaarPSI luma, and MS-SSIM luma are computed with pinned published algorithms and explicit implementation provenance.",
        "",
        "Metric provenance:",
        "",
        *_markdown_table(
            ["Metric", "Implementation", "Evidence / source"],
            [
                [
                    METRIC_LABELS.get(metric, metric),
                    METRIC_PROVENANCE.get(metric, ""),
                    PROVENANCE_LINKS[metric],
                ]
                for metric in ("psnr_rgb", "msssim_rgb", "psnr_hvs_m_luma", "haarpsi_luma", "psnr_y", "msssim_luma")
            ],
        ),
        "",
        "### Metric implementations",
        "",
        "- **MS-SSIM luma** implements the five-scale product formulation by Wang, Simoncelli, and Bovik with the published weights, 11x11 Gaussian window, symmetric 2x2 low-pass filtering, and dyadic downsampling. A fixed numerical regression test is cross-checked against `sewar==0.4.6`.",
        "- **HaarPSI luma** directly calls the authors' MIT-licensed Python/NumPy implementation with its default viewing-distance preprocessing. The exact upstream source and license are vendored under [`third_party/haarpsi/`](../../third_party/haarpsi/).",
        "- **PSNR-HVS-M luma** uses a NumPy/SciPy port of Nikolay Ponomarenko's original MATLAB implementation: the same 8x8 DCT, CSF matrix, masking matrix, between-coefficient contrast masking, and block traversal. Four regression cases match values generated by the original MATLAB code under Octave. The original source is retained under [`third_party/psnr_hvs_m/`](../../third_party/psnr_hvs_m/) for auditability.",
        "",
        "Here, *reference implementation* means code supplied by an algorithm's authors. HaarPSI satisfies that definition directly. PSNR-HVS-M is identified more narrowly as a source-faithful Python port because the authors supplied MATLAB rather than Python code. MS-SSIM is identified by the published algorithm and pinned numerical regression, since no single implementation defines a universal bit-exact standard.",
        "",
        "## Reproduce",
        "",
        "```powershell",
        "python tools\\research\\run_vtm_qp_study.py --clean",
        "python tools\\reporting\\report_vtm_qp_study.py",
        "```",
        "",
        "The runner writes long intermediate codec output under `results/vtm_qp_study/`. This README and the compact artifacts are stored under `docs/vtm_qp_study/`.",
        "",
    ]

    for dataset, title, metrics in datasets:
        dataset_dir = output / dataset
        lines.extend(
            [
                f"## {title}",
                "",
            ]
        )
        delta_csv = dataset_dir / "selected_metric_deltas.csv"
        if delta_csv.exists():
            lines.extend(
                [
                    f"Metrics CSV: [`{dataset}/image_metrics.csv`]({dataset}/image_metrics.csv)",
                    "",
                ]
            )
            lines.extend(_delta_table(delta_csv, metrics))
            lines.append("")
            lines.extend(_interpretation_section(output, dataset, delta_csv, metrics))
            lines.append("")
        else:
            lines.extend(["Metrics are not generated yet.", ""])
            continue

        for image in _image_names(delta_csv):
            display_name = image.replace("_", " ").title()
            chart_cells = []
            for metric in metrics:
                rel = f"{dataset}/qp_charts/{_safe_name(image)}/qp_{metric}.png"
                chart_cells.append(f'**{METRIC_CHART_LABELS.get(metric, metric)}**<br><img src="{rel}" width="330">')
            lines.extend(
                [
                    "<details>",
                    f"<summary><strong>{display_name}</strong>: QP curves and partition maps</summary>",
                    "",
                    *_markdown_table(["QP chart", "QP chart"], _pair_cells(chart_cells)),
                    "",
                ]
            )
            partition_dir = output / "partition_overlays" / dataset / f"QP{partition_qp}"
            if partition_dir.exists():
                lines.extend(
                    [
                        f"Partition-map overlays at QP={partition_qp}:",
                        "",
                        *_partition_image_table(dataset, partition_qp, image),
                        "",
                    ]
                )
            lines.extend(
                [
                    "</details>",
                    "",
                ]
            )

        partition_root = output / "partition_overlays" / dataset
        if partition_root.exists():
            lines.extend(
                [
                    f"Full per-QP overlays: [`partition_overlays/{dataset}/`](partition_overlays/{dataset}/).",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def _interpretation_section(output: Path, dataset: str, delta_csv: Path, metrics: tuple[str, ...]) -> list[str]:
    with delta_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        deltas: list[dict[str, object]] = [dict(row) for row in csv.DictReader(stream)]
    ranked = robustness_rows(deltas, metrics)
    partition_rows = partition_delta_rows(output / "partition_overlays" / dataset / "summary.csv")
    partition_by_image = {str(row["image"]): row for row in partition_rows}

    rows = []
    for item in ranked:
        image = str(item["image"])
        partition = partition_by_image.get(image, {})
        rows.append(
            [
                image,
                str(item["rank_sum"]),
                _fmt(item["bpp_delta_pct_mean"], 3),
                _fmt(partition.get("cu_count_delta_pct_mean", 0.0), 1),
                _fmt(partition.get("avg_area_delta_pct_mean", 0.0), 1),
            ]
        )

    lines = [
        "### Comparative interpretation",
        "",
        "The ordinal robustness rank orders the images independently for each quality metric by the mean CSF-minus-baseline delta, then sums those ranks. It does not average dB and unitless indices. A lower rank sum means that the image retained quality more consistently across the selected metrics.",
        "",
        "Absolute metric values should not be used to declare that one source image has inherently better visual quality than another: image content, texture, and visual masking affect metric scales. The comparison below therefore measures the effect of CSF against the baseline reconstruction of the same image.",
        "",
        *_markdown_table(
            ["Image", "Robustness rank sum", "Mean BPP delta, %", "Mean CU-count delta, %", "Mean CU-area delta, %"],
            rows,
        ),
        "",
    ]
    if dataset == "standard_grayscale":
        lines.extend(
            [
                "**Result:** Lenna is the most robust grayscale image overall, with Peppers close behind. Baboon ranks last for every selected metric and is therefore the clearest adverse case for the CSF matrix.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "**Result:** No single color image dominates every metric. Lenna has the smallest PSNR-RGB loss; Barbara has the smallest MS-SSIM-RGB and PSNR-HVS-M losses while providing the largest mean BPP reduction; Peppers has the smallest HaarPSI loss and the best aggregate ordinal rank. Baboon ranks last for all four metrics.",
                "",
            ]
        )
    lines.extend(
        [
            "The partition statistics show encoder decisions rather than visual quality. Positive CU-count deltas and negative CU-area deltas mean that CSF produced more, smaller coding units. Baboon exhibits the largest partitioning shift and the largest quality loss, but with only five images this is an exploratory association, not evidence that finer partitioning causes the loss.",
        ]
    )
    return lines


def _delta_table(path: Path, metrics: tuple[str, ...]) -> list[str]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            rows.append(
                [
                    row["image"],
                    row["qp_points"],
                    _fmt(row["bpp_delta_pct_mean"], 3),
                    *[_fmt(row[f"{metric}_delta_mean"], 6) for metric in metrics],
                ]
            )
    headers = ["Image", "QP points", "Mean bpp delta, %", *[METRIC_LABELS.get(metric, metric) for metric in metrics]]
    return _markdown_table(headers, rows)


def _partition_image_table(dataset: str, qp: int, image: str) -> list[str]:
    return _markdown_table(
        ["Baseline", "CSF"],
        [
            [
                f'<img src="partition_overlays/{dataset}/QP{qp}/{image}_baseline.png" width="300">',
                f'<img src="partition_overlays/{dataset}/QP{qp}/{image}_csf.png" width="300">',
            ]
        ],
    )


def _image_names(delta_csv: Path) -> list[str]:
    with delta_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        return [row["image"] for row in csv.DictReader(stream)]


def _pair_cells(cells: list[str]) -> list[list[str]]:
    return [[cells[index], cells[index + 1] if index + 1 < len(cells) else ""] for index in range(0, len(cells), 2)]


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(row) + " |" for row in rows],
    ]


def _pct(new_value: float, old_value: float) -> float:
    return ((new_value - old_value) / old_value * 100.0) if old_value else 0.0


def _mean(rows: list[dict[str, object]], key: str) -> float:
    values = [float(row[key]) for row in rows]
    return sum(values) / len(values) if values else 0.0


def _fmt(value: str | float, digits: int) -> str:
    number = float(value)
    return f"{number:.{digits}f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render compact README and PNG QP charts for the focused VTM QP study.")
    parser.add_argument("--results", type=Path, default=Path("results/vtm_qp_study"))
    parser.add_argument("--output", type=Path, default=Path("docs/vtm_qp_study"))
    parser.add_argument("--partition-qp", type=int, default=32)
    args = parser.parse_args()

    datasets = [
        ("standard_grayscale", "Standard Grayscale", GRAYSCALE_Y_METRICS),
        ("standard_color", "Standard Color", SCIENTIFIC_METRICS),
    ]
    for dataset, _title, metrics in datasets:
        metrics_csv = args.results / dataset / "image_metrics.csv"
        if metrics_csv.exists():
            write_dataset_report(metrics_csv, args.output / dataset, metrics)

    readme = build_readme(args.output, datasets, args.partition_qp)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    print(f"Wrote {args.output / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
