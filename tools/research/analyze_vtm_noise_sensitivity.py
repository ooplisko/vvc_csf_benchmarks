"""Explore noise-response differences and image ranks using saved VTM results."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.research.analyze_vtm_spatial_complexity import (
    DEFAULT_RESULTS, FEATURES, ROOT, SETTINGS, SIGNS, build_cells, condition_key,
    read_rows, validate_measurements, write_rows,
)
from vvenc_csf.study_statistics import simultaneous_basic_intervals, spearman_last_axis


DEFAULT_OUTPUT = ROOT / "results/vtm_content_partition_four_qp/noise_sensitivity"
QPS = (22, 27, 32, 37)
SEEDS = ("20260811", "20260812", "20260813")
HOMOGENEITY = "glcm_homogeneity"


def validate_cache(rows: list[dict], correlations: list[dict], observed: np.ndarray,
                   distribution: np.ndarray) -> list[dict]:
    """Check the complete image matrix, cell order and sampled paired draws.

    Only the first two saved replicates are replayed, with ranks recomputed
    after sampling; this detects incorrect coupling without rerunning bootstrap.
    """
    validate_measurements(rows)
    cells, _, x, y = build_cells(rows)
    keys = lambda items: [(*condition_key(row), row["feature"]) for row in items]
    if keys(cells) != keys(correlations):
        raise ValueError("Correlation CSV cell order does not match the measurement matrix")
    if any(int(row["n_images"]) != 24 or str(row["primary"]).lower() != str(cell["primary"]).lower()
           for cell, row in zip(cells, correlations, strict=True)):
        raise ValueError("Correlation CSV sample size or primary status changed")
    if observed.shape != (312,) or distribution.shape != (SETTINGS["bootstrap_resamples"], 312):
        raise ValueError("Expected observed (312,) and bootstrap (99999, 312) arrays")
    if any(not np.isfinite(value).all() for value in (x, y, observed, distribution)):
        raise ValueError("Measurements and cached correlations must all be finite")
    if np.any(np.abs(distribution) > 1 + 1e-12):
        raise ValueError("Cached correlations exceed [-1, 1]")
    recomputed = spearman_last_axis(x, y)
    csv_rho = np.array([float(row["rho"]) for row in correlations])
    if not np.allclose(recomputed, observed, atol=1e-12, rtol=0) or not np.allclose(
            recomputed, csv_rho, atol=1e-12, rtol=0):
        raise ValueError("Observed correlations disagree with the CSV or measurements")
    rng = np.random.Generator(np.random.PCG64(SETTINGS["bootstrap_seed"]))
    indices = rng.integers(0, x.shape[1], size=(2, x.shape[1]))
    replayed = spearman_last_axis(x[:, indices], y[:, indices]).T
    if not np.allclose(distribution[:2], replayed, atol=1e-12, rtol=0):
        raise ValueError("Cached bootstrap does not match shared paired image-index draws")
    return cells


def load_analysis(analysis_dir: Path) -> tuple[list[dict], list[dict], np.ndarray, np.ndarray]:
    rows = read_rows(analysis_dir / "joined_measurements.csv")
    correlations = read_rows(analysis_dir / "correlations.csv")
    with np.load(analysis_dir / "bootstrap_correlations.npz", allow_pickle=False) as cached:
        observed, distribution = cached["observed"], cached["distribution"]
    cells = validate_cache(rows, correlations, observed, distribution)
    return rows, cells, observed, distribution


def noise_contrasts(cells: list[dict], observed: np.ndarray, distribution: np.ndarray,
                    seeds: tuple[str, ...]) -> tuple[list[dict], np.ndarray, np.ndarray]:
    """Compare homogeneity's oriented change with five other changes at sigma 30.

    Average the seed-specific correlations within each shared image replicate;
    do not pool seeds as extra images or bootstrap the seed axis.
    """
    lookup = {(*condition_key(cell), cell["feature"]): i for i, cell in enumerate(cells)}

    def effect(qp: int, feature: str) -> tuple[float, np.ndarray]:
        clean = lookup[("clean", 0, "", qp, feature)]
        noisy = [lookup[("awgn", 30, seed, qp, feature)] for seed in seeds]
        sign = SIGNS[feature]
        return (float(sign * (observed[noisy].mean() - observed[clean])),
                sign * (distribution[:, noisy].mean(axis=1) - distribution[:, clean]))

    metadata, values, samples = [], [], []
    for qp in QPS:
        hom, hom_draws = effect(qp, HOMOGENEITY)
        for feature in FEATURES:
            if feature == HOMOGENEITY:
                continue
            other, other_draws = effect(qp, feature)
            metadata.append({"distortion": "awgn", "level": 30, "qp": qp, "feature": feature,
                             "reference_feature": HOMOGENEITY, "n_images": 24,
                             "b_homogeneity": hom, "b_other": other})
            values.append(hom - other)
            samples.append(hom_draws - other_draws)
    return metadata, np.asarray(values), np.asarray(samples).T


def noise_comparisons(cells: list[dict], observed: np.ndarray, distribution: np.ndarray) -> list[dict]:
    """Two separate, post-hoc families of 20 approximate simultaneous intervals."""
    rows = []
    for summary, seeds in (("primary", SEEDS[:1]), ("equal_mean3", SEEDS)):
        metadata, values, sampled = noise_contrasts(cells, observed, distribution, seeds)
        intervals = simultaneous_basic_intervals(values, sampled, alpha=0.05, bounds=(-4, 4))
        for i, row in enumerate(metadata):
            low, high = float(intervals["low"][i]), float(intervals["high"][i])
            rows.append({"analysis_status": "exploratory", "family": f"{summary}_sigma30",
                         "seed_summary": summary, "seeds": ";".join(seeds), "n_seeds": len(seeds),
                         **row, "oriented_difference": values[i],
                         "definition": "C = B_homogeneity - B_other; B = s * (rho_noisy - rho_clean)",
                         "family_size": len(values), "alpha": 0.05,
                         "bootstrap_resamples": distribution.shape[0],
                         "simultaneous_low": low, "simultaneous_high": high,
                         "critical_value": intervals["critical_value"],
                         "evaluable": bool(intervals["evaluable"][i]),
                         "excludes_zero": bool(low > 0 or high < 0)})
    return rows


def noise_rank_diagnostics(rows: list[dict]) -> list[dict]:
    """Describe clean/noisy rank preservation and spread across 24 paired images.

    SD uses n-1; IQR uses linearly interpolated quartiles. Feature diagnostics
    repeat across QPs because the stimulus is fixed, while CU counts can change.
    GLCM variants are descriptive checks, without new intervals or tests.
    """
    validate_measurements(rows)
    groups: dict[tuple, dict[str, dict]] = {}
    for row in rows:
        groups.setdefault(condition_key(row), {})[row["source"]] = row
    variants = [(feature, "primary", feature) for feature in FEATURES]
    variants += [(feature, variant["name"], f"{feature}_{variant['name']}")
                 for variant in SETTINGS["glcm_sensitivity"] for feature in FEATURES
                 if feature.startswith("glcm_")]
    result = []
    for qp in QPS:
        clean_group = groups[("clean", 0, "", qp)]
        sources = sorted(clean_group)
        for level in (5, 15, 30):
            for seed in SEEDS:
                noisy_group = groups[("awgn", level, seed, qp)]
                clean_cu = np.array([float(clean_group[source]["cu_count"]) for source in sources])
                noisy_cu = np.array([float(noisy_group[source]["cu_count"]) for source in sources])
                cu_rank = float(spearman_last_axis(clean_cu, noisy_cu))
                for feature, variant, column in variants:
                    clean = np.array([float(clean_group[source][column]) for source in sources])
                    noisy = np.array([float(noisy_group[source][column]) for source in sources])
                    if not np.isfinite(clean).all() or not np.isfinite(noisy).all():
                        raise ValueError(f"Non-finite descriptor values: {column}")
                    row = {"feature": feature, "variant": variant, "distortion": "awgn", "level": level,
                           "seed": seed, "qp": qp, "n_images": len(sources),
                           "descriptor_rank_rho": float(spearman_last_axis(clean, noisy)),
                           "cu_count_rank_rho": cu_rank,
                           "rho_clean": float(spearman_last_axis(clean, clean_cu)),
                           "rho_noisy": float(spearman_last_axis(noisy, noisy_cu))}
                    for prefix, values in (("clean", clean), ("noisy", noisy)):
                        row.update({f"{prefix}_mean": float(values.mean()),
                                    f"{prefix}_sd": float(values.std(ddof=1)),
                                    f"{prefix}_iqr": float(np.diff(np.quantile(values, [0.25, 0.75]))[0]),
                                    f"{prefix}_min": float(values.min()), f"{prefix}_max": float(values.max()),
                                    f"{prefix}_range": float(np.ptp(values)),
                                    f"{prefix}_unique_values": int(np.unique(values).size),
                                    f"{prefix}_exact_one_count": int(np.count_nonzero(values == 1))
                                    if feature == "edge_fraction" else ""})
                    result.append(row)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows, cells, observed, distribution = load_analysis(args.analysis_dir)
    comparisons = noise_comparisons(cells, observed, distribution)
    diagnostics = noise_rank_diagnostics(rows)
    write_rows(args.output / "exploratory_noise_comparisons.csv", comparisons)
    write_rows(args.output / "noise_rank_diagnostics.csv", diagnostics)
    print(f"Saved {len(comparisons)} exploratory comparisons and {len(diagnostics)} rank diagnostics to {args.output}")


if __name__ == "__main__":
    main()
