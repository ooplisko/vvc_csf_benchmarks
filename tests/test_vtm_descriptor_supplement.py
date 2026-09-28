from __future__ import annotations

import shutil

import numpy as np
import pytest

from tools.benchmarking import benchmark_vtm_descriptors as timing
from tools.research import summarize_vtm_spatial_complexity as summary
from tools.reporting import vtm_descriptor_supplement_report as report
from vvenc_csf.spatial_complexity import FEATURES, spatial_complexity_metrics


@pytest.mark.parametrize("kind", ["flat", "random", "bands"])
def test_timed_operations_match_existing_descriptors(kind):
    image = np.full((17, 23, 3), 128, dtype=np.uint8)
    if kind == "random":
        image = np.random.default_rng(42).integers(0, 256, image.shape, dtype=np.uint8)
    elif kind == "bands":
        image[::2] = 255
    values = spatial_complexity_metrics(image)
    calls = timing.verify_operations(image, {"stimulus": kind, **values})
    assert calls["glcm_shared"]() == pytest.approx({f: values[f] for f in FEATURES[3:]})
    assert len(calls) == 10
    values["sobel_si"] += 1
    with pytest.raises(ValueError, match="saved value"):
        timing.verify_operations(image, {"stimulus": kind, **values})


LOG = """VVCSoftware: VTM Encoder Version 23.0
POC 0 LId: 0 TId: 0 ( IDR_N_LP, I-SLICE, QP 32 ) 1000 bits [Y 35.0000 dB U 42.0000 dB V 43.0000 dB]
Total Frames | Bitrate Y-PSNR U-PSNR V-PSNR YUV-PSNR
1 a 1.0000 35.0000 42.0000 43.0000 39.0000
"""


def test_quality_parser_preserves_components_and_rejects_wrong_frame_or_summary():
    assert summary.parse_quality_log(LOG, 32) == {
        "coded_picture_bits": 1000, "psnr_y_db": 35, "psnr_u_db": 42,
        "psnr_v_db": 43, "psnr_yuv_db": 39}
    with pytest.raises(ValueError, match="QP"):
        summary.parse_quality_log(LOG, 27)
    for damaged in (LOG + LOG, LOG.replace("1 a 1.0000 35.0000", "1 a 1.0000 34.0000"),
                    LOG.replace("VTM Encoder Version 23.0", "VTM Encoder Version 18.0"),
                    LOG.replace("1 a 1.0000", "2 a 1.0000")):
        with pytest.raises(ValueError):
            summary.parse_quality_log(damaged, 32)


def test_timing_summary_uses_image_medians_not_pooled_repetitions():
    rows = []
    for source, values in (("a", [1, 2, 100]), ("b", [10, 20, 30])):
        for i, value in enumerate(values):
            rows.append({"source": source, "stimulus": source, "distortion": "clean", "level": 0,
                         "seed": "", "operation": "sobel_si", "repeat": i, "elapsed_ms": value})
    images, groups = timing.summarize_timings(rows)
    assert images.median_ms.tolist() == [2, 20]
    assert groups.iloc[0].median_ms == 11
    assert groups.iloc[0].n_images == 2


def test_paired_descriptor_changes_distinguish_offset_from_rank_reversal():
    rows = []
    for qp in (22, 27, 32, 37):
        for source in range(1, 25):
            for distortion, level in summary.CONDITIONS:
                value = source if distortion == "clean" else (source + 100 if distortion == "awgn" else 25-source)
                rows.append({"qp": qp, "source": str(source), "distortion": distortion, "level": level,
                             **{feature: value for feature in FEATURES}})
    changes = summary.descriptor_changes(rows)
    assert len(changes) == 36
    for row in changes:
        assert row["n_images"] == 24
        if row["distortion"] == "awgn":
            assert row["median_paired_change"] == 100
            assert row["clean_disturbed_rank_rho"] == pytest.approx(1)
        else:
            assert row["median_paired_change"] == 0
            assert row["median_absolute_paired_change"] == 12
            assert row["clean_disturbed_rank_rho"] == pytest.approx(-1)


