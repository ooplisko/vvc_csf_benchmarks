from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
REPORT = ROOT / "docs/image_benchmark_report.md"

DATASETS = [
    ("standard_grayscale", "Standard grayscale", "image_sets/standard_grayscale/png"),
    ("synthetic", "Synthetic", "image_sets/synthetic/png"),
    ("kodak", "Kodak", "image_sets/kodak/png"),
]

METRIC_COLUMNS = [
    ("psnr_y_delta_mean", "PSNR-Y"),
    ("ssim_delta_mean", "SSIM"),
    ("xpsnr_y_delta_mean", "XPSNR-Y"),
    ("vmaf_delta_mean", "VMAF"),
    ("msssim_luma_delta_mean", "MS-SSIM"),
    ("fsim_luma_delta_mean", "FSIM"),
    ("haarpsi_luma_delta_mean", "HaarPSI"),
    ("psnr_hvs_m_luma_delta_mean", "PSNR-HVS-M"),
]

CHARTS = [
    ("PSNR-Y", "docs/image_benchmark/combined/charts/rd_psnr_y.svg"),
    ("SSIM", "docs/image_benchmark/combined/charts/rd_ssim.svg"),
    ("XPSNR-Y", "docs/image_benchmark/combined/charts/rd_xpsnr_y.svg"),
    ("VMAF", "docs/image_benchmark/combined/charts/rd_vmaf.svg"),
    ("MS-SSIM luma", "docs/image_benchmark/combined/charts/rd_msssim_luma.svg"),
    ("FSIM luma", "docs/image_benchmark/combined/charts/rd_fsim_luma.svg"),
    ("HaarPSI luma", "docs/image_benchmark/combined/charts/rd_haarpsi_luma.svg"),
    ("PSNR-HVS-M luma", "docs/image_benchmark/combined/charts/rd_psnr_hvs_m_luma.svg"),
]


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
                ["Compared modes", "`vvenc_default.exe` vs `vvenc_csf.exe --CSFScalingList 1`"],
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
                ["[Partition summary CSV](docs/partition_maps/summary.csv)", "CU counts and dominant block sizes"],
            ],
        ),
        "",
        "## Repository Layout",
        "",
        *markdown_table(
            ["Path", "Purpose"],
            [
                ["`binaries/`", "Encoder and decoder binaries used by the benchmark"],
                ["`image_sets/standard_grayscale/`", "Primary grayscale control images, stored as BMP sources and PNG benchmark inputs"],
                ["`image_sets/synthetic/png/`", "Deterministic synthetic PNG images"],
                ["`image_sets/kodak/png/`", "Kodak image suite"],
                ["`run_all.py`", "Image-only orchestrator for smoke checks, neutral-value checks, benchmark runs, and report regeneration"],
                ["`tools/`", "Dataset, benchmark, report, matrix, and partition-map utilities"],
                ["`metrics/`", "Local visual-quality metric implementations"],
                ["`docs/`", "Generated evidence, tables, charts, and detailed reports"],
            ],
        ),
        "",
        "## Quick Start",
        "",
        "```powershell",
        "py -3 -m venv .venv",
        ".\\.venv\\Scripts\\pip.exe install -r requirements.txt",
        ".\\.venv\\Scripts\\python.exe run_all.py quick --clean",
        "```",
        "",
        "`ffmpeg`, `ffprobe`, and `curl.exe` must be available in `PATH`. The `.venv` and `results/` directories are local and are not committed. `quick` runs console sanity checks: smoke encode/decode and neutral-16 verification. `full` runs all image benchmarks and regenerates CSV reports, charts, partition maps, and Markdown documentation.",
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
        "## Result Snapshot",
        "",
        "Same-QP and equal-bpp summaries are generated from `docs/image_benchmark/combined_image_metrics.csv`. Negative deltas mean the current CSF result is lower than the default encoder under the same comparison method.",
        "",
        *metric_summary_table("docs/image_benchmark/combined/same_qp_summary.csv"),
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
            "Standard grayscale partition maps",
            [
                "The maps are generated by `tools/build_partition_evidence.py` from VVenC `D_QP` traces at `QP=32`, `preset=medium`, and one encoded frame.",
                "",
                *partition_map_table("standard_grayscale", "image_sets/standard_grayscale/png"),
            ],
        ),
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
                ["`binaries/vvenc_default.exe`", "Clean upstream/default VVenC encoder without CSF"],
                ["`binaries/vvenc_csf.exe`", "Modified VVenC encoder. CSF is enabled with `--CSFScalingList 1`"],
                ["`binaries/vvenc_default_trace.exe`", "Default encoder built with `VVENC_ENABLE_TRACING=ON` for partition maps only"],
                ["`binaries/vvenc_csf_trace.exe`", "CSF encoder built with `VVENC_ENABLE_TRACING=ON` for partition maps only"],
                ["`binaries/vvdecapp.exe`", "VVdeC decoder used to verify bitstream decoding"],
            ],
        ),
        "",
        "The current benchmark can be reproduced directly from the binaries stored in the repository. Local VVenC build directories are not required.",
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
        "Baseline maps are generated with `vvenc_default_trace.exe`; CSF maps are generated with `vvenc_csf_trace.exe`. Both binaries write final luma CU coordinates through the same `D_QP` trace, so a denser CSF map means the encoder selected more small CUs under the CSF configuration.",
        "",
        "## Reproducing the Run",
        "",
        "```powershell",
        "py -3 -m venv .venv",
        ".\\.venv\\Scripts\\pip.exe install -r requirements.txt",
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
                ["Baseline mode", "`vvenc_default.exe`, without `--CSFScalingList`"],
                ["CSF mode", "`vvenc_csf.exe --CSFScalingList 1`"],
                ["Decoder", "`vvdecapp.exe`"],
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
    print(f"Wrote {README}")
    print(f"Wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
