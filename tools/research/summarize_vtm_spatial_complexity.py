"""Summarize saved primary Kodak quality logs and descriptor changes without encoding."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.research.analyze_vtm_spatial_complexity import DEFAULT_TABLES, validate_measurements
from tools.research.run_vtm_content_partition_study import ROOT, output_paths, read_rows, write_rows
from vvenc_csf.spatial_complexity import FEATURES
from vvenc_csf.stimuli import file_sha256


CONDITIONS = (("clean", 0), ("awgn", 5), ("awgn", 15), ("awgn", 30),
              ("stripes", 8), ("stripes", 16), ("stripes", 32))
IDENTITY = ("source", "stimulus", "distortion", "level", "seed")
DEFAULT_OUTPUT = ROOT / "results/vtm_spatial_complexity_supplement"
FRAME = re.compile(r"POC\s+0\s+LId:\s*0\s+TId:\s*0\s*\([^)]*I-SLICE,\s*QP\s+(\d+)\s*\)"
                   r"\s+(\d+) bits\s+\[Y\s+([\d.]+) dB\s+U\s+([\d.]+) dB\s+V\s+([\d.]+) dB\]")
SUMMARY = re.compile(r"Total Frames\s*\|\s*Bitrate\s+Y-PSNR\s+U-PSNR\s+V-PSNR\s+YUV-PSNR"
                     r"\s+1\s+a\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)")


def primary_measurements(path: Path) -> list[dict]:
    rows = read_rows(path)
    validate_measurements(rows)
    return [row for row in rows if row["distortion"] != "awgn" or row["seed"] == "20260811"]


def parse_quality_log(text: str, qp: int) -> dict:
    frames, summaries = FRAME.findall(text), SUMMARY.findall(text)
    if ("VTM Encoder Version 23.0" not in text or len(frames) != 1 or len(summaries) != 1
            or len(re.findall(r"^POC\s+", text, re.MULTILINE)) != 1):
        raise ValueError("Expected one VTM 23.0 intra frame and one quality summary")
    frame, summary = frames[0], summaries[0]
    if int(frame[0]) != qp:
        raise ValueError("Logged QP differs from the saved measurement")
    psnr = np.asarray(frame[2:], dtype=float)
    if not np.isfinite(psnr).all() or not np.allclose(psnr, np.asarray(summary[1:4], dtype=float), atol=5e-5, rtol=0):
        raise ValueError("Frame and summary PSNR disagree")
    return {"coded_picture_bits": int(frame[1]), **dict(zip(
        ("psnr_y_db", "psnr_u_db", "psnr_v_db"), psnr, strict=True)),
        "psnr_yuv_db": float(summary[4])}


def quality_measurements(rows: list[dict], root: Path = ROOT) -> list[dict]:
    result = []
    for row in rows:
        paths = output_paths(root / row["artifact_run"], row)
        log_hash = file_sha256(paths["encoder_log"])
        recorded_hash = row.get("encoder_log_sha256", "")
        if recorded_hash and recorded_hash != log_hash:
            raise ValueError(f"Changed encoder log: {paths['encoder_log']}")
        if (paths["bitstream"].stat().st_size != int(row["bitstream_bytes"])
                or file_sha256(paths["bitstream"]) != row["bitstream_sha256"]):
            raise ValueError(f"Changed bitstream: {paths['bitstream']}")
        text = paths["encoder_log"].read_text(encoding="utf-8-sig")
        # Legacy measurements have no recorded log hash; check the original invocation too.
        if row["stimulus"] not in text.splitlines()[0] or "--InputChromaFormat=444" not in text.splitlines()[0]:
            raise ValueError("Encoder invocation does not identify the expected 4:4:4 stimulus")
        result.append({**{key: row[key] for key in IDENTITY}, "qp": int(row["qp"]),
                       **parse_quality_log(text, int(row["qp"])),
                       "bitstream_bytes": int(row["bitstream_bytes"]),
                       "file_bpp": 8 * int(row["bitstream_bytes"]) / int(row["coded_area"]),
                       "encode_seconds": float(row["encode_seconds"]),
                       "reference": "actual_encoder_input", "chroma_format": "444",
                       "encoder_log": paths["encoder_log"].relative_to(root).as_posix(),
                       "encoder_log_sha256": log_hash, "log_hash_previously_recorded": bool(recorded_hash)})
    return result


def summarize_quality(rows: list[dict]) -> list[dict]:
    table = pd.DataFrame(rows)
    result = []
    for (distortion, level, qp), group in table.groupby(["distortion", "level", "qp"], sort=True):
        if len(group) != 24 or group.source.nunique() != 24:
            raise ValueError("Expected 24 different images per quality condition/QP")
        values = {"distortion": distortion, "level": int(level), "qp": int(qp), "n_images": 24}
        for metric in ("psnr_y_db", "psnr_u_db", "psnr_v_db", "file_bpp", "encode_seconds"):
            for name, quantile in (("min", 0), ("q25", .25), ("median", .5), ("q75", .75), ("max", 1)):
                values[f"{metric}_{name}"] = float(group[metric].quantile(quantile))
        result.append(values)
    return result


def descriptor_changes(rows: list[dict]) -> list[dict]:
    # Input descriptors do not depend on QP. Retain each stimulus once, not four times.
    table = pd.DataFrame([row for row in rows if int(row["qp"]) == 32])
    clean = table[table.distortion.eq("clean")].set_index("source").sort_index()
    result = []
    for distortion, level in CONDITIONS[1:]:
        noisy = table[table.distortion.eq(distortion) & table.level.astype(int).eq(level)].set_index("source").sort_index()
        if len(noisy) != 24 or not noisy.index.equals(clean.index):
            raise ValueError("Expected matching 24 clean and disturbed source images")
        for feature in FEATURES:
            a, b = clean[feature].to_numpy(dtype=float), noisy[feature].to_numpy(dtype=float)
            result.append({"distortion": distortion, "level": level,
                           "seed": "20260811" if distortion == "awgn" else "", "feature": feature,
                           "n_images": 24, "clean_median": float(np.median(a)),
                           "disturbed_median": float(np.median(b)), "median_paired_change": float(np.median(b-a)),
                           "median_absolute_paired_change": float(np.median(np.abs(b-a))),
                           "clean_iqr": float(np.quantile(a, .75)-np.quantile(a, .25)),
                           "disturbed_iqr": float(np.quantile(b, .75)-np.quantile(b, .25)),
                           "clean_disturbed_rank_rho": float(spearmanr(a, b).statistic)})
    return result


def build(measurements: Path, output: Path) -> None:
    rows = primary_measurements(measurements)
    quality = quality_measurements(rows)
    write_rows(output / "quality_measurements.csv", quality)
    write_rows(output / "quality_summary.csv", summarize_quality(quality))
    write_rows(output / "descriptor_changes.csv", descriptor_changes(rows))
    write_rows(output / "summary_inputs.csv", [
        {"path": str(path.resolve()), "sha256": file_sha256(path)}
        for path in (measurements, Path(__file__))])
    print(f"Saved quality for {len(quality)} primary encodings and 36 descriptor-change summaries in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurements", type=Path, default=DEFAULT_TABLES / "joined_measurements.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.measurements, args.output)
