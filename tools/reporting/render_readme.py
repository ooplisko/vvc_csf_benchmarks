from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
REPORT = ROOT / "docs/image_benchmark_report.md"

logger = logging.getLogger(__name__)

DATASETS = [
    ("standard_grayscale", "Standard grayscale", "data/datasets/images/standard_grayscale/png"),
    ("synthetic", "Synthetic", "data/datasets/images/synthetic/png"),
    ("kodak", "Kodak", "data/datasets/images/kodak/png"),
]

from metrics.registry import CHARTS, METRIC_CHART_LABELS, METRIC_LABELS, METRICS


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


def existing_codec_result_root(codec: str) -> str | None:
    current = f"docs/image_benchmark/{codec}"
    if (ROOT / current / "combined" / "same_qp_summary.csv").exists():
        return current
    return None


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
        [[summary_metric_label(row["metric"]), fmt(row["mean"]), fmt(row["min"]), fmt(row["max"])] for row in rows],
    )


def summary_metric_label(metric: str) -> str:
    """Return a readable label for aggregate delta summary keys."""

    if metric.endswith("_equal_bpp_delta"):
        base = metric.removesuffix("_equal_bpp_delta")
        return f"{METRIC_LABELS.get(base, base)} equal-bpp delta"
    if metric.endswith("_delta"):
        base = metric.removesuffix("_delta")
        return f"{METRIC_LABELS.get(base, base)} same-QP delta"
    return METRIC_LABELS.get(metric, metric)


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


def chart_grid(base: str = "docs/image_benchmark/vvenc/combined", from_docs: bool = False) -> list[str]:
    rows = []
    charts = [(label, f"{base}/charts/rd_{metric}.svg") for metric, label in ((metric, METRIC_CHART_LABELS[metric]) for metric in METRICS)]
    for index in range(0, len(charts), 2):
        left = charts[index]
        right = charts[index + 1] if index + 1 < len(charts) else ("", "")
        rows.append(
            [
                f'**{left[0]}**<br><img src="{rel(left[1], from_docs)}" width="360">',
                f'**{right[0]}**<br><img src="{rel(right[1], from_docs)}" width="360">' if right[0] else "",
            ]
        )
    return markdown_table(["Chart", "Chart"], rows)


def codec_result_block(codec: str, title: str, from_docs: bool = False) -> list[str]:
    root = existing_codec_result_root(codec)
    if root is None:
        return [
            f"### {title}",
            "",
            f"No generated `{codec}` image benchmark report is present yet. Run `python run_all.py full --codec {codec} --clean` to create it.",
        ]

    combined = f"{root}/combined"
    lines = [
        f"### {title}",
        "",
        f"Metrics CSV: [`{root}/combined_image_metrics.csv`]({rel(f'{root}/combined_image_metrics.csv', from_docs)})",
        "",
        "Summary CSVs:",
        "",
        *markdown_table(
            ["Artifact", "File"],
            [
                ["Same-QP deltas", f"[`{combined}/same_qp_summary.csv`]({rel(f'{combined}/same_qp_summary.csv', from_docs)})"],
                ["Equal-bpp interpolation deltas", f"[`{combined}/equal_bpp_metric_summary.csv`]({rel(f'{combined}/equal_bpp_metric_summary.csv', from_docs)})"],
                ["BD-Rate summary", f"[`{combined}/bd_rate_summary.csv`]({rel(f'{combined}/bd_rate_summary.csv', from_docs)})"],
            ],
        ),
        "",
        "Same-QP summary:",
        "",
        *metric_summary_table(f"{combined}/same_qp_summary.csv"),
        "",
        "Equal-bpp summary:",
        "",
        *metric_summary_table(f"{combined}/equal_bpp_metric_summary.csv"),
        "",
        "BD-Rate summary:",
        "",
        *bd_rate_summary_table(f"{combined}/bd_rate_summary.csv"),
        "",
        *details(f"Show {title} RD charts", chart_grid(combined, from_docs=from_docs)),
    ]
    return lines

