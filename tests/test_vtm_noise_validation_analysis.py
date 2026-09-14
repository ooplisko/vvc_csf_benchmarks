import numpy as np
import pytest
from scipy.stats import spearmanr

from tools.research import analyze_vtm_noise_validation as analysis


def measurements():
    sources = sorted(analysis.selected_sources())
    rng = np.random.default_rng(7)
    rows = []
    for source in sources:
        for qp in analysis.QPS:
            for distortion, level, seed in analysis.CONDITIONS:
                rows.append({"source": source, "qp": qp, "distortion": distortion, "level": level, "seed": seed,
                             "cu_count": rng.integers(10, 200),
                             **dict(zip(analysis.FEATURES, rng.uniform(0, 1, 6)))})
    return sources, rows


@pytest.mark.parametrize("damage", ["duplicate", "missing", "qp", "seed", "nan", "fractional_count"])
def test_matrix_rejects_invalid_measurements(damage):
    sources, rows = measurements()
    if damage == "duplicate":
        rows.append(dict(rows[0]))
    elif damage == "missing":
        rows.pop()
    elif damage == "qp":
        rows[0]["qp"] = 24
    elif damage == "seed":
        rows[0]["seed"] = "unknown"
    elif damage == "nan":
        rows[0]["sobel_si"] = np.nan
    else:
        rows[0]["cu_count"] = 1.5
    with pytest.raises(ValueError):
        analysis.build_cells(rows, sources)


def test_matrix_alignment_and_mean_of_three_effects():
    sources, rows = measurements()
    cells, x, y = analysis.build_cells(rows, sources)
    shuffled = np.random.default_rng(8).permutation(rows).tolist()
    _, xx, yy = analysis.build_cells(shuffled, sources)
    np.testing.assert_array_equal(x, xx)
    np.testing.assert_array_equal(y, yy)
    assert x.shape == (96, 48)
    rho = np.zeros(96)
    for i, cell in enumerate(cells):
        seed_index = 0 if not cell["seed"] else analysis.AWGN_SEEDS.index(int(cell["seed"])) + 1
        rho[i] = ((-.8, -.2, -.4, -.6) if cell["feature"] == "glcm_homogeneity" else (.2, .1, .4, .7))[seed_index]
    metadata, values, clean, noisy, b = analysis.effect_values(cells, rho)
    assert len(metadata) == 44
    np.testing.assert_allclose(b[:20], .2)
    np.testing.assert_allclose(b[20:], -.4)
    np.testing.assert_allclose(values[24:], -.6)
    # A change in only one realization contributes exactly one third to B.
    altered = rho.copy()
    altered[1] += .09
    _, distribution, _, _, _ = analysis.effect_values(cells, np.stack((rho, altered)))
    assert distribution[1, 0] - distribution[0, 0] == pytest.approx(.03)
    assert distribution[1, 24] - distribution[0, 24] == pytest.approx(-.03)


def test_joint_44_family_uses_largest_C_error_and_coordinate_bounds():
    sources, rows = measurements()
    cells, _, _ = analysis.build_cells(rows, sources)
    observed = np.zeros(96)
    draw = np.array([(.95 if c["distortion"] == "clean" else -.95) for c in cells])
    result = analysis.effect_rows(cells, observed, np.tile(draw, (5, 1)), "image", 48)
    assert {row["family_size"] for row in result} == {44}
    assert {row["alpha"] for row in result} == {.05}
    assert all(row["critical_value"] == pytest.approx(3.8) for row in result)
    assert all(row["simultaneous_low"] == -2 and row["simultaneous_high"] == 2 for row in result[:24])
    assert all(row["simultaneous_low"] == pytest.approx(-3.8) for row in result[24:])


def test_cluster_expansion_and_bootstrap_match_independent_scalar_oracle():
    sources = ("0801.png", "0854.png", "0864.png", "0890.png", "0899.png")
    groups = analysis.cluster_groups(sources)
    assert groups == [(0,), (1, 2), (3,), (4,)]
    draws = np.array([[0,0,0,0], [1,0,2,3], [1,1,1,1]])
    expanded = {}
    for positions, indices in analysis.expand_cluster_draws(draws, groups):
        expanded.update(zip(positions.tolist(), indices.tolist()))
    assert expanded == {0: [0,0,0,0], 1: [1,2,0,3,4], 2: [1,2,1,2,1,2,1,2]}
    rng = np.random.default_rng(21)
    x, y = rng.integers(0, 5, (2, 3, 5)).astype(float)
    observed, actual = analysis.cluster_bootstrap(x, y, sources, n_resamples=19, seed=4, batch_size=7)
    draws = np.random.Generator(np.random.PCG64(4)).integers(0, 4, (19, 4))
    expected = []
    for draw in draws:
        indices = [image for group in draw for image in groups[group]]
        expected.append([spearmanr(a[indices], b[indices]).statistic for a,b in zip(x,y)])
    np.testing.assert_allclose(actual, expected, atol=1e-14, equal_nan=True)
    np.testing.assert_allclose(observed, [spearmanr(a,b).statistic for a,b in zip(x,y)], atol=1e-14)
    _, different_batch = analysis.cluster_bootstrap(x,y,sources,n_resamples=19,seed=4,batch_size=3)
    np.testing.assert_array_equal(actual, different_batch)


@pytest.mark.parametrize("method", ["image", "scene_cluster"])
def test_bootstrap_cache_reuses_completed_work_and_rejects_changed_inputs(tmp_path, monkeypatch, method):
    sources, rows = measurements()
    cells, x, y = analysis.build_cells(rows, sources)
    monkeypatch.setattr(analysis, "N_RESAMPLES", 19)
    path = tmp_path / "bootstrap.npz"
    first = analysis.cached_bootstrap(path, method, cells, sources, x, y)
    saved = path.read_bytes()
    second = analysis.cached_bootstrap(path, method, cells, sources, x, y)
    assert path.read_bytes() == saved
    np.testing.assert_array_equal(first[1], second[1])
    with pytest.raises(ValueError, match="does not match"):
        analysis.cached_bootstrap(path, method, cells, sources[::-1], x, y)
    with np.load(path, allow_pickle=False) as cache:
        changed = {name: cache[name] for name in cache.files}
    changed["distribution"][0,0] += .01
    np.savez_compressed(path, **changed)
    with pytest.raises(ValueError, match="pairing"):
        analysis.cached_bootstrap(path, method, cells, sources, x, y)


def test_feature_checks_reject_removed_entries_and_tampering(tmp_path):
    paths = [tmp_path / "a.csv", tmp_path / "b.csv"]
    for p in paths:
        p.write_text("example", encoding="utf-8")
    rows = [{"path": str(p.resolve()), "sha256": analysis.file_sha256(p)} for p in paths]
    checks = tmp_path / "checks.csv"
    analysis.write_rows(checks, rows)
    analysis.verify_checks(checks, paths)
    analysis.write_rows(checks, rows[:1])
    with pytest.raises(ValueError, match="inventory"):
        analysis.verify_checks(checks, paths)
    analysis.write_rows(checks, rows)
    paths[0].write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Changed"):
        analysis.verify_checks(checks, paths)
