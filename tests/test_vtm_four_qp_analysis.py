from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tools.research.verify_vtm_spatial_complexity_analysis import (
    FEATURES, verify_cached_inference, verify_matrix, verify_percentiles,
)


def matrix_rows():
    features, existing, new = [], [], []
    conditions = [("clean", 0, "")]
    conditions += [("awgn", level, seed) for level in (5, 15, 30)
                   for seed in ("20260811", "20260812", "20260813")]
    conditions += [("stripes", level, "") for level in (8, 16, 32)]
    for source in range(1, 25):
        for distortion, level, seed in conditions:
            stimulus = f"{source}_{distortion}_{level}_{seed}"
            feature = dict(source=f"kodim{source:02d}.png", stimulus=stimulus, distortion=distortion,
                           level=str(level), seed=seed, sha256=stimulus)
            features.append(feature)
            for qp in (22, 27, 32, 37):
                row = dict(feature, qp=str(qp), mode="baseline", image_sha256=stimulus,
                           yuv_sha256="input-yuv", encoder_sha256="baseline-encoder",
                           conversion="opencv_444", reconstruction_verified="True", cu_coverage_verified="True")
                old = distortion == "clean" or (qp in (22, 32, 37) and (
                    distortion != "awgn" or seed == "20260811")) or qp == 32
                row["config_sha256" if old else "encoder_config_sha256"] = "baseline-config"
                (existing if old else new).append(row)
    return features, existing, new


@pytest.mark.parametrize("completed", [False, True])
def test_verifier_accepts_only_the_exact_matrix(completed):
    _, existing, new = matrix_rows()
    joined = pd.DataFrame(existing + (new if completed else []))
    joined[["level", "qp"]] = joined[["level", "qp"]].astype(int)
    joined[["reconstruction_verified", "cu_coverage_verified"]] = True
    cells = joined[["distortion", "level", "seed", "qp"]].drop_duplicates()
    correlations = pd.DataFrame([{**row, "feature": feature,
                                  "primary": row["distortion"] != "awgn" or row["seed"] == "20260811"}
                                 for row in cells.to_dict("records") for feature in FEATURES])
    assert verify_matrix(joined, correlations) == completed
    # Keep all counts intact but mislabel one supplementary condition.
    correlations.loc[correlations.seed == "20260812", "seed"] = "999"
    with pytest.raises(AssertionError):
        verify_matrix(joined, correlations)


def test_cached_percentile_verification_detects_interval_tampering():
    draws = np.array([[0.1, np.nan], [0.2, 0.2], [0.3, 0.3]])
    table = pd.DataFrame(dict(rho=[0.2, 0.2], ci_low=[0.105, np.nan], ci_high=[0.295, np.nan],
                              ci_invalid_resamples=[0, 1], ci_evaluable=[True, False],
                              ci_degenerate=[False, False]))
    verify_percentiles(table, draws, "ci_")
    table.loc[0, "ci_low"] = 0.15
    with pytest.raises(AssertionError):
        verify_percentiles(table, draws, "ci_")


@pytest.mark.parametrize("damage", ["duplicate", "primary", "nan_condition", "missing_image"])
def test_matrix_rejects_incomplete_or_mislabeled_data(damage):
    _, existing, new = matrix_rows()
    joined = pd.DataFrame(existing + new)
    joined[["level", "qp"]] = joined[["level", "qp"]].astype(int)
    joined[["reconstruction_verified", "cu_coverage_verified"]] = True
    cells = joined[["distortion", "level", "seed", "qp"]].drop_duplicates()
    correlations = pd.DataFrame([{**row, "feature": feature,
                                  "primary": row["distortion"] != "awgn" or row["seed"] == "20260811"}
                                 for row in cells.to_dict("records") for feature in FEATURES])
    if damage == "duplicate":
        joined.iloc[-1] = joined.iloc[0]
    elif damage == "primary":
        correlations.loc[0, "primary"] = not correlations.loc[0, "primary"]
    elif damage == "nan_condition":
        joined.loc[0, "seed"] = np.nan
    else:
        joined = joined.iloc[1:]
    with pytest.raises(AssertionError):
        verify_matrix(joined, correlations)


def cached_tables(tmp_path):
    observed = np.array([0.5, 0.2, 0.3])
    draws = observed + np.linspace(-0.1, 0.1, 99999)[:, None]
    correlations = pd.DataFrame(dict(rho=observed, primary=[True, True, False],
                                     permutation_p=[0.0001, 0.001, np.nan], holm_p=[0.0002, 0.001, np.nan]))
    contrasts = pd.DataFrame(dict(cell_index=[1, 2], reference_index=[0, 0],
                                  family=["RQ1", "RQ2"], feature=["luma_sd", "glcm_entropy"],
                                  oriented_difference=[-0.3, -0.2],
                                  simultaneous_low=[-0.3, -0.2], simultaneous_high=[-0.3, -0.2]))
    for table, distribution, prefix in (
        (correlations, draws, "ci_"),
        (contrasts, draws[:, [1, 2]] - draws[:, [0, 0]], "pointwise_"),
    ):
        table[prefix + "low"], table[prefix + "high"] = np.quantile(distribution, [0.025, 0.975], axis=0)
        table[prefix + "invalid_resamples"] = 0
        table[prefix + "evaluable"] = True
        table[prefix + "degenerate"] = np.all(distribution == distribution[0], axis=0)
    np.savez(tmp_path / "bootstrap_correlations.npz", observed=observed, distribution=draws)
    np.savez(tmp_path / "permutation_correlations.npz", observed=observed[:2],
             extreme_count=[9, 99], invalid_resamples=[0, 0], pvalue=[0.0001, 0.001])
    return correlations, contrasts


def test_cached_inference_uses_only_npz_and_tables_without_writes(tmp_path):
    correlations, contrasts = cached_tables(tmp_path)
    files = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    verify_cached_inference(tmp_path, correlations, contrasts)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == files


@pytest.mark.parametrize("field", ["holm_p", "ci_low", "simultaneous_low"])
@pytest.mark.parametrize("replacement", [0.9, np.nan])
def test_cached_inference_rejects_wrong_values_and_missing_bounds(tmp_path, field, replacement):
    correlations, contrasts = cached_tables(tmp_path)
    table = contrasts if field == "simultaneous_low" else correlations
    table.loc[0, field] = replacement
    with pytest.raises(AssertionError):
        verify_cached_inference(tmp_path, correlations, contrasts)
