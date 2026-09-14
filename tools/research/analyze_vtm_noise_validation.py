"""Analyze the frozen independent DIV2K experiment without further encoding."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.research.complete_vtm_noise_validation import NoiseValidationCompletion, default_settings
from tools.research.run_vtm_content_partition_study import ROOT, read_rows, write_rows
from tools.research.run_vtm_noise_validation import ANALYSIS_SETTINGS, AWGN_SEEDS, QPS, selected_sources
from vvenc_csf.spatial_complexity import FEATURES, spatial_complexity_metrics
from vvenc_csf.stimuli import file_sha256, read_png
from vvenc_csf.study_statistics import paired_spearman_bootstrap, simultaneous_basic_intervals, spearman_last_axis


DEFAULT_OUTPUT = ROOT / "results/vtm_noise_validation/analysis"
N_RESAMPLES, BOOTSTRAP_SEED, ALPHA = 99_999, 20260905, 0.05
CONDITIONS = (("clean", 0, ""), *(("awgn", 30, str(seed)) for seed in AWGN_SEEDS))
PAIR = ("0854.png", "0864.png")
FEATURE_TABLES = ("stimulus_features", "joined_measurements", "selected_sources")


def feature_paths(study, output):
    return [Path(__file__).resolve(), study.checks_path, study.summary_path, study.pilot.checks_path,
            study.pilot.analysis_protocol_path, ROOT / "vvenc_csf/spatial_complexity.py",
            ROOT / "vvenc_csf/study_statistics.py", *(output / f"{name}.csv" for name in FEATURE_TABLES)]


def verify_checks(path, expected_paths):
    rows = read_rows(path)
    if len(rows) != len(expected_paths) or {row["path"] for row in rows} != {str(p.resolve()) for p in expected_paths}:
        raise ValueError("Feature-cache check inventory changed")
    for row in rows:
        target = Path(row["path"])
        if not target.is_file() or file_sha256(target) != row["sha256"]:
            raise ValueError(f"Changed analysis input or feature table: {target}")


def prepare_features(study, output):
    study.validate()
    protocol = {row["setting"]: row["value"] for row in read_rows(study.pilot.analysis_protocol_path)}
    if protocol != {key: str(value) for key, value in ANALYSIS_SETTINGS.items()}:
        raise ValueError("The frozen statistical protocol differs from the planned analysis")
    checks_path = output / "feature_checks.csv"
    if checks_path.is_file():
        verify_checks(checks_path, feature_paths(study, output))
        print("Reused verified DIV2K feature tables.", flush=True)
        return
    manifest = read_rows(study.pilot.manifest_path)
    measurements = read_rows(study.summary_path)
    sources = sorted(selected_sources())
    if len(manifest) != 192 or len(measurements) != 768 or set(row["source"] for row in manifest) != set(sources):
        raise ValueError("Expected the complete 48-source DIV2K matrix")
    features = []
    for row in manifest:
        path = study._project_path(Path(row["path"]))
        image = read_png(path)
        if image.shape != (512, 768, 3) or file_sha256(path) != row["sha256"]:
            raise ValueError(f"Changed or incorrectly sized stimulus: {path}")
        features.append({**row, **spatial_complexity_metrics(image)})
    by_stimulus = {row["stimulus"]: row for row in features}
    fields = ("dataset", "source", "stimulus", "distortion", "level", "seed", "actual_luma_rms", "qp",
              "cu_count", "coded_width", "coded_height", "coded_area", "image_sha256", "conversion",
              "encoder_sha256", "decoder_sha256", "encoder_config_sha256", "reconstruction_verified", "cu_coverage_verified")
    joined = []
    for row in measurements:
        feature = by_stimulus[row["stimulus"]]
        if (row["image_sha256"] != feature["sha256"] or int(row["coded_area"]) != 768 * 512
                or any(str(row[name]) != str(feature[name]) for name in ("source", "distortion", "level", "seed"))):
            raise ValueError("Feature/measurement join changed the image or condition")
        joined.append({**{name: row[name] for name in fields}, **{name: feature[name] for name in FEATURES}})
    build_cells(joined, sources)
    selected = [row for row in read_rows(study.pilot.inventory_path) if row["source"] in sources]
    for name, rows in zip(FEATURE_TABLES, (features, joined, selected)):
        write_rows(output / f"{name}.csv", rows)
    paths = feature_paths(study, output)
    write_rows(checks_path, [{"path": str(path.resolve()), "sha256": file_sha256(path)} for path in paths])
    print("Saved 192 feature rows, 768 joined measurements and 48 selected sources.", flush=True)


def build_cells(rows, sources):
    sources = tuple(sources)
    expected = {(source, qp, *condition) for source in sources for qp in QPS for condition in CONDITIONS}
    indexed = {(row["source"], int(row["qp"]), row["distortion"], float(row["level"]), str(row["seed"])): row
               for row in rows}
    if len(indexed) != len(rows) or set(indexed) != expected or len(set(sources)) != len(sources):
        raise ValueError("Duplicate, missing or unexpected DIV2K source/condition/QP")
    cells, x, y = [], [], []
    for feature in FEATURES:
        for qp in QPS:
            for distortion, level, seed in CONDITIONS:
                ordered = [indexed[source, qp, distortion, level, seed] for source in sources]
                cells.append({"feature": feature, "qp": qp, "distortion": distortion, "level": level, "seed": seed})
                x.append([float(row[feature]) for row in ordered])
                y.append([float(row["cu_count"]) for row in ordered])
    x, y = np.asarray(x), np.asarray(y)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(y < 1) or np.any(y != np.floor(y)):
        raise ValueError("Descriptors and positive integer CU counts must be finite")
    return cells, x, y


def effect_values(cells, correlations):
    lookup = {(row["feature"], row["qp"], row["distortion"], str(row["seed"])): i for i, row in enumerate(cells)}
    metadata = [{"effect_type": "B", "feature": feature, "qp": qp} for feature in FEATURES for qp in QPS]
    clean = correlations[..., [lookup[row["feature"], row["qp"], "clean", ""] for row in metadata]]
    noisy = correlations[..., [[lookup[row["feature"], row["qp"], "awgn", str(seed)] for seed in AWGN_SEEDS]
                               for row in metadata]].mean(axis=-1)
    signs = np.array([-1 if row["feature"] == "glcm_homogeneity" else 1 for row in metadata])
    b = signs * (noisy - clean)
    other = list(range(20))
    reference = [20 + i % 4 for i in other]
    values = np.concatenate((b, b[..., reference] - b[..., other]), axis=-1)
    metadata += [{"effect_type": "C", "feature": row["feature"], "qp": row["qp"]} for row in metadata[:20]]
    return metadata, values, clean, noisy, b


def cluster_groups(sources):
    sources = tuple(sources)
    if not set(PAIR).issubset(sources) or len(set(sources)) != len(sources):
        raise ValueError("The predeclared scene pair must occur exactly once")
    return [tuple(sources.index(name) for name in PAIR) if source == PAIR[0] else (i,)
            for i, source in enumerate(sources) if source != PAIR[1]]


def expand_cluster_draws(draws, groups):
    """Yield equally sized sub-batches, retaining both photos on every pair draw."""
    pair = next(i for i, group in enumerate(groups) if len(group) == 2)
    first = np.array([group[0] for group in groups])
    paired = draws == pair
    counts = paired.sum(axis=1)
    for count in np.unique(counts):
        positions = np.flatnonzero(counts == count)
        batch, flags = draws[positions], paired[positions]
        indices = np.empty((len(batch), draws.shape[1] + count), dtype=np.int64)
        slots = np.arange(draws.shape[1])[None, :] + np.cumsum(flags, axis=1) - flags
        indices[np.arange(len(batch))[:, None], slots] = first[batch]
        row, column = np.nonzero(flags)
        indices[row, slots[row, column] + 1] = groups[pair][1]
        yield positions, indices


def cluster_bootstrap(x, y, sources, n_resamples=N_RESAMPLES, seed=BOOTSTRAP_SEED, batch_size=512):
    groups = cluster_groups(sources)
    rng = np.random.Generator(np.random.PCG64(seed))
    distribution = np.empty((n_resamples, len(x)))
    for start in range(0, n_resamples, batch_size):
        stop = min(start + batch_size, n_resamples)
        draws = rng.integers(0, len(groups), size=(stop-start, len(groups)))
        for positions, indices in expand_cluster_draws(draws, groups):
            distribution[start + positions] = spearman_last_axis(x[:, indices], y[:, indices]).T
    return spearman_last_axis(x, y), distribution


def cached_bootstrap(path, method, cells, sources, x, y):
    metadata = {"x": x, "y": y, "sources": np.array(sources),
                "cells": np.array([f"{r['feature']}|{r['qp']}|{r['distortion']}|{r['seed']}" for r in cells]),
                "method": np.array(method), "settings": np.array([N_RESAMPLES, BOOTSTRAP_SEED]),
                "analysis_sha256": np.array(file_sha256(Path(__file__)))}
    observed = spearman_last_axis(x, y)
    if path.exists():
        with np.load(path, allow_pickle=False) as cache:
            if any(key not in cache or not np.array_equal(cache[key], value) for key, value in metadata.items()):
                raise ValueError(f"Bootstrap cache does not match the analysis: {path}")
            distribution = cache["distribution"]
            if (distribution.shape != (N_RESAMPLES, len(cells)) or not np.array_equal(cache["observed"], observed, equal_nan=True)
                    or np.isinf(distribution).any()
                    or np.any(np.isfinite(distribution) & (np.abs(distribution) > 1))):
                raise ValueError(f"Invalid bootstrap cache: {path}")
        replay = (paired_spearman_bootstrap(x, y, n_resamples=2, seed=BOOTSTRAP_SEED)[1] if method == "image"
                  else cluster_bootstrap(x, y, sources, n_resamples=2, seed=BOOTSTRAP_SEED)[1])
        if not np.allclose(distribution[:2], replay, atol=1e-12, rtol=0, equal_nan=True):
            raise ValueError("Cached bootstrap draws do not preserve the planned pairing")
        print(f"Reused {method} bootstrap cache.", flush=True)
        return observed, distribution
    print(f"Computing {method}: {N_RESAMPLES:,} paired bootstrap samples.", flush=True)
    if method == "image":
        observed, distribution = paired_spearman_bootstrap(x, y, n_resamples=N_RESAMPLES, seed=BOOTSTRAP_SEED)
    elif method == "scene_cluster":
        observed, distribution = cluster_bootstrap(x, y, sources, n_resamples=N_RESAMPLES, seed=BOOTSTRAP_SEED)
    else:
        raise ValueError("Unknown bootstrap sampling unit")
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **metadata, observed=observed, distribution=distribution)
    temporary.replace(path)
    return observed, distribution


def effect_rows(cells, observed, distribution, method, n_images):
    metadata, values, clean, noisy, b = effect_values(cells, observed)
    _, samples, _, _, _ = effect_values(cells, distribution)
    bounds = np.array([2.0] * 24 + [4.0] * 20)
    intervals = simultaneous_basic_intervals(values, samples, alpha=ALPHA, bounds=(-bounds, bounds))
    rows = []
    for i, item in enumerate(metadata):
        feature_index = FEATURES.index(item["feature"]) * 4 + QPS.index(item["qp"])
        homogeneity_index = 20 + QPS.index(item["qp"])
        low, high = intervals["low"][i], intervals["high"][i]
        rows.append({**item, "resampling": method, "n_images": n_images,
                     "n_clusters": n_images if method == "image" else n_images - 1,
                     "family_size": 44, "alpha": ALPHA, "bootstrap_resamples": len(distribution),
                     "rho_clean": clean[feature_index], "rho_noisy_mean3": noisy[feature_index],
                     "b_homogeneity": b[homogeneity_index], "b_other": b[feature_index],
                     "estimate": values[i], "bound_low": -bounds[i], "bound_high": bounds[i],
                     "simultaneous_low": low, "simultaneous_high": high,
                     "critical_value": intervals["critical_value"], "evaluable": intervals["evaluable"][i],
                     "invalid_resamples": intervals["invalid_resamples"][i],
                     "excludes_zero": bool(intervals["evaluable"][i] and (low > 0 or high < 0))})
    return rows


def statistics(output):
    verify_checks(output / "feature_checks.csv", feature_paths(NoiseValidationCompletion(default_settings()), output))
    sources = sorted(row["source"] for row in read_rows(output / "selected_sources.csv"))
    if tuple(sources) != tuple(sorted(selected_sources())):
        raise ValueError("Changed independent source selection")
    cells, x, y = build_cells(read_rows(output / "joined_measurements.csv"), sources)
    rows = []
    for method in ("image", "scene_cluster"):
        observed, distribution = cached_bootstrap(output / f"bootstrap_{method}.npz", method, cells, sources, x, y)
        rows.extend(effect_rows(cells, observed, distribution, method, len(sources)))
    write_rows(output / "correlations.csv", [{**cell, "n_images": len(sources), "rho": value}
                                             for cell, value in zip(cells, observed)])
    write_rows(output / "effects.csv", rows)
    print("Saved 96 correlation cells and two separate families of 44 effects.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("features", "statistics", "all"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.stage in ("features", "all"):
        prepare_features(NoiseValidationCompletion(default_settings()), args.output)
    if args.stage in ("statistics", "all"):
        statistics(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
