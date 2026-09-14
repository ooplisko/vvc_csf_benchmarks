"""Build the project report from completed VTM spatial-complexity tables."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.reporting.vtm_noise_validation_report import (
    TABLES as VALIDATION_TABLES, load_validation_tables, plot_validation, validation_section,
)

LABELS = {"sobel_si": "Sobel SD", "luma_sd": "Luma SD", "edge_fraction": "Edge fraction",
          "glcm_contrast": "GLCM contrast", "glcm_entropy": "GLCM entropy",
          "glcm_homogeneity": "GLCM homogeneity"}
COLORS = ("#222222", "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#6A51A3")
TABLE_DESCRIPTIONS = {
    "stimulus_features": "Complexity values for each clean or disturbed input image",
    "joined_measurements": "Complexity values and final CU counts for the same image and QP",
    "correlations": "Correlations and their uncertainty at every tested QP and disturbance condition",
    "contrasts": "Whether differences from Sobel or from the clean-image correlation are supported",
    "parameter_sensitivity": "How correlations change with the GLCM settings",
    "clean_feature_associations": "How strongly the complexity descriptors relate to one another",
    "direction_features": "GLCM values for each separate neighbor direction",
    "leave_one_out_contrasts": "How comparisons change when each image is left out in turn",
    "paired_change_correlations": "Supplementary association between within-image descriptor and CU changes",
    "paired_changes": "Individual descriptor and CU changes relative to the clean image",
}
NOISE_TABLES = {
    "exploratory_noise_comparisons": "Direct comparisons of noise responses between homogeneity and other descriptors",
    "noise_rank_diagnostics": "Changes in image ranks and descriptor spread under AWGN",
}
ROOT = Path(__file__).resolve().parents[2]
QP_STYLES = {22: ("#0072B2", "o"), 27: ("#CC79A7", "D"),
             32: ("#D55E00", "s"), 37: ("#009E73", "^")}


def disturbance_qps(correlations: pd.DataFrame) -> tuple[int, ...]:
    return tuple(sorted(correlations.loc[correlations.primary & (correlations.distortion != "clean"), "qp"].unique()))


def load_tables(analysis: Path, validation: Path | None = None) -> dict[str, pd.DataFrame]:
    """Check the saved measurement matrix before creating report artifacts."""

    if validation is not None and not validation.is_dir():
        raise ValueError(f"Missing DIV2K analysis directory: {validation}")
    tables = {}
    for name in TABLE_DESCRIPTIONS:
        path = analysis / f"{name}.csv"
        if not path.is_file():
            raise ValueError(f"Missing analysis table: {name}")
        tables[name] = pd.read_csv(path, dtype={"seed": str}, float_precision="round_trip").fillna({"seed": ""})
    joined = tables["joined_measurements"]
    if not joined["mode"].eq("baseline").all():
        raise ValueError("The report accepts baseline VTM measurements only")
    if not joined["reconstruction_verified"].eq(True).all() or not joined["cu_coverage_verified"].eq(True).all():
        raise ValueError("The report requires verified reconstructions and CU coverage")
    if len(joined) not in (672, 1248) or joined.source.nunique() != 24:
        raise ValueError("Expected 672 original or 1248 four-QP measurements of all 24 Kodak images")
    extended = len(joined) == 1248
    if joined.duplicated(["stimulus", "qp"]).any():
        raise ValueError("Duplicate stimulus/QP measurements")
    if extended and (joined.stimulus.nunique() != 312 or
                     not joined.groupby("stimulus").qp.apply(lambda qps: set(qps) == set(QP_STYLES)).all()):
        raise ValueError("The extension requires every stimulus at all four QPs")
    correlations, contrasts = tables["correlations"], tables["contrasts"]
    total, primary, rq2 = (312, 168, 144) if extended else (168, 132, 108)
    if len(correlations) != total or correlations.primary.sum() != primary or not correlations.n_images.eq(24).all():
        raise ValueError(f"Expected {primary} primary and {total - primary} extra-seed correlation cells, each with 24 images")
    if contrasts.family.value_counts().to_dict() != {"RQ2": rq2, "RQ1": 20}:
        raise ValueError(f"Expected 20 RQ1 and {rq2} RQ2 dependent comparisons")
    expected_qps = (22, 27, 32, 37) if extended else (22, 32, 37)
    if disturbance_qps(correlations) != expected_qps:
        raise ValueError("Unexpected disturbance QPs")
    if correlations.duplicated(["distortion", "level", "seed", "qp", "feature"]).any():
        raise ValueError("Duplicate correlation cells")
    if extended and (correlations[correlations.primary].groupby("qp").size().to_dict() != dict.fromkeys(QP_STYLES, 42)
                     or correlations[~correlations.primary].groupby("qp").size().to_dict() != dict.fromkeys(QP_STYLES, 36)):
        raise ValueError("Expected primary and supplementary correlations at all four QPs")
    condition_columns = ["distortion", "level", "seed", "qp"]
    conditions = {("clean", 0, "", qp) for qp in QP_STYLES}
    conditions |= {("stripes", level, "", qp) for level in (8, 16, 32) for qp in expected_qps}
    conditions |= {("awgn", level, "20260811", qp) for level in (5, 15, 30) for qp in expected_qps}
    conditions |= {("awgn", level, seed, qp) for level in (5, 15, 30)
                   for seed in ("20260812", "20260813") for qp in (expected_qps if extended else (32,))}
    if set(joined[condition_columns].itertuples(index=False, name=None)) != conditions:
        raise ValueError("Missing or unexpected measurement condition")
    expected_cells = {(*condition, feature)
                      for condition in joined[condition_columns].drop_duplicates().itertuples(index=False, name=None)
                      for feature in LABELS}
    observed_cells = set(correlations[condition_columns + ["feature"]].itertuples(index=False, name=None))
    if observed_cells != expected_cells:
        raise ValueError("Correlation cells do not match the measured conditions and descriptors")
    if not joined.groupby(condition_columns).source.nunique().eq(24).all():
        raise ValueError("Every measured condition requires the same 24 images")
    expected_primary = correlations.distortion.ne("awgn") | correlations.seed.eq("20260811")
    if not correlations.primary.eq(expected_primary).all():
        raise ValueError("Primary AWGN cells must use base seed 20260811")
    if not np.isfinite(correlations.rho).all() or not correlations.rho.between(-1, 1).all():
        raise ValueError("Correlations must be finite values between -1 and 1")
    if contrasts.duplicated(["family", *condition_columns, "feature"]).any():
        raise ValueError("Duplicate comparison cells")
    expected_contrasts = {("RQ1" if row.distortion == "clean" else "RQ2", row.distortion, row.level, row.seed, row.qp, row.feature)
                          for row in correlations[correlations.primary].itertuples()
                          if row.distortion != "clean" or row.feature != "sobel_si"}
    if set(contrasts[["family", *condition_columns, "feature"]].itertuples(index=False, name=None)) != expected_contrasts:
        raise ValueError("Comparison cells do not match the primary correlations")
    present = [(analysis / f"{name}.csv").is_file() for name in NOISE_TABLES]
    if any(present) and not all(present):
        raise ValueError("Both noise-sensitivity tables are required together")
    if all(present):
        for name in NOISE_TABLES:
            tables[name] = pd.read_csv(analysis / f"{name}.csv", dtype={"seed": str}, float_precision="round_trip")
        comparisons = tables["exploratory_noise_comparisons"]
        expected = {(family, feature, qp) for family in ("primary_sigma30", "equal_mean3_sigma30")
                    for feature in LABELS if feature != "glcm_homogeneity" for qp in QP_STYLES}
        if (len(comparisons) != 40 or set(comparisons[["family", "feature", "qp"]].itertuples(index=False, name=None)) != expected
                or not comparisons.analysis_status.eq("exploratory").all() or not comparisons.n_images.eq(24).all()
                or not comparisons.family_size.eq(20).all() or not comparisons.alpha.eq(0.05).all()):
            raise ValueError("Unexpected exploratory noise-comparison families")
        if not np.allclose(comparisons.oriented_difference, comparisons.b_homogeneity - comparisons.b_other, atol=1e-12, rtol=0):
            raise ValueError("Noise differences do not match their component changes")
        supported = comparisons.evaluable & ((comparisons.simultaneous_low > 0) | (comparisons.simultaneous_high < 0))
        if not supported.equals(comparisons.excludes_zero):
            raise ValueError("Noise comparison flags do not match their intervals")
        diagnostics = tables["noise_rank_diagnostics"]
        variants = {(feature, "primary") for feature in LABELS}
        variants |= {(feature, variant) for feature in LABELS if feature.startswith("glcm_")
                     for variant in ("levels32", "horizontal")}
        expected_diagnostics = {(feature, variant, level, seed, qp) for feature, variant in variants
                                for level in (5, 15, 30) for seed in ("20260811", "20260812", "20260813") for qp in QP_STYLES}
        if (len(diagnostics) != len(expected_diagnostics) or not diagnostics.n_images.eq(24).all()
                or set(diagnostics[["feature", "variant", "level", "seed", "qp"]].itertuples(index=False, name=None)) != expected_diagnostics):
            raise ValueError("Unexpected noise rank-diagnostic conditions")
    tables.update(load_validation_tables(validation or analysis / "div2k"))
    return tables


def noise_sensitivity_section(tables: dict[str, pd.DataFrame]) -> list[str]:
    if "exploratory_noise_comparisons" not in tables:
        return []
    comparisons = tables["exploratory_noise_comparisons"]
    lines = ["<details>", "<summary>Exploratory comparison of descriptor responses to strong AWGN</summary>", "",
             "To compare noise responses directly, define `C = B[homogeneity] − B[other]` at sigma 30. "
             "A negative C means a more negative direction-adjusted change for homogeneity. "
             "Weakening of homogeneity itself additionally requires a negative B. "
             "Comparing the significance labels of two separate B intervals does not test C.", "",
             "These comparisons were selected after inspecting the original results and are exploratory. "
             "Each of the two summaries below uses its own family of 20 simultaneous intervals at alpha 0.05; "
             "they do not provide a joint error guarantee across both summaries or replace the original comparisons. "
             "An asterisk means that the interval for C excludes zero. Independent images are needed to confirm the pattern.", ""]
    for family, title in (("primary_sigma30", "Primary AWGN realization"),
                          ("equal_mean3_sigma30", "Equal mean of three realization-specific changes")):
        selected = comparisons[comparisons.family.eq(family)]
        lines += [f"**{title}**", "", "| Compared with homogeneity | QP 22 | QP 27 | QP 32 | QP 37 |",
                  "| --- | ---: | ---: | ---: | ---: |"]
        for feature, label in LABELS.items():
            if feature == "glcm_homogeneity":
                continue
            rows = selected[selected.feature.eq(feature)].set_index("qp").loc[list(QP_STYLES)]
            lines.append(f"| {label} | " + " | ".join(
                f"{row.oriented_difference:+.3f}{'*' if row.excludes_zero else ''}" for row in rows.itertuples()) + " |")
        lines += ["", f"The simultaneous interval half-width is {selected.critical_value.iloc[0]:.3f}; "
                  "exact intervals are in the comparison CSV.", ""]
    lines += ["The second summary averages correlations/changes across seeds, with the same sampled images for each seed. "
              "It keeps 24 independent images and describes uncertainty conditional on these three realizations. "
              "Neither table establishes that edge fraction, contrast or entropy is stable.", "",
              "**Image-rank diagnostic at QP 32, sigma 30, primary seed**", "",
              "The following correlations compare clean and noisy rankings of the same images by each descriptor. "
              "They are descriptive checks of rank preservation, not correlations with CU count or prediction tests.", "",
              "| Measure | Clean–noisy rank correlation |", "| --- | ---: |"]
    diagnostics = tables["noise_rank_diagnostics"]
    selected = diagnostics[diagnostics.variant.eq("primary") & diagnostics.seed.eq("20260811")
                           & diagnostics.qp.eq(32) & diagnostics.level.eq(30)].set_index("feature").loc[list(LABELS)]
    for feature, row in selected.iterrows():
        lines.append(f"| {LABELS[feature]} | {row.descriptor_rank_rho:.3f} |")
    lines += ["", f"CU-count ranks have a clean–noisy correlation of {selected.cu_count_rank_rho.iloc[0]:.3f}. "
              "Both the descriptor and the CU-count ordering can change. This diagnostic does not establish a causal mechanism. "
              "The full table includes all AWGN strengths, seeds and QPs, descriptor spread and ties, and the two alternative GLCM settings.", ""]
    strong = diagnostics[diagnostics.variant.eq("primary") & diagnostics.qp.eq(32) & diagnostics.level.eq(30)]
    homogeneity = strong[strong.feature.eq("glcm_homogeneity")]
    edge = strong[strong.feature.eq("edge_fraction")]
    edge_iqr_ratio = edge.noisy_iqr / edge.clean_iqr
    lines += [f"Across the three seeds at sigma 30, homogeneity's clean–noisy rank correlation is "
              f"{homogeneity.descriptor_rank_rho.min():.3f}–{homogeneity.descriptor_rank_rho.max():.3f}. "
              f"Edge fraction's between-image interquartile range is {100 * edge_iqr_ratio.min():.1f}–"
              f"{100 * edge_iqr_ratio.max():.1f}% of its clean-image value. "
              f"The minimum number of distinct noisy descriptor values is {int(strong.noisy_unique_values.min())} out of 24; "
              f"{int(edge.noisy_exact_one_count.max())} images reach an edge fraction of exactly one. "
              "The spread narrows without exact ties or complete edge saturation in this sample. "
              "Narrowing alone cannot explain a Spearman-correlation change, because it depends on ordering.", "",
              "The sign near zero also depends on the GLCM setting: horizontal-only homogeneity gives positive "
              "primary-seed point estimates at QP 27 and 32, whereas the eight-level, four-direction descriptor "
              "gives negative estimates. A universal sign reversal is therefore not a supported description.", "",
              "</details>", ""]
    return lines


def image_omission_sensitivity(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Exploratory clean-image check; rerank after omitting the two labelled examples."""
    joined = tables["joined_measurements"]
    clean = tables["correlations"].query("distortion == 'clean'").set_index(["qp", "feature"])
    influence = tables["leave_one_out_contrasts"]
    rows = []
    for qp in QP_STYLES:
        group = joined[joined.distortion.eq("clean") & joined.qp.eq(qp)]
        reduced = group[~group.source.isin(("kodim02.png", "kodim08.png"))]
        if len(group) != 24 or len(reduced) != 22:
            raise ValueError("Image-omission check requires all 24 images and the two labelled examples")
        values = {feature: spearmanr(reduced[feature], reduced.cu_count).statistic for feature in LABELS}
        for feature in LABELS:
            full = clean.loc[(qp, feature), "rho"]
            sign = -1 if feature == "glcm_homogeneity" else 1
            loo = influence[influence.family.eq("RQ1") & influence.qp.eq(qp) & influence.feature.eq(feature)]
            rows.append(dict(feature=feature, qp=qp, omitted_sources="kodim02.png;kodim08.png",
                             n_images_full=24, n_images_reduced=22, rho_full=full, rho_omitted=values[feature],
                             rho_change=values[feature] - full,
                             difference_from_sobel_full=(sign * full - clean.loc[(qp, "sobel_si"), "rho"])
                             if feature != "sobel_si" else np.nan,
                             difference_from_sobel_omitted=(sign * values[feature] - values["sobel_si"])
                             if feature != "sobel_si" else np.nan,
                             leave_one_out_difference_min=loo.oriented_difference.min(),
                             leave_one_out_difference_max=loo.oriented_difference.max()))
    return pd.DataFrame(rows)


