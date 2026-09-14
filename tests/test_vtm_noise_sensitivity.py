from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import spearmanr

from tools.research import analyze_vtm_noise_sensitivity as noise
from tools.research.analyze_vtm_spatial_complexity import DEFAULT_TABLES


def contrast_fixture():
    cells, values = [], []
    for qp in noise.QPS:
        for distortion, seed in (("clean", ""), *(("awgn", seed) for seed in noise.SEEDS)):
            for feature in noise.FEATURES:
                hom = feature == noise.HOMOGENEITY
                if distortion == "clean":
                    rho = -0.8 if hom else 0.6
                else:
                    index = noise.SEEDS.index(seed)
                    rho = (0.1, -0.4, -0.7)[index] if hom else (0.7, 0.4, 0.2)[index]
                cells.append({"distortion": distortion, "level": 0 if distortion == "clean" else 30,
                              "seed": seed, "qp": qp, "feature": feature})
                values.append(rho)
    values = np.asarray(values)
    # Different paired replicates ensure averaging is tested at the draw level.
    draws = np.stack([values, values + np.linspace(-0.04, 0.04, len(values)), values * 0.9])
    return cells, values, draws


def test_direct_comparisons_use_fixed_signs_and_paired_differences():
    cells, observed, distribution = contrast_fixture()
    metadata, values, draws = noise.noise_contrasts(cells, observed, distribution, noise.SEEDS[:1])
    assert len(metadata) == 20
    assert {row["qp"] for row in metadata} == set(noise.QPS)
    assert {row["feature"] for row in metadata} == set(noise.FEATURES) - {noise.HOMOGENEITY}
    np.testing.assert_allclose(values, -1.0)
    np.testing.assert_allclose(draws[0], values)
    np.testing.assert_allclose(draws[2], values * 0.9)
    assert all(row["b_homogeneity"] == pytest.approx(-0.9) for row in metadata)
    assert all(row["b_other"] == pytest.approx(0.1) for row in metadata)


def test_seed_average_preserves_pairing_in_every_replicate():
    cells, observed, distribution = contrast_fixture()
    _, values, draws = noise.noise_contrasts(cells, observed, distribution, noise.SEEDS)
    separate = [noise.noise_contrasts(cells, observed, distribution, (seed,)) for seed in noise.SEEDS]
    np.testing.assert_allclose(values, -0.3)
    np.testing.assert_allclose(values, np.mean([result[1] for result in separate], axis=0))
    np.testing.assert_allclose(draws, np.mean([result[2] for result in separate], axis=0))


def test_mean_of_seed_correlations_does_not_pool_seed_images():
    cells, observed, _ = contrast_fixture()
    x = np.array([[1, 2, 3, 4], [101, 102, 103, 104], [201, 202, 203, 204]])
    y = np.array([[1, 3, 2, 4], [104, 103, 102, 101], [201, 202, 204, 203]])
    seed_rho = np.array([spearmanr(a, b).statistic for a, b in zip(x, y, strict=True)])
    for i, cell in enumerate(cells):
        if cell["distortion"] == "awgn" and cell["feature"] == "sobel_si":
            observed[i] = seed_rho[noise.SEEDS.index(cell["seed"])]
    metadata, _, _ = noise.noise_contrasts(cells, observed, observed[None, :], noise.SEEDS)
    sobel = next(row for row in metadata if row["feature"] == "sobel_si")
    assert sobel["b_other"] == pytest.approx(seed_rho.mean() - 0.6)
    assert sobel["b_other"] != pytest.approx(spearmanr(x.ravel(), y.ravel()).statistic - 0.6)
    assert sobel["n_images"] == 24


def test_families_are_separate_exploratory_and_support_difference_of_differences():
    cells, observed, distribution = contrast_fixture()
    # Achievable correlation extremes give C=-4, outside the support of a single B.
    for i, cell in enumerate(cells):
        observed[i] = -1.0 if cell["distortion"] == "clean" else 1.0
    distribution = np.stack([observed, observed * 0.9, observed * 0.8])
    rows = noise.noise_comparisons(cells, observed, distribution)
    assert len(rows) == 40
    assert {row["family"] for row in rows} == {"primary_sigma30", "equal_mean3_sigma30"}
    for row in rows:
        assert row["analysis_status"] == "exploratory"
        assert row["oriented_difference"] == -4
        assert row["simultaneous_low"] == -4
        assert -4 < row["simultaneous_high"] < -2
        assert row["family_size"] == 20 and row["alpha"] == 0.05
        assert row["evaluable"] and row["excludes_zero"]


