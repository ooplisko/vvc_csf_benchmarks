"""Time the six Kodak descriptors on saved primary inputs with no encoding."""

from __future__ import annotations

import argparse
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns

import cv2
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.research.summarize_vtm_spatial_complexity import (
    DEFAULT_OUTPUT, DEFAULT_TABLES, IDENTITY, primary_measurements,
)
from tools.research.run_vtm_content_partition_study import ROOT, read_rows, write_rows
from vvenc_csf.spatial_complexity import EDGE_KERNELS, FEATURES, glcm_features, glcm_matrices, spatial_complexity_metrics
from vvenc_csf.stimuli import _to_luma, complexity_metrics, file_sha256, read_png


def edge_fraction(luma: np.ndarray) -> float:
    values = luma.astype(np.float64)
    edge_sum = sum(np.abs(cv2.filter2D(values, cv2.CV_64F, kernel)) for kernel in EDGE_KERNELS)
    return float(np.mean(edge_sum[1:-1, 1:-1] > 150))


def glcm_single(luma: np.ndarray, feature: str) -> float:
    """Reuse the registered GLCM builder and evaluate only the requested property."""
    probabilities = glcm_matrices(luma)
    if feature == "glcm_entropy":
        logs = np.zeros_like(probabilities)
        np.log(probabilities, out=logs, where=probabilities > 0)
        return float(-np.sum(probabilities * logs, axis=(1, 2)).mean())
    differences_squared = (np.arange(8)[:, None] - np.arange(8)[None, :]) ** 2
    if feature == "glcm_contrast":
        return float(np.sum(probabilities * differences_squared, axis=(1, 2)).mean())
    if feature == "glcm_homogeneity":
        return float(np.sum(probabilities / (1 + differences_squared), axis=(1, 2)).mean())
    raise ValueError(f"Unknown GLCM feature: {feature}")


def operations(image: np.ndarray) -> dict:
    luma = _to_luma(image)
    return {
        "sobel_si": lambda: complexity_metrics(luma)["sobel_si"],
        "luma_sd": lambda: float(np.std(luma.astype(np.float64))),
        "edge_fraction": lambda: edge_fraction(luma),
        **{feature: (lambda feature=feature: glcm_single(luma, feature)) for feature in FEATURES[3:]},
        "glcm_shared": lambda: glcm_features(luma),
        "glcm_build": lambda: glcm_matrices(luma),
        "luma_conversion": lambda: _to_luma(image),
        "full_pipeline": lambda: spatial_complexity_metrics(image),
    }


def verify_operations(image: np.ndarray, row: dict) -> dict:
    calls = operations(image)
    actual = calls["full_pipeline"]()
    for feature in FEATURES:
        if not np.isclose(actual[feature], float(row[feature]), atol=1e-12, rtol=1e-12):
            raise ValueError(f"Descriptor differs from saved value: {row['stimulus']} / {feature}")
        if not np.isclose(calls[feature](), actual[feature], atol=1e-12, rtol=1e-12):
            raise ValueError(f"Isolated operation differs from the existing pipeline: {feature}")
    return calls