def partition_dataset_root(dataset: str, codec: str = "vvenc") -> str:
    current = f"docs/partition_maps/{codec}/{dataset}"
    if (ROOT / current / "summary.csv").exists():
        return current
    if codec == "vvenc":
        return f"docs/partition_maps/{dataset}"
    return current


def partition_summary_table(dataset: str, codec: str = "vvenc") -> list[str]:
    rows = read_csv(f"{partition_dataset_root(dataset, codec)}/summary.csv")
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


def partition_map_table(dataset: str, image_dir: str, codec: str = "vvenc", from_docs: bool = False) -> list[str]:
    rows = []
    root = partition_dataset_root(dataset, codec)
    for image in sorted((ROOT / image_dir).glob("*.png")):
        name = image.stem
        rows.append(
            [
                name,
                f'<img src="{rel(f"{image_dir}/{image.name}", from_docs)}" width="180">',
                f'<img src="{rel(f"{root}/{name}_baseline.svg", from_docs)}" width="240">',
                f'<img src="{rel(f"{root}/{name}_csf.svg", from_docs)}" width="240">',
            ]
        )
    return markdown_table(["Image", "Original", "Baseline", "CSF"], rows)


def partition_codec_block(codec: str, title: str, from_docs: bool = False) -> list[str]:
    if not (ROOT / f"docs/partition_maps/{codec}/summary.csv").exists():
        return [
            f"### {title}",
            "",
            f"No `{codec}` partition-map report is present yet. Run `python run_all.py full --codec {codec} --clean` to generate it.",
        ]

    lines = [
        f"### {title}",
        "",
        f"Summary CSV: [`docs/partition_maps/{codec}/summary.csv`]({rel(f'docs/partition_maps/{codec}/summary.csv', from_docs)})",
        "",
    ]
    for dataset, dataset_title, _image_dir in DATASETS:
        lines.extend(
            [
                f"#### {dataset_title}",
                "",
                *details(f"Show {dataset_title} partition summary", partition_summary_table(dataset, codec)),
                "",
            ]
        )
    return lines


