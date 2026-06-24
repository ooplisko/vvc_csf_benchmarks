from __future__ import annotations

import csv
from pathlib import Path

from tools.reporting.report_vtm_qp_study import build_readme, robustness_rows


def test_vtm_qp_readme_groups_charts_by_image(tmp_path: Path) -> None:
    dataset = tmp_path / "standard_color"
    dataset.mkdir()
    delta_csv = dataset / "selected_metric_deltas.csv"
    with delta_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "image",
                "qp_points",
                "bpp_delta_pct_mean",
                "psnr_rgb_delta_mean",
                "msssim_rgb_delta_mean",
                "psnr_hvs_m_luma_delta_mean",
                "haarpsi_luma_delta_mean",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "image": "baboon",
                "qp_points": 4,
                "bpp_delta_pct_mean": -1,
                "psnr_rgb_delta_mean": -0.1,
                "msssim_rgb_delta_mean": -0.001,
                "psnr_hvs_m_luma_delta_mean": -0.2,
                "haarpsi_luma_delta_mean": -0.01,
            }
        )

    readme = build_readme(
        tmp_path,
        [
            (
                "standard_color",
                "Standard Color",
                ("psnr_rgb", "msssim_rgb", "psnr_hvs_m_luma", "haarpsi_luma"),
            )
        ],
        32,
    )

    assert "<summary><strong>Baboon</strong>: QP curves and partition maps</summary>" in readme
    assert "It intentionally excludes Kodak" not in readme
    assert "Each image is reported independently" not in readme
    assert "authors' MIT-licensed Python/NumPy implementation" in readme
    assert "PSNR-HVS-M is identified more narrowly as a source-faithful Python port" in readme
    assert "[Duan et al. validation report](../vtm_validation/lossy-vae/README.md)" in readme
    assert "[CompressAI validation report](../vtm_validation/compressai/README.md)" in readme
    assert "../../third_party/haarpsi/SOURCE.md" in readme
    assert "../../third_party/psnr_hvs_m/SOURCE.md" in readme


def test_robustness_ranking_uses_per_metric_ordinal_ranks() -> None:
    rows = [
        {"image": "a", "m1_delta_mean": -0.1, "m2_delta_mean": -0.3},
        {"image": "b", "m1_delta_mean": -0.2, "m2_delta_mean": -0.1},
        {"image": "c", "m1_delta_mean": -0.3, "m2_delta_mean": -0.2},
    ]

    ranked = robustness_rows(rows, ("m1", "m2"))

    assert [row["image"] for row in ranked] == ["b", "a", "c"]
    assert [row["rank_sum"] for row in ranked] == [3, 4, 5]
