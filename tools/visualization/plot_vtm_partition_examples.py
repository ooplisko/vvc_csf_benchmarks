"""Compose clean Kodak images and their existing QP 32 CU maps for a paper."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "docs/vtm_content_partition_study"
OUTPUT = STUDY / "spatial_complexity/figures"


def main() -> None:
    with (STUDY / "spatial_complexity/tables/joined_measurements.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        counts = {
            row["source"]: int(row["cu_count"])
            for row in csv.DictReader(stream)
            if row["distortion"] == "clean" and int(row["qp"]) == 32
        }

    with plt.rc_context({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
        "font.size": 12,
        "axes.titlesize": 12,
        "axes.titleweight": "normal",
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    }):
        fig, axes = plt.subplots(2, 2, figsize=(6.8, 5.1), layout="constrained")
        for column, number in enumerate(("02", "08")):
            source = f"kodim{number}.png"
            axes[0, column].imshow(plt.imread(STUDY / "examples/sources" / source))
            axes[0, column].set_title(f"Kodak {number}", pad=5)
            axes[1, column].imshow(plt.imread(
                STUDY / f"examples/partition_maps/complexity/kodim{number}/QP32.png"
            ))
            axes[1, column].set_title(f"QP 32   {counts[source]:} CUs", pad=5)
        for ax in axes.flat:
            ax.set_axis_off()
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for extension in ("png", "pdf", "svg"):
            path = OUTPUT / f"Kodak_partition_examples_QP32.{extension}"
            fig.savefig(path, dpi=600, bbox_inches="tight", pad_inches=0.025)
            print(path.relative_to(ROOT))
        plt.close(fig)


if __name__ == "__main__":
    main()