def build_readme() -> str:
    lines: list[str] = [
        "# VVC CSF Benchmarks",
        "",
        '<p align="center">',
        '  <a href="https://github.com/ooplisko/vvc_csf_benchmarks/blob/master/LICENSE">',
        '    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license">',
        "  </a>",
        '  <a href="https://www.python.org/downloads/">',
        '    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">',
        "  </a>",
        '  <a href="https://github.com/ooplisko/vvc_csf_benchmarks/actions/workflows/build.yml">',
        '    <img src="https://github.com/ooplisko/vvc_csf_benchmarks/actions/workflows/build.yml/badge.svg" alt="Tests">',
        "  </a>",
        '  <a href="https://github.com/ooplisko/vvc_csf_benchmarks/actions">',
        '    <img src="https://img.shields.io/badge/build-validation-brightgreen" alt="Build validation">',
        "  </a>",
        '  <a href="https://github.com/ooplisko/vvc_csf_benchmarks/releases">',
        '    <img src="https://img.shields.io/badge/release-assets-blue" alt="Release assets">',
        "  </a>",
        "</p>",
        "",
        '**O. O. Plisko** - [Department of Information and Communication Technologies](https://dict.khai.edu/), National Aerospace University "Kharkiv Aviation Institute"',
        "",
        "This repository is a reproducible image-only benchmark for Contrast Sensitivity Function (CSF) scaling-list modifications in VVenC and VTM. It can download or build the required codec binaries, run baseline-vs-CSF experiments, verify decoded bitstreams, compute objective image metrics, render RD charts, and generate Coding Unit (CU) partition-map evidence from trace-enabled encoders.",
        "",
        "## What It Does",
        "",
        *markdown_table(
            ["Workflow", "Output"],
            [
                ["Smoke checks", "One-image encode/decode checks for VVenC or VTM"],
                ["Full image benchmark", "Per-image/per-QP metric CSVs, summaries, XLSX workbooks, and RD charts"],
                ["Partition maps", "CU SVG overlays and summaries from `D_QP` traces for VVenC and VTM"],
                ["VTM validation", "Historical VTM 18.0 anchor replication plus local VTM 23.0 baseline/CSF curves"],
                ["Report rendering", "Root README and detailed benchmark report regenerated from committed artifacts"],
            ],
        ),
        "",
        "## Quick Start",
        "",
        "```powershell",
        "py -3 -m venv .venv",
        ".\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt",
        ".\\.venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt",
        ".\\.venv\\Scripts\\python.exe tools\\data_prep\\download_binaries.py",
        ".\\.venv\\Scripts\\python.exe run_all.py quick --clean",
        ".\\.venv\\Scripts\\python.exe run_all.py quick --codec vtm --clean",
        "```",
        "",
        "Requirements: Python 3.10+, `ffmpeg`, and `ffprobe` in `PATH`. Windows release binaries are not tracked in git; `download_binaries.py` downloads `binaries.zip` from GitHub Releases and extracts the top-level `binaries/` folder into the repository.",
        "",
        "## Main Commands",
        "",
        *markdown_table(
            ["Task", "Command"],
            [
                ["Run full VVenC benchmark", "`.\\.venv\\Scripts\\python.exe run_all.py full --codec vvenc --clean`"],
                ["Run full VTM benchmark", "`.\\.venv\\Scripts\\python.exe run_all.py full --codec vtm --clean`"],
                ["Re-render existing reports", "`.\\.venv\\Scripts\\python.exe tools\\reporting\\render_readme.py`"],
                ["Run tests", "`.\\.venv\\Scripts\\python.exe -m pytest -q`"],
                ["Build VVenC encoders", "`.\\.venv\\Scripts\\python.exe tools\\building\\build_vvenc.py all`"],
                ["Build VTM encoders/decoders", "`.\\.venv\\Scripts\\python.exe tools\\building\\build_vtm.py all`"],
            ],
        ),
        "",
        "Full runs are intentionally slow. They regenerate `docs/image_benchmark/{vvenc,vtm}/`, `docs/partition_maps/{vvenc,vtm}/`, and the Markdown reports.",
        "",
        "## Binaries",
        "",
        "Ready-to-use Windows binaries are provided as a GitHub Release asset named `binaries.zip`. The archive contains the complete `binaries/` folder, including VVenC, VVdeC, VTM 18.0 validation binaries, VTM 23.0 baseline/CSF binaries, and trace-enabled encoders for partition maps.",
        "",
        *markdown_table(
            ["Path", "Purpose"],
            [
                ["`binaries/vvenc/`", "VVenC baseline, CSF, trace encoders, and VVdeC decoder"],
                ["`binaries/vtm/vtm18/baseline/`", "Historical VTM 18.0 validation encoder/decoder"],
                ["`binaries/vtm/vtm23/baseline/`", "Clean VTM 23.0 encoder/decoder"],
                ["`binaries/vtm/vtm23/csf/`", "Modified VTM 23.0 CSF encoder"],
                ["`binaries/vtm/vtm23/*_trace/`", "Trace-enabled VTM encoders for CU partition maps"],
            ],
        ),
        "",
        "A CSF decoder is intentionally not used. The CSF changes are encoder-side; the clean decoder is the compatibility check. Detailed build and binary-layout notes are in [`binaries/README.md`](binaries/README.md).",
        "",
        "## Results",
        "",
        *markdown_table(
            ["Artifact", "Location"],
            [
                ["Detailed benchmark report", "[`docs/image_benchmark_report.md`](docs/image_benchmark_report.md)"],
                ["VVenC metrics", "[`docs/image_benchmark/vvenc/`](docs/image_benchmark/vvenc/)"],
                ["VTM 23.0 metrics", "[`docs/image_benchmark/vtm/`](docs/image_benchmark/vtm/)"],
                ["VVenC partition maps", "[`docs/partition_maps/vvenc/`](docs/partition_maps/vvenc/)"],
                ["VTM partition maps", "[`docs/partition_maps/vtm/`](docs/partition_maps/vtm/)"],
                ["VTM validation", "[`docs/vtm_validation/`](docs/vtm_validation/)"],
                ["Matrix evidence", "[`docs/matrices/`](docs/matrices/)"],
            ],
        ),
        "",
        "Current generated results show that CSF bitstreams decode correctly and reconstruction checks pass, but the current CSF matrix does not improve average quality or rate-distortion performance under the fixed image/QP conditions used here. See the detailed report for tables and interpretation.",
        "",
        "## Repository Layout",
        "",
        *markdown_table(
            ["Path", "Purpose"],
            [
                ["`configs/`", "Benchmark defaults for paths, binaries, QP points, and output options"],
                ["`data/datasets/images/`", "Primary grayscale, synthetic, and Kodak PNG inputs"],
                ["`metrics/`", "Local visual-quality metric implementations"],
                ["`tools/`", "Build, benchmark, validation, reporting, and visualization CLIs"],
                ["`vvenc_csf/`", "Reusable command, encoding, config, and benchmark library code"],
                ["`tests/`", "Fast unit tests and binary-availability integration checks"],
                ["`docs/`", "Generated reports, validation artifacts, matrices, charts, and partition maps"],
            ],
        ),
        "",
        "## Key Documents",
        "",
        *markdown_table(
            ["Document", "Use"],
            [
                ["[`docs/image_benchmark_report.md`](docs/image_benchmark_report.md)", "Main scientific report for image benchmark results"],
                ["[`binaries/README.md`](binaries/README.md)", "Binary layout, download, and build instructions"],
                ["[`docs/vtm_validation/`](docs/vtm_validation/)", "VTM anchor validation and VTM 23.0 cross-checks"],
                ["[`CITATION.cff`](CITATION.cff)", "Citation metadata"],
            ],
        ),
        "",
    ]
    return "\n".join(lines)


