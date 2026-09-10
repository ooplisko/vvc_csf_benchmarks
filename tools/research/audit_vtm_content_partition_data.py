"""Audit historical VTM artifacts without encoding or changing the source results."""

from __future__ import annotations

import argparse
import hashlib
import sys
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.research.run_vtm_content_partition_study import output_paths, read_rows, write_rows
from tools.visualization.parse_vvenc_qp_trace import parse_trace
from vvenc_csf.content_partition import ContentPartitionProtocol
from vvenc_csf.partitions import summarize_partitions
from vvenc_csf.stimuli import (
    add_achromatic_awgn,
    add_sinusoidal_interference,
    complexity_metrics,
    derive_image_seed,
    file_sha256,
    read_png,
)


HISTORICAL_RUNS = (
    "vtm_content_partition_study",
    "vtm_content_partition_qp_extension",
    "vtm_content_partition_task2_completion",
    "vtm_content_partition_task3_completion",
)
IDENTITY_FIELDS = (
    "source", "distortion", "level", "seed", "image_sha256", "yuv_sha256",
    "encoder_sha256", "config_sha256", "bitstream_sha256", "trace_sha256",
    "partition_csv_sha256", "reconstruction_sha256", "decoded_sha256", "cu_count",
)


def baseline_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int, int]:
    """Exclude other modes and reject conflicting repeats of a baseline job."""
    unique: dict[tuple[str, int], dict[str, str]] = {}
    excluded = duplicates = 0
    for row in rows:
        if row["dataset"] != "kodak" or row["mode"] != "baseline":
            excluded += 1
            continue
        key = row["stimulus"], int(row["qp"])
        if key in unique:
            if any(unique[key].get(k) != row.get(k) for k in IDENTITY_FIELDS):
                raise ValueError(f"Conflicting baseline duplicate: {key}")
            duplicates += 1
        else:
            unique[key] = row
    return [unique[key] for key in sorted(unique)], excluded, duplicates


def require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"Audit mismatch for {label}: {actual!r} != {expected!r}")


