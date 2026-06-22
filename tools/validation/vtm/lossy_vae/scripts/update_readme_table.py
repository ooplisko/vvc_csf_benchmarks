"""Update the Markdown comparison table in the lossy-vae VTM validation README."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[5]


def read_reference_points(path: Path, qps: list[int]) -> dict[int, dict[str, float]]:
    with path.open("r", encoding="utf-8") as stream:
        ref_data = json.load(stream)
    return {
        qp: {"bpp": float(ref_data["bpp"][qp - 15]), "psnr": float(ref_data["psnr"][qp - 15])}
        for qp in qps
    }


def read_csv_points(path: Path, qps: list[int], mode: str | None = "baseline") -> dict[int, dict[str, float]]:
    if not path.exists():
        return {}

    frame = pd.read_csv(path)
    if mode is not None and "mode" in frame.columns:
        frame = frame[frame["mode"] == mode]

    data = {}
    for qp in qps:
        qp_rows = frame[frame["qp"] == qp]
        if not qp_rows.empty:
            data[qp] = {
                "bpp": float(qp_rows["bpp"].mean()),
                "psnr": float(qp_rows["psnr_rgb"].mean()),
            }
    return data


def value_at(points: dict[int, dict[str, float]], qp: int, key: str) -> str:
    if qp not in points:
        return "N/A"
    return f"{points[qp][key]:.5f}"


def bold_value_at(points: dict[int, dict[str, float]], qp: int, key: str) -> str:
    value = value_at(points, qp, key)
    if value == "N/A":
        return value
    return f"**{value}**"


def build_table(results_dir: Path, baseline_json: Path, qps: list[int]) -> str:
    reference = read_reference_points(baseline_json, qps)
    opencv = read_csv_points(results_dir / "vtm_opencv.csv", qps)

    ref_link = "https://github.com/duanzhiihao/lossy-vae/blob/main/results/kodak/kodak-vtm18.0.json"
    opencv_link = "../vtm_opencv.csv"

    lines = [
        "| QP | [Duan et al. VTM 18.0 Anchor BPP]({ref}) | [Local VTM 18.0 (OpenCV 4:4:4) BPP]({opencv}) | [Duan et al. VTM 18.0 Anchor PSNR-RGB]({ref}) | [Local VTM 18.0 (OpenCV 4:4:4) PSNR-RGB]({opencv}) |".format(
            ref=ref_link,
            opencv=opencv_link,
        ),
        "|----|------------------------|--------------------|----------------------------|---------------------------|",
    ]

    for qp in qps:
        reference_bpp = value_at(reference, qp, "bpp")
        opencv_bpp = bold_value_at(opencv, qp, "bpp")
        reference_psnr = value_at(reference, qp, "psnr")
        opencv_psnr = value_at(opencv, qp, "psnr")
        lines.append(
            f"| {qp} | "
            f"{reference_bpp:<15} | "
            f"{opencv_bpp:<18} | "
            f"{reference_psnr:<12} | "
            f"{opencv_psnr:<25} |"
        )
    return "\n".join(lines) + "\n"


def delta_at(left: dict[int, dict[str, float]], right: dict[int, dict[str, float]], qp: int, key: str) -> str:
    if qp not in left or qp not in right:
        return "N/A"
    return f"{right[qp][key] - left[qp][key]:+.5f}"


def build_vtm23_table(results_dir: Path, qps: list[int], csv_name: str, label: str, table_number: int) -> str:
    baseline = read_csv_points(results_dir / csv_name, qps, mode="baseline")
    csf = read_csv_points(results_dir / csv_name, qps, mode="csf")
    link = f"../{csv_name}"

    lines = [
        f"### Table {table_number}: Local VTM 23.0 Baseline vs. CSF ({label})",
        "",
        f"| QP | [Baseline BPP]({link}) | [CSF BPP]({link}) | Delta BPP | [Baseline PSNR-RGB]({link}) | [CSF PSNR-RGB]({link}) | Delta PSNR-RGB |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for qp in qps:
        lines.append(
            f"| {qp} | "
            f"{value_at(baseline, qp, 'bpp')} | {value_at(csf, qp, 'bpp')} | {delta_at(baseline, csf, qp, 'bpp')} | "
            f"{value_at(baseline, qp, 'psnr')} | {value_at(csf, qp, 'psnr')} | {delta_at(baseline, csf, qp, 'psnr')} |"
        )
    return "\n".join(lines)


def build_vtm23_section(results_dir: Path, qps: list[int]) -> str:
    return "\n\n".join(
        [
            "## Scenario 3: Local VTM 23.0 Baseline vs. CSF",
            "The generated RD plots include local VTM 23.0 baseline and CSF curves from [`vtm23_ffmpeg.csv`](../vtm23_ffmpeg.csv) and [`vtm23_opencv.csv`](../vtm23_opencv.csv). The tables below keep this experiment separate from the historical VTM 18.0 anchor replication and report average Kodak deltas at the same QP.",
            build_vtm23_table(results_dir, qps, "vtm23_ffmpeg.csv", "FFmpeg 4:4:4", 3),
            build_vtm23_table(results_dir, qps, "vtm23_opencv.csv", "OpenCV 4:4:4", 4),
        ]
    )


def update_readme(readme_path: Path, table: str, vtm23_section: str) -> None:
    content = readme_path.read_text(encoding="utf-8")
    table_pattern = re.compile(
        r"(?<=### Table 1: VTM 18\.0 \(4:4:4\) Replication\n\n)"
        r"\| QP \|.*?\n\n",
        re.DOTALL,
    )

    if not table_pattern.search(content):
        raise RuntimeError(f"Could not find Table 1 in {readme_path}")

    content = table_pattern.sub(table + "\n", content)
    scenario_pattern = re.compile(r"## Scenario 3: Local VTM 23\.0 Baseline vs\. CSF\n\n.*?(?=\n## Conclusion)", re.DOTALL)
    if not scenario_pattern.search(content):
        raise RuntimeError(f"Could not find Scenario 3 in {readme_path}")
    content = scenario_pattern.sub(vtm23_section, content)

    readme_path.write_text(content, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update the VTM validation README comparison table.")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "docs" / "vtm_validation")
    parser.add_argument("--readme", type=Path, default=ROOT / "docs" / "vtm_validation" / "lossy-vae" / "README.md")
    parser.add_argument("--baseline-json", type=Path, default=ROOT / "data" / "baselines" / "kodak_vtm.json")
    parser.add_argument("--qps", default="22,27,32,37", help="Comma-separated QP list.")
    args = parser.parse_args()
    args.qps = [int(item) for item in args.qps.split(",") if item.strip()]
    return args


def main() -> int:
    args = parse_args()
    update_readme(args.readme, build_table(args.results_dir, args.baseline_json, args.qps), build_vtm23_section(args.results_dir, args.qps))
    print(f"README updated: {args.readme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