def build_report() -> str:
    lines: list[str] = [
        "# Image Benchmark Report",
        "",
        "This report expands the root README with the exact binaries, commands, CSV outputs, charts, and partition-map evidence used in the image benchmark. Results are organized by codec: VVenC and VTM 23.0 use the same image sets and QP points, but their reports are stored under separate directories.",
        "",
        "## Binaries",
        "",
        *markdown_table(
            ["File", "Purpose"],
            [
                ["`binaries/vvenc/vvenc_default[.exe]`", "Clean upstream/default VVenC encoder without CSF. Local build from [fraunhoferhhi/vvenc](https://github.com/fraunhoferhhi/vvenc)"],
                ["`binaries/vvenc/vvenc_csf[.exe]`", "Modified VVenC encoder. CSF is enabled with `--CSFScalingList 1`. Local build from the [CSF VVenC branch](https://github.com/ooplisko/vvenc/tree/feature-branch)"],
                ["`binaries/vvenc/vvenc_default_trace[.exe]`", "Default encoder built with `VVENC_ENABLE_TRACING=ON` for partition maps only. Local build from [fraunhoferhhi/vvenc](https://github.com/fraunhoferhhi/vvenc)"],
                ["`binaries/vvenc/vvenc_csf_trace[.exe]`", "CSF encoder built with `VVENC_ENABLE_TRACING=ON` for partition maps only. Local build from the [CSF VVenC branch](https://github.com/ooplisko/vvenc/tree/feature-branch)"],
                ["`binaries/vvenc/vvdecapp[.exe]`", "VVdeC decoder used to verify VVenC bitstreams. Local build from [Fraunhofer HHI VVdeC](https://github.com/fraunhoferhhi/vvdec)"],
                ["`binaries/vtm/vtm18/baseline/EncoderApp[.exe]`", "Clean VTM 18.0 encoder used only by the historical Kodak validation against Duan et al. anchors."],
                ["`binaries/vtm/vtm18/baseline/DecoderApp[.exe]`", "Clean VTM 18.0 decoder used only by the historical Kodak validation."],
                ["`binaries/vtm/vtm23/baseline/EncoderApp[.exe]`", "Clean VTM 23.0 encoder built from `VVCSoftware_VTM` tag `VTM-23.0`."],
                ["`binaries/vtm/vtm23/baseline/DecoderApp[.exe]`", "Clean VTM 23.0 decoder used for normative cross-checks, including CSF bitstreams."],
                ["`binaries/vtm/vtm23/csf/EncoderApp[.exe]`", "Modified VTM 23.0 encoder with `--CSFScalingList=1` support."],
                ["`binaries/vtm/vtm23/baseline_trace/EncoderApp[.exe]`", "Clean VTM 23.0 encoder built with `ENABLE_TRACING=ON` for partition maps only."],
                ["`binaries/vtm/vtm23/csf_trace/EncoderApp[.exe]`", "Modified VTM 23.0 encoder built with `ENABLE_TRACING=ON` for partition maps only."],
            ],
        ),
        "",
        "A separate CSF decoder is not required for the VTM 23.0 experiment. The modified encoder writes the scaling-list data into the bitstream; the clean decoder is the stricter compatibility check.",
        "",
        "VVenC encoder binaries are built through `tools/building/build_vvenc.py`. VTM binary sets are built through `tools/building/build_vtm.py`: `vtm18-validation` for historical anchor checks, `vtm23-baseline` and `vtm23-csf` for RD experiments, plus `vtm23-baseline-trace` and `vtm23-csf-trace` for partition maps.",
        "",
        "Windows `.exe` binaries are distributed through GitHub Releases as `binaries.zip`; the archive contains the complete top-level `binaries/` folder. On Linux/macOS, place suffixless binaries with the same stems under `binaries/vvenc/` or `binaries/vtm/`. The scripts select the platform-specific executable names automatically. More detail is available in [`binaries/README.md`](../binaries/README.md).",
        "",
        *details(
            "Encoder rebuild commands",
            [
                "```powershell",
                "python tools\\building\\build_vvenc.py all",
                "python tools\\building\\build_vtm.py all",
                "python tools\\building\\package_binaries.py",
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
        "The maps in this repository come from codec `D_QP` traces, not from a synthetic approximation. Both VVenC and VTM trace final luma CUs in `CABACWriter.cpp`:",
        "",
        "```cpp",
        "DTRACE_COND( ( isEncoding() ), g_trace_ctx, D_QP,",
        "  \"x=%d, y=%d, w=%d, h=%d, qp=%d\\n\",",
        "  cu.Y().x, cu.Y().y, cu.Y().width, cu.Y().height, cu.qp );",
        "```",
        "",
        "VVenC maps are generated with `vvenc_default_trace` and `vvenc_csf_trace`; VTM maps are generated with `vtm23/baseline_trace/EncoderApp` and `vtm23/csf_trace/EncoderApp` (`.exe` suffix on Windows). A denser CSF map means the selected encoder emitted more final luma CUs under the CSF configuration.",
        "",
        "## Reproducing the Run",
        "",
        "```powershell",
        "py -3 -m venv .venv",
        ".\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt",
        ".\\.venv\\Scripts\\python.exe run_all.py full --codec vvenc --clean",
        ".\\.venv\\Scripts\\python.exe run_all.py full --codec vtm --clean",
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
                ["VVenC encode pixel format", "`yuv420p`, 8-bit"],
                ["VTM encode pixel format", "`yuv444p`, 8-bit"],
                ["QP points", "22, 27, 32, 37"],
                ["Preset", "`medium`"],
                ["VVenC baseline/CSF", "`vvenc_default` vs. `vvenc_csf --CSFScalingList 1`"],
                ["VTM baseline/CSF", "`vtm23/baseline/EncoderApp` vs. `vtm23/csf/EncoderApp --CSFScalingList=1`"],
                ["Decoder checks", "VVenC uses `vvdecapp`; VTM uses clean `vtm23/baseline/DecoderApp`"],
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
        "Encoder behavior is evaluated through same-QP comparison and equal-bpp interpolation. For scientific interpretation, PSNR-RGB and MS-SSIM-RGB are the primary metrics because the validation reports cross-check those naming and measurement protocols against external VTM anchors: [CompressAI](vtm_validation/compressai/README.md) covers both PSNR-RGB and MS-SSIM-RGB, while [lossy-vae](vtm_validation/lossy-vae/README.md) independently checks PSNR-RGB and BPP.",
        "",
        "Luma means the Y component in the YUV representation. The luma metrics and approximations remain useful diagnostic indicators, but they are not the primary externally anchored claims in this repository.",
        "",
        *markdown_table(
            ["Metric", "Source"],
            [
                ["PSNR-Y/U/V", "Parsed from the codec encode log"],
                ["SSIM", "`ffmpeg -lavfi ssim`, parsed as the aggregate `All` score"],
                ["XPSNR-Y", "`ffmpeg -lavfi xpsnr`, Y score"],
                ["VMAF", "`ffmpeg -lavfi libvmaf` when the local ffmpeg build provides libvmaf"],
                ["MS-SSIM luma", "Local Y-plane implementation in `metrics/image_quality.py`"],
                ["FSIM luma approx", "Local Y-plane approximation in `metrics/image_quality.py`"],
                ["HaarPSI luma approx", "Local Y-plane approximation in `metrics/image_quality.py`"],
                ["PSNR-HVS-M luma approx", "Local Y-plane approximation in `metrics/image_quality.py`"],
                ["PSNR-RGB", "Local YUV-to-RGB (BT.601) conversion + per-channel MSE in `metrics/image_quality.py`"],
                ["MS-SSIM-RGB", "Local YUV-to-RGB (BT.601) conversion + per-channel MS-SSIM in `metrics/image_quality.py`"],
            ],
        ),
        "",
        "The local luma and approximation metrics are not bit-exact replacements for pinned external implementations. External implementations can differ by RGB/YUV input handling, chroma use, padding, scaling, filters, multi-scale weights, phase congruency details, and Haar-wavelet details. Here they are reproducible in-repository indicators applied identically to baseline and CSF.",
        "",
        "## Codec-Separated Results",
        "",
        *codec_result_block("vvenc", "VVenC Baseline vs. CSF", from_docs=True),
        "",
        *codec_result_block("vtm", "VTM 23.0 Baseline vs. CSF", from_docs=True),
        "",
        "## Partition Map Summary",
        "",
        "Each generated map shows final luma CUs encoded at `QP=32`, `preset=medium`, and one frame. New runs write codec-separated partition reports to `docs/partition_maps/vvenc/` and `docs/partition_maps/vtm/`.",
        "",
        *partition_codec_block("vvenc", "VVenC Partition Maps", from_docs=True),
        "",
        *partition_codec_block("vtm", "VTM 23.0 Partition Maps", from_docs=True),
        "",
    ]

    lines.extend(["## Partition Maps", ""])
    for dataset, title, image_dir in DATASETS:
        lines.extend(
            [
                f"### {title}",
                "",
                *details(
                    f"Show {title} original images and map pairs",
                    [
                        "Each row links the original PNG with baseline and CSF SVG maps generated from VVenC `D_QP` traces at the same image size and QP. VTM map pairs are stored under `docs/partition_maps/vtm/` after a VTM full run.",
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
            "1. Create a subdirectory under `data/datasets/images/` containing your input images in PNG format (e.g., `data/datasets/images/custom_set/png/`).",
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