def write_report(analysis: Path, output: Path, tables: dict[str, pd.DataFrame], validation: Path | None = None) -> None:
    """Export the CSVs and one research README."""

    table_dir = output / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    for name in tables:
        source, destination = analysis / f"{name}.csv", table_dir / f"{name}.csv"
        if name.startswith("div2k/") and validation is not None:
            source = validation / f"{name.split('/')[1]}.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)

    correlations, contrasts = tables["correlations"], tables["contrasts"]
    clean = correlations[correlations.distortion.eq("clean")]
    joined = tables["joined_measurements"]
    omission = image_omission_sensitivity(tables)
    omission.to_csv(table_dir / "image_omission_sensitivity.csv", index=False)
    qps = disturbance_qps(correlations)
    qp_text = ", ".join(map(str, qps))
    supported = contrasts[(contrasts.simultaneous_low > 0) | (contrasts.simultaneous_high < 0)]
    superiority = supported[supported.family.eq("RQ1") & (supported.simultaneous_low > 0)]
    rq2 = supported[supported.family.eq("RQ2")]
    winners = clean.loc[clean.groupby("qp").rho.idxmax()]
    winner_text = (f"{LABELS[winners.feature.iloc[0]]} has the largest positive point correlation at every clean-image QP."
                   if winners.feature.nunique() == 1 else
                   "The descriptor with the largest positive point correlation varies with QP; the clean-image table gives every value.")
    superiority_text = ("The simultaneous comparisons do not establish that any candidate has a stronger association than Sobel."
                        if superiority.empty else
                        f"The simultaneous comparisons support a stronger association than Sobel in {len(superiority)} candidate/QP comparisons; the table below identifies them.")
    if rq2.empty:
        disturbance_text = "The simultaneous intervals do not resolve any clean-versus-disturbed correlation difference."
    else:
        effects = []
        for (distortion, feature, level), group in rq2.groupby(["distortion", "feature", "level"], sort=False):
            for direction, rows in (("weaker", group[group.simultaneous_high < 0]),
                                    ("stronger", group[group.simultaneous_low > 0])):
                if not rows.empty:
                    name = "AWGN" if distortion == "awgn" else "sinusoidal bands"
                    effects.append(f"{LABELS[feature]} under {name} at level {level:g} has a {direction} direction-adjusted association at QP {', '.join(map(str, sorted(rows.qp)))}")
        disturbance_text = "; ".join(effects) + ". Other disturbance comparisons remain inconclusive."

    lines = [
        "# VTM Image Complexity and Block Partitioning", "",
        "This study extends the [content-partition study](../README.md) by comparing six image-complexity measures with "
        "the final luma coding-unit (CU) count produced by the unmodified VTM 23.0 reference encoder in single-frame intra coding.", "",
        "The focus of this extension is how these associations change after adding Gaussian noise and sinusoidal bands at a fixed QP. "
        "Clean-image correlations provide the reference for evaluating disturbance effects. Paired comparisons quantify the magnitude "
        "and uncertainty of the changes and identify which changes are supported in the studied sample. "
        "Together, these results characterize the sensitivity of descriptor–CU associations to the tested disturbances.", "",
        "## Key Findings", "",
        f"- {winner_text}",
        "- GLCM contrast and entropy have positive clean-image correlations; homogeneity has a negative correlation. "
        "Brightness spread (Luma SD) is less strongly associated with CU count in these images.",
        f"- {superiority_text}",
        f"- {disturbance_text}", "",
        "## Experimental Protocol", "",
        "| Item | Setting |", "| --- | --- |",
        "| Encoder | Unmodified VTM 23.0; trace-enabled build for final CU boundaries |",
        "| Configuration | Single-frame all-intra, [vtm_encoder_intra.cfg](../../../configs/vtm_encoder_intra.cfg) |",
        "| Input | OpenCV planar YUV 4:4:4 conversion; 8-bit input, 10-bit internal processing |",
        "| Images | 24 Kodak images; 393,216 pixels per image |",
        "| Clean-image QPs | 22, 27, 32, 37 |",
        f"| Disturbance QPs | {qp_text} |",
        "| Gaussian noise (AWGN) | Nominal sigma 5, 15, 30; base seeds 20260811, 20260812, 20260813 |",
        "| Sinusoidal bands | Horizontal; amplitude 8, 16, 32; period 16 pixels; phase zero |",
        f"| Measurements | 312 saved stimuli; {len(joined):,} encodings |",
        "| Consistency checks | Decoder output matches encoder reconstruction; CU rectangles cover the coded image |", "",
        "AWGN adds the same random field to each color channel before rounding and clipping. Noise levels for one image "
        "and base seed scale the same field. Nominal sigma and amplitude differ from the actual luma RMS after clipping; "
        "the measured RMS is included in the CSVs.", "",
        "## Complexity Measures", "",
        "[Zhang et al., *An Adaptive Infrared Image Preprocessing Method Based on Background Complexity Descriptors*]"
        "(https://doi.org/10.1109/IMCCC.2018.00079) compares GLCM entropy, edge-pixel ratio, GLCM contrast, GLCM correlation "
        "and GLCM energy for infrared preprocessing. Here, edge fraction, contrast and entropy are compared with Sobel SD, "
        "Luma SD and homogeneity. This examines three of the paper's descriptor types with explicit parameters; "
        "it does not reproduce its full method or combined score.", "",
        "All descriptors are calculated from the actual input PNG, using its OpenCV 8-bit luma plane Y. "
        "SD means population standard deviation. No resizing, denoising or intensity normalization is applied.", "",
        "| Measure | What it describes | Definition |", "| --- | --- | --- |",
        "| Sobel SD | Variation in local gradient strength | SD of the unnormalized 3 × 3 Sobel gradient magnitude; exclude the one-pixel border |",
        "| Luma SD | Spread of pixel brightness, regardless of arrangement | SD of all Y pixels |",
        "| Edge fraction | Fraction of pixels with strong local brightness changes | Fraction of interior pixels with summed absolute response to four directional Sobel masks > 150 |",
        "| GLCM contrast | Differences between neighboring gray levels | Mean over directions of `sum(P(i,j) × (i-j)^2)` |",
        "| GLCM entropy | Diversity of neighboring gray-level pairs | Mean over directions of `-sum(P(i,j) × ln(P(i,j)))`; `0 ln(0) = 0` |",
        "| GLCM homogeneity | Local similarity of gray levels | Mean over directions of `sum(P(i,j) / (1 + (i-j)^2))` |", "",
        "GLCM is the gray-level co-occurrence matrix: how often neighboring gray levels occur together. "
        "Y is quantized to eight levels as `floor(8 × Y / 256)`. Offsets `(row, column)` are `(0,1), (1,1), (1,0), (1,-1)`. "
        "Each matrix uses valid pairs, is symmetrized and normalized separately; the resulting feature values are averaged. "
        "The exact edge masks and formulas are in [spatial_complexity.py](../../../vvenc_csf/spatial_complexity.py). "
        "The edge masks and threshold follow [Zhao et al.](https://doi.org/10.3390/electronics11142147); "
        "the GLCM-setting comparison is motivated by [Bakkouri et al.](https://doi.org/10.3390/app16031368). "
        "The 32-level and horizontal-only GLCMs are sensitivity checks.", "",
        "## Statistical Method", "",
        "For each fixed QP, disturbance level and seed, Spearman rho compares the ordering of the same 24 images by "
        "a descriptor and by CU count. Near +1 means larger descriptor values tend to accompany more CUs; "
        "near −1 means fewer CUs; near zero means little consistent increasing or decreasing ordering. "
        "A coefficient describes the group of images, not one image. CU density is `1,000,000 × CU count / coded area`; "
        "equal image areas make its ranks identical to CU-count ranks.", "",
        "The primary AWGN realization uses base seed 20260811. Seeds 20260812 and 20260813 are analyzed separately. "
        "QP, noise levels and seeds do not increase the number of independent images beyond 24.", "",
        "Pointwise 95% correlation intervals use 99,999 paired image-bootstrap samples (seed 20260905), "
        "with average ranks for ties and reranking within each sample. The same sampled images are used across conditions. "
        f"Simultaneous comparisons cover 20 candidate-versus-Sobel contrasts and {int(contrasts.family.eq('RQ2').sum())} "
        "disturbed-versus-clean contrasts. Basic maximum-error intervals use alpha 0.025 per family, for a combined nominal "
        "error rate of 0.05. Finite-sample coverage is approximate. Direction is positive for five descriptors and negative "
        "for homogeneity; raw signed correlations are shown throughout. An interval containing zero is inconclusive.", "",
        "Sobel SD is the reference descriptor inherited from the original study, not an established best descriptor. "
        "For descriptor k, let `s[k] = +1` for Sobel SD, Luma SD, edge fraction, contrast and entropy, and `s[k] = −1` "
        "for homogeneity. These directions were fixed before the descriptor comparison; they are not estimated from the clean correlations. "
        "Clean-image comparisons with Sobel use `A = s[k] × rho[k, clean, QP] − rho[Sobel, clean, QP]`. "
        "Disturbance comparisons use `B = s[k] × (rho[k, disturbed, QP] − rho[k, clean, QP])`. "
        "Negative B means weakening in the expected direction, not necessarily a smaller absolute correlation.", "",
        f"Auxiliary tests of independence use 99,999 permutations (seed 20260906) with Holm correction over {int(correlations.primary.sum())} "
        "primary correlations. They do not test differences between correlations. "
        "[study_statistics.py](../../../vvenc_csf/study_statistics.py) implements these calculations.", "",
        "## Clean Images", "",
        "<details>", "<summary>Image examples and all-image scatter plots at QP 32</summary>", "",
        "The two examples retain the low- and high-Sobel images used in the original study. Both maps show final CU "
        "boundaries at QP 32. More CUs mean smaller blocks on average.", "",
        "![Kodak images 02 and 08 with final CU boundaries at QP 32](figures/Kodak_partition_examples_QP32.png)", "",
        "[PDF](figures/Kodak_partition_examples_QP32.pdf) · [SVG](figures/Kodak_partition_examples_QP32.svg). "
        "Generate from the repository root with `python -m tools.visualization.plot_vtm_partition_examples`.", "",
        "| | kodim02.png | kodim08.png |", "| --- | :---: | :---: |",
    ]
    examples = joined[joined.distortion.eq("clean") & joined.qp.eq(32)].set_index("source")
    a, b = examples.loc["kodim02.png"], examples.loc["kodim08.png"]
    lines.append(f"| CU count | {a.cu_count:,.0f} | {b.cu_count:,.0f} |")
    for feature, label in LABELS.items():
        lines.append(f"| {label} | {a[feature]:.3f} | {b[feature]:.3f} |")
    lines += ["",
              "The scatter plots show all 24 clean images at QP 32. Each point is one image; labels 02 and 08 "
              "appear above the orange and purple circles, respectively. All panels use the same CU-count scale.", "",
              "![All 24 images: complexity versus CU count at QP 32](figures/Fig5_all_images_QP32_manuscript.png)", "",
              "[PDF](figures/Fig5_all_images_QP32_manuscript.pdf).", "",
              "These scatter plots expose the observations behind the correlations. Their appearance alone is not an influence test; "
              "the omission analysis below checks the two labelled images explicitly.", "", "</details>", "",
              "### Correlation at Each QP", "",
              "| Measure | QP 22 | QP 27 | QP 32 | QP 37 |", "| --- | ---: | ---: | ---: | ---: |"]
    for feature, label in LABELS.items():
        values = clean[clean.feature.eq(feature)].set_index("qp").loc[list(QP_STYLES), "rho"]
        lines.append(f"| {label} | " + " | ".join(f"{value:.3f}" for value in values) + " |")
    lines += ["", "![Clean correlations with pointwise 95% intervals](figures/Fig1_clean_correlations.png)", "",
              "Dots are estimated correlations; horizontal lines are pointwise 95% bootstrap confidence intervals. "
              "They show uncertainty in each correlation, without adjustment for inspecting multiple intervals. "
              "The Luma SD intervals include zero at all four QPs, which leaves substantial uncertainty about its association; "
              "this does not establish absence of an association. The Holm-adjusted independence tests are reported separately in the CSV.", "",
              "A larger point estimate alone does not establish a better descriptor. "
              "The paired candidate-versus-Sobel comparisons answer a different question from individual correlation intervals; "
              "overlap of those individual intervals is not the comparison test.", "",
              "<details>", "<summary>Paired comparisons with Sobel SD</summary>", "",
              "![Clean candidate-versus-Sobel comparisons](figures/Fig3_dependent_clean_comparisons.png)", "",
              "These are simultaneous intervals for A. Luma SD has a weaker association than Sobel at QP 32 and 37. "
              "The remaining candidate comparisons are inconclusive; that does not establish equivalence to Sobel.", "", "</details>", "",
              "## Disturbance Effects", "",
              "The first map shows signed correlations for every primary condition, with a shared −1 to +1 color scale. "
              "Each cell compares the same 24 images at one QP. The clean column is the reference for the change map.", "",
              "![All primary correlation cells](figures/Fig2_disturbance_correlations.png)", "",
              "The second map shows B, the direction-adjusted difference from clean images. "
              "Its values are correlation differences, whose possible range is −2 to +2. "
              "The shared color scale runs from −2 to +2; use the cell values to compare their magnitude.", "",
              "![Direction-adjusted changes from clean correlations](figures/Fig4_disturbance_changes.png)", "",
              "**An asterisk (*) means that the simultaneous confidence interval for B excludes zero**, "
              "using all 144 disturbed-versus-clean comparisons as one family. It does not mark a sign change in rho, "
              "nor whether an individual correlation interval contains zero. No asterisk means the comparison is inconclusive, "
              "not that the descriptor is proven stable.", "",
              "<details>", "<summary>Disturbance trends on a common correlation scale</summary>", "",
              "Each line keeps QP fixed, zero disturbance is the clean reference, and each point uses 24 images. "
              "All panels in both figures use the same −1 to +1 vertical range. Lines connect tested levels without fitting a model. "
              "These plots repeat the raw correlations in the first map; the second map additionally shows paired differences and inference. "
              "Slope magnitudes across AWGN sigma and sinusoidal amplitude are not interchangeable because the horizontal quantities differ.", "",
              "### Gaussian Noise", "",
              "These curves show the primary AWGN realization, base seed 20260811. The other two realizations are "
              "reported separately in the sensitivity table below and the complete correlation CSV. We do not pool seeds as independent images.", "",
              "![Correlation versus AWGN strength at each QP](figures/awgn_correlation_trends.png)", "",
              "### Sinusoidal Bands", "",
              "![Correlation versus sinusoidal amplitude at each QP](figures/sine_correlation_trends.png)", "",
              "</details>", "", "<details>", "<summary>Magnified trends for reading close QP curves</summary>", "",
              "These supplementary views use a separate vertical range for each descriptor. Compare QPs within a panel; "
              "equal visual slopes across panels can represent different numerical changes. The common-scale figures above support cross-panel comparison.", "",
              "![AWGN trends with individual panel ranges](figures/awgn_correlation_trends_zoomed.png)", "",
              "![Sinusoidal trends with individual panel ranges](figures/sine_correlation_trends_zoomed.png)", "", "</details>", "",
              "### Comparisons Supported by the Simultaneous Intervals", "",
              "Positive differences mean a stronger association in the expected direction; negative differences mean a weaker one. "
              "For homogeneity, weakening means a shift away from its expected negative association. "
              "All remaining comparisons are retained in the complete CSV.", "",
              "| Measure | Condition | QP | Direction-adjusted difference | Simultaneous interval |",
              "| --- | --- | ---: | ---: | --- |"]
    for row in supported.itertuples():
        condition = "Clean versus Sobel" if row.family == "RQ1" else f"{'AWGN' if row.distortion == 'awgn' else 'Sine'}, level {row.level:g} versus clean"
        lines.append(f"| {LABELS[row.feature]} | {condition} | {row.qp} | {row.oriented_difference:+.3f} | "
                     f"[{row.simultaneous_low:+.3f}, {row.simultaneous_high:+.3f}] |")
    lines += ["", "For example, homogeneity under AWGN sigma 30 illustrates the asterisk rule at all four QPs. "
              "Here B is the negative of disturbed-minus-clean rho because the fixed direction is −1.", "",
              "| QP | Clean rho | AWGN rho | B | Simultaneous interval for B | Asterisk |",
              "| ---: | ---: | ---: | ---: | --- | :---: |"]
    for qp in qps:
        row = contrasts[contrasts.family.eq("RQ2") & contrasts.feature.eq("glcm_homogeneity") &
                        contrasts.distortion.eq("awgn") & contrasts.level.eq(30) & contrasts.qp.eq(qp)].iloc[0]
        clean_rho = clean[clean.feature.eq("glcm_homogeneity") & clean.qp.eq(qp)].rho.iloc[0]
        disturbed_rho = correlations[correlations.primary & correlations.feature.eq("glcm_homogeneity") &
                                    correlations.distortion.eq("awgn") & correlations.level.eq(30) & correlations.qp.eq(qp)].rho.iloc[0]
        star = "*" if row.simultaneous_low > 0 or row.simultaneous_high < 0 else "—"
        lines.append(f"| {qp} | {clean_rho:+.3f} | {disturbed_rho:+.3f} | {row.oriented_difference:+.3f} | "
                     f"[{row.simultaneous_low:+.3f}, {row.simultaneous_high:+.3f}] | {star} |")
    lines += ["", "The decision depends on the interval for the change, not on how close the disturbed rho is to zero. "
              "At QP 32 the raw correlation remains negative, yet the change interval excludes zero. "
              "At QP 27 it includes zero. Rounded cell values alone do not determine statistical support.", ""]
    lines += ["", "<details>", "<summary>AWGN realization sensitivity: all descriptors, strengths and QPs</summary>", "",
              "Each value below uses 24 images for one seed. The primary seed remains 20260811; additional seeds are "
              "sensitivity checks on these same images.", "",
              "| Measure | Sigma | QP | Seed 20260811 | Seed 20260812 | Seed 20260813 |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    awgn = correlations[correlations.distortion.eq("awgn")]
    for feature, label in LABELS.items():
        for level in (5, 15, 30):
            for qp in qps:
                values = awgn[awgn.feature.eq(feature) & awgn.level.eq(level) & awgn.qp.eq(qp)].set_index("seed").rho
                lines.append(f"| {label} | {level} | {qp} | " + " | ".join(
                    f"{values[seed]:+.3f}" if seed in values else "—" for seed in ("20260811", "20260812", "20260813")) + " |")
    lines += ["", "</details>", "", "<details>", "<summary>Influence of images 02 and 08 on clean-image correlations</summary>", "",
              "This exploratory check removes both labelled images together and recalculates ranks for the remaining 22 images. "
              "The pair was chosen after inspecting the examples, so this is an additional sensitivity check rather than a "
              "prespecified confirmation. The main results continue to use all 24 images. "
              "No new confidence intervals or significance tests are inferred for the reduced sample.", "",
              "Each entry is full-sample rho → rho without images 02 and 08.", "",
              "| Measure | QP 22 | QP 27 | QP 32 | QP 37 |", "| --- | ---: | ---: | ---: | ---: |"]
    for feature, label in LABELS.items():
        rows = omission[omission.feature.eq(feature)].set_index("qp").loc[list(QP_STYLES)]
        lines.append(f"| {label} | " + " | ".join(f"{row.rho_full:+.3f} → {row.rho_omitted:+.3f}" for row in rows.itertuples()) + " |")
    maximum = omission.loc[omission.rho_change.abs().idxmax()]
    preserved = int((np.sign(omission.rho_full) == np.sign(omission.rho_omitted)).sum())
    comparisons = omission[omission.feature.ne("sobel_si")]
    sign_count = int((np.sign(comparisons.difference_from_sobel_full) == np.sign(comparisons.difference_from_sobel_omitted)).sum())
    lines += ["", f"The raw correlation sign is retained in {preserved}/{len(omission)} cells. "
              f"The largest absolute rho change is {abs(maximum.rho_change):.3f} for {LABELS[maximum.feature]} at QP {maximum.qp}. "
              f"The candidate-versus-Sobel point difference keeps its sign in {sign_count}/{len(comparisons)} comparisons. "
              "These point-estimate checks do not establish unchanged statistical support or eliminate influence from other images.", "",
              "The existing leave-one-image-out analysis reranks 23 images after each individual omission. "
              "Its clean candidate-versus-Sobel point differences span zero for GLCM entropy at QP 32 and 37; "
              "the other clean comparisons retain their point-difference signs. This further limits any claim of a universal descriptor ranking. "
              "The [omission table](tables/image_omission_sensitivity.csv) includes those ranges and the two-image omission results.", "",
              "</details>", ""]
    lines += noise_sensitivity_section(tables)
    lines += validation_section(tables, LABELS)
    lines += ["## Data", "",
              "Leave-one-image-out comparisons, GLCM parameter changes and within-image descriptor/CU changes are supplementary checks. "
              "All measurements and comparisons are retained in these tables.", "",
              "| What can be checked | CSV |", "| --- | --- |"]
    for name, description in TABLE_DESCRIPTIONS.items():
        lines.append(f"| {description} | [{name}](tables/{name}.csv) |")
    lines.append("| Exploratory removal of images 02/08 and single-image omission ranges | [image_omission_sensitivity](tables/image_omission_sensitivity.csv) |")
    for name, description in NOISE_TABLES.items():
        if name in tables:
            lines.append(f"| {description} | [{name}](tables/{name}.csv) |")
    if "div2k/effects" in tables:
        for name, description in VALIDATION_TABLES.items():
            lines.append(f"| {description} | [div2k/{name}](tables/div2k/{name}.csv) |")
    lines += ["", "## Reproduction", "",
              "From the repository root, regenerate the README and figures from the saved CSVs:", "",
              "```powershell", "python tools/reporting/report_vtm_spatial_complexity.py", "```", "",
              "Use `--analysis-dir <directory>` to select another completed analysis and `--output <directory>` to write elsewhere. "
              "This command also recalculates the descriptive image-omission check; it performs no encoding or statistical resampling.", ""]
    if "exploratory_noise_comparisons" in tables:
        lines += ["To reproduce the exploratory noise comparisons and rank diagnostics using the saved paired-bootstrap cache:", "",
                  "```powershell",
                  "python tools/research/analyze_vtm_noise_sensitivity.py --output docs/vtm_content_partition_study/spatial_complexity/tables",
                  "python tools/reporting/report_vtm_spatial_complexity.py",
                  "```", "",
                  "The noise-analysis command checks the cached correlation order and values, and replays the first two paired bootstrap draws before export. "
                  "It requires the completed analysis and its local bootstrap cache; it does not generate new resamples or encodings.", ""]
    if "div2k/effects" in tables:
        lines += ["To reproduce the independent DIV2K analysis from the completed encodings:", "",
                  "```powershell", "python tools/research/analyze_vtm_noise_validation.py all",
                  "python tools/reporting/report_vtm_spatial_complexity.py --validation-dir results/vtm_noise_validation/analysis",
                  "```", "", "The analysis verifies the completed experiment, computes the descriptors and reuses matching completed "
                  "bootstrap caches. Its first statistical run generates the two sets of 99,999 paired samples. "
                  "The [DIV2K encoding runner](../../../tools/research/complete_vtm_noise_validation.py) retains the pilot and full-run provenance.", ""]
    lines += ["To recompute the Kodak descriptors and statistical analysis from the saved input images and measurements, then verify the result:", "",
              "```powershell",
              "python tools/research/analyze_vtm_spatial_complexity.py all",
              "python tools/research/verify_vtm_spatial_complexity_analysis.py --analysis-dir results/vtm_content_partition_four_qp/analysis_workspace/analysis",
              "python tools/reporting/report_vtm_spatial_complexity.py --analysis-dir results/vtm_content_partition_four_qp/analysis_workspace/analysis",
              "```", "",
              "The analysis writes CSV tables and bootstrap caches to the results directory shown above; resampling can take time. "
              "Use the analysis command's `--output <directory>` to select another directory and pass it to the verifier. "
              "The [encoding runner](../../../tools/research/complete_vtm_four_qp_study.py) provides the VTM measurements.", "",
              "## Limitations", "",
              "The results describe 24 Kodak images in single-frame intra coding, one VTM configuration and the tested disturbances. "
              "Additional seeds reuse the same images; sinusoidal bands have one orientation and period. "
              "No temporal prediction, motion or video-sequence behavior is evaluated. The tested synthetic disturbances do not represent every acquisition artifact. "
              "The measured endpoint is final image-level CU count, not local split prediction or the encoder's search cost. "
              "A high correlation does not by itself make a descriptor a validated predictor or a fast partitioning algorithm. "
              "These associations do not establish causation, predictive accuracy, encoding speedup or improved visual quality. "
              "Validation on new images is needed before generalizing the findings.", ""]
    if "div2k/effects" in tables:
        lines = [line.replace("## Key Findings", "## Key Findings on Kodak")
                 .replace("## Experimental Protocol", "## Kodak Protocol")
                 .replace("The results describe 24 Kodak images in single-frame intra coding, one VTM configuration and the tested disturbances.",
                          "The results describe 24 Kodak images and 48 central DIV2K crops in single-frame intra coding, one VTM configuration and the tested disturbances.")
                 .replace("Validation on new images is needed before generalizing the findings.",
                          "Broader generalization requires other acquisition conditions, image domains and encoder configurations.")
                 for line in lines]
        plot_validation(tables, output / "figures", LABELS, QP_STYLES)
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")


def save(figure: plt.Figure, output: Path, name: str) -> None:
    for extension in ("pdf", "png"):
        figure.savefig(output / f"{name}.{extension}", dpi=350, bbox_inches="tight")
    plt.close(figure)


def plot_disturbance_trends(correlations: pd.DataFrame, output: Path) -> None:
    """Show signed rho on a common scale, with separate zoomed views for detail."""

    qps = disturbance_qps(correlations)
    for distortion, levels, xlabel, name in (
        ("awgn", (0, 5, 15, 30), "AWGN strength, sigma (8-bit values)", "awgn_correlation_trends"),
        ("stripes", (0, 8, 16, 32), "Sinusoidal amplitude, A (8-bit values)", "sine_correlation_trends"),
    ):
        for zoomed in (False, True):
            figure, axes = plt.subplots(2, 3, figsize=(11, 6.6), sharex=True)
            figure.subplots_adjust(left=0.08, right=0.98, bottom=0.14, top=0.85, hspace=0.35, wspace=0.28)
            for axis, (feature, label) in zip(axes.flat, LABELS.items(), strict=True):
                panel_values = []
                for qp in qps:
                    color, marker = QP_STYLES[qp]
                    selected = correlations[(correlations.qp == qp) & correlations.primary & (correlations.feature == feature)]
                    values = [selected[selected.distortion == "clean"].rho.iloc[0]]
                    values += [selected[(selected.distortion == distortion) & (selected.level == level)].rho.iloc[0] for level in levels[1:]]
                    panel_values.extend(values)
                    axis.plot(levels, values, marker=marker, color=color, linewidth=1.7, markersize=5, label=f"QP {qp}")
                lower, upper = -1, 1
                if zoomed:
                    minimum, maximum = min(panel_values), max(panel_values)
                    padding = max(0.02, 0.12 * (maximum - minimum))
                    lower = max(-1, np.floor((minimum - padding) * 20) / 20)
                    upper = min(1, np.ceil((maximum + padding) * 20) / 20)
                    if minimum >= 0:
                        lower = max(0, lower)
                    axis.yaxis.set_major_locator(MaxNLocator(nbins=5))
                else:
                    axis.set_yticks((-1, -0.5, 0, 0.5, 1))
                axis.set(title=label, ylim=(lower, upper), xticks=levels)
                if lower <= 0 <= upper:
                    axis.axhline(0, color="0.5", linewidth=0.7)
                axis.grid(alpha=0.18)
                axis.tick_params(labelsize=9)
            handles, labels = axes.flat[0].get_legend_handles_labels()
            figure.legend(handles, labels, loc="upper center", ncol=len(qps), frameon=False, fontsize=11)
            title = "Zoomed Y scales: each panel has its own range" if zoomed else "Common Y scale: Spearman correlation from -1 to 1"
            figure.suptitle(title, y=0.93, fontsize=10)
            figure.supylabel("Spearman correlation with CU count", fontsize=11, x=0.01)
            figure.supxlabel(xlabel + "  |  0 = clean image", fontsize=11, y=0.03)
            save(figure, output, name + ("_zoomed" if zoomed else ""))


def plot_disturbance_correlations(correlations: pd.DataFrame, output: Path) -> None:
    """Show all primary correlation cells in compact QP panels."""
    qps = disturbance_qps(correlations)
    conditions = (("clean", 0), ("awgn", 5), ("awgn", 15), ("awgn", 30),
                  ("stripes", 8), ("stripes", 16), ("stripes", 32))
    condition_labels = ("Clean", "AWGN\n5", "AWGN\n15", "AWGN\n30", "Sine\n8", "Sine\n16", "Sine\n32")
    rows = (len(qps) + 1) // 2
    figure, axes = plt.subplots(rows, 2, figsize=(9.5, 3.0 * rows), squeeze=False, layout="constrained")
    for panel, qp in enumerate(qps):
        axis = axes.flat[panel]
        selected = correlations[(correlations.qp == qp) & correlations.primary]
        matrix = np.array([[float(selected[(selected.feature == feature) & (selected.distortion == distortion)
                                           & (selected.level == level)].rho.iloc[0])
                            for distortion, level in conditions] for feature in LABELS])
        visual = axis.imshow(matrix, vmin=-1, vmax=1, cmap="RdBu_r", aspect="auto")
        for i in range(6):
            for j in range(7):
                axis.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center",
                          color="white" if abs(matrix[i, j]) > 0.65 else "black", fontsize=8)
        axis.set(title=f"QP {qp}", xticks=range(7), xticklabels=condition_labels,
                 yticks=range(6), yticklabels=list(LABELS.values()) if panel % 2 == 0 else [])
        axis.tick_params(length=0)
        axis.tick_params(axis="x", labelsize=7, labelrotation=0)
        for tick in axis.get_xticklabels():
            tick.set_ha("center")
            tick.set_multialignment("center")
        axis.axvline(0.5, color="white", linewidth=1.4)
        axis.axvline(3.5, color="white", linewidth=1.4)
    for axis in list(axes.flat)[len(qps):]:
        axis.set_visible(False)
    figure.colorbar(visual, ax=list(axes.flat), location="right", orientation="vertical",
                    fraction=0.025, pad=0.025, label="Signed Spearman correlation")
    save(figure, output, "Fig2_disturbance_correlations")