@pytest.fixture
def saved_cells(monkeypatch):
    rows = noise.read_rows(DEFAULT_TABLES / "joined_measurements.csv")
    correlations = noise.read_rows(DEFAULT_TABLES / "correlations.csv")
    cells, _, x, y = noise.build_cells(rows)
    observed = np.array([spearmanr(a, b).statistic for a, b in zip(x, y, strict=True)])
    rng = np.random.Generator(np.random.PCG64(noise.SETTINGS["bootstrap_seed"]))
    indices = rng.integers(0, 24, size=(2, 24))
    draws = np.array([[spearmanr(a[index], b[index]).statistic for a, b in zip(x, y, strict=True)]
                      for index in indices])
    monkeypatch.setitem(noise.SETTINGS, "bootstrap_resamples", 2)
    return rows, correlations, cells, observed, draws


def test_saved_cache_alignment_and_observed_points(saved_cells):
    rows, correlations, expected_cells, observed, draws = saved_cells
    cells = noise.validate_cache(rows, correlations, observed, draws)
    assert cells == expected_cells
    metadata, values, _ = noise.noise_contrasts(cells, observed, draws, noise.SEEDS[:1])
    selected = next(i for i, row in enumerate(metadata) if row["qp"] == 32 and row["feature"] == "sobel_si")
    assert metadata[selected]["b_homogeneity"] == pytest.approx(-0.7539130434782607)
    # Independent raw-rho arithmetic with the fixed negative homogeneity direction.
    lookup = {(*noise.condition_key(row), row["feature"]): float(row["rho"]) for row in correlations}
    expected = -(lookup[("awgn", 30, "20260811", 32, "glcm_homogeneity")]
                 - lookup[("clean", 0, "", 32, "glcm_homogeneity")])
    expected -= lookup[("awgn", 30, "20260811", 32, "sobel_si")] - lookup[("clean", 0, "", 32, "sobel_si")]
    assert values[selected] == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("damage", ["order", "csv_rho", "observed", "uncoupled", "shape", "nonfinite", "sample_size"])
def test_cache_rejects_changed_cells_or_unpaired_draws(saved_cells, damage):
    rows, correlations, _, observed, draws = saved_cells
    if damage == "order":
        correlations[0], correlations[1] = correlations[1], correlations[0]
    elif damage == "csv_rho":
        correlations[0]["rho"] = str(float(correlations[0]["rho"]) + 0.001)
    elif damage == "observed":
        observed[0] += 0.001
    elif damage == "uncoupled":
        # Per-cell bootstrap rows cannot be shuffled independently.
        draws[:, 0] = draws[::-1, 0]
    elif damage == "shape":
        draws = draws[:, :-1]
    elif damage == "nonfinite":
        draws[1, 1] = np.nan
    else:
        correlations[0]["n_images"] = "72"
    with pytest.raises(ValueError):
        noise.validate_cache(rows, correlations, observed, draws)


def test_diagnostics_cover_all_seeds_qps_and_existing_glcm_variants():
    rows = noise.read_rows(DEFAULT_TABLES / "joined_measurements.csv")
    diagnostics = noise.noise_rank_diagnostics(rows)
    assert len(diagnostics) == 432
    assert {row["variant"] for row in diagnostics} == {"primary", "levels32", "horizontal"}
    assert all(row["n_images"] == 24 for row in diagnostics)
    main = {row["feature"]: row for row in diagnostics if row["variant"] == "primary"
            and row["qp"] == 32 and row["level"] == 30 and row["seed"] == "20260811"}
    expected = {"glcm_homogeneity": 0.549, "glcm_entropy": 0.683, "edge_fraction": 0.848, "sobel_si": 0.998}
    for feature, rho in expected.items():
        assert main[feature]["descriptor_rank_rho"] == pytest.approx(rho, abs=0.0005)
        assert main[feature]["cu_count_rank_rho"] == pytest.approx(0.762, abs=0.0005)
    clean = np.array([float(row["edge_fraction"]) for row in rows if row["distortion"] == "clean" and row["qp"] == "32"])
    edge = main["edge_fraction"]
    assert edge["clean_sd"] == pytest.approx(np.std(clean, ddof=1))
    assert edge["clean_iqr"] == pytest.approx(np.quantile(clean, 0.75) - np.quantile(clean, 0.25))
    assert edge["clean_unique_values"] == len(np.unique(clean))
    assert edge["clean_exact_one_count"] == np.count_nonzero(clean == 1)
    assert main["glcm_homogeneity"]["clean_exact_one_count"] == ""
