"""Reader-facing timing, quality and descriptor-change tables for the Kodak study."""

from pathlib import Path

import numpy as np
import pandas as pd

from tools.research.summarize_vtm_spatial_complexity import CONDITIONS, summarize_quality
from vvenc_csf.spatial_complexity import FEATURES


TABLES = {
    "descriptor_timing_summary": "Descriptor runtime by input condition",
    "descriptor_timing_images": "Repeated-runtime summaries for each of the 168 inputs",
    "descriptor_timing_environment": "Runtime settings, software, hardware and input hashes",
    "quality_measurements": "VTM-reported component PSNR and file size for 672 primary encodings",
    "quality_summary": "Quality and file-size summaries at each condition and QP",
    "descriptor_changes": "Changes in descriptor values and image rankings for the primary disturbances",
}


def load_supplement(directory: Path) -> dict:
    if not directory.exists():
        return {}
    result = {}
    for name in TABLES:
        path = directory / f"{name}.csv"
        if not path.is_file():
            raise ValueError(f"Incomplete descriptor supplement: {name}")
        result[f"supplement/{name}"] = pd.read_csv(path, dtype={"seed": str}, float_precision="round_trip").fillna({"seed": ""})
    quality = result["supplement/quality_measurements"]
    expected = {(f"kodim{i:02d}.png", distortion, level, qp)
                for i in range(1, 25) for distortion, level in CONDITIONS for qp in (22, 27, 32, 37)}
    if (len(quality) != len(expected) or set(quality[["source", "distortion", "level", "qp"]].itertuples(index=False, name=None)) != expected
            or not quality.reference.eq("actual_encoder_input").all()
            or not quality.seed.eq(np.where(quality.distortion.eq("awgn"), "20260811", "")).all()):
        raise ValueError("Invalid primary quality matrix or reference")
    rebuilt = pd.DataFrame(summarize_quality(quality.to_dict("records"))).sort_values(["distortion", "level", "qp"]).reset_index(drop=True)
    saved = result["supplement/quality_summary"].sort_values(["distortion", "level", "qp"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(saved, rebuilt, check_dtype=False, rtol=1e-12, atol=1e-12)
    changes = result["supplement/descriptor_changes"]
    expected_changes = {(d, level, f) for d, level in CONDITIONS[1:] for f in FEATURES}
    if (len(changes) != 36 or set(changes[["distortion", "level", "feature"]].itertuples(index=False, name=None)) != expected_changes
            or not changes.n_images.eq(24).all() or not changes.clean_disturbed_rank_rho.between(-1, 1).all()):
        raise ValueError("Invalid primary descriptor-change matrix")
    timings = result["supplement/descriptor_timing_summary"]
    operations = (*FEATURES, "glcm_shared", "glcm_build", "luma_conversion", "full_pipeline")
    expected_timings = {(d, level, op) for d, level in CONDITIONS for op in operations}
    if (len(timings) != 70 or set(timings[["distortion", "level", "operation"]].itertuples(index=False, name=None)) != expected_timings
            or not timings.n_images.eq(24).all() or not np.isfinite(timings.median_ms).all()
            or not timings.median_ms.gt(0).all()):
        raise ValueError("Invalid runtime condition matrix")
    images = result["supplement/descriptor_timing_images"]
    expected_images = {(f"kodim{i:02d}.png", d, level, op)
                       for i in range(1, 25) for d, level in CONDITIONS for op in operations}
    settings = result["supplement/descriptor_timing_environment"].set_index("setting").value
    if (len(images) != len(expected_images)
            or set(images[["source", "distortion", "level", "operation"]].itertuples(index=False, name=None)) != expected_images
            or not images.repeats.eq(int(settings["repeats"])).all()):
        raise ValueError("Invalid per-image timing coverage")
    for row in timings.itertuples():
        values = images[images.distortion.eq(row.distortion) & images.level.eq(row.level)
                        & images.operation.eq(row.operation)].median_ms.to_numpy()
        if not np.allclose(np.quantile(values, [0, .25, .5, .75, 1]),
                           [row.min_ms, row.q25_ms, row.median_ms, row.q75_ms, row.max_ms], atol=1e-12, rtol=1e-12):
            raise ValueError("Runtime summary differs from per-image medians")
    return result


def supplement_section(tables: dict, labels: dict) -> list[str]:
    if "supplement/quality_summary" not in tables:
        return []
    environment = tables["supplement/descriptor_timing_environment"].set_index("setting").value
    timings = tables["supplement/descriptor_timing_summary"]
    clean = timings[timings.distortion.eq("clean")].set_index("operation")
    names = {**labels, "glcm_shared": "Three GLCM features together", "luma_conversion": "BGR-to-luma preparation",
             "full_pipeline": "Existing six-descriptor pipeline from BGR"}
    lines = ["## Computation Time", "",
             f"Measured on {environment['cpu']} with Python {environment['python']}, NumPy {environment['numpy']} "
             f"and OpenCV {environment['opencv']}. OpenCV uses one thread and OpenCL is disabled. "
             f"Each of the 168 primary inputs has {environment['warmup']} warmup runs and {environment['repeats']} timed repetitions per operation. "
             "Operation order is randomized within each repetition. PNG loading is outside the timer. "
             "Timing does not depend on QP, so the same input is measured once across the four coding settings.", "",
             "The table reports the median and interquartile range of the 24 per-image median times for clean Kodak images "
             "(393,216 pixels each). Individual descriptors start from the prepared 8-bit luma plane. "
             "Every standalone GLCM time includes quantization and construction of all four directional matrices. "
             "The shared row builds these matrices once for all three features. Preparation and the existing full pipeline "
             "are timed separately; its internal conversions are retained. Do not add these overlapping rows together.", "",
             "| Operation | Median (ms/image) | Interquartile range (ms/image) |",
             "| --- | ---: | ---: |"]
    for operation, label in names.items():
        row = clean.loc[operation]
        lines.append(f"| {label} | {row.median_ms:.3f} | {row.q25_ms:.3f}–{row.q75_ms:.3f} |")
    lines += ["", "These measurements describe the tested implementations on this computer. Isolated edge/GLCM calculations "
              "use the same operations and are checked against the existing pipeline and saved feature values on every input. "
              "Timings for every disturbance condition and per-image variation are retained in the CSVs. "
              "They do not measure an encoder speedup or establish a hardware-independent ranking.", "",
              "## Reconstruction Quality at the Tested QPs", "",
              "PSNR is extracted from the saved VTM 23.0 single-frame summaries for Y, U and V in 4:4:4 coding. "
              "The reference is the actual encoder input, including any added disturbance. These values therefore describe "
              "compression error; they do not measure noise removal relative to the clean original. "
              "The table shows clean-image medians, with the full range across 24 images in parentheses, in dB.", "",
              "| QP | Y-PSNR | U-PSNR | V-PSNR |", "| --- | ---: | ---: | ---: |"]
    quality = tables["supplement/quality_summary"]
    for row in quality[quality.distortion.eq("clean")].sort_values("qp").to_dict("records"):
        values = [f"{row[f'psnr_{c}_db_median']:.2f} ({row[f'psnr_{c}_db_min']:.2f}–{row[f'psnr_{c}_db_max']:.2f})" for c in "yuv"]
        lines.append(f"| {row['qp']} | " + " | ".join(values) + " |")
    lines += ["", "PSNR quantifies sample error and does not establish whether distortion is invisible or non-annoying. "
              "The full tables retain all seven input conditions and four QPs, component PSNR, file size and recorded encoding time. "
              "File bpp uses the complete bitstream byte count divided by image area, including file overhead. "
              "Recorded VTM times come from trace-enabled runs with different concurrent workloads, "
              "so they are not used as a controlled speed comparison with the descriptor benchmark.", "",
              "<details>", "<summary>Descriptor values and image ordering under disturbances</summary>", "",
              "The correlations below compare clean and disturbed rankings by the same descriptor, not rankings by CU count. "
              "They use 24 paired sources and the primary AWGN realization. The input descriptor does not depend on QP. "
              "The strongest tested conditions illustrate ordering changes; all six disturbance levels are retained in the CSV.", "",
              "| Measure | Clean vs AWGN 30 rank correlation | Clean vs Sine 32 rank correlation |",
              "| --- | ---: | ---: |"]
    changes = tables["supplement/descriptor_changes"].set_index(["feature", "distortion", "level"])
    for feature, label in labels.items():
        a, b = changes.loc[(feature, "awgn", 30)], changes.loc[(feature, "stripes", 32)]
        lines.append(f"| {label} | {a.clean_disturbed_rank_rho:.3f} | {b.clean_disturbed_rank_rho:.3f} |")
    edge = changes.loc[("edge_fraction", "awgn", 30)]
    lines += ["", f"For example, median edge fraction rises from {edge.clean_median:.3f} to {edge.disturbed_median:.3f} "
              f"under AWGN 30, while its clean–disturbed rank correlation remains {edge.clean_disturbed_rank_rho:.3f}. "
              "Changes in values, changes in ordering, and changes in association with CU count are different questions. "
              "These descriptive summaries contain no new significance tests and do not validate a threshold for choosing a codec.", "",
              "</details>", ""]
    return lines
