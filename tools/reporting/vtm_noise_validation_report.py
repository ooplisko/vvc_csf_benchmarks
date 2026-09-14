"""DIV2K tables and figures for the existing spatial-complexity README."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vvenc_csf.spatial_complexity import FEATURES


TABLES = {
    "stimulus_features": "DIV2K descriptors for each input stimulus",
    "joined_measurements": "DIV2K descriptors and final CU counts",
    "selected_sources": "DIV2K source selection and crop coordinates",
    "correlations": "DIV2K correlations for clean images and each AWGN realization",
    "effects": "DIV2K changes and direct comparisons with simultaneous intervals",
}
QPS = (22, 27, 32, 37)
SEEDS = ("20260811", "20260812", "20260813")


def point_effects(correlations):
    changes = {}
    for feature in FEATURES:
        for qp in QPS:
            rows = correlations[correlations.feature.eq(feature) & correlations.qp.eq(qp)]
            clean = rows[rows.distortion.eq("clean")].rho.iloc[0]
            noisy = rows[rows.distortion.eq("awgn") & rows.level.eq(30)].rho.mean()
            changes[feature, qp] = (-1 if feature == "glcm_homogeneity" else 1) * (noisy - clean)
    return {**{("B", feature, qp): value for (feature, qp), value in changes.items()},
            **{("C", feature, qp): changes["glcm_homogeneity", qp] - changes[feature, qp]
               for feature in FEATURES[:-1] for qp in QPS}}


def load_validation_tables(directory: Path):
    if not directory.exists():
        return {}
    tables = {}
    for name in TABLES:
        path = directory / f"{name}.csv"
        if not path.is_file():
            raise ValueError(f"Incomplete DIV2K report tables: {name}")
        tables[f"div2k/{name}"] = pd.read_csv(path, dtype={"seed": str}, float_precision="round_trip").fillna({"seed": ""})
    joined, sources, features, rho, effects = (tables[f"div2k/{name}"] for name in (
        "joined_measurements", "selected_sources", "stimulus_features", "correlations", "effects"))
    if (len(sources) != 48 or sources.source.nunique() != 48 or len(features) != 192
            or features.stimulus.nunique() != 192 or len(joined) != 768
            or joined.duplicated(["stimulus", "qp"]).any()
            or set(joined.source) != set(sources.source)
            or set(joined.stimulus) != set(features.stimulus)
            or not joined.groupby("stimulus").qp.apply(lambda values: set(values) == set(QPS)).all()):
        raise ValueError("DIV2K report requires 48 sources, 192 stimuli and 768 unique measurements")
    cells = {(feature, qp, distortion, level, seed) for feature in FEATURES for qp in QPS
             for distortion, level, seed in (("clean", 0, ""), *(("awgn", 30, seed) for seed in SEEDS))}
    if (len(rho) != 96 or not rho.n_images.eq(48).all()
            or set(rho[["feature", "qp", "distortion", "level", "seed"]].itertuples(index=False, name=None)) != cells
            or not np.isfinite(rho.rho).all() or not rho.rho.between(-1, 1).all()):
        raise ValueError("DIV2K report requires the 96 fixed correlation cells")
    expected = point_effects(rho)
    keys = {(method, *key) for method in ("image", "scene_cluster") for key in expected}
    if (len(effects) != 88 or set(effects[["resampling", "effect_type", "feature", "qp"]].itertuples(index=False, name=None)) != keys
            or not effects.n_images.eq(48).all() or not effects.family_size.eq(44).all()
            or not effects.alpha.eq(0.05).all()):
        raise ValueError("DIV2K report requires two separate 44-effect analyses")
    for row in effects.itertuples():
        if not np.isclose(row.estimate, expected[row.effect_type, row.feature, row.qp], atol=1e-12, rtol=0):
            raise ValueError("DIV2K effect does not match its mean-of-three correlations")
        supported = row.evaluable and (row.simultaneous_low > 0 or row.simultaneous_high < 0)
        if row.excludes_zero != supported:
            raise ValueError("DIV2K significance flag does not match its interval")
        if row.evaluable:
            bound = 2 if row.effect_type == "B" else 4
            interval = (max(-bound, row.estimate - row.critical_value), min(bound, row.estimate + row.critical_value))
            if not np.allclose(interval, (row.simultaneous_low, row.simultaneous_high), atol=1e-12, rtol=0):
                raise ValueError("DIV2K interval does not match its family critical value and bounds")
    if not effects.groupby("resampling").critical_value.nunique().eq(1).all():
        raise ValueError("Each DIV2K family must use one shared critical value")
    return tables


def supported_text(rows, labels, negative=True):
    selected = rows[rows.evaluable & ((rows.simultaneous_high < 0) if negative else (rows.simultaneous_low > 0))]
    return "; ".join(f"{labels[feature]} at QP {', '.join(map(str, sorted(group.qp)))}"
                     for feature, group in selected.groupby("feature", sort=False)) or "none"


def validation_section(tables, labels):
    if "div2k/effects" not in tables:
        return []
    effects = tables["div2k/effects"]
    primary = effects[effects.resampling.eq("image")]
    b = primary[primary.effect_type.eq("B")]
    c = primary[primary.effect_type.eq("C")]
    cluster = effects[effects.resampling.eq("scene_cluster")]
    keys = ["effect_type", "feature", "qp"]
    disagreements = primary.merge(cluster, on=keys, suffixes=("_primary", "_cluster"))
    disagreements = disagreements[disagreements.excludes_zero_primary.ne(disagreements.excludes_zero_cluster)]
    negative = supported_text(c, labels)
    direct_text = (f"Direct comparisons support a more negative homogeneity change than {negative}."
                   if negative != "none" else "No direct comparison supports a more negative homogeneity change.")
    positive = supported_text(c, labels, False)
    if positive != "none":
        direct_text += f" A more positive homogeneity change is supported relative to {positive}."
    lines = ["## Independent Check on DIV2K", "",
             "The follow-up uses 48 DIV2K validation photographs, selected before examining their encoding results. "
             "Each contributes one central 768 × 512 crop without resizing. Clean inputs and AWGN sigma 30 with the same "
             "three base seeds are encoded at QP 22, 27, 32 and 37: 192 stimuli and 768 encodings. "
             "The VTM build, conversion and six descriptor definitions are the same as in the Kodak study. "
             "The official images are available from [DIV2K](https://data.vision.ee.ethz.ch/cvl/DIV2K/).", "",
             "Selection uses PCG64 seed 20260910 to permute the sorted 100 validation IDs and take the first 48. "
             "The full selection determines image-specific noise seeds; the two timing-pilot sources remain in the analysis. "
             "The source CSV records the selected IDs, original hashes and crop coordinates.", "",
             "**Prespecified comparison.** At each QP, average the three realization-specific Spearman correlations, "
             "then compute `B = s × (mean(rho noisy) − rho clean)` and `C = B[homogeneity] − B[other]`. "
             "The primary family contains all 24 B and 20 C intervals together, at alpha 0.05. "
             "It uses 99,999 paired image-bootstrap samples (seed 20260905), reranking within each sample. "
             "The same sampled images are used for every QP, descriptor and seed. "
             "There are 48 source images, not 144 independent noise realizations; uncertainty is conditional on the three fixed realizations. "
             "The interval method and its approximate finite-sample coverage are the same as above, with bounds B [−2,2] and C [−4,4].", "",
             "![Noise-related changes on Kodak and DIV2K](figures/Fig6_dataset_noise_changes.png)", "",
             "Both panels show mean-of-three B at sigma 30 on the same scale. Kodak values are exploratory point estimates. "
             "Only the DIV2K panel marks intervals from the prespecified family of 44 comparisons; asterisks refer to B, not to raw rho. "
             "The figure does not test the difference between datasets.", "",
             f"Supported weakening of the direction-adjusted association on DIV2K (B < 0): {supported_text(b, labels)}. "
             f"Supported strengthening (B > 0): {supported_text(b, labels, False)}.", "",
             direct_text + " "
             "An interval containing zero remains inconclusive; it does not establish equivalence or stability.", "",
             "| C = homogeneity change minus the listed descriptor's change | QP 22 | QP 27 | QP 32 | QP 37 |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for feature in FEATURES[:-1]:
        rows = c[c.feature.eq(feature)].set_index("qp").loc[list(QPS)]
        lines.append(f"| {labels[feature]} | " + " | ".join(
            f"{row.estimate:+.3f}{'*' if row.excludes_zero else ''}" for row in rows.itertuples()) + " |")
    lines += ["", "Here, an asterisk refers to the C interval in the same 44-comparison family. "
              "A negative C alone does not prove that homogeneity weakens: its B must also be negative.", "",
              "<details>", "<summary>Direct-comparison intervals and related-scene sensitivity</summary>", "",
              "**Raw correlations: clean → mean of the three AWGN realizations**", "",
              "| Descriptor | QP 22 | QP 27 | QP 32 | QP 37 |", "| --- | ---: | ---: | ---: | ---: |"]
    rho = tables["div2k/correlations"]
    for feature in FEATURES:
        values = []
        for qp in QPS:
            selected = rho[rho.feature.eq(feature) & rho.qp.eq(qp)]
            clean = selected[selected.distortion.eq("clean")].rho.iloc[0]
            noisy = selected[selected.distortion.eq("awgn")].rho.mean()
            values.append(f"{clean:+.3f} → {noisy:+.3f}")
        lines.append(f"| {labels[feature]} | " + " | ".join(values) + " |")
    lines += ["", "These are signed point estimates. Crossing zero here does not by itself establish a statistically "
              "supported association of the opposite sign.", "",
              "![Direct DIV2K comparisons with simultaneous intervals](figures/Fig7_validation_comparisons.png)", "",
              "The horizontal intervals use the mathematical C range [−4,4]; the dashed line marks no difference. "
              "These are direct differences of changes, not separate tests of individual correlations.", "",
              "Visual inspection found no obvious duplicate photographs or reuse of Kodak images. "
              "DIV2K 0854 and 0864 show the Colosseum from different viewpoints. The prespecified sensitivity analysis "
              "therefore samples these two photographs together as one of 47 clusters. Each sampled cluster contributes "
              "all its photographs, so the number of photographs varies across bootstrap samples; the observed estimate still uses all 48. "
              "This check addresses the identified pair and does not establish independence of every scene.", "",
              f"The primary family has a max-error critical value of {primary.critical_value.iloc[0]:.3f}; "
              f"the separate cluster sensitivity has {cluster.critical_value.iloc[0]:.3f}. "
              f"Whether an interval excludes zero changes for {len(disagreements)} of the 44 effects. "
              "The two analyses have separate alpha 0.05 families; they do not provide joint 95% coverage across both.", ""]
    for row in disagreements.itertuples():
        lines.append(f"- {row.effect_type}, {labels[row.feature]}, QP {row.qp}: "
                     f"primary [{row.simultaneous_low_primary:+.3f}, {row.simultaneous_high_primary:+.3f}]; "
                     f"cluster [{row.simultaneous_low_cluster:+.3f}, {row.simultaneous_high_cluster:+.3f}].")
    lines += ["", "</details>", "",
              "The follow-up tests the response to strong synthetic AWGN on these fixed-size crops. "
              "It does not independently validate the full noise-strength trajectory, sinusoidal disturbances, "
              "local CU decisions or prediction accuracy.", ""]
    return lines


def plot_validation(tables, output, labels, qp_styles):
    if "div2k/effects" not in tables:
        return
    output.mkdir(parents=True, exist_ok=True)
    primary = tables["div2k/effects"].query("resampling == 'image'")
    kodak = point_effects(tables["correlations"])
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4), layout="constrained")
    for axis, title, is_validation in zip(axes, ("Kodak · 24 images\nExploratory point estimates",
                                                "DIV2K · 48 crops\n* Prespecified family of 44 intervals"), (False, True)):
        rows = primary[primary.effect_type.eq("B")].set_index(["feature", "qp"])
        matrix = np.array([[rows.loc[feature, qp].estimate if is_validation else kodak["B", feature, qp]
                            for qp in QPS] for feature in FEATURES])
        visual = axis.imshow(matrix, vmin=-2, vmax=2, cmap="RdBu_r", aspect="auto")
        for i, feature in enumerate(FEATURES):
            for j, qp in enumerate(QPS):
                star = "*" if is_validation and rows.loc[feature, qp].excludes_zero else ""
                value = f"{matrix[i,j]:+.2f}" if round(matrix[i,j], 2) != 0 else "0.00"
                axis.text(j, i, value + star, ha="center", va="center", fontsize=10,
                          color="white" if abs(matrix[i,j]) > 1.3 else "black")
        axis.set(title=title, xticks=range(4), xticklabels=[f"QP {q}" for q in QPS],
                 yticks=range(6), yticklabels=[labels[f] for f in FEATURES])
        axis.tick_params(length=0)
    fig.colorbar(visual, ax=axes, fraction=0.03, pad=0.03, ticks=(-2,-1,0,1,2), label="B: direction-adjusted change from clean")
    for extension in ("png", "pdf"):
        fig.savefig(output / f"Fig6_dataset_noise_changes.{extension}", dpi=350, bbox_inches="tight")
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(8.2, 7), layout="constrained")
    names = []
    for i, feature in enumerate(FEATURES[:-1]):
        for j, qp in enumerate(QPS):
            row = primary[(primary.effect_type == "C") & (primary.feature == feature) & (primary.qp == qp)].iloc[0]
            y = i * 5 + j
            color, marker = qp_styles[qp]
            axis.errorbar(row.estimate, y, xerr=[[row.estimate - row.simultaneous_low], [row.simultaneous_high - row.estimate]],
                          color=color, marker=marker, markersize=5, capsize=2, linewidth=1.2)
            names.append((y, f"{labels[feature]}, QP {qp}"))
    axis.axvline(0, color="0.5", linestyle="--", linewidth=1)
    axis.set(xlim=(-4,4), yticks=[y for y, _ in names], yticklabels=[label for _, label in names],
             xlabel="C = B[homogeneity] − B[other]", title="DIV2K: direct differences of noise-related changes\nSimultaneous intervals from the primary 44-effect family")
    axis.invert_yaxis()
    axis.grid(axis="x", alpha=0.15)
    for extension in ("png", "pdf"):
        fig.savefig(output / f"Fig7_validation_comparisons.{extension}", dpi=350, bbox_inches="tight")
    plt.close(fig)