def summarize_timings(raw: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = pd.DataFrame(raw)
    table["elapsed_ms"] = pd.to_numeric(table.elapsed_ms)
    per_image = table.groupby([*IDENTITY, "operation"], dropna=False).elapsed_ms.agg(
        repeats="size", median_ms="median", min_ms="min", max_ms="max").reset_index()
    summary = per_image.groupby(["distortion", "level", "seed", "operation"], dropna=False).median_ms.agg(
        n_images="size", median_ms="median", q25_ms=lambda s: s.quantile(.25),
        q75_ms=lambda s: s.quantile(.75), min_ms="min", max_ms="max").reset_index()
    return per_image, summary


def cpu_name() -> str:
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
    return platform.processor() or platform.machine()


def benchmark(measurements: Path, output: Path, repeats: int = 11, warmup: int = 2) -> None:
    if repeats < 3 or warmup < 1:
        raise ValueError("Use at least three repetitions and one warmup")
    cv2.setNumThreads(1)
    cv2.ocl.setUseOpenCL(False)
    rows = [row for row in primary_measurements(measurements) if int(row["qp"]) == 32]
    rows.sort(key=lambda row: row["stimulus"])
    environment = {
        "cpu": cpu_name(), "logical_cpus": os.cpu_count(), "os": platform.platform(),
        "python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
        "opencv_threads": cv2.getNumThreads(), "opencl": cv2.ocl.useOpenCL(),
        "repeats": repeats, "warmup": warmup, "ordering_seed": 20260919,
        "timer": "perf_counter_ns", "input_count": len(rows), "pixels_per_image": 393216,
        "input": "uint8 BGR PNG loaded before timing; existing OpenCV luma conversion",
        "scope": "six standalone descriptors from luma; shared GLCM; conversion; existing full pipeline",
    }
    for path in (measurements, Path(__file__), ROOT / "vvenc_csf/spatial_complexity.py", ROOT / "vvenc_csf/stimuli.py"):
        environment[path.name + "_sha256"] = file_sha256(path)
    raw_path, environment_path = output / "descriptor_timing_raw.csv", output / "descriptor_timing_environment.csv"
    raw = []
    if environment_path.exists():
        saved = {row["setting"]: row["value"] for row in read_rows(environment_path)}
        if any(saved.get(key) != str(value) for key, value in environment.items()):
            raise ValueError("Benchmark settings or inputs changed; use a new --output directory")
        environment["started_utc"] = saved["started_utc"]
        if raw_path.exists():
            raw = read_rows(raw_path)
    else:
        if raw_path.exists():
            raise ValueError("Timing rows exist without their environment record")
        environment["started_utc"] = datetime.now(timezone.utc).isoformat()
    by_stimulus = {}
    for row in raw:
        by_stimulus.setdefault(row["stimulus"], []).append(row)
    if not set(by_stimulus).issubset({row["stimulus"] for row in rows}):
        raise ValueError("Saved timings contain unknown stimuli")
    write_rows(environment_path, [{"setting": key, "value": value} for key, value in environment.items()])
    for i, row in enumerate(rows):
        path = ROOT / row["path"]
        if file_sha256(path) != row["image_sha256"]:
            raise ValueError(f"Changed input PNG: {path}")
        image = read_png(path)
        calls = verify_operations(image, row)
        if row["stimulus"] in by_stimulus:
            saved = by_stimulus[row["stimulus"]]
            expected = {(name, repeat) for name in calls for repeat in range(repeats)}
            if (len(saved) != len(expected) or {(r["operation"], int(r["repeat"])) for r in saved} != expected
                    or any(not np.isfinite(float(r["elapsed_ms"])) or float(r["elapsed_ms"]) <= 0 for r in saved)):
                raise ValueError("Incomplete or invalid saved timing block")
            continue
        rng = np.random.default_rng(20260919 + i)
        for repeat in range(-warmup, repeats):
            for name in rng.permutation(list(calls)):
                start = perf_counter_ns()
                value = calls[name]()
                elapsed_ms = (perf_counter_ns() - start) / 1_000_000
                del value
                if repeat >= 0:
                    raw.append({**{key: row[key] for key in IDENTITY}, "operation": name,
                                "repeat": repeat, "elapsed_ms": elapsed_ms})
        # Persist complete image blocks so a continuation reuses finished measurements.
        write_rows(raw_path, raw)
        if (i + 1) % 24 == 0:
            print(f"Timed {i+1}/{len(rows)} inputs", flush=True)
    per_image, summary = summarize_timings(raw)
    write_rows(output / "descriptor_timing_images.csv", per_image.to_dict("records"))
    write_rows(output / "descriptor_timing_summary.csv", summary.to_dict("records"))
    print(f"Saved {len(raw)} measurements and timing summaries in {output}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurements", type=Path, default=DEFAULT_TABLES / "joined_measurements.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repeats", type=int, default=11)
    parser.add_argument("--warmup", type=int, default=2)
    args = parser.parse_args()
    benchmark(args.measurements, args.output, args.repeats, args.warmup)
