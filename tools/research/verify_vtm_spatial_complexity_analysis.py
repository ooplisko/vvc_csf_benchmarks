"""Check completed analysis tables against SciPy without repeating resampling."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


FEATURES = ("sobel_si", "luma_sd", "edge_fraction", "glcm_contrast", "glcm_entropy", "glcm_homogeneity")
CONDITION = ["distortion", "level", "seed", "qp"]


def verify_matrix(joined: pd.DataFrame, correlations: pd.DataFrame) -> bool:
    """Require the exact legacy or completed four-QP design, not just its size."""

    assert len(joined) in (672, 1248), "Unexpected encoding matrix size"
    four_qp = len(joined) == 1248
    disturbed_qps = (22, 27, 32, 37) if four_qp else (22, 32, 37)
    extra_qps = (22, 27, 32, 37) if four_qp else (32,)
    expected = {("clean", 0, "", qp) for qp in (22, 27, 32, 37)}
    expected |= {("stripes", level, "", qp) for level in (8, 16, 32) for qp in disturbed_qps}
    expected |= {("awgn", level, "20260811", qp) for level in (5, 15, 30) for qp in disturbed_qps}
    expected |= {("awgn", level, seed, qp) for level in (5, 15, 30)
                 for seed in ("20260812", "20260813") for qp in extra_qps}
    sources = {f"kodim{i:02d}.png" for i in range(1, 25)}
    assert set(joined.source) == sources
    assert not joined.duplicated(["source", *CONDITION]).any()
    groups = joined.groupby(CONDITION, dropna=False)
    assert set(groups.groups) == expected, "Missing or unexpected condition"
    assert all(set(group.source) == sources for _, group in groups)
    assert not joined.duplicated(["stimulus", "qp"]).any()
    assert joined.stimulus.nunique() == 312
    assert (joined.groupby("stimulus")["source"].nunique() == 1).all()
    assert (joined.groupby("stimulus")["image_sha256"].nunique() == 1).all()
    assert (joined["mode"] == "baseline").all()
    assert joined.reconstruction_verified.eq(True).all() and joined.cu_coverage_verified.eq(True).all()
    expected_cells = {(*key, feature) for key in expected for feature in FEATURES}
    assert not correlations.duplicated([*CONDITION, "feature"]).any()
    assert set(correlations[[*CONDITION, "feature"]].itertuples(index=False, name=None)) == expected_cells
    primary = (correlations.distortion != "awgn") | (correlations.seed == "20260811")
    assert correlations.primary.equals(primary), "Primary and supplementary seed labels disagree"
    assert primary.sum() == (168 if four_qp else 132)
    return four_qp


def verify_percentiles(table: pd.DataFrame, draws: np.ndarray, prefix: str) -> None:
    assert draws.ndim == 2 and draws.shape[0] > 0 and draws.shape[1] == len(table)
    invalid = np.sum(~np.isfinite(draws), axis=0)
    evaluable = np.isfinite(table.rho if "rho" in table else table.oriented_difference) & (invalid == 0)
    low, high = np.full(len(table), np.nan), np.full(len(table), np.nan)
    low[evaluable], high[evaluable] = np.quantile(draws[:, evaluable], [0.025, 0.975], axis=0)
    np.testing.assert_allclose(table[f"{prefix}low"], low, atol=1e-12, rtol=0)
    np.testing.assert_allclose(table[f"{prefix}high"], high, atol=1e-12, rtol=0)
    np.testing.assert_array_equal(table[f"{prefix}invalid_resamples"], invalid)
    np.testing.assert_array_equal(table[f"{prefix}evaluable"], evaluable)
    np.testing.assert_array_equal(table[f"{prefix}degenerate"], evaluable & np.all(draws == draws[0], axis=0))


def verify_cached_inference(output: Path, correlations: pd.DataFrame, contrasts: pd.DataFrame) -> None:
    """Independently recompute interval and multiplicity arithmetic from saved draws."""

    with np.load(output / "bootstrap_correlations.npz") as saved:
        draws, observed = saved["distribution"], saved["observed"]
    assert draws.shape == (99999, len(correlations))
    np.testing.assert_allclose(observed, correlations.rho, atol=1e-12, rtol=0)
    verify_percentiles(correlations, draws, "ci_")
    signs = np.where(contrasts.feature == "glcm_homogeneity", -1, 1)
    reference_signs = np.where(contrasts.family == "RQ1", 1, signs)
    contrast_draws = (draws[:, contrasts.cell_index] * signs
                      - draws[:, contrasts.reference_index] * reference_signs)
    verify_percentiles(contrasts, contrast_draws, "pointwise_")
    for family in ("RQ1", "RQ2"):
        selected = (contrasts.family == family).to_numpy()
        values, family_draws = contrasts.oriented_difference.to_numpy()[selected], contrast_draws[:, selected]
        valid = np.isfinite(values) & np.isfinite(family_draws).all(axis=0)
        low, high = np.full(values.size, np.nan), np.full(values.size, np.nan)
        critical = np.nan
        if valid.any():
            critical = np.quantile(np.max(np.abs(family_draws[:, valid] - values[valid]), axis=1), 0.975)
            low[valid], high[valid] = np.maximum(-2, values[valid] - critical), np.minimum(2, values[valid] + critical)
        np.testing.assert_allclose(contrasts.loc[selected, "simultaneous_low"], low, atol=1e-12, rtol=0)
        np.testing.assert_allclose(contrasts.loc[selected, "simultaneous_high"], high, atol=1e-12, rtol=0)
    primary = correlations.primary.to_numpy()
    with np.load(output / "permutation_correlations.npz") as permutation:
        assert all(permutation[name].shape == (int(primary.sum()),) for name in
                   ("observed", "extreme_count", "invalid_resamples", "pvalue"))
        np.testing.assert_allclose(permutation["observed"], observed[primary], atol=1e-12, rtol=0)
        assert ((permutation["extreme_count"] >= 0) & (permutation["extreme_count"] <= 99999)).all()
        assert np.equal(permutation["extreme_count"], np.floor(permutation["extreme_count"])).all()
        assert ((permutation["invalid_resamples"] >= 0) & (permutation["invalid_resamples"] <= 99999)).all()
        p = (permutation["extreme_count"] + 1.0) / 100000.0
        p[(permutation["invalid_resamples"] > 0) | ~np.isfinite(permutation["observed"])] = np.nan
        np.testing.assert_allclose(permutation["pvalue"], p, atol=1e-12, rtol=0)
    order = np.flatnonzero(np.isfinite(p))
    order = order[np.argsort(p[order], kind="stable")]
    adjusted = np.full(p.size, np.nan)
    adjusted[order] = np.minimum(1, np.maximum.accumulate(p[order] * (p.size - np.arange(order.size))))
    np.testing.assert_allclose(correlations.loc[primary, "permutation_p"], p, atol=1e-12, rtol=0)
    np.testing.assert_allclose(correlations.loc[primary, "holm_p"], adjusted, atol=1e-12, rtol=0)
    assert correlations.loc[~primary, ["permutation_p", "holm_p"]].isna().all().all()


def verify(output: Path) -> dict[str, object]:
    """Verify the numerical CSV tables and NPZ draws directly, without state files."""

    def read(name: str) -> pd.DataFrame:
        return pd.read_csv(output / f"{name}.csv", dtype={"seed": str},
                           float_precision="round_trip").fillna({"seed": ""})

    joined, correlations = read("joined_measurements"), read("correlations")
    contrasts, influence = read("contrasts"), read("leave_one_out_contrasts")
    four_qp = verify_matrix(joined, correlations)
    assert np.isfinite(joined[[*FEATURES, "cu_density_per_mpixel"]].to_numpy()).all()
    assert (joined.cu_density_per_mpixel > 0).all()
    rq2_count = 144 if four_qp else 108
    assert len(contrasts) == 20 + rq2_count and len(influence) == 24 * len(contrasts)
    assert contrasts.family.value_counts().to_dict() == {"RQ2": rq2_count, "RQ1": 20}
    expected_contrasts = correlations.index[correlations.primary & ~(
        (correlations.distortion == "clean") & (correlations.feature == "sobel_si"))]
    assert sorted(contrasts.cell_index) == sorted(expected_contrasts)
    assert not influence.duplicated(["omitted_source", "cell_index"]).any()
    assert set(influence.cell_index) == set(contrasts.cell_index)
    assert all(set(group.omitted_source) == set(joined.source) for _, group in influence.groupby("cell_index"))
    assert (correlations.n_images == 24).all() and (influence.n_images == 23).all()
    groups = {key: group.sort_values("source") for key, group in
              joined.groupby(["distortion", "level", "seed", "qp"], dropna=False)}
    arrays, maximum_error = [], 0.0
    for row in correlations.itertuples():
        group = groups[(row.distortion, row.level, row.seed, row.qp)]
        assert len(group) == 24 and group.source.nunique() == 24
        x = group[row.feature].to_numpy()
        y = group.cu_density_per_mpixel.to_numpy()
        rho = spearmanr(x, y).statistic
        maximum_error = max(maximum_error, abs(rho - row.rho))
        np.testing.assert_allclose(rho, row.rho, atol=1e-12, rtol=0)
        np.testing.assert_allclose((-1 if row.feature == "glcm_homogeneity" else 1) * rho,
                                   row.oriented_rho, atol=1e-12, rtol=0)
        arrays.append((x, y))

    sources = sorted(joined.source.unique())
    for row in contrasts.itertuples():
        current, reference = correlations.iloc[row.cell_index], correlations.iloc[row.reference_index]
        sign = -1 if row.feature == "glcm_homogeneity" else 1
        reference_sign = 1 if row.family == "RQ1" else sign
        assert current.primary and reference.primary and reference.distortion == "clean"
        assert current.qp == reference.qp == row.qp
        assert current.feature == row.feature
        assert (current.distortion, current.level, current.seed) == (row.distortion, row.level, row.seed)
        assert reference.feature == ("sobel_si" if row.family == "RQ1" else row.feature)
        assert (current.distortion == "clean") == (row.family == "RQ1")
        np.testing.assert_allclose(sign * current.rho - reference_sign * reference.rho,
                                   row.oriented_difference, atol=1e-12, rtol=0)
        np.testing.assert_allclose(current.rho - reference.rho,
                                   row.raw_rho_difference, atol=1e-12, rtol=0)
    # Compute the 24 reduced correlation vectors once using the independent SciPy API.
    reduced = {}
    for omitted_index, source in enumerate(sources):
        keep = np.arange(24) != omitted_index
        reduced[source] = [spearmanr(x[keep], y[keep]).statistic for x, y in arrays]
    for row in influence.itertuples():
        full = contrasts.loc[contrasts.cell_index == row.cell_index].iloc[0]
        assert all(getattr(row, name) == full[name] for name in
                   ("reference_index", "feature", "family", *CONDITION))
        rho = reduced[row.omitted_source]
        sign = -1 if row.feature == "glcm_homogeneity" else 1
        reference_sign = 1 if row.family == "RQ1" else sign
        np.testing.assert_allclose(sign * rho[row.cell_index] - reference_sign * rho[row.reference_index],
                                   row.oriented_difference, atol=1e-12, rtol=0)
        np.testing.assert_allclose(rho[row.cell_index] - rho[row.reference_index],
                                   row.raw_rho_difference, atol=1e-12, rtol=0)

    changes = read("paired_changes")
    delta_correlations = read("paired_change_correlations")
    assert len(changes) == 24 * rq2_count and len(delta_correlations) == rq2_count
    assert not changes.duplicated(["source", *CONDITION, "feature"]).any()
    assert not delta_correlations.duplicated([*CONDITION, "feature"]).any()
    expected_delta = correlations[correlations.primary & (correlations.distortion != "clean")]
    assert set(delta_correlations[[*CONDITION, "feature"]].itertuples(index=False, name=None)) == set(
        expected_delta[[*CONDITION, "feature"]].itertuples(index=False, name=None))
    for row in delta_correlations.itertuples():
        selected = changes[(changes.distortion == row.distortion) & (changes.level == row.level)
                           & (changes.seed == row.seed) & (changes.qp == row.qp) & (changes.feature == row.feature)]
        assert len(selected) == 24 and set(selected.source) == set(sources)
        selected = selected.sort_values("source")
        current = groups[(row.distortion, row.level, row.seed, row.qp)]
        reference = groups[("clean", 0, "", row.qp)]
        sign = -1 if row.feature == "glcm_homogeneity" else 1
        np.testing.assert_allclose(selected.oriented_feature_change,
                                   sign * (current[row.feature].to_numpy() - reference[row.feature].to_numpy()),
                                   atol=1e-12, rtol=0)
        ratio = current.cu_density_per_mpixel.to_numpy() / reference.cu_density_per_mpixel.to_numpy()
        np.testing.assert_allclose(selected.log_density_ratio, np.log(ratio), atol=1e-12, rtol=0)
        np.testing.assert_allclose(selected.density_change_percent, 100 * (ratio - 1), atol=1e-12, rtol=0)
        rho = spearmanr(selected.oriented_feature_change, selected.log_density_ratio).statistic
        np.testing.assert_allclose(rho, row.rho, atol=1e-12, rtol=0)

    sensitivity = read("parameter_sensitivity")
    expected_sensitivity = {(*key, feature, variant)
                            for key, group in groups.items() if key[0] != "awgn" or key[2] == "20260811"
                            for feature in FEATURES if feature.startswith("glcm_")
                            for variant in ("levels32", "horizontal")}
    assert not sensitivity.duplicated([*CONDITION, "feature", "variant"]).any()
    assert set(sensitivity[[*CONDITION, "feature", "variant"]].itertuples(index=False, name=None)) == expected_sensitivity
    for row in sensitivity.itertuples():
        group = groups[(row.distortion, row.level, row.seed, row.qp)]
        for feature, expected in ((row.feature, row.rho_primary), (f"{row.feature}_{row.variant}", row.rho_variant)):
            np.testing.assert_allclose(spearmanr(group[feature], group.cu_density_per_mpixel).statistic,
                                       expected, atol=1e-12, rtol=0)
    associations = read("clean_feature_associations")
    assert len(associations) == 36 and not associations.duplicated(["feature_a", "feature_b"]).any()
    assert set(associations[["feature_a", "feature_b"]].itertuples(index=False, name=None)) == {
        (a, b) for a in FEATURES for b in FEATURES}
    clean = groups[("clean", 0, "", 22)]
    for row in associations.itertuples():
        np.testing.assert_allclose(spearmanr(clean[row.feature_a], clean[row.feature_b]).statistic,
                                   row.rho, atol=1e-12, rtol=0)

    verify_cached_inference(output, correlations, contrasts)
    with np.load(output / "bootstrap_paired_changes.npz") as bootstrap:
        assert bootstrap["distribution"].shape == (99999, rq2_count)
        np.testing.assert_allclose(bootstrap["observed"], delta_correlations.rho, atol=1e-12, rtol=0)
        verify_percentiles(delta_correlations, bootstrap["distribution"], "ci_")
    supported = contrasts[(contrasts.simultaneous_low > 0) | (contrasts.simultaneous_high < 0)]
    return {"passed": True, "resampling_repeated": False, "encoding_rows": len(joined),
            "primary_correlations": int(correlations.primary.sum()),
            "extra_seed_correlations": int((~correlations.primary).sum()), "dependent_contrasts": len(contrasts),
            "leave_one_out_rows": len(influence), "paired_change_correlations": rq2_count,
            "cached_intervals_and_holm_verified": True,
            "max_scipy_point_error": maximum_error,
            "supported_contrasts": supported[["family", "feature", "distortion", "level", "qp",
                                                "oriented_difference", "simultaneous_low",
                                                "simultaneous_high"]].to_dict(orient="records")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path,
                        default=Path(__file__).resolve().parents[2] /
                        "results/vtm_content_partition_four_qp/analysis_workspace/analysis")
    args = parser.parse_args()
    report = verify(args.analysis_dir)
    print(f"PASS: {report['encoding_rows']} measurements, "
          f"{report['primary_correlations'] + report['extra_seed_correlations']} correlations, "
          f"{report['dependent_contrasts']} contrasts; "
          f"maximum SciPy difference {report['max_scipy_point_error']:.3g}. "
          "Saved intervals and Holm corrections verified; no resampling repeated.")
