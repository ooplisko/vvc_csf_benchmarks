from __future__ import annotations

import shutil

import numpy as np
import pandas as pd
import pytest

from tools.research import analyze_vtm_spatial_complexity as analysis
from tools.research.analyze_vtm_spatial_complexity import FEATURES, build_cells, contrasts


def measurements() -> list[dict]:
    rows = []
    for distortion, seed in (("clean", ""), ("awgn", "20260811"), ("awgn", "20260812")):
        for index, source in enumerate(("a", "b", "c")):
            rows.append({"source": source, "distortion": distortion, "level": 0 if distortion == "clean" else 5,
                         "seed": seed, "qp": 32, "cu_density_per_mpixel": 10 + index,
                         **{feature: index + len(feature) for feature in FEATURES}})
    return rows


def test_cells_align_images_and_keep_additional_seeds_supplementary() -> None:
    rows = measurements()
    cells, sources, x, y = build_cells(rows[::-1], expected_sources=3)
    assert sources == ["a", "b", "c"]
    assert len(cells) == 18
    assert sum(cell["primary"] for cell in cells) == 12
    np.testing.assert_array_equal(y, np.tile([10, 11, 12], (18, 1)))
    assert np.all(np.diff(x, axis=1) == 1)


def test_missing_and_duplicate_sources_fail_before_statistics() -> None:
    rows = measurements()
    with pytest.raises(ValueError, match="Incomplete condition"):
        build_cells(rows[:-1], expected_sources=3)
    with pytest.raises(ValueError, match="Duplicate"):
        build_cells(rows + [rows[0]], expected_sources=3)


def test_contrasts_match_same_qp_and_correct_direction_without_seed_pooling() -> None:
    cells, _, _, _ = build_cells(measurements(), expected_sources=3)
    observed = np.array([-0.4 if cell["feature"] == "glcm_homogeneity" else 0.4 for cell in cells])
    observed += np.array([0.2 if cell["distortion"] == "clean" else 0 for cell in cells])
    distribution = np.tile(observed, (4, 1))
    metadata, values, draws = contrasts(cells, observed, distribution)
    assert len(values) == 11  # Five clean comparisons and six primary noise contrasts.
    assert all(row["seed"] != "20260812" for row in metadata)
    hom = next(i for i, row in enumerate(metadata) if row["family"] == "RQ2" and row["feature"] == "glcm_homogeneity")
    assert values[hom] == pytest.approx(0.2)
    np.testing.assert_array_equal(draws, np.tile(values, (4, 1)))


def test_statistics_reproduction_uses_csv_without_state_and_preserves_point_results(tmp_path):
    shutil.copyfile(analysis.DEFAULT_TABLES / "joined_measurements.csv", tmp_path / "joined_measurements.csv")
    # A stale resampling file must not be silently reused for changed inputs/settings.
    (tmp_path / "bootstrap_correlations.npz").write_bytes(b"stale")
    config = dict(analysis.SETTINGS, bootstrap_resamples=19, permutation_resamples=19)
    analysis.run_statistics(tmp_path, config)
    for name, columns in (("correlations", ["rho", "oriented_rho"]),
                          ("contrasts", ["oriented_difference"]),
                          ("paired_change_correlations", ["rho"]),
                          ("parameter_sensitivity", ["rho_primary", "rho_variant"])):
        actual = pd.read_csv(tmp_path / f"{name}.csv", float_precision="round_trip")
        expected = pd.read_csv(analysis.DEFAULT_TABLES / f"{name}.csv", float_precision="round_trip")
        np.testing.assert_allclose(actual[columns], expected[columns], atol=1e-12, rtol=0)
    assert not list(tmp_path.glob("*.json"))
    with np.load(tmp_path / "bootstrap_correlations.npz") as samples:
        assert samples["distribution"].shape == (19, 312)


@pytest.mark.parametrize("damage", ["missing", "duplicate", "condition", "identity", "density"])
def test_analysis_rejects_incomplete_or_conflicting_inputs(damage):
    rows = analysis.read_rows(analysis.DEFAULT_TABLES / "joined_measurements.csv")
    if damage == "missing":
        rows.pop()
    elif damage == "duplicate":
        rows[-1] = rows[0]
    elif damage == "condition":
        rows[0]["seed"] = "999"
    elif damage == "identity":
        rows[0]["image_sha256"] = "changed"
    else:
        rows[0]["cu_density_per_mpixel"] = "0"
    with pytest.raises(ValueError):
        analysis.validate_measurements(rows)


def test_feature_stage_replaces_old_values_in_joined_measurements(tmp_path):
    import cv2

    image = np.arange(192, dtype=np.uint8).reshape(8, 8, 3)
    image_path = tmp_path / "fixture.png"
    assert cv2.imwrite(str(image_path), image)
    expected = analysis.spatial_complexity_metrics(image)
    rows = analysis.read_rows(analysis.DEFAULT_TABLES / "joined_measurements.csv")
    manifest = analysis.read_rows(analysis.DEFAULT_TABLES / "stimulus_features.csv")
    for row in manifest:
        row.update(path=str(image_path), sha256=analysis.file_sha256(image_path),
                   stimulus_sobel_si=expected["sobel_si"])
    for row in rows:
        row["image_sha256"] = analysis.file_sha256(image_path)
        row.update({feature: -999 for feature in FEATURES})
    analysis.write_rows(tmp_path / "stimuli.csv", manifest)
    analysis.write_rows(tmp_path / "measurements.csv", rows)
    output = tmp_path / "output"
    analysis.make_features(tmp_path / "stimuli.csv", tmp_path / "measurements.csv", output, analysis.SETTINGS)
    joined = analysis.read_rows(output / "joined_measurements.csv")
    assert len(joined) == 1248
    for feature, value in expected.items():
        np.testing.assert_allclose([float(row[feature]) for row in joined], value)
    assert not list(output.glob("*.json"))
