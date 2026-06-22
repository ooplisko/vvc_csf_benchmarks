"""Build the CompressAI Kodak VTM validation report."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[5]
COMPRESSAI_SOURCE = "https://raw.githubusercontent.com/InterDigitalInc/CompressAI/master/results/image/kodak/vtm.json"
COMPRESSAI_JSON_LINK = "https://github.com/InterDigitalInc/CompressAI/blob/master/results/image/kodak/vtm.json"
COMPRESSAI_CODE = "https://github.com/InterDigitalInc/CompressAI/blob/master/compressai/utils/bench/codecs.py"
COMPRESSAI_MAIN = "https://github.com/InterDigitalInc/CompressAI/blob/master/compressai/utils/bench/__main__.py"
COMPRESSAI_PAPER = "https://arxiv.org/pdf/2011.03029"
DUAN_SOURCE = "https://raw.githubusercontent.com/duanzhiihao/lossy-vae/main/results/kodak/kodak-vtm18.0.json"
DUAN_COMPRESSAI_VTM_SOURCE = "https://raw.githubusercontent.com/duanzhiihao/lossy-vae/main/results/kodak/kodak-vtm-compressai.json"
SERIES_STYLES = {
    "CompressAI VTM 9.1 Anchor": {"color": "#111111", "marker": "o", "linestyle": "-", "zorder": 9},
    "Local VTM 18.0 (OpenCV 4:4:4)": {"color": "#d62728", "marker": "s", "linestyle": "--", "linewidth": 3, "zorder": 10},
    "Local VTM 23.0 Baseline (FFmpeg 4:4:4)": {"color": "#17becf", "marker": "^", "linestyle": "-", "zorder": 6},
    "Local VTM 23.0 CSF (FFmpeg 4:4:4)": {"color": "#8c564b", "marker": "P", "linestyle": (0, (5, 2)), "zorder": 7},
    "Local VTM 23.0 Baseline (OpenCV 4:4:4)": {"color": "#ff7f0e", "marker": "D", "linestyle": "-", "zorder": 6},
    "Local VTM 23.0 CSF (OpenCV 4:4:4)": {"color": "#9467bd", "marker": "X", "linestyle": "-.", "zorder": 7},
    "Local VVenC (FFmpeg 4:2:0)": {"color": "#2ca02c", "marker": "*", "linestyle": (0, (1, 1)), "zorder": 4},
    "Local VVenC (OpenCV 4:2:0)": {"color": "#7f7f7f", "marker": "h", "linestyle": (0, (3, 1, 1, 1)), "zorder": 4},
}


def load_json(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def compressai_rows(reference: dict) -> list[dict[str, float | int]]:
    results = reference["results"]
    keys = ("bpp", "psnr-rgb", "ms-ssim-rgb", "encoding_time", "decoding_time")
    lengths = {len(results[key]) for key in keys}
    if len(lengths) != 1:
        raise ValueError(f"CompressAI result arrays have different lengths: {lengths}")

    rows = []
    for point, values in enumerate(zip(*(results[key] for key in keys)), start=1):
        bpp, psnr, msssim, enc_time, dec_time = values
        rows.append(
            {
                "point": point,
                "bpp": float(bpp),
                "psnr_rgb": float(psnr),
                "msssim_rgb": float(msssim),
                "encoding_time": float(enc_time),
                "decoding_time": float(dec_time),
            }
        )
    return rows


def local_vtm_overlap_rows(
    compressai: list[dict[str, float | int]],
    local_csv: Path,
) -> list[dict[str, float | int]]:
    with local_csv.open("r", newline="", encoding="utf-8") as stream:
        local_rows = [row for row in csv.DictReader(stream) if row.get("mode") == "baseline"]

    rows = []
    for qp in (22, 27, 32, 37):
        qp_rows = [row for row in local_rows if int(row["qp"]) == qp]
        if not qp_rows:
            continue
        local_bpp = sum(float(row["bpp"]) for row in qp_rows) / len(qp_rows)
        local_psnr = sum(float(row["psnr_rgb"]) for row in qp_rows) / len(qp_rows)
        nearest = min(range(len(compressai)), key=lambda index: abs(float(compressai[index]["bpp"]) - local_bpp))
        reference = compressai[nearest]
        rows.append(
            {
                "local_qp": qp,
                "compressai_point": int(reference["point"]),
                "local_bpp": local_bpp,
                "compressai_bpp": float(reference["bpp"]),
                "delta_bpp": local_bpp - float(reference["bpp"]),
                "local_psnr_rgb": local_psnr,
                "compressai_psnr_rgb": float(reference["psnr_rgb"]),
                "delta_psnr_rgb": local_psnr - float(reference["psnr_rgb"]),
            }
        )
    return rows


def local_summary_rows(path: Path, qps: tuple[int, ...] = (22, 27, 32, 37), mode: str | None = "baseline") -> list[dict[str, float | int]]:
    if not path.exists():
        return []

    with path.open("r", newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    if mode is not None and rows and "mode" in rows[0]:
        rows = [row for row in rows if row.get("mode") == mode]

    summary = []
    for qp in qps:
        qp_rows = [row for row in rows if int(row["qp"]) == qp]
        if not qp_rows:
            continue
        item: dict[str, float | int] = {
            "qp": qp,
            "bpp": sum(float(row["bpp"]) for row in qp_rows) / len(qp_rows),
            "psnr_rgb": sum(float(row["psnr_rgb"]) for row in qp_rows) / len(qp_rows),
        }
        if "msssim_rgb" in qp_rows[0]:
            item["msssim_rgb"] = sum(float(row["msssim_rgb"]) for row in qp_rows) / len(qp_rows)
        summary.append(item)
    return summary


def nearest_duan_rows(compressai: list[dict[str, float | int]], duan: dict) -> list[dict[str, float | int | str]]:
    duan_bpp = [float(value) for value in duan["bpp"]]
    duan_psnr = [float(value) for value in duan["psnr"]]
    rows = []
    for row in compressai:
        point_bpp = float(row["bpp"])
        nearest = min(range(len(duan_bpp)), key=lambda index: abs(duan_bpp[index] - point_bpp))
        rows.append(
            {
                "compressai_point": int(row["point"]),
                "in_duan_qp_range": "yes" if point_bpp <= max(duan_bpp) else "no",
                "nearest_duan_qp": nearest + 15,
                "compressai_bpp": point_bpp,
                "duan_bpp": duan_bpp[nearest],
                "delta_bpp": point_bpp - duan_bpp[nearest],
                "compressai_psnr_rgb": float(row["psnr_rgb"]),
                "duan_psnr_rgb": duan_psnr[nearest],
                "delta_psnr_rgb": float(row["psnr_rgb"]) - duan_psnr[nearest],
            }
        )
    rows[-1]["in_duan_qp_range"] = "no"
    return rows


def validate_monotonic(rows: list[dict[str, float | int]]) -> dict[str, bool]:
    return {
        "bpp": _strictly_increasing([float(row["bpp"]) for row in rows]),
        "psnr_rgb": _strictly_increasing([float(row["psnr_rgb"]) for row in rows]),
        "msssim_rgb": _strictly_increasing([float(row["msssim_rgb"]) for row in rows]),
    }


def _strictly_increasing(values: list[float]) -> bool:
    return all(left < right for left, right in zip(values, values[1:]))


def plot_metric(
    title: str,
    ylabel: str,
    series: list[dict],
    metric_key: str,
    out_path: Path,
) -> None:
    plt.figure(figsize=(10, 6))
    for item in series:
        label = item["name"]
        rows = item["data"]
        linestyle = item.get("linestyle", "-")
        style = SERIES_STYLES.get(label, {})
        sorted_rows = sorted([row for row in rows if metric_key in row], key=lambda row: float(row["bpp"]))
        if not sorted_rows:
            continue
        plt.plot(
            [float(row["bpp"]) for row in sorted_rows],
            [float(row[metric_key]) for row in sorted_rows],
            color=style.get("color"),
            marker=style.get("marker", "o"),
            linewidth=style.get("linewidth", 2),
            markersize=style.get("markersize", 8),
            linestyle=style.get("linestyle", linestyle),
            label=label,
            zorder=style.get("zorder", 3),
        )

    plt.title(title, fontsize=14)
    plt.xlabel("BPP (Bits Per Pixel)", fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.legend(fontsize=9)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def local_overlap_points(overlap: list[dict[str, float | int]]) -> list[dict[str, float | int]]:
    return [
        {
            "qp": int(row["local_qp"]),
            "bpp": float(row["local_bpp"]),
            "psnr_rgb": float(row["local_psnr_rgb"]),
        }
        for row in overlap
    ]


def write_readme(
    path: Path,
    rows: list[dict[str, float | int]],
    local_overlap: list[dict[str, float | int]],
    overlap: list[dict[str, float | int | str]],
    monotonic: dict[str, bool],
    vtm23_ffmpeg_baseline: list[dict[str, float | int]],
    vtm23_ffmpeg_csf: list[dict[str, float | int]],
    vtm23_opencv_baseline: list[dict[str, float | int]],
    vtm23_opencv_csf: list[dict[str, float | int]],
) -> None:
    path.write_text(
        f"""# CompressAI VTM Validation against InterDigital Anchors

