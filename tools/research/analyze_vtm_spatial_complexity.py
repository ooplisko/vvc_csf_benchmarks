"""Measure saved PNGs and analyze their fixed-condition VTM CU associations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.research.run_vtm_content_partition_study import read_rows, write_rows
from vvenc_csf.spatial_complexity import FEATURES, glcm_features, spatial_complexity_metrics
from vvenc_csf.stimuli import _to_luma, file_sha256, read_png
from vvenc_csf.study_statistics import (
    holm_adjust,
    paired_spearman_bootstrap,
    percentile_intervals,
    simultaneous_basic_intervals,
    spearman_independence_permutation,
    spearman_last_axis,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS = ROOT / "results/vtm_content_partition_four_qp/analysis_workspace/analysis"
DEFAULT_TABLES = ROOT / "docs/vtm_content_partition_study/spatial_complexity/tables"
DEFAULT_STIMULI = ROOT / "results/vtm_content_partition_four_qp/manifest.csv"
SETTINGS = {
    "expected_sources": 24,
    "expected_correlation_cells": 312,
    "expected_rq2_contrasts": 144,
    "permutation_holm_family_size": 168,
    "bootstrap_resamples": 99_999,
    "bootstrap_seed": 20260905,
    "permutation_resamples": 99_999,
    "permutation_seed": 20260906,
    "contrast_family_alpha": 0.025,
    "pointwise_confidence": 0.95,
    "glcm_offsets_row_column": ((0, 1), (1, 1), (1, 0), (1, -1)),
    "glcm_sensitivity": (
        {"name": "levels32", "levels": 32, "offsets": ((0, 1), (1, 1), (1, 0), (1, -1))},
        {"name": "horizontal", "levels": 8, "offsets": ((0, 1),)},
    ),
}
SIGNS = dict(zip(FEATURES, (1, 1, 1, 1, 1, -1), strict=True))


def condition_key(row: dict[str, object]) -> tuple[str, int, str, int]:
    return str(row["distortion"]), int(float(row["level"])), str(row["seed"]), int(row["qp"])


def build_cells(
    rows: list[dict[str, object]], expected_sources: int = 24
) -> tuple[list[dict[str, object]], list[str], np.ndarray, np.ndarray]:
    """Align each feature/condition with the same complete, sorted image sample."""

    sources = sorted({str(row["source"]) for row in rows})
    if len(sources) != expected_sources:
        raise ValueError("Incomplete source set")
    groups: dict[tuple[str, int, str, int], dict[str, dict[str, object]]] = {}
    for row in rows:
        group = groups.setdefault(condition_key(row), {})
        source = str(row["source"])
        if source in group:
            raise ValueError("Duplicate source in an encoding condition")
        group[source] = row
    cells, x, y = [], [], []
    for condition, group in sorted(groups.items()):
        if sorted(group) != sources:
            raise ValueError(f"Incomplete condition: {condition}")
        distortion, level, seed, qp = condition
        primary = distortion != "awgn" or seed == "20260811"
        for feature in FEATURES:
            cells.append({"distortion": distortion, "level": level, "seed": seed, "qp": qp,
                          "feature": feature, "primary": primary, "n_images": len(sources)})
            x.append([float(group[source][feature]) for source in sources])
            y.append([float(group[source]["cu_density_per_mpixel"]) for source in sources])
    return cells, sources, np.asarray(x), np.asarray(y)


def contrasts(
    cells: list[dict[str, object]], observed: np.ndarray, distribution: np.ndarray
) -> tuple[list[dict[str, object]], np.ndarray, np.ndarray]:
    lookup = {(*condition_key(cell), cell["feature"]): i for i, cell in enumerate(cells)}
    metadata, values, sampled = [], [], []
    for i, cell in enumerate(cells):
        if not cell["primary"]:
            continue
        feature, qp = str(cell["feature"]), int(cell["qp"])
        sign = SIGNS[feature]
        if cell["distortion"] == "clean":
            if feature == "sobel_si":
                continue
            reference = lookup[("clean", 0, "", qp, "sobel_si")]
            family, reference_sign = "RQ1", 1
        else:
            reference = lookup[("clean", 0, "", qp, feature)]
            family, reference_sign = "RQ2", sign
        metadata.append({**cell, "family": family, "reference_index": reference,
                         "cell_index": i, "raw_rho_difference": observed[i] - observed[reference]})
        values.append(sign * observed[i] - reference_sign * observed[reference])
        sampled.append(sign * distribution[:, i] - reference_sign * distribution[:, reference])
    return metadata, np.asarray(values), np.asarray(sampled).T


def validate_measurements(rows: list[dict]) -> None:
    """Require all 24 images in every condition at all four QPs."""
    conditions = {("clean", 0, "", qp) for qp in (22, 27, 32, 37)}
    conditions |= {("stripes", level, "", qp) for level in (8, 16, 32) for qp in (22, 27, 32, 37)}
    conditions |= {("awgn", level, seed, qp) for level in (5, 15, 30)
                   for seed in ("20260811", "20260812", "20260813") for qp in (22, 27, 32, 37)}
    expected = {(f"kodim{i:02d}.png", *condition) for i in range(1, 25) for condition in conditions}
    keys = [(row["source"], *condition_key(row)) for row in rows]
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError("Expected every Kodak image/condition at QP 22, 27, 32 and 37 exactly once")
    if len({(r["stimulus"], int(r["qp"])) for r in rows}) != 1248:
        raise ValueError("Duplicate stimulus/QP measurements")
    stimuli = {}
    for row in rows:
        identity = (row["source"], row["distortion"], row["level"], row["seed"], row["image_sha256"])
        if stimuli.setdefault(row["stimulus"], identity) != identity:
            raise ValueError("Conflicting stimulus identity across QPs")
    if len(stimuli) != 312:
        raise ValueError("Expected 312 stimuli, each evaluated at four QPs")
    if any(row["mode"] != "baseline" or any(str(row[key]).lower() != "true" for key in
           ("reconstruction_verified", "cu_coverage_verified")) for row in rows):
        raise ValueError("Measurements require verified baseline reconstructions and CU coverage")
    for row in rows:
        area, count, density = (float(row[key]) for key in ("coded_area", "cu_count", "cu_density_per_mpixel"))
        if area != 393216 or count <= 0 or not count.is_integer() or not np.isclose(
                density, 1_000_000 * count / area, rtol=1e-12, atol=0):
            raise ValueError("CU count, coded area and density are inconsistent")


def make_features(stimuli: Path, measurements_path: Path, output: Path, config: dict[str, object]) -> None:
    manifest = read_rows(stimuli)
    rows = read_rows(measurements_path)
    validate_measurements(rows)
    if len(manifest) != 312 or len({r["stimulus"] for r in manifest}) != 312:
        raise ValueError("Expected 312 unique input PNGs")
    features = []
    directions = []
    for row in manifest:
        image_path = ROOT / row["path"]
        if file_sha256(image_path) != row["sha256"]:
            raise ValueError(f"PNG hash changed: {image_path}")
        image = read_png(image_path)
        measurements = spatial_complexity_metrics(image)
        if measurements["sobel_si"] != float(row["stimulus_sobel_si"]):
            raise ValueError("Sobel baseline changed")
        luma = _to_luma(image)
        for variant in config["glcm_sensitivity"]:
            values = glcm_features(luma, variant["levels"], tuple(map(tuple, variant["offsets"])))
            measurements.update({f"{key}_{variant['name']}": value for key, value in values.items()})
        for dr, dc in config["glcm_offsets_row_column"]:
            directions.append({"stimulus": row["stimulus"], "dr": dr, "dc": dc,
                               **glcm_features(luma, offsets=((dr, dc),))})
        features.append({**row, **measurements})
    by_stimulus = {row["stimulus"]: row for row in features}
    joined = []
    for row in rows:
        feature = by_stimulus[row["stimulus"]]
        if row["image_sha256"] != feature["sha256"]:
            raise ValueError("Feature/encoding stimulus hash mismatch")
        if any(str(row[key]) != str(feature[key]) for key in ("source", "distortion", "level", "seed")):
            raise ValueError("Feature/encoding condition mismatch")
        computed = {key: value for key, value in feature.items() if key in FEATURES or
                    any(key == f"{name}_{variant['name']}" for name in FEATURES for variant in config["glcm_sensitivity"])}
        joined.append({**row, **{k: v for k, v in feature.items() if k not in row}, **computed})
    write_rows(output / "stimulus_features.csv", features)
    write_rows(output / "direction_features.csv", directions)
    write_rows(output / "joined_measurements.csv", joined)
    print(f"Saved {len(features)} stimulus feature rows and {len(joined)} encoding joins", flush=True)


def interval_row(intervals: dict, index: int, prefix: str = "") -> dict[str, object]:
    return {f"{prefix}{key}": value[index].item() for key, value in intervals.items()
            if isinstance(value, np.ndarray)}


def run_statistics(output: Path, config: dict[str, object]) -> None:
    rows = read_rows(output / "joined_measurements.csv")
    validate_measurements(rows)
    cells, sources, x, y = build_cells(rows, int(config["expected_sources"]))
    primary = np.array([cell["primary"] for cell in cells], dtype=bool)
    expected_cells = int(config.get("expected_correlation_cells", 168))
    expected_primary = int(config["permutation_holm_family_size"])
    if len(cells) != expected_cells or primary.sum() != expected_primary:
        raise ValueError("Correlation cells do not match the registered primary/supplementary counts")
    print(f"Computing paired image bootstrap for {len(cells)} correlation cells", flush=True)
    observed, distribution = paired_spearman_bootstrap(
        x, y, n_resamples=int(config["bootstrap_resamples"]), seed=int(config["bootstrap_seed"]))
    np.savez_compressed(output / "bootstrap_correlations.npz", observed=observed, distribution=distribution)
    ci = percentile_intervals(observed, distribution, confidence_level=float(config["pointwise_confidence"]))
    print(f"Computing independence permutations for {expected_primary} primary cells", flush=True)
    permutation = spearman_independence_permutation(
        x[primary], y[primary], n_resamples=int(config["permutation_resamples"]),
        seed=int(config["permutation_seed"]))
    np.savez_compressed(output / "permutation_correlations.npz", **permutation)
    p, adjusted = np.full(len(cells), np.nan), np.full(len(cells), np.nan)
    p[primary], adjusted[primary] = permutation["pvalue"], holm_adjust(permutation["pvalue"])
    correlation_rows = []
    for i, cell in enumerate(cells):
        correlation_rows.append({**cell, "rho": observed[i], "oriented_rho": SIGNS[cell["feature"]] * observed[i],
                                 **interval_row(ci, i, "ci_"), "permutation_p": p[i], "holm_p": adjusted[i],
                                 "unique_feature_values": np.unique(x[i]).size,
                                 "unique_density_values": np.unique(y[i]).size})
    write_rows(output / "correlations.csv", correlation_rows)
    meta, values, draws = contrasts(cells, observed, distribution)
    pointwise = percentile_intervals(values, draws)
    simultaneous_low, simultaneous_high = np.full(values.shape, np.nan), np.full(values.shape, np.nan)
    critical_values = {}
    for family, expected in (("RQ1", 20), ("RQ2", int(config.get("expected_rq2_contrasts", 108)))):
        selected = np.array([row["family"] == family for row in meta])
        if selected.sum() != expected:
            raise ValueError(f"Unexpected {family} contrast count")
        result = simultaneous_basic_intervals(values[selected], draws[:, selected],
                                              alpha=float(config["contrast_family_alpha"]))
        simultaneous_low[selected], simultaneous_high[selected] = result["low"], result["high"]
        critical_values[family] = result["critical_value"]
    contrast_rows = [{**row, "oriented_difference": values[i], **interval_row(pointwise, i, "pointwise_"),
                      "simultaneous_low": simultaneous_low[i], "simultaneous_high": simultaneous_high[i]}
                     for i, row in enumerate(meta)]
    write_rows(output / "contrasts.csv", contrast_rows)

    influence = []
    for source_index, source in enumerate(sources):
        keep = np.arange(len(sources)) != source_index
        omitted = spearman_last_axis(x[:, keep], y[:, keep])
        leave_meta, leave_values, _ = contrasts(cells, omitted, omitted[None, :])
        influence.extend({"omitted_source": source, **row, "n_images": int(keep.sum()),
                          "oriented_difference": leave_values[i]}
                         for i, row in enumerate(leave_meta))
    write_rows(output / "leave_one_out_contrasts.csv", influence)

    # Supplementary paired changes use the same shared index sequence, no formal tests.
    lookup = {(*condition_key(cell), cell["feature"]): i for i, cell in enumerate(cells)}
    delta_cells, dx, dy, delta_rows = [], [], [], []
    for i, cell in enumerate(cells):
        if not cell["primary"] or cell["distortion"] == "clean":
            continue
        ref = lookup[("clean", 0, "", int(cell["qp"]), cell["feature"])]
        delta_x = SIGNS[cell["feature"]] * (x[i] - x[ref])
        delta_y = np.log(y[i] / y[ref])
        delta_cells.append(cell)
        dx.append(delta_x)
        dy.append(delta_y)
        delta_rows.extend({**cell, "source": source, "oriented_feature_change": delta_x[j],
                           "log_density_ratio": delta_y[j], "density_change_percent": 100 * (y[i, j] / y[ref, j] - 1)}
                          for j, source in enumerate(sources))
    write_rows(output / "paired_changes.csv", delta_rows)
    print("Computing supplementary paired-change bootstrap", flush=True)
    delta_observed, delta_draws = paired_spearman_bootstrap(
        np.asarray(dx), np.asarray(dy), n_resamples=int(config["bootstrap_resamples"]),
        seed=int(config["bootstrap_seed"]))
    np.savez_compressed(output / "bootstrap_paired_changes.npz", observed=delta_observed, distribution=delta_draws)
    delta_ci = percentile_intervals(delta_observed, delta_draws)
    write_rows(output / "paired_change_correlations.csv", [
        {**cell, "rho": delta_observed[i], **interval_row(delta_ci, i, "ci_")}
        for i, cell in enumerate(delta_cells)])

    sensitivity_rows = []
    by_condition = {(str(row["source"]), *condition_key(row)): row for row in rows}
    for i, cell in enumerate(cells):
        if not cell["primary"] or not str(cell["feature"]).startswith("glcm_"):
            continue
        for variant in config["glcm_sensitivity"]:
            feature = f"{cell['feature']}_{variant['name']}"
            variant_x = [float(by_condition[(source, *condition_key(cell))][feature]) for source in sources]
            sensitivity_rows.append({**cell, "variant": variant["name"], "rho_primary": observed[i],
                                     "rho_variant": float(spearman_last_axis(variant_x, y[i]))})
    write_rows(output / "parameter_sensitivity.csv", sensitivity_rows)
    # Inter-feature redundancy on all clean images, separate from endpoint tests.
    clean = [row for row in rows if row["distortion"] == "clean" and int(row["qp"]) == 22]
    feature_associations = [{"feature_a": a, "feature_b": b,
                             "rho": float(spearman_last_axis([float(r[a]) for r in clean], [float(r[b]) for r in clean]))}
                            for a in FEATURES for b in FEATURES]
    write_rows(output / "clean_feature_associations.csv", feature_associations)
    print(f"Saved {len(cells)} correlations and {len(meta)} comparisons; "
          f"simultaneous critical values: {critical_values}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("features", "statistics", "all"), nargs="?", default="all")
    parser.add_argument("--stimuli", type=Path, default=DEFAULT_STIMULI)
    parser.add_argument("--measurements", type=Path, default=DEFAULT_TABLES / "joined_measurements.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.action in ("features", "all"):
        make_features(args.stimuli, args.measurements, args.output, SETTINGS)
    if args.action in ("statistics", "all"):
        run_statistics(args.output, SETTINGS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