def audit(repo: Path, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    protocol = ContentPartitionProtocol.from_json(repo / "configs/vtm_content_partition_study.json")
    inventory: list[dict[str, object]] = []

    @lru_cache(maxsize=None)
    def sha(path: Path) -> str:
        digest = file_sha256(path)
        inventory.append({"path": path.relative_to(repo).as_posix(), "bytes": path.stat().st_size,
                          "sha256": digest})
        return digest

    all_rows = []
    input_counts = {}
    for name in HISTORICAL_RUNS:
        path = repo / "results" / name / "run/partition_summary.csv"
        sha(path)
        rows = read_rows(path)
        input_counts[name] = len(rows)
        all_rows.extend(dict(row, artifact_run=f"results/{name}/run") for row in rows)
        sha(repo / "results" / name / "manifest.csv")
    rows, excluded, duplicates = baseline_rows(all_rows)
    manifest_path = repo / "results/vtm_content_partition_study/manifest.csv"
    manifest = read_rows(manifest_path)
    by_stimulus = {row["stimulus"]: row for row in manifest}
    require_equal(len(by_stimulus), 312, "unique stimuli")
    planned = {job.key for job in protocol.plan(manifest)}
    require_equal({(r["stimulus"], int(r["qp"]), r["mode"]) for r in rows}, planned, "job plan")
    require_equal(len(rows), 672, "unique baseline jobs")
    source_paths = sorted((repo / protocol.source_dir).glob("*.png"))
    source_pixels = {p.name: read_png(p) for p in source_paths}
    source_hashes = {p.name: sha(p) for p in source_paths}
    source_indices = {p.name: i for i, p in enumerate(source_paths)}
    conversion_hashes = {}
    encoder_hash = sha(repo / "binaries/vtm/vtm23/baseline_trace/EncoderApp.exe")
    config_hash = sha(repo / protocol.encoder_config)
    sha(repo / "binaries/vtm/vtm23/baseline/DecoderApp.exe")

    for m in manifest:
        path = repo / "results/vtm_content_partition_study/stimuli" / f"{m['stimulus']}.png"
        require_equal(sha(path), m["sha256"], f"PNG {m['stimulus']}")
        require_equal(m["stimulus"].split("__")[0].rsplit("_", 1)[1],
                      source_hashes[m["source"]][:12], "source hash prefix")
        image = read_png(path)
        require_equal(image.shape[:2], (int(m["height"]), int(m["width"])), "PNG dimensions")
        source = source_pixels[m["source"]]
        if m["distortion"] == "awgn":
            seed = derive_image_seed(int(m["seed"]), source_indices[m["source"]])
            require_equal(str(seed), m["derived_seed"], "derived AWGN seed")
            recreated = add_achromatic_awgn(source, float(m["level"]), seed)
        elif m["distortion"] == "stripes":
            recreated = add_sinusoidal_interference(source, float(m["level"]))
        else:
            recreated = source
        require_equal(np.array_equal(image, recreated), True, "recreated stimulus pixels")
        require_equal(complexity_metrics(image)["sobel_si"], float(m["stimulus_sobel_si"]), "Sobel")
        yuv = cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), cv2.COLOR_RGB2YUV)
        conversion_hashes[m["stimulus"]] = hashlib.sha256(yuv.transpose(2, 0, 1).tobytes()).hexdigest()
        m["path"] = path.relative_to(repo).as_posix()

    for index, row in enumerate(rows, 1):
        m = by_stimulus[row["stimulus"]]
        require_equal(row["image_sha256"], m["sha256"], "summary/manifest PNG")
        require_equal(row["yuv_sha256"], conversion_hashes[row["stimulus"]], "PNG conversion/input hash")
        require_equal(row["encoder_sha256"], encoder_hash, "encoder binary")
        require_equal(row["config_sha256"], config_hash, "encoder configuration")
        run = repo / row["artifact_run"]
        paths = output_paths(run, row)
        for name, path in paths.items():
            actual_hash = sha(path)
            if f"{name}_sha256" in row:
                require_equal(actual_hash, row[f"{name}_sha256"], name)
        require_equal(sha(paths["decoded"]), sha(paths["reconstruction"]), "decoded/reconstruction")
        log = paths["encoder_log"].read_text(encoding="utf-8")
        require_equal("VTM Encoder Version 23.0" in log and "ScalingList:0" in log
                      and "I-SLICE" in log and "D_QP:poc==0" in log, True, "encoder log")
        yuv = run / "yuv" / f"{m['stimulus']}_{m['sha256'][:12]}_{m['width']}x{m['height']}.yuv"
        require_equal(sha(yuv), row["yuv_sha256"], "stored YUV")
        parsed = parse_trace(paths["trace"], frame=0, mode="baseline")
        saved = read_rows(paths["partition_csv"])
        require_equal([{k: str(v) for k, v in r.items()} for r in parsed], saved, "trace/partition CSV")
        stats = summarize_partitions(parsed, int(m["width"]), int(m["height"]))
        for field in ("cu_count", "coded_area", "padding_area", "cu_density_per_mpixel", "mean_area"):
            require_equal(float(row[field]), float(stats[field]), field)
        require_equal(int(row["padding_area"]), 0, "no Kodak padding")
        row["path"] = m["path"]
        row["cu_coverage_verified"] = "True"
        if index % 96 == 0:
            print(f"Audited {index}/{len(rows)} baseline jobs", flush=True)

    # Compare every row of all published measurement tables to the audited originals.
    by_condition = {(r["source"], r["distortion"], float(r["level"]), r["seed"], int(r["qp"])): r
                    for r in rows}
    table_counts = {}
    for filename in ("clean_cu_measurements.csv", "interference_cu_measurements.csv",
                     "awgn_realization_cu_measurements.csv"):
        path = repo / "docs/vtm_content_partition_study/tables" / filename
        sha(path)
        published = read_rows(path)
        table_counts[filename] = len(published)
        for p in published:
            distortion = p.get("distortion", "awgn" if "sigma" in p else "clean")
            level = float(p.get("level", p.get("sigma", 0)))
            original = by_condition[(p["source"], distortion, level, p.get("seed", ""), int(p["qp"]))]
            for field, value in p.items():
                if field in original:
                    require_equal(value, original[field], f"published {filename}/{field}")
    variability = repo / "docs/vtm_content_partition_study/tables/awgn_realization_variability.csv"
    sha(variability)
    for p in read_rows(variability):
        values = [int(by_condition[(p["source"], "awgn", float(p["sigma"]), str(s), 32)]["cu_count"])
                  for s in protocol.awgn_seeds]
        require_equal(int(p["cu_count_range"]), max(values) - min(values), "realization range")
        require_equal(float(p["relative_cu_count_range_percent"]),
                      100 * (max(values) - min(values)) / (sum(values) / 3), "relative realization range")
    write_rows(output / "baseline_measurements.csv", rows)
    write_rows(output / "stimulus_manifest.csv", manifest)
    write_rows(output / "file_inventory.csv", inventory)
    report = {
        "source_run_rows": input_counts, "excluded_other_mode_rows": excluded,
        "identical_duplicate_baseline_rows": duplicates, "unique_baseline_jobs": len(rows),
        "verified_stimuli": len(manifest), "verified_sources": len(source_paths),
        "hashed_files": len(inventory), "published_table_rows": table_counts,
        "png_pixels_reproduced": True, "png_to_yuv_hashes_verified": True,
        "all_baseline_artifact_hashes_verified": True, "traces_match_partition_csvs": True,
        "all_cu_coverage_verified": True, "all_decoded_reconstructions_identical": True,
        "encoder_sha256": encoder_hash, "encoder_config_sha256": config_hash,
        "limitations": ["Historical protocol files referenced in snapshots are absent from the current tree.",
                        "Historical snapshots do not bind encoder source commit or decoder binary hash.",
                        "Current baseline VTM source checkout is absent; source-to-binary correspondence is not rebuilt.",
                        "The consolidated runner layout is not the historical on-disk layout."],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.repo, args.output)
    print(f"Verified {report['unique_baseline_jobs']} baseline measurements, "
          f"{report['verified_stimuli']} stimuli and {report['hashed_files']} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