This folder contains the validation environment designed to benchmark the local VTM/VVenC research pipeline against the public Kodak VTM anchor published by InterDigital's CompressAI project and described in the CompressAI paper.

## Experimental Setup

The original dataset results are published at [`CompressAI/results/image/kodak/vtm.json`]({COMPRESSAI_SOURCE}).
The benchmark implementation is available in [`compressai/utils/bench/codecs.py`]({COMPRESSAI_CODE}), and the dataset aggregation CLI is available in [`compressai/utils/bench/__main__.py`]({COMPRESSAI_MAIN}).
The secondary VTM 18.0 anchor used for cross-checking is the raw Duan et al. file [`lossy-vae/results/kodak/kodak-vtm18.0.json`]({DUAN_SOURCE}).

The CompressAI paper reports that its traditional-codec comparison used VVC with **VTM version 9.1**, default intra mode configuration, and **8-bit YCbCr 4:4:4** inputs/outputs. The historical local anchor run reports `VTM Encoder Version 18.0`, so that overlap check remains cross-version rather than an exact same-binary replication. Local VTM 23.0 baseline/CSF curves are added separately when their CSV files are present.

> [!NOTE]
> CompressAI publishes BPP, PSNR-RGB, and MS-SSIM-RGB values, but its `vtm.json` does not store the exact QP list or encoder config path. The report therefore validates RD-curve consistency and metric protocol alignment, not bit-exact reproduction of the CompressAI VTM 9.1 executable.