def plot_all_images(joined: pd.DataFrame, output: Path) -> None:
    """Show all clean observations, with the two illustrated images identified."""
    selected = joined[(joined.distortion == "clean") & (joined.qp == 32)].sort_values("source")
    highlights = {"kodim02.png": "#D55E00", "kodim08.png": "#6A51A3"}
    other = selected[~selected.source.isin(highlights)]
    figure, axes = plt.subplots(3, 2, figsize=(7.16, 7.8), sharey=True, layout="constrained")
    for axis, (feature, label) in zip(axes.flat, LABELS.items(), strict=True):
        axis.scatter(other[feature], other.cu_count, s=32, c="#0072B2", alpha=0.75,
                     label="Other 22 images")
        axis.set_title(label, fontsize=11)
        axis.set_ylim(0, 9500)
        axis.set_yticks((0, 3000, 6000, 9000))
        axis.tick_params(labelsize=9)
        for source, color in highlights.items():
            row = selected[selected.source == source].iloc[0]
            axis.scatter(row[feature], row.cu_count, s=32, c=color, marker="o",
                         edgecolors="white", linewidths=0.6, zorder=3, label=f"Image {source[5:7]}")
            axis.annotate(source[5:7], (row[feature], row.cu_count),
                          xytext=(0, 7), ha="center", va="bottom", textcoords="offset points",
                          fontsize=9, fontweight="bold", color=color,
                          bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.2))
        axis.grid(alpha=0.16)
    for axis in axes[:, 0]:
        axis.set_ylabel("Final CU count at QP 32", fontsize=10)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.04),
                  ncol=3, frameon=False, fontsize=10)
    save(figure, output, "Fig5_all_images_QP32_manuscript")


