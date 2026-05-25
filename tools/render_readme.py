from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

DATASETS = [
    ("synthetic", "Synthetic", "image_sets/synthetic/png"),
    ("kodak", "Kodak", "image_sets/kodak/png"),
    ("standard_grayscale", "Standard grayscale", "image_sets/standard_grayscale/png"),
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


def metric_summary_table(path: str) -> list[str]:
    rows = read_csv(path)
    return markdown_table(
        ["Metric", "Mean", "Min", "Max"],
        [[row["metric"], fmt(row["mean"]), fmt(row["min"]), fmt(row["max"])] for row in rows],
    )


def per_image_table() -> list[str]:
    rows = read_csv("docs/image_benchmark/combined/per_image_summary.csv")
    table_rows = []
    for row in rows:
        table_rows.append(
            [
                row["image"],
                fmt(row["bpp_delta_pct_mean"], 2),
                fmt(row["compression_ratio_delta_pct_mean"], 2),
                *[fmt(row[key], 6 if "luma" in key or "ssim" in key else 3) for key, _label in METRIC_COLUMNS],
            ]
        )
    return markdown_table(
        [
            "Image",
            "bpp CSF vs base, %",
            "Compression ratio CSF vs base, %",
            *[label for _key, label in METRIC_COLUMNS],
        ],
        table_rows,
    )


def chart_grid() -> list[str]:
    rows = []
    for index in range(0, len(CHARTS), 2):
        left = CHARTS[index]
        right = CHARTS[index + 1] if index + 1 < len(CHARTS) else ("", "")
        rows.append(
            [
                f'**{left[0]}**<br><img src="{left[1]}" width="360">',
                f'**{right[0]}**<br><img src="{right[1]}" width="360">' if right[0] else "",
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


def partition_map_table(dataset: str, image_dir: str) -> list[str]:
    rows = []
    for image in sorted((ROOT / image_dir).glob("*.png")):
        name = image.stem
        rows.append(
            [
                name,
                f'<img src="{image_dir}/{image.name}" width="180">',
                f'<img src="docs/partition_maps/{dataset}/{name}_baseline.svg" width="240">',
                f'<img src="docs/partition_maps/{dataset}/{name}_csf.svg" width="240">',
            ]
        )
    return markdown_table(["Image", "Original", "Baseline", "CSF"], rows)


def build_readme() -> str:
    lines: list[str] = [
        "# VVenC CSF Image Benchmark",
        "",
        "This repository contains an image-only benchmark for a custom CSF scaling-list modification in VVenC. It includes reproducible encoder/decoder binaries, synthetic images, Kodak images, standard grayscale control images, benchmark scripts, metric tables, RD charts, and Coding Unit (CU) partition maps.",
        "",
        "## 1. Repository Layout",
        "",
        *markdown_table(
            ["Path", "Purpose"],
            [
                ["`binaries/`", "Reproducible encoder/decoder binaries used by this experiment."],
                ["`image_sets/synthetic/png/`", "Four deterministic synthetic PNG images."],
                ["`image_sets/kodak/png/`", "The 24-image Kodak suite."],
                ["`image_sets/standard_grayscale/`", "BARBARA, BABOON, goldhill, lenna, and peppers as BMP sources and PNG benchmark inputs."],
                ["`tools/`", "Dataset, benchmark, report, matrix, and partition-map utilities."],
                ["`metrics/image_quality.py`", "In-repository luma implementations of MS-SSIM, FSIM, HaarPSI, and PSNR-HVS-M-like indicators."],
                ["`docs/matrices/`", "CSV snapshots of default and CSF scaling matrices. The encoder remains the source of truth."],
                ["`docs/image_benchmark/`", "CSV results, summary tables, and RD charts."],
                ["`docs/partition_maps/`", "CSV/SVG CU partition evidence for all image sets."],
            ],
        ),
        "",
        "## 2. Binaries",
        "",
        *markdown_table(
            ["File", "Purpose"],
            [
                ["`binaries/vvenc_default.exe`", "Clean upstream/default VVenC encoder without CSF."],
                ["`binaries/vvenc_csf.exe`", "Modified VVenC encoder. CSF is enabled with `--CSFScalingList 1`."],
                ["`binaries/vvenc_default_trace.exe`", "Default encoder built with `VVENC_ENABLE_TRACING=ON` for partition maps only."],
                ["`binaries/vvenc_csf_trace.exe`", "CSF encoder built with `VVENC_ENABLE_TRACING=ON` for partition maps only."],
                ["`binaries/vvdecapp.exe`", "VVdeC decoder used to verify bitstream decoding."],
            ],
        ),
        "",
        "The binaries correspond to two VVenC trees: upstream/default VVenC and the modified `feature-branch`. The current benchmark can be reproduced directly from the binaries in this repository; local build directories are not required.",
        "",
        "To rebuild the default encoder binaries:",
        "",
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
        "",
        "The CSF binaries are built from the VVenC fork/branch that implements `--CSFScalingList`, then copied as `vvenc_csf.exe` and `vvenc_csf_trace.exe`.",
        "",
        "## 3. Scaling Matrices",
        "",
        "Scaling matrices are defined in the encoder, not in this Python project. In the CSF branch, the base table is in `source/Lib/CommonLib/CSFWeights.h`; quant/dequant application is implemented in `source/Lib/CommonLib/Quant.cpp`.",
        "",
        "`docs/matrices/` stores CSV snapshots of the default and CSF matrices. These files do not drive the encoder. They record the numerical matrices used for analysis, comparison, and result verification.",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe tools\\dump_csf_matrices.py --output docs\\matrices",
        "```",
        "",
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
        "",
        "For non-8x8 Transform Units (TU), the encoder maps the 8x8 CSF table to the active TU size. Square TUs use scaled indices up to `min(size, 8)`. Rectangular TUs use the longer side and `ratioH`/`ratioW` mapping to select coordinates from the base CSF table. Coefficients outside the zero-out threshold are written as zero, matching the standard scaling-list behavior.",
        "",
        "## 4. Image Partitioning",
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
        "Baseline maps are generated with `vvenc_default_trace.exe`; CSF maps are generated with `vvenc_csf_trace.exe`. For each image, both maps use the same canvas size. When a CSF map looks visually smaller or denser, the scale is not different; the encoder selected more small CUs.",
        "",
        "## 5. Reproducing the Run",
        "",
        "Create the local Python environment:",
        "",
        "```powershell",
        "py -3 -m venv .venv",
        ".\\.venv\\Scripts\\pip.exe install -r requirements.txt",
        "```",
        "",
        "The `.venv` directory is local and is not part of the repository. `ffmpeg`, `ffprobe`, and `curl.exe` must be available in `PATH`.",
        "",
        "Generate or refresh input images:",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe tools\\generate_synthetic_images.py --output image_sets\\synthetic\\png",
        "```",
        "",
        "Run the three image benchmarks:",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe tools\\image_csf_benchmark.py --root results\\image_synthetic_full --png-dir image_sets\\synthetic\\png --qps 22,27,32,37",
        ".\\.venv\\Scripts\\python.exe tools\\image_csf_benchmark.py --root results\\image_kodak_full --png-dir image_sets\\kodak\\png --download-kodak --qps 22,27,32,37",
        ".\\.venv\\Scripts\\python.exe tools\\image_csf_benchmark.py --root results\\image_standard_grayscale_full --png-dir image_sets\\standard_grayscale\\png --qps 22,27,32,37",
        "```",
        "",
        "Merge metrics and regenerate reports:",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe tools\\merge_image_metrics.py results\\image_synthetic_full\\image_metrics.csv results\\image_kodak_full\\image_metrics.csv results\\image_standard_grayscale_full\\image_metrics.csv --output docs\\image_benchmark\\combined_image_metrics.csv",
        ".\\.venv\\Scripts\\python.exe tools\\report_image_benchmark.py docs\\image_benchmark\\combined_image_metrics.csv --output docs\\image_benchmark\\combined",
        ".\\.venv\\Scripts\\python.exe tools\\build_partition_evidence.py --qp 32",
        ".\\.venv\\Scripts\\python.exe tools\\render_readme.py",
        "```",
        "",
        "## 6. Experiment Conditions",
        "",
        *markdown_table(
            ["Parameter", "Value"],
            [
                ["Dataset", "4 synthetic + 24 Kodak + 5 standard grayscale images"],
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
        "The compression control parameter in this experiment is `QP`. All other conditions are fixed. Lower QP increases bitrate and quality; higher QP increases compression strength.",
        "",
        "Compression ratio is computed per `image + QP + mode` point:",
        "",
        "```text",
        "raw_bytes = width * height * 3 / 2",
        "compression_ratio = raw_bytes / bitstream_bytes",
        "bpp = bitstream_bytes * 8 / (width * height)",
        "```",
        "",
        "`raw_bytes` corresponds to one 8-bit YUV420 frame. `bitstream_bytes` is the encoded `.vvc` bitstream size. The values are recorded in `docs/image_benchmark/combined_image_metrics.csv`.",
        "",
        "## 7. Visual Quality Metrics",
        "",
        "Encoder behavior is evaluated in two ways:",
        "",
        "1. Same-QP comparison: baseline and CSF are compared at identical QP points 22/27/32/37.",
        "2. Equal-bpp comparison: CSF metric values are interpolated to baseline bpp points to estimate quality at comparable bitrate.",
        "",
        "Luma means the Y component in the YUV representation. The benchmark stores source and reconstruction frames as YUV420, so the local MS-SSIM, FSIM, HaarPSI, and PSNR-HVS-M columns are computed on the Y plane. This aligns them with PSNR-Y and XPSNR-Y and makes the comparison stable for structures, edges, and textures visible in brightness.",
        "",
        "The local luma metrics are not bit-exact replacements for pinned external implementations. External implementations can differ by RGB/YUV input handling, chroma use, padding, scaling, filters, multi-scale weights, phase congruency details, and Haar-wavelet details. In this project they are used as reproducible in-repository indicators applied identically to baseline and CSF.",
        "",
        *markdown_table(
            ["Metric", "Source"],
            [
                ["PSNR-Y/U/V", "Parsed from the VVenC encode log."],
                ["SSIM", "`ffmpeg -lavfi ssim`, parsed as the aggregate `All` score."],
                ["XPSNR-Y", "`ffmpeg -lavfi xpsnr`, Y score."],
                ["VMAF", "`ffmpeg -lavfi libvmaf` when the local ffmpeg build provides libvmaf."],
                ["MS-SSIM", "Local luma implementation in `metrics/image_quality.py`."],
                ["FSIM", "Local luma implementation in `metrics/image_quality.py`."],
                ["HaarPSI", "Local luma implementation in `metrics/image_quality.py`."],
                ["PSNR-HVS-M", "Local luma implementation in `metrics/image_quality.py`."],
            ],
        ),
        "",
        "## 8. Same-QP Summary",
        "",
        "CSV: `docs/image_benchmark/combined/same_qp_summary.csv`",
        "",
        *metric_summary_table("docs/image_benchmark/combined/same_qp_summary.csv"),
        "",
        "## 9. Equal-bpp Summary",
        "",
        "CSV: `docs/image_benchmark/combined/equal_bpp_metric_summary.csv`",
        "",
        *metric_summary_table("docs/image_benchmark/combined/equal_bpp_metric_summary.csv"),
        "",
        "## 10. Per-Image Summary",
        "",
        "The table aggregates four QP points for each image. The full per-image/QP/mode table is stored in `docs/image_benchmark/combined_image_metrics.csv`; the summarized table is stored in `docs/image_benchmark/combined/per_image_summary.csv`.",
        "",
        *per_image_table(),
        "",
        "## 11. RD Charts",
        "",
        "The charts show average RD curves over the combined dataset. Numeric axis ticks, QP labels, and the in-plot legend are embedded in the SVG files. Dataset-specific charts are also available under `docs/image_benchmark/synthetic/charts/`, `docs/image_benchmark/kodak/charts/`, and `docs/image_benchmark/standard_grayscale/charts/`.",
        "",
        *chart_grid(),
        "",
        "## 12. Partition Map Summary",
        "",
        "Each map shows final luma CUs encoded at `QP=32`, `preset=medium`, and `1 frame`.",
        "",
    ]

    for dataset, title, _image_dir in DATASETS:
        lines.extend([f"### {title}", "", *partition_summary_table(dataset), ""])

    for number, (dataset, title, image_dir) in enumerate(DATASETS, start=13):
        lines.extend(
            [
                f"## {number}. Partition Maps: {title}",
                "",
                "Original images, baseline maps, and CSF maps are shown with fixed display widths. A denser CSF map indicates more small CUs, not a different image scale.",
                "",
                *partition_map_table(dataset, image_dir),
                "",
            ]
        )

    lines.extend(
        [
            "## 16. Current Conclusion",
            "",
            "The CSF integration is mechanically stable for this benchmark: `--CSFScalingList 1` is accepted, generated bitstreams decode through VVdeC, encoder reconstruction matches decoded output, matrices are signaled, and the tables, RD charts, and CU partition maps are reproducible from repository scripts.",
            "",
            "Across the current synthetic, Kodak, and standard grayscale datasets, the average same-QP and equal-bpp deltas remain negative for most quality metrics. This means the current CSF matrix shape does not outperform the default encoder configuration under the fixed conditions used here.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    README.write_text(build_readme(), encoding="utf-8", newline="\n")
    print(f"Wrote {README}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