## Validation Scope

This validation directly checks:
- CompressAI's public Kodak/VTM result structure.
- Monotonic RD behavior for BPP, PSNR-RGB, and MS-SSIM-RGB.
- BPP/PSNR-RGB consistency between the local VTM 18.0 Kodak run and the nearest CompressAI VTM 9.1 RD points.
- The CompressAI metric protocol: RGB PSNR and RGB MS-SSIM averaged over the dataset.

It does not, by itself, fully validate VVenC CSF behavior or local luma/approximation metrics such as `MS-SSIM luma`, `FSIM luma approx`, `HaarPSI luma approx`, `PSNR-HVS-M luma approx`, or `VMAF`.

## Scenario 1: VTM Anchor Overlap

The table below compares the CompressAI VTM 9.1 anchor with the nearest local VTM 18.0 OpenCV 4:4:4 Kodak points. The small BPP and PSNR-RGB deltas indicate that the local pipeline lands on the same Kodak/VTM RD curve family, while the different VTM versions prevent a strict bit-exact claim.

### Table 1: CompressAI VTM 9.1 Anchor vs. Local VTM 18.0 (OpenCV 4:4:4)

| QP | [Local VTM 18.0 (OpenCV 4:4:4) BPP](../vtm_opencv.csv) | [CompressAI VTM 9.1 Anchor BPP]({COMPRESSAI_JSON_LINK}) | [Local VTM 18.0 (OpenCV 4:4:4) PSNR-RGB](../vtm_opencv.csv) | [CompressAI VTM 9.1 Anchor PSNR-RGB]({COMPRESSAI_JSON_LINK}) |
|---:|---:|---:|---:|---:|
{local_overlap_comparison_table(local_overlap)}

![CompressAI VTM 9.1 Anchor vs Local VTM 18.0 (OpenCV 4:4:4)](rd_psnr_compressai_anchor.png)

## Scenario 2: CompressAI MS-SSIM-RGB Reference

Unlike the Duan et al. VTM 18.0 anchor, CompressAI publishes `ms-ssim-rgb` values alongside BPP and PSNR-RGB. The `lossy-vae` repository's `kodak-vtm18.0.json` file only contains `bpp` and `psnr`; `lossy-vae` also keeps a separate [`kodak-vtm-compressai.json`]({DUAN_COMPRESSAI_VTM_SOURCE}) file with CompressAI-style `ms-ssim`, but that is not the VTM 18.0 anchor used by the lossy-vae validation report. This CompressAI report therefore treats MS-SSIM-RGB as a CompressAI-protocol validation target.

