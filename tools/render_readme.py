from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
REPORT = ROOT / "docs/image_benchmark_report.md"

logger = logging.getLogger(__name__)

DATASETS = [
    ("standard_grayscale", "Standard grayscale", "image_sets/standard_grayscale/png"),
    ("synthetic", "Synthetic", "image_sets/synthetic/png"),
    ("kodak", "Kodak", "image_sets/kodak/png"),
]

from metrics.registry import CHARTS, METRIC_COLUMNS, METRIC_LABELS, METRICS


def read_csv(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def fmt(value: str, digits: int = 6) -> str:
    number = float(value)
    if abs(number) < 0.000001 and number != 0:
        return f"{number:.3e}"
    return f"{number:.{digits}f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def details(summary: str, body: list[str]) -> list[str]:
    return [
        f"<details>",
        f"<summary>{summary}</summary>",
        "",
        *body,
        "",
        "</details>",
    ]


def rel(path: str, from_docs: bool = False) -> str:
    return f"../{path}" if from_docs else path


def dataset_image_order() -> dict[str, tuple[int, int, str, str]]:
    order: dict[str, tuple[int, int, str, str]] = {}
    for dataset_index, (dataset, title, image_dir) in enumerate(DATASETS):
        for image_index, image in enumerate(sorted((ROOT / image_dir).glob("*.png"))):
            order[image.stem] = (dataset_index, image_index, dataset, title)
    return order


def metric_summary_table(path: str) -> list[str]:
    rows = read_csv(path)
    return markdown_table(
        ["Metric", "Mean", "Min", "Max"],
        [[row["metric"], fmt(row["mean"]), fmt(row["min"]), fmt(row["max"])] for row in rows],
    )


def bd_rate_summary_table(path: str) -> list[str]:
    rows = read_csv(path)
    return markdown_table(
        ["Metric", "Valid images", "BD-Rate mean, %", "BD-Rate min, %", "BD-Rate max, %", "BD quality mean"],
        [
            [
                METRIC_LABELS.get(row["metric"], row["metric"]),
                row["valid_images"],
                fmt(row["bd_rate_pct_mean"], 3) if row["bd_rate_pct_mean"] else "",
                fmt(row["bd_rate_pct_min"], 3) if row["bd_rate_pct_min"] else "",
                fmt(row["bd_rate_pct_max"], 3) if row["bd_rate_pct_max"] else "",
                fmt(row["bd_psnr_delta_mean"], 6) if row["bd_psnr_delta_mean"] else "",
            ]
            for row in rows
        ],
    )


def bd_rate_per_image_table() -> list[str]:
    rows = read_csv("docs/image_benchmark/combined/bd_rate_by_image.csv")
    order = dataset_image_order()
    data: dict[str, dict[str, str]] = {}
    for row in rows:
        img = row["image"]
        metric = row["metric"]
        val = row["bd_rate_pct"]
        data.setdefault(img, {})[metric] = val
    table_rows = []
    for img in sorted(data.keys(), key=lambda name: order.get(name, (999, 999, "", ""))[:2]):
        _dataset_index, _image_index, _dataset, dataset_title = order.get(img, (999, 999, "unknown", "Unknown"))
        img_metrics = data[img]
        row_vals = [
            dataset_title,
            img,
            *[fmt(img_metrics.get(m, ""), 3) if img_metrics.get(m, "") else "" for m in METRICS]
        ]
        table_rows.append(row_vals)
    return markdown_table(
        [
            "Dataset",
            "Image",
            *[f"{METRIC_LABELS[m]}, %" for m in METRICS],
        ],
        table_rows,
    )


def per_image_table() -> list[str]:
    rows = read_csv("docs/image_benchmark/combined/per_image_summary.csv")
    order = dataset_image_order()
    table_rows = []
    for row in sorted(rows, key=lambda item: order.get(item["image"], (999, 999, "", ""))[:2]):
        _dataset_index, _image_index, _dataset, dataset_title = order.get(row["image"], (999, 999, "unknown", "Unknown"))
        table_rows.append(
            [
                dataset_title,
                row["image"],
                fmt(row["bpp_delta_pct_mean"], 2),
                fmt(row["compression_ratio_delta_pct_mean"], 2),
                *[fmt(row[key], 6 if "luma" in key or "ssim" in key else 3) for key, _label in METRIC_COLUMNS],
            ]
        )
    return markdown_table(
        [
            "Dataset",
            "Image",
            "bpp CSF vs base, %",
            "Compression ratio CSF vs base, %",
            *[label for _key, label in METRIC_COLUMNS],
        ],
        table_rows,
    )


def chart_grid(from_docs: bool = False) -> list[str]:
    rows = []
    for index in range(0, len(CHARTS), 2):
        left = CHARTS[index]
        right = CHARTS[index + 1] if index + 1 < len(CHARTS) else ("", "")
        rows.append(
            [
                f'**{left[0]}**<br><img src="{rel(left[1], from_docs)}" width="360">',
                f'**{right[0]}**<br><img src="{rel(right[1], from_docs)}" width="360">' if right[0] else "",
            ]
        )
    return markdown_table(["Chart", "Chart"], rows)


def qp_chart_grid(dataset: str, image: str, from_docs: bool = False) -> list[str]:
    rows = []
    for index in range(0, len(CHARTS), 2):
        left_label, left_path = CHARTS[index]
        right_label, right_path = CHARTS[index + 1] if index + 1 < len(CHARTS) else ("", "")
        left_metric = Path(left_path).stem.removeprefix("rd_")
        right_metric = Path(right_path).stem.removeprefix("rd_") if right_label else ""
        rows.append(
            [
                f'**{left_label}**<br><img src="{rel(f"docs/image_benchmark/{dataset}/qp_charts/{image}/qp_{left_metric}.svg", from_docs)}" width="360">',
                f'**{right_label}**<br><img src="{rel(f"docs/image_benchmark/{dataset}/qp_charts/{image}/qp_{right_metric}.svg", from_docs)}" width="360">' if right_label else "",
            ]
        )
    return markdown_table(["Metric vs QP", "Metric vs QP"], rows)


def standard_grayscale_qp_sections(from_docs: bool = False) -> list[str]:
    sections: list[str] = []
    for image in sorted((ROOT / "image_sets/standard_grayscale/png").glob("*.png")):
        sections.extend([f"### {image.stem}", "", *qp_chart_grid("standard_grayscale", image.stem, from_docs), ""])
    return sections


def partition_summary_table(dataset: str) -> list[str]:
    rows = read_csv(f"docs/partition_maps/{dataset}/summary.csv")
    by_image: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        by_image.setdefault(row["image"], {})[row["mode"]] = row

    table_rows = []
    for image, modes in sorted(by_image.items()):
        baseline = modes["baseline"]
        csf = modes["csf"]
        baseline_count = int(baseline["cu_count"])
        csf_count = int(csf["cu_count"])
        delta = (csf_count - baseline_count) * 100.0 / baseline_count if baseline_count else 0.0
        table_rows.append(
            [
                image,
                f'{baseline["width"]}x{baseline["height"]}',
                str(baseline_count),
                str(csf_count),
                f"{delta:.2f}",
                baseline["dominant_sizes"],
                csf["dominant_sizes"],
            ]
        )
    return markdown_table(
        ["Image", "Size", "CU baseline", "CU CSF", "Delta, %", "Dominant baseline", "Dominant CSF"],
        table_rows,
    )


def partition_map_table(dataset: str, image_dir: str, from_docs: bool = False) -> list[str]:
    rows = []
    for image in sorted((ROOT / image_dir).glob("*.png")):
        name = image.stem
        rows.append(
            [
                name,
                f'<img src="{rel(f"{image_dir}/{image.name}", from_docs)}" width="180">',
                f'<img src="{rel(f"docs/partition_maps/{dataset}/{name}_baseline.svg", from_docs)}" width="240">',
                f'<img src="{rel(f"docs/partition_maps/{dataset}/{name}_csf.svg", from_docs)}" width="240">',
            ]
        )
    return markdown_table(["Image", "Original", "Baseline", "CSF"], rows)


def build_readme() -> str:
    lines: list[str] = [
        "# VVenC CSF Image Benchmark",
        "",
        '<p align="center">',
        '  <a href="https://github.com/For2natop1ua/vvenc_csf_tests/blob/master/LICENSE">',
        '    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license">',
        "  </a>",
        '  <a href="https://www.python.org/downloads/">',
        '    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">',
        "  </a>",
        '  <a href="https://github.com/For2natop1ua/vvenc_csf_tests/actions/workflows/build.yml">',
        '    <img src="https://github.com/For2natop1ua/vvenc_csf_tests/actions/workflows/build.yml/badge.svg" alt="Tests">',
        "  </a>",
        '  <a href="https://github.com/For2natop1ua/vvenc_csf_tests/actions">',
        '    <img src="https://img.shields.io/badge/build-validation-brightgreen" alt="Build validation">',
        "  </a>",
        '  <a href="https://github.com/For2natop1ua/vvenc_csf_tests/releases">',
        '    <img src="https://img.shields.io/badge/release-source%20package-blue" alt="Release package">',
        "  </a>",
        "</p>",
        "",
        '**O. O. Plisko** - [Department of Information and Communication Technologies](https://dict.khai.edu/), National Aerospace University "Kharkiv Aviation Institute"',
        "",
        "Image-only benchmark for a custom Contrast Sensitivity Function (CSF) scaling-list modification in VVenC. The repository contains pinned binaries, image sets, scripts, generated metric tables, RD charts, matrix evidence, and Coding Unit (CU) partition maps.",
        "",
        "## Status",
        "",
        *markdown_table(
            ["Item", "Current state"],
            [
                ["Primary control images", "5 standard grayscale images: BABOON, BARBARA, goldhill, lenna, peppers"],
                ["Additional images", "4 synthetic images and 24 Kodak images"],
                ["QP points", "22, 27, 32, 37"],
                ["Compared modes", "`vvenc_default` vs `vvenc_csf --CSFScalingList 1` (`.exe` suffix on Windows)"],
                ["Neutral value check", "`16` verified from VVenC source and by a practical CSF-off control run"],
                ["Current outcome", "CSF bitstreams decode correctly and reconstruction checks pass, but the current CSF matrix does not outperform the default encoder on average"],
            ],
        ),
        "",
        "## Documentation",
        "",
        *markdown_table(
            ["Document", "Content"],
            [
                ["[Full benchmark report](docs/image_benchmark_report.md)", "Binaries, matrices, reproduce steps, metrics, tables, charts, and partition maps"],
                ["[Neutral 16 source verification](docs/matrices/neutral_16_verification.md)", "Why scaling-list value `16` is neutral in the current VVenC code"],
                ["[Neutral 16 control run](docs/matrices/neutral_16_control.md)", "Default encoder vs CSF encoder with `--CSFScalingList 0`, compared byte-for-byte"],
                ["[Combined metrics CSV](docs/image_benchmark/combined_image_metrics.csv)", "All image/QP/mode measurements"],
                ["[BD-Rate summary CSV](docs/image_benchmark/combined/bd_rate_summary.csv)", "Equal-quality bitrate comparison between baseline and CSF"],
                ["[Partition summary CSV](docs/partition_maps/summary.csv)", "CU counts and dominant block sizes"],
                ["[Citation metadata](CITATION.cff)", "Citation information for academic use"],
            ],
        ),
        "",
        "## Repository Layout",
        "",
        *markdown_table(
            ["Path", "Purpose"],
            [
                ["`binaries/`", "Encoder and decoder binaries used by the benchmark; see `binaries/README.md`"],
                ["`image_sets/`", "Primary grayscale, synthetic, and Kodak inputs; see `image_sets/README.md`"],
                ["`configs/`", "INI defaults for benchmark paths, binaries, QP points, and smoke settings"],
                ["`run_all.py`", "Image-only orchestrator for smoke checks, neutral-value checks, benchmark runs, and report regeneration"],
                ["`vvenc_csf/`", "Reusable benchmark, encoding, neutral-value, and shared command-running classes"],
                ["`tools/`", "Thin CLI wrappers for dataset, benchmark, report, matrix, and partition-map utilities"],
                ["`metrics/`", "Local visual-quality metric implementations"],
                ["`tests/`", "Fast unit tests for helpers, command construction, config loading, and report builders"],
                ["`docs/`", "Generated evidence, tables, charts, and detailed reports"],
            ],
        ),
        "",
        "## Library API",
        "",
        "The project exposes a Python library in `vvenc_csf/` and `metrics/` that can be imported to run custom benchmarks or extract metric calculations.",
        "",
        *markdown_table(
            ["Class/Function", "Module", "Description"],
            [
                ["`CommandRunner`", "`vvenc_csf.core`", "Executes subprocesses and handles logging"],
                ["`EncoderRunner`", "`vvenc_csf.encoding`", "Runs VVenC with typed parameter objects"],
                ["`bd_rate()`", "`metrics.bd_rate`", "Bjontegaard delta bitrate calculation"],
            ],
        ),
        "",
        "## Quick Start",
        "",
        "```powershell",
        "py -3 -m venv .venv",
        ".\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt",
        ".\\.venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt",
        ".\\.venv\\Scripts\\python.exe run_all.py quick --clean",
        "```",
        "",
        "`ffmpeg`, `ffprobe`, and `curl` must be available in `PATH`. On Windows, `curl.exe` is used automatically. The `.venv` and `results/` directories are local and are not committed. `quick` runs console sanity checks: smoke encode/decode and neutral-16 verification. `full` runs all image benchmarks and regenerates CSV/XLSX reports, charts, partition maps, and Markdown documentation.",
        "",
        "Benchmark defaults are stored in `configs/image_benchmark.ini`. Binary paths are configured without a file suffix; the scripts add `.exe` on Windows and use suffixless names on Linux/macOS. Command-line arguments still override the config values.",
        "",
        *details(
            "Full reproduction commands",
            [
                "```powershell",
                ".\\.venv\\Scripts\\python.exe run_all.py full --clean",
                "```",
            ],
        ),
        "",
        "## Run vs Re-render",
        "",
        *markdown_table(
            ["Task", "Command", "What it does"],
            [
                ["Quick validation", "`.\\.venv\\Scripts\\python.exe run_all.py quick --clean`", "Runs smoke encode/decode and neutral-16 checks"],
                ["Full run", "`.\\.venv\\Scripts\\python.exe run_all.py full --clean`", "Runs encoders, decoder checks, metrics, CSV/XLSX summaries, charts, partition maps, and Markdown rendering"],
                ["Re-render reports only", "`.\\.venv\\Scripts\\python.exe tools\\report_image_benchmark.py docs\\image_benchmark\\combined_image_metrics.csv --output docs\\image_benchmark\\combined --xlsx`", "Regenerates summary CSVs, XLSX, RD charts, and per-image QP charts from an existing metrics CSV"],
                ["Re-render README/report", "`.\\.venv\\Scripts\\python.exe tools\\render_readme.py`", "Rebuilds README and the detailed benchmark report from existing docs artifacts"],
                ["Run unit tests", "`.\\.venv\\Scripts\\python.exe -m pytest -q`", "Runs the fast test suite used by CI"],
            ],
        ),
        "",
        "## Result Snapshot",
        "",
        "Same-QP and equal-bpp summaries are generated from `docs/image_benchmark/combined_image_metrics.csv`. Negative deltas mean the current CSF result is lower than the default encoder under the same comparison method.",
        "",
        *metric_summary_table("docs/image_benchmark/combined/same_qp_summary.csv"),
        "",
        "BD-Rate is generated from the same metrics CSV and compares CSF against baseline at equal quality. Negative BD-Rate means bitrate saving by CSF; positive BD-Rate means extra bitrate is needed for the same metric level.",
        "",
        *bd_rate_summary_table("docs/image_benchmark/combined/bd_rate_summary.csv"),
        "",
        *details("Show BD-Rate per image", bd_rate_per_image_table()),
        "",
        *details(
            "RD charts",
            [
                "The charts are rendered by `tools/report_image_benchmark.py` from `docs/image_benchmark/combined_image_metrics.csv`. The x-axis is bitrate in bpp, and each y-axis is one quality metric averaged over the combined image set.",
                "",
                *chart_grid(),
            ],
        ),
        "",
        *details(
            "Standard grayscale metric-vs-QP charts",
            [
                "These charts are rendered from the `standard_grayscale` rows produced by `tools/image_csf_benchmark.py` and summarized by `tools/report_image_benchmark.py`. Each chart shows one measured metric as a function of QP for one image.",
                "",
                *standard_grayscale_qp_sections(),
            ],
        ),
        "",
        *details(
            "Standard grayscale partition maps",
            [
                "The maps are generated by `tools/build_partition_evidence.py` from VVenC `D_QP` traces at `QP=32`, `preset=medium`, and one encoded frame.",
                "",
                *partition_map_table("standard_grayscale", "image_sets/standard_grayscale/png"),
            ],
        ),
        "",
        "## How to Extend",
        "",
        "This benchmark is designed to be easily extensible. You can customize the image inputs or add new visual quality metrics.",
        "",
        "### Adding a Custom Image Set",
        "1. Create a subdirectory under `image_sets/` containing your input images in PNG format (e.g., `image_sets/custom_set/png/`).",
        "2. Update the paths in `configs/image_benchmark.ini` or pass your custom directory via the `--smoke-dir`, `--synthetic-dir`, or `--kodak-dir` CLI arguments when invoking `run_all.py`.",
        "",
        "### Adding a Custom Quality Metric",
        "1. Implement the luma metric calculation function in `metrics/image_quality.py`.",
        "2. Update the `calculate_luma_metrics()` function in `metrics/image_quality.py` to execute your new metric and append its score to the returned dictionary.",
        "3. Add a tuple with the metric's CSV key, short label, and chart label to `_METRIC_DEFS` in `metrics/registry.py`. All report scripts pick up the new metric automatically.",
        "",
        "## Conclusion",
        "",
        "The benchmark pipeline verifies three things: CSF bitstreams decode through VVdeC, encoder reconstructions match decoded output, and the neutral scaling-list value `16` behaves as the default no-op matrix value. Under the fixed image/QP conditions used here, the active CSF matrix shape does not show an average quality advantage over the default encoder.",
        "",
    ]
    return "\n".join(lines)


def build_report() -> str:
    lines: list[str] = [
        "# Image Benchmark Report",
        "",
        "This report expands the root README with the exact binaries, commands, CSV outputs, charts, and partition-map evidence used in the image benchmark. Standard grayscale images are listed first because they are the primary control set for this stage of the experiment.",
        "",
        "## Binaries",
        "",
        *markdown_table(
            ["File", "Purpose"],
            [
                ["`binaries/vvenc_default[.exe]`", "Clean upstream/default VVenC encoder without CSF. Local build from [fraunhoferhhi/vvenc](https://github.com/fraunhoferhhi/vvenc)"],
                ["`binaries/vvenc_csf[.exe]`", "Modified VVenC encoder. CSF is enabled with `--CSFScalingList 1`. Local build from the [CSF VVenC branch](https://github.com/For2natop1ua/vvenc/tree/feature-branch)"],
                ["`binaries/vvenc_default_trace[.exe]`", "Default encoder built with `VVENC_ENABLE_TRACING=ON` for partition maps only. Local build from [fraunhoferhhi/vvenc](https://github.com/fraunhoferhhi/vvenc)"],
                ["`binaries/vvenc_csf_trace[.exe]`", "CSF encoder built with `VVENC_ENABLE_TRACING=ON` for partition maps only. Local build from the [CSF VVenC branch](https://github.com/For2natop1ua/vvenc/tree/feature-branch)"],
                ["`binaries/vvdecapp[.exe]`", "VVdeC decoder used to verify bitstream decoding. Local build from [Fraunhofer HHI VVdeC](https://github.com/fraunhoferhhi/vvdec)"],
            ],
        ),
        "",
        "The repository currently stores Windows `.exe` binaries. On Linux/macOS, place suffixless binaries with the same stems in `binaries/`. The scripts select the platform-specific executable names automatically. More detail is available in [`binaries/README.md`](../binaries/README.md).",
        "",
        *details(
            "Default encoder rebuild commands",
            [
                "```powershell",
                "git clone https://github.com/fraunhoferhhi/vvenc ..\\vvenc_upstream",
                "cd ..\\vvenc_upstream",
                "git checkout 6f76748",
                "cmake -S . -B build\\release -G \"MinGW Makefiles\" -DCMAKE_BUILD_TYPE=Release -DVVENC_ENABLE_LINK_TIME_OPT=OFF",
                "cmake --build build\\release --target vvencFFapp --parallel 8",
                "Copy-Item bin\\release-static\\vvencFFapp.exe ..\\vvenc_csf_tests\\binaries\\vvenc_default.exe",
                "",
                "cmake -S . -B build\\trace -G \"MinGW Makefiles\" -DCMAKE_BUILD_TYPE=Release -DVVENC_ENABLE_TRACING=ON -DVVENC_ENABLE_LINK_TIME_OPT=OFF",
                "cmake --build build\\trace --target vvencFFapp --parallel 8",
                "Copy-Item bin\\release-static\\vvencFFapp.exe ..\\vvenc_csf_tests\\binaries\\vvenc_default_trace.exe",
                "```",
            ],
        ),
        "",
        "## Scaling Matrices",
        "",
        "Scaling matrices are defined in the encoder, not in this Python project. In the CSF branch, the base table is in `source/Lib/CommonLib/CSFWeights.h`; quant/dequant application is implemented in `source/Lib/CommonLib/Quant.cpp`.",
        "",
        "`docs/matrices/` stores CSV snapshots of the default and CSF matrices. These files do not drive the encoder. They record the numerical matrices used for analysis, comparison, and result verification.",
        "",
        *details(
            "Default and CSF 8x8 matrices",
            [
                "Default 8x8 matrix:",
                "",
                "```text",
                "16,16,16,16,16,16,16,16",
                "16,16,16,16,16,16,16,16",
                "16,16,16,16,16,16,16,16",
                "16,16,16,16,16,16,16,16",
                "16,16,16,16,16,16,16,16",
                "16,16,16,16,16,16,16,16",
                "16,16,16,16,16,16,16,16",
                "16,16,16,16,16,16,16,16",
                "```",
                "",
                "CSF 8x8 matrix:",
                "",
                "```text",
                "16,16,16,19,22,26,32,40",
                "16,16,17,20,24,30,38,48",
                "16,17,19,23,28,35,45,58",
                "19,20,23,28,34,43,56,72",
                "22,24,28,34,43,55,71,92",
                "26,30,35,43,55,71,92,119",
                "32,38,45,56,71,92,119,155",
                "40,48,58,72,92,119,155,200",
                "```",
            ],
        ),
        "",
        "For non-8x8 Transform Units (TU), the encoder maps the 8x8 CSF table to the active TU size. Square TUs use scaled indices up to `min(size, 8)`. Rectangular TUs use the longer side and `ratioH`/`ratioW` mapping to select coordinates from the base CSF table. Coefficients outside the zero-out threshold are written as zero, matching the standard scaling-list behavior.",
        "",
        "The current VVenC application binaries do not expose a `--ScalingListFile` option, so the VTM-style external scaling-list file check is not used in this project. The neutral value evidence is split into [source verification](matrices/neutral_16_verification.md) and a [practical control run](matrices/neutral_16_control.md).",
        "",
        "## Image Partitioning",
        "",
        "VVenC codes a picture through Coding Tree Units (CTU) and recursively selects CU partitions through rate-distortion search. The final partition structure is copied into the picture-level coding structure.",
        "",
        "```cpp",
        "partitioner->initCtu( area, CH_L, *cs.slice );",
        "xCompressCU( tempCS, bestCS, *partitioner );",
        "cs.useSubStructure( *bestCS, partitioner->chType, TREE_D,",
        "  CS::getArea( *bestCS, area, partitioner->chType, partitioner->treeType ) );",
        "```",
        "",
        "The maps in this repository come from the VVenC `D_QP` trace, not from a synthetic approximation. The trace records final luma CUs in `CABACWriter.cpp`:",
        "",
        "```cpp",
        "DTRACE_COND( ( isEncoding() ), g_trace_ctx, D_QP,",
        "  \"x=%d, y=%d, w=%d, h=%d, qp=%d\\n\",",
        "  cu.Y().x, cu.Y().y, cu.Y().width, cu.Y().height, cu.qp );",
        "```",
        "",
        "Baseline maps are generated with `vvenc_default_trace`; CSF maps are generated with `vvenc_csf_trace` (`.exe` suffix on Windows). Both binaries write final luma CU coordinates through the same `D_QP` trace, so a denser CSF map means the encoder selected more small CUs under the CSF configuration.",
        "",
        "## Reproducing the Run",
        "",
        "```powershell",
        "py -3 -m venv .venv",
        ".\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt",
        ".\\.venv\\Scripts\\python.exe run_all.py full --clean",
        "```",
        "",
        "## Experiment Conditions",
        "",
        *markdown_table(
            ["Parameter", "Value"],
            [
                ["Primary dataset", "5 standard grayscale images"],
                ["Additional datasets", "4 synthetic + 24 Kodak images"],
                ["Frames", "1 frame per image"],
                ["Encode pixel format", "`yuv420p`, 8-bit"],
                ["QP points", "22, 27, 32, 37"],
                ["Preset", "`medium`"],
                ["Baseline mode", "`vvenc_default`, without `--CSFScalingList` (`.exe` suffix on Windows)"],
                ["CSF mode", "`vvenc_csf --CSFScalingList 1` (`.exe` suffix on Windows)"],
                ["Decoder", "`vvdecapp` (`.exe` suffix on Windows)"],
            ],
        ),
        "",
        "The compression control parameter is `QP`. All other conditions are fixed. Compression ratio is computed per `image + QP + mode` point:",
        "",
        "```text",
        "raw_bytes = width * height * 3 / 2",
        "compression_ratio = raw_bytes / bitstream_bytes",
        "bpp = bitstream_bytes * 8 / (width * height)",
        "```",
        "",
        "## Visual Quality Metrics",
        "",
        "Encoder behavior is evaluated through same-QP comparison and equal-bpp interpolation. Luma means the Y component in the YUV representation. The local MS-SSIM, FSIM, HaarPSI, and PSNR-HVS-M columns are computed on the Y plane to keep structural, edge, and texture comparisons stable.",
        "",
        *markdown_table(
            ["Metric", "Source"],
            [
                ["PSNR-Y/U/V", "Parsed from the VVenC encode log"],
                ["SSIM", "`ffmpeg -lavfi ssim`, parsed as the aggregate `All` score"],
                ["XPSNR-Y", "`ffmpeg -lavfi xpsnr`, Y score"],
                ["VMAF", "`ffmpeg -lavfi libvmaf` when the local ffmpeg build provides libvmaf"],
                ["MS-SSIM", "Local luma implementation in `metrics/image_quality.py`"],
                ["FSIM", "Local luma implementation in `metrics/image_quality.py`"],
                ["HaarPSI", "Local luma implementation in `metrics/image_quality.py`"],
                ["PSNR-HVS-M", "Local luma implementation in `metrics/image_quality.py`"],
                ["PSNR-RGB", "Local YUV\u2192RGB (BT.601) conversion + per-channel MSE in `metrics/image_quality.py`"],
                ["MS-SSIM-RGB", "Local YUV\u2192RGB (BT.601) conversion + per-channel MS-SSIM in `metrics/image_quality.py`"],
            ],
        ),
        "",
        "The local luma metrics are not bit-exact replacements for pinned external implementations. External implementations can differ by RGB/YUV input handling, chroma use, padding, scaling, filters, multi-scale weights, phase congruency details, and Haar-wavelet details. Here they are reproducible in-repository indicators applied identically to baseline and CSF.",
        "",
        "## Same-QP Summary",
        "",
        "CSV: [`docs/image_benchmark/combined/same_qp_summary.csv`](image_benchmark/combined/same_qp_summary.csv)",
        "",
        *metric_summary_table("docs/image_benchmark/combined/same_qp_summary.csv"),
        "",
        "## Equal-bpp Summary",
        "",
        "CSV: [`docs/image_benchmark/combined/equal_bpp_metric_summary.csv`](image_benchmark/combined/equal_bpp_metric_summary.csv)",
        "",
        *metric_summary_table("docs/image_benchmark/combined/equal_bpp_metric_summary.csv"),
        "",
        "## BD-Rate Summary",
        "",
        "CSV: [`docs/image_benchmark/combined/bd_rate_summary.csv`](image_benchmark/combined/bd_rate_summary.csv). Per-image values are stored in [`docs/image_benchmark/combined/bd_rate_by_image.csv`](image_benchmark/combined/bd_rate_by_image.csv). Negative BD-Rate means the CSF encoder needs fewer bits than baseline for the same quality metric; positive BD-Rate means it needs more bits.",
        "",
        *bd_rate_summary_table("docs/image_benchmark/combined/bd_rate_summary.csv"),
        "",
        *details("Show BD-Rate per image", bd_rate_per_image_table()),
        "",
        "The generated XLSX workbook `docs/image_benchmark/combined/results.xlsx` contains the full metrics table, same-QP summary, and BD-Rate summary when `openpyxl` is installed and XLSX output is enabled.",
        "",
        "## Per-Image Summary",
        "",
        "The table aggregates four QP points for each image. The full per-image/QP/mode table is stored in [`docs/image_benchmark/combined_image_metrics.csv`](image_benchmark/combined_image_metrics.csv).",
        "",
        *details("Show per-image summary", per_image_table()),
        "",
        "## RD Charts",
        "",
        "The charts are rendered by `tools/report_image_benchmark.py` from `docs/image_benchmark/combined_image_metrics.csv`. They plot bpp against each quality metric for baseline and CSF, averaged over the combined image set. Dataset-specific charts are stored under `docs/image_benchmark/standard_grayscale/`, `docs/image_benchmark/synthetic/`, and `docs/image_benchmark/kodak/`.",
        "",
        *details("Show combined RD charts", chart_grid(from_docs=True)),
        "",
        "## Standard Grayscale Metric-vs-QP Charts",
        "",
        "The following charts use only the `standard_grayscale` benchmark rows. They are rendered from `docs/image_benchmark/standard_grayscale/` and show one measured metric as a function of QP for one image.",
        "",
        *details("Show standard grayscale metric-vs-QP charts", standard_grayscale_qp_sections(from_docs=True)),
        "",
        "## Partition Map Summary",
        "",
        "Each map shows final luma CUs encoded at `QP=32`, `preset=medium`, and one frame.",
        "",
    ]

    for dataset, title, _image_dir in DATASETS:
        lines.extend(
            [
                f"### {title}",
                "",
                *details(f"Show {title} partition summary", partition_summary_table(dataset)),
                "",
            ]
        )

    lines.extend(["## Partition Maps", ""])
    for dataset, title, image_dir in DATASETS:
        lines.extend(
            [
                f"### {title}",
                "",
                *details(
                    f"Show {title} original images and map pairs",
                    [
                        "Each row links the original PNG with baseline and CSF SVG maps generated from VVenC `D_QP` traces at the same image size and QP. A denser CSF map indicates more small CUs selected by the encoder.",
                        "",
                        *partition_map_table(dataset, image_dir, from_docs=True),
                    ],
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## How to Extend",
            "",
            "This benchmark is designed to be easily extensible. You can customize the image inputs or add new visual quality metrics.",
            "",
            "### Adding a Custom Image Set",
            "1. Create a subdirectory under `image_sets/` containing your input images in PNG format (e.g., `image_sets/custom_set/png/`).",
            "2. Update the paths in `configs/image_benchmark.ini` or pass your custom directory via the `--smoke-dir`, `--synthetic-dir`, or `--kodak-dir` CLI arguments when invoking `run_all.py`.",
            "",
            "### Adding a Custom Quality Metric",
            "1. Implement the luma metric calculation function in `metrics/image_quality.py`.",
            "2. Update the `calculate_luma_metrics()` function in `metrics/image_quality.py` to execute your new metric and append its score to the returned dictionary.",
            "3. Add a tuple with the metric's CSV key, short label, and chart label to `_METRIC_DEFS` in `metrics/registry.py`. All report scripts pick up the new metric automatically.",
            "",
            "## Current Conclusion",
            "",
            "The CSF integration passes the mechanical checks used by this benchmark: `--CSFScalingList 1` is accepted, generated bitstreams decode through VVdeC, encoder reconstruction matches decoded output, matrices are signaled, and the tables, RD charts, and CU partition maps are regenerated from repository scripts.",
            "",
            "Across the current standard grayscale, synthetic, and Kodak datasets, the average same-QP and equal-bpp deltas remain negative for most quality metrics. This means the current CSF matrix shape does not outperform the default encoder configuration under the fixed conditions used here.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    README.write_text(build_readme(), encoding="utf-8", newline="\n")
    REPORT.write_text(build_report(), encoding="utf-8", newline="\n")
    logger.info("Wrote %s", README)
    logger.info("Wrote %s", REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