def build(analysis: Path, report: Path, validation: Path | None = None) -> None:
    tables = load_tables(analysis, validation)
    output = report / "figures"
    output.mkdir(parents=True, exist_ok=True)
    correlations = tables["correlations"]
    contrasts = tables["contrasts"]
    qps = disturbance_qps(correlations)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.labelsize": 8,
                         "axes.titlesize": 9, "pdf.fonttype": 42, "ps.fonttype": 42})
    clean = correlations[correlations.distortion == "clean"]
    figure, axes = plt.subplots(2, 2, figsize=(7.16, 4.9), sharex=True, sharey=True, layout="constrained")
    for axis, qp in zip(axes.flat, (22, 27, 32, 37), strict=True):
        selected = clean[clean.qp == qp].set_index("feature").loc[list(LABELS)]
        for i, (_, row) in enumerate(selected.iterrows()):
            axis.plot([row.ci_low, row.ci_high], [i, i], color=COLORS[i], linewidth=1.4)
            axis.plot(row.rho, i, "o", color=COLORS[i], markersize=4)
        axis.axvline(0, color="0.65", linewidth=0.6)
        axis.set(title=f"QP {qp}", xlim=(-1, 1), xticks=(-1, -0.5, 0, 0.5, 1), yticks=range(6), yticklabels=list(LABELS.values()),
                 xlabel="Spearman correlation")
        axis.invert_yaxis() if not axis.yaxis_inverted() else None
        axis.grid(axis="x", alpha=0.18)
    figure.suptitle("Clean-image correlations: pointwise 95% bootstrap intervals", fontsize=10)
    save(figure, output, "Fig1_clean_correlations")

    conditions = (("clean", 0), ("awgn", 5), ("awgn", 15), ("awgn", 30),
                  ("stripes", 8), ("stripes", 16), ("stripes", 32))
    condition_labels = ("Clean", "AWGN\n5", "AWGN\n15", "AWGN\n30", "Sine\n8", "Sine\n16", "Sine\n32")
    plot_disturbance_correlations(correlations, output)

    first = contrasts[contrasts.family == "RQ1"]
    figure, axis = plt.subplots(figsize=(7.16, 4.8), layout="constrained")
    positions, labels = [], []
    for i, feature in enumerate(list(LABELS)[1:]):
        for j, qp in enumerate((22, 27, 32, 37)):
            row = first[(first.feature == feature) & (first.qp == qp)].iloc[0]
            position = i * 5 + j
            axis.plot([row.simultaneous_low, row.simultaneous_high], [position, position],
                      color=COLORS[i + 1], linewidth=1.1)
            axis.plot(row.oriented_difference, position, ("o", "s", "^", "D")[j],
                      color=COLORS[i + 1], markersize=3.3)
            positions.append(position)
            labels.append(f"{LABELS[feature]}, QP {qp}")
    axis.set(yticks=positions, yticklabels=labels, xlabel="Oriented correlation difference from Sobel SD")
    axis.invert_yaxis()
    axis.axvline(0, color="0.3", linestyle="--", linewidth=0.8)
    axis.grid(axis="x", alpha=0.18)
    figure.suptitle("Paired comparisons with the Sobel SD reference\nSimultaneous intervals for direction-adjusted differences", fontsize=10)
    save(figure, output, "Fig3_dependent_clean_comparisons")

    second = contrasts[contrasts.family == "RQ2"]
    figure, axes = plt.subplots(len(qps), 1, figsize=(7.16, 2.17 * len(qps)), layout="constrained")
    for axis, qp in zip(axes, qps, strict=True):
        matrix = np.empty((6, 6))
        supported = np.zeros((6, 6), dtype=bool)
        for i, feature in enumerate(LABELS):
            for j, (distortion, level) in enumerate(conditions[1:]):
                row = second[(second.qp == qp) & (second.feature == feature)
                             & (second.distortion == distortion) & (second.level == level)].iloc[0]
                matrix[i, j] = row.oriented_difference
                supported[i, j] = row.simultaneous_low > 0 or row.simultaneous_high < 0
        visual = axis.imshow(matrix, vmin=-2, vmax=2, cmap="RdBu_r", aspect="auto")
        for i in range(6):
            for j in range(6):
                axis.text(j, i, f"{matrix[i, j]:+.2f}" + ("*" if supported[i, j] else ""),
                          ha="center", va="center", color="white" if abs(matrix[i, j]) > 1.3 else "black", fontsize=8)
        axis.set(title=f"QP {qp}", xticks=range(6), xticklabels=condition_labels[1:],
                 yticks=range(6), yticklabels=list(LABELS.values()))
        axis.tick_params(length=0)
        axis.axvline(2.5, color="white", linewidth=1.4)
    figure.colorbar(visual, ax=axes, fraction=0.018, pad=0.02, label="Oriented difference from clean")
    figure.suptitle("Change from clean images: B = s × (rho disturbed − rho clean)\ns = −1 for homogeneity; +1 otherwise\n* Simultaneous interval for B excludes zero (family alpha = 0.025)", fontsize=9)
    save(figure, output, "Fig4_disturbance_changes")

    plot_all_images(tables["joined_measurements"], output)
    plot_disturbance_trends(correlations, output)
    write_report(analysis, report, tables, validation)
    print(f"Saved research README, CSV tables and PDF/PNG figures in {report}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, default=ROOT / "docs/vtm_content_partition_study/spatial_complexity/tables",
                        help="Directory containing the completed CSV tables")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/vtm_content_partition_study/spatial_complexity")
    parser.add_argument("--validation-dir", type=Path, help="Completed independent DIV2K analysis; otherwise read tables/div2k when present")
    args = parser.parse_args()
    build(args.analysis_dir, args.output, args.validation_dir)