Any residual difference between the CompressAI curve and local curves should be interpreted cautiously: CompressAI reports RGB MS-SSIM from its PyTorch pipeline, while the local project reports a standard Gaussian-window MS-SSIM implementation from `metrics/image_quality.py`. The curves are useful for trend and reporting-protocol checks, but they are not a proof of bit-exact numerical equivalence with `pytorch_msssim`.

### Table 2: CompressAI VTM 9.1 Anchor Published Metrics

| Point | [BPP]({COMPRESSAI_JSON_LINK}) | [PSNR-RGB]({COMPRESSAI_JSON_LINK}) | [MS-SSIM-RGB]({COMPRESSAI_JSON_LINK}) |
|---:|---:|---:|---:|
{reference_table(rows)}

![CompressAI VTM 9.1 Anchor MS-SSIM-RGB](rd_msssim_compressai_anchor.png)

## Scenario 3: Local VTM 23.0 Baseline vs. CSF

The same plots also include local VTM 23.0 baseline and CSF curves from [`vtm23_ffmpeg.csv`](../vtm23_ffmpeg.csv) and [`vtm23_opencv.csv`](../vtm23_opencv.csv). These tables report the same-QP Kodak deltas separately from the CompressAI VTM 9.1 anchor overlap, because they compare two local VTM 23.0 executables rather than external anchors.

### Table 3: Local VTM 23.0 Baseline vs. CSF (FFmpeg 4:4:4)

| QP | [Baseline BPP](../vtm23_ffmpeg.csv) | [CSF BPP](../vtm23_ffmpeg.csv) | Delta BPP | [Baseline PSNR-RGB](../vtm23_ffmpeg.csv) | [CSF PSNR-RGB](../vtm23_ffmpeg.csv) | Delta PSNR-RGB |
|---:|---:|---:|---:|---:|---:|---:|
{vtm23_delta_table(vtm23_ffmpeg_baseline, vtm23_ffmpeg_csf)}

### Table 4: Local VTM 23.0 Baseline vs. CSF (OpenCV 4:4:4)

| QP | [Baseline BPP](../vtm23_opencv.csv) | [CSF BPP](../vtm23_opencv.csv) | Delta BPP | [Baseline PSNR-RGB](../vtm23_opencv.csv) | [CSF PSNR-RGB](../vtm23_opencv.csv) | Delta PSNR-RGB |
|---:|---:|---:|---:|---:|---:|---:|
{vtm23_delta_table(vtm23_opencv_baseline, vtm23_opencv_csf)}

### Table 5: Local VTM 18.0 (OpenCV 4:4:4) vs. CompressAI VTM 9.1 Anchor Overlap

| QP | [Local VTM 18.0 (OpenCV 4:4:4) BPP](../vtm_opencv.csv) | [CompressAI VTM 9.1 Anchor BPP]({COMPRESSAI_JSON_LINK}) | Delta BPP | [Local VTM 18.0 (OpenCV 4:4:4) PSNR-RGB](../vtm_opencv.csv) | [CompressAI VTM 9.1 Anchor PSNR-RGB]({COMPRESSAI_JSON_LINK}) | Delta PSNR-RGB |
|---:|---:|---:|---:|---:|---:|---:|
{local_overlap_table(local_overlap)}

## Secondary Cross-Anchor Sanity

The following table compares CompressAI points to the nearest points from the Duan et al. VTM 18.0 raw baseline. This is retained only as a secondary sanity check across public VTM anchors; it is not the primary CompressAI validation.

| QP | [Duan et al. VTM 18.0 Anchor BPP]({DUAN_SOURCE}) | [CompressAI VTM 9.1 Anchor BPP]({COMPRESSAI_JSON_LINK}) | Delta BPP | [Duan et al. VTM 18.0 Anchor PSNR-RGB]({DUAN_SOURCE}) | [CompressAI VTM 9.1 Anchor PSNR-RGB]({COMPRESSAI_JSON_LINK}) | Delta PSNR-RGB |
|---:|---:|---:|---:|---:|---:|---:|
{overlap_table(overlap)}

## Conclusion