def test_benchmark_resumes_complete_images_without_retiming(tmp_path, monkeypatch):
    image = np.full((5, 6, 3), 128, dtype=np.uint8)
    input_path = tmp_path / "input.png"
    input_path.write_bytes(b"hash fixture")
    measurements = tmp_path / "measurements.csv"
    measurements.write_text("fixture")
    row = {"source": "a", "stimulus": "a", "distortion": "clean", "level": "0", "seed": "", "qp": 32,
           "path": str(input_path), "image_sha256": timing.file_sha256(input_path),
           **spatial_complexity_metrics(image)}
    monkeypatch.setattr(timing, "primary_measurements", lambda path: [row])
    monkeypatch.setattr(timing, "read_png", lambda path: image)
    timing.benchmark(measurements, tmp_path / "out", repeats=3, warmup=1)
    raw = (tmp_path / "out/descriptor_timing_raw.csv").read_bytes()
    monkeypatch.setattr(timing, "perf_counter_ns", lambda: pytest.fail("Completed inputs must not be timed again"))
    timing.benchmark(measurements, tmp_path / "out", repeats=3, warmup=1)
    assert (tmp_path / "out/descriptor_timing_raw.csv").read_bytes() == raw
    with pytest.raises(ValueError, match="settings or inputs"):
        timing.benchmark(measurements, tmp_path / "out", repeats=5, warmup=1)


def test_quality_summary_does_not_pool_qps_or_disturbance_conditions():
    rows = []
    for qp, level in ((22, 0), (37, 30)):
        for source in range(24):
            rows.append({"source": str(source), "distortion": "clean" if level == 0 else "awgn",
                         "level": level, "qp": qp, "psnr_y_db": qp+source,
                         "psnr_u_db": qp+source+1, "psnr_v_db": qp+source+2,
                         "file_bpp": 1, "encode_seconds": 20})
    groups = {row["qp"]: row for row in summary.summarize_quality(rows)}
    assert groups[22]["psnr_y_db_median"] == 33.5
    assert groups[37]["psnr_y_db_median"] == 48.5
    with pytest.raises(ValueError, match="24 different"):
        summary.summarize_quality(rows[:-1])


def test_optional_supplement_rejects_partial_exports(tmp_path):
    assert report.load_supplement(tmp_path / "absent") == {}
    with pytest.raises(ValueError, match="Incomplete descriptor supplement"):
        report.load_supplement(tmp_path)


def test_published_supplement_and_readme_only_preserve_figures(tmp_path, monkeypatch):
    from tools.reporting import report_vtm_spatial_complexity as main_report

    published = summary.DEFAULT_TABLES / "supplement"
    tables = report.load_supplement(published)
    assert len(tables["supplement/quality_measurements"]) == 672
    assert len(tables["supplement/descriptor_timing_images"]) == 1680
    monkeypatch.setattr(main_report, "plot_validation", lambda *args: pytest.fail("Figures must be reused"))
    output = tmp_path / "report"
    (output / "figures").mkdir(parents=True)
    figure = output / "figures/unchanged.pdf"
    figure.write_bytes(b"existing figure")
    main_report.build(summary.DEFAULT_TABLES, output, readme_only=True)
    assert figure.read_bytes() == b"existing figure"
    assert list((output / "figures").iterdir()) == [figure]
    text = (output / "README.md").read_text(encoding="utf-8")
    assert "## Computation Time" in text and "## Reconstruction Quality" in text
    assert "do not measure an encoder speedup" in text
    assert "actual encoder input" in text and "not rankings by CU count" in text
    for name in report.TABLES:
        assert (output / "tables/supplement" / f"{name}.csv").read_bytes() == (published / f"{name}.csv").read_bytes()
    copied = tmp_path / "invalid"
    shutil.copytree(published, copied)
    path = copied / "descriptor_timing_summary.csv"
    frame = timing.pd.read_csv(path)
    frame.loc[0, "median_ms"] += 1
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="differs from per-image"):
        report.load_supplement(copied)