The CompressAI anchor supports the correctness of the local research protocol for BPP, PSNR-RGB naming, MS-SSIM-RGB naming, RD-point ordering, and dataset-level averaging. It also provides an external reference for MS-SSIM-RGB reporting, which the Duan validation did not cover. Local luma and approximation metrics remain secondary diagnostics.

Exact same-binary VTM replication would require adding VTM 9.1 to the validation toolchain. Current monotonic checks: BPP `{monotonic["bpp"]}`, PSNR-RGB `{monotonic["psnr_rgb"]}`, MS-SSIM-RGB `{monotonic["msssim_rgb"]}`.
""",
        encoding="utf-8",
        newline="\n",
    )


def reference_table(rows: list[dict[str, float | int]]) -> str:
    return "\n".join(
        f"| {row['point']} | {float(row['bpp']):.5f} | {float(row['psnr_rgb']):.5f} | {float(row['msssim_rgb']):.8f} |"
        for row in rows
    )


def local_overlap_comparison_table(rows: list[dict[str, float | int]]) -> str:
    return "\n".join(
        f"| {row['local_qp']} | "
        f"{float(row['local_bpp']):.5f} | {float(row['compressai_bpp']):.5f} | "
        f"{float(row['local_psnr_rgb']):.5f} | {float(row['compressai_psnr_rgb']):.5f} |"
        for row in rows
    )


def local_overlap_table(rows: list[dict[str, float | int]]) -> str:
    return "\n".join(
        f"| {row['local_qp']} | "
        f"{float(row['local_bpp']):.5f} | {float(row['compressai_bpp']):.5f} | {float(row['delta_bpp']):+.5f} | "
        f"{float(row['local_psnr_rgb']):.5f} | {float(row['compressai_psnr_rgb']):.5f} | {float(row['delta_psnr_rgb']):+.5f} |"
        for row in rows
    )


def vtm23_delta_table(baseline: list[dict[str, float | int]], csf: list[dict[str, float | int]]) -> str:
    baseline_by_qp = {int(row["qp"]): row for row in baseline}
    csf_by_qp = {int(row["qp"]): row for row in csf}
    lines = []
    for qp in sorted(set(baseline_by_qp) | set(csf_by_qp)):
        base = baseline_by_qp.get(qp)
        csf_row = csf_by_qp.get(qp)
        if base is None or csf_row is None:
            lines.append(f"| {qp} | N/A | N/A | N/A | N/A | N/A | N/A |")
            continue
        baseline_bpp = float(base["bpp"])
        csf_bpp = float(csf_row["bpp"])
        baseline_psnr = float(base["psnr_rgb"])
        csf_psnr = float(csf_row["psnr_rgb"])
        lines.append(
            f"| {qp} | {baseline_bpp:.5f} | {csf_bpp:.5f} | {csf_bpp - baseline_bpp:+.5f} | "
            f"{baseline_psnr:.5f} | {csf_psnr:.5f} | {csf_psnr - baseline_psnr:+.5f} |"
        )
    return "\n".join(lines)


def overlap_table(rows: list[dict[str, float | int | str]]) -> str:
    return "\n".join(
        f"| {row['nearest_duan_qp']} | "
        f"{float(row['duan_bpp']):.5f} | {float(row['compressai_bpp']):.5f} | {float(row['delta_bpp']):+.5f} | "
        f"{float(row['duan_psnr_rgb']):.5f} | {float(row['compressai_psnr_rgb']):.5f} | {float(row['delta_psnr_rgb']):+.5f} |"
        for row in rows
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CompressAI Kodak VTM validation artifacts.")
    parser.add_argument("--compressai-json", type=Path, default=ROOT / "data" / "baselines" / "compressai_kodak_vtm.json")
    parser.add_argument("--duan-json", type=Path, default=ROOT / "data" / "baselines" / "kodak_vtm.json")
    parser.add_argument("--local-vtm-csv", type=Path, default=ROOT / "docs" / "vtm_validation" / "vtm_opencv.csv")
    parser.add_argument("--vtm23-ffmpeg-csv", type=Path, default=ROOT / "docs" / "vtm_validation" / "vtm23_ffmpeg.csv")
    parser.add_argument("--vtm23-opencv-csv", type=Path, default=ROOT / "docs" / "vtm_validation" / "vtm23_opencv.csv")
    parser.add_argument("--vvenc-baseline-csv", type=Path, default=ROOT / "docs" / "vtm_validation" / "vvenc_baseline.csv")
    parser.add_argument("--vvenc-opencv-csv", type=Path, default=ROOT / "docs" / "vtm_validation" / "vvenc_opencv.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "vtm_validation" / "compressai")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = compressai_rows(load_json(args.compressai_json))
    local_overlap = local_vtm_overlap_rows(rows, args.local_vtm_csv)
    local_vtm = local_summary_rows(args.local_vtm_csv)
    vtm23_ffmpeg_baseline = local_summary_rows(args.vtm23_ffmpeg_csv, mode="baseline")
    vtm23_ffmpeg_csf = local_summary_rows(args.vtm23_ffmpeg_csv, mode="csf")
    vtm23_opencv_baseline = local_summary_rows(args.vtm23_opencv_csv, mode="baseline")
    vtm23_opencv_csf = local_summary_rows(args.vtm23_opencv_csv, mode="csf")
    vvenc_baseline = local_summary_rows(args.vvenc_baseline_csv)
    vvenc_opencv = local_summary_rows(args.vvenc_opencv_csv)
    overlap = nearest_duan_rows(rows, load_json(args.duan_json))
    monotonic = validate_monotonic(rows)

    plot_metric(
        "Rate-Distortion Comparison: CompressAI VTM 9.1 Anchor vs Local VTM 18.0 (Kodak)",
        "PSNR-RGB (dB)",
        [
            {"name": "CompressAI VTM 9.1 Anchor", "data": rows, "linestyle": "-"},
            {"name": "Local VTM 18.0 (OpenCV 4:4:4)", "data": local_vtm, "linestyle": "--"},
            {"name": "Local VTM 23.0 Baseline (FFmpeg 4:4:4)", "data": vtm23_ffmpeg_baseline, "linestyle": "-"},
            {"name": "Local VTM 23.0 CSF (FFmpeg 4:4:4)", "data": vtm23_ffmpeg_csf, "linestyle": "-."},
            {"name": "Local VTM 23.0 Baseline (OpenCV 4:4:4)", "data": vtm23_opencv_baseline, "linestyle": "-"},
            {"name": "Local VTM 23.0 CSF (OpenCV 4:4:4)", "data": vtm23_opencv_csf, "linestyle": "-."},
            {"name": "Local VVenC (FFmpeg 4:2:0)", "data": vvenc_baseline, "linestyle": "-"},
            {"name": "Local VVenC (OpenCV 4:2:0)", "data": vvenc_opencv, "linestyle": "-."},
        ],
        "psnr_rgb",
        output_dir / "rd_psnr_compressai_anchor.png",
    )
    plot_metric(
        "Rate-Distortion Comparison: CompressAI VTM 9.1 Anchor MS-SSIM-RGB",
        "MS-SSIM-RGB",
        [
            {"name": "CompressAI VTM 9.1 Anchor", "data": rows, "linestyle": "-"},
            {"name": "Local VTM 18.0 (OpenCV 4:4:4)", "data": local_vtm, "linestyle": "--"},
            {"name": "Local VTM 23.0 Baseline (FFmpeg 4:4:4)", "data": vtm23_ffmpeg_baseline, "linestyle": "-"},
            {"name": "Local VTM 23.0 CSF (FFmpeg 4:4:4)", "data": vtm23_ffmpeg_csf, "linestyle": "-."},
            {"name": "Local VTM 23.0 Baseline (OpenCV 4:4:4)", "data": vtm23_opencv_baseline, "linestyle": "-"},
            {"name": "Local VTM 23.0 CSF (OpenCV 4:4:4)", "data": vtm23_opencv_csf, "linestyle": "-."},
            {"name": "Local VVenC (FFmpeg 4:2:0)", "data": vvenc_baseline, "linestyle": "-"},
            {"name": "Local VVenC (OpenCV 4:2:0)", "data": vvenc_opencv, "linestyle": "-."},
        ],
        "msssim_rgb",
        output_dir / "rd_msssim_compressai_anchor.png",
    )
    write_readme(
        output_dir / "README.md",
        rows,
        local_overlap,
        overlap,
        monotonic,
        vtm23_ffmpeg_baseline,
        vtm23_ffmpeg_csf,
        vtm23_opencv_baseline,
        vtm23_opencv_csf,
    )
    print(f"CompressAI validation written to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
