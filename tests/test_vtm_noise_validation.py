from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from tools.research import run_vtm_noise_validation as validation
from tools.research.run_vtm_content_partition_study import output_paths, read_rows, write_rows
from vvenc_csf.partitions import summarize_partitions
from vvenc_csf.stimuli import derive_image_seed, file_sha256, read_png, write_png


def test_fixed_selection_and_pilot_cover_every_qp_and_noise_seed():
    selection = validation.selected_sources()
    assert len(selection) == len(set(selection)) == 48
    assert selection[:2] == ("0882.png", "0832.png")
    assert set(selection).issubset(validation.SOURCE_NAMES)
    manifest = []
    for source in selection:
        for distortion, seed in [("clean", ""), *(("awgn", str(seed)) for seed in validation.AWGN_SEEDS)]:
            manifest.append({"source": source, "stimulus": f"{source}_{distortion}_{seed}",
                             "distortion": distortion, "seed": seed})
    candidate = validation.validation_plan(manifest)
    pilot = validation.validation_plan(manifest, set(selection[:2]))
    assert len(candidate) == 768
    assert len(pilot) == 32
    by_stimulus = {row["stimulus"]: row for row in manifest}
    assert {(by_stimulus[job.stimulus]["source"], by_stimulus[job.stimulus]["seed"], job.qp)
            for job in pilot} == {(source, seed, qp) for source in selection[:2]
                                  for seed in ("", *map(str, validation.AWGN_SEEDS)) for qp in validation.QPS}
    assert {job.key for job in pilot}.issubset({job.key for job in candidate})
    assert validation.default_settings().workers == 4
    assert validation.default_settings(workers=20).workers == 20
    assert str(validation.default_settings().protocol.source_dir).replace("\\", "/").startswith("results/")


def tiny_study(tmp_path, monkeypatch):
    monkeypatch.setattr(validation, "SOURCE_NAMES", ("0801.png", "0802.png", "0803.png", "0804.png"))
    monkeypatch.setattr(validation, "SOURCE_COUNT", 3)
    monkeypatch.setattr(validation, "CROP_WIDTH", 4)
    monkeypatch.setattr(validation, "CROP_HEIGHT", 3)
    sources = tmp_path / "originals"
    sources.mkdir()
    for index, name in enumerate(validation.SOURCE_NAMES):
        image = np.arange(8 * 6 * 3, dtype=np.uint8).reshape(6, 8, 3) + index * 20
        write_png(sources / name, image)
    binaries = {}
    for name in validation.EXPECTED_HASHES:
        path = tmp_path / f"{name}.stub"
        path.write_bytes(name.encode())
        binaries[name] = path
    monkeypatch.setattr(validation, "EXPECTED_HASHES", {name: file_sha256(path) for name, path in binaries.items()})
    settings = replace(validation.default_settings(sources, workers=1), results=tmp_path / "results", **binaries)
    study = validation.NoiseValidationPilot(settings)
    monkeypatch.setattr(study.encoder, "encode", lambda *args, **kwargs: pytest.fail("No actual encoder may run"))
    return study


def test_prepare_crops_without_resizing_and_keeps_full_selection_noise_indices(tmp_path, monkeypatch):
    study = tiny_study(tmp_path, monkeypatch)
    monkeypatch.setattr(study, "prepare_yuv", lambda *args: pytest.fail("prepare cannot convert inputs"))
    study.prepare()
    manifest, pilot, _ = study._load_frozen_inputs()
    assert len(manifest) == 12
    assert len(pilot) == 32
    assert len(read_rows(study.candidate_plan_path)) == 48
    protocol = {row["setting"]: row["value"] for row in read_rows(study.analysis_protocol_path)}
    assert protocol["simultaneous_family"] == "24 B plus 20 C at sigma 30 across all four QPs"
    assert protocol["B_bounds"] == "-2;2" and protocol["C_bounds"] == "-4;4"
    sorted_sources = sorted(validation.selected_sources())
    for row in read_rows(study.inventory_path):
        if not row["selection_rank"]:
            continue
        original = read_png(Path(row["original_path"]))
        crop = read_png(Path(row["crop_path"]))
        np.testing.assert_array_equal(crop, original[1:4, 2:6])
        assert int(row["source_index"]) == sorted_sources.index(row["source"])
    for row in manifest:
        if row["seed"]:
            assert int(row["derived_seed"]) == derive_image_seed(int(row["seed"]), sorted_sources.index(row["source"]))
    saved = {path.name: path.read_bytes() for path in (study.manifest_path, study.plan_path, study.checks_path)}
    study.prepare()
    assert saved == {path.name: path.read_bytes() for path in (study.manifest_path, study.plan_path, study.checks_path)}
    assert not (study.results / "encoded").exists()
    assert not (study.results / "yuv").exists()
    assert not list(study.results.rglob("*.json"))


@pytest.mark.parametrize("damage", ["missing", "undersized", "duplicate", "grayscale"])
def test_preflight_rejects_invalid_original_pool_without_replacements(tmp_path, monkeypatch, damage):
    study = tiny_study(tmp_path, monkeypatch)
    source_dir = study.protocol.source_dir
    last = source_dir / validation.SOURCE_NAMES[-1]
    if damage == "missing":
        last.unlink()
    elif damage == "undersized":
        write_png(last, np.zeros((2, 2, 3), dtype=np.uint8))
    elif damage == "grayscale":
        write_png(last, np.zeros((6, 8), dtype=np.uint8))
    else:
        last.write_bytes((source_dir / validation.SOURCE_NAMES[0]).read_bytes())
    with pytest.raises(ValueError):
        study.prepare()
    assert not study.manifest_path.exists()


@pytest.mark.parametrize("damage", ["original", "crop", "stimulus", "plan", "analysis_protocol", "encoder", "check_missing"])
def test_resume_rejects_changed_frozen_inputs(tmp_path, monkeypatch, damage):
    study = tiny_study(tmp_path, monkeypatch)
    study.prepare()
    if damage == "original":
        path = study.protocol.source_dir / validation.SOURCE_NAMES[0]
    elif damage == "crop":
        path = study.crop_dir / validation.selected_sources()[0]
    elif damage == "stimulus":
        path = Path(read_rows(study.manifest_path)[0]["path"])
    elif damage == "plan":
        path = study.plan_path
    elif damage == "analysis_protocol":
        path = study.analysis_protocol_path
    elif damage == "encoder":
        path = study.settings.encoder
    else:
        rows = [row for row in read_rows(study.checks_path) if not row["name"].startswith("original:")]
        write_rows(study.checks_path, rows)
        path = None
    if path is not None:
        path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises((RuntimeError, ValueError), match="changed"):
        study.prepare()


def completed_study(tmp_path, monkeypatch):
    study = tiny_study(tmp_path, monkeypatch)
    study.prepare()
    manifest, plan, snapshot = study._load_frozen_inputs()
    by_stimulus = {row["stimulus"]: row for row in manifest}
    rows = []
    for job in plan:
        stimulus = by_stimulus[job.stimulus]
        yuv = study._yuv_path(stimulus)
        yuv.parent.mkdir(parents=True, exist_ok=True)
        yuv.write_bytes(b"yuv" * 12)
        outputs = output_paths(study.results, job)
        for path in outputs.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test artifact")
        partitions = [{"x": 0, "y": 0, "width": 4, "height": 3}]
        write_rows(outputs["partition_csv"], partitions)
        rows.append({**stimulus, **snapshot, "qp": job.qp, "mode": "baseline",
                     "image_sha256": stimulus["sha256"], "yuv_sha256": file_sha256(yuv),
                     "conversion": "opencv_444", "trace_rule": "D_QP:poc==0",
                     "reconstruction_verified": True, "cu_coverage_verified": True,
                     **summarize_partitions(partitions, 4, 3),
                     **{f"{name}_sha256": file_sha256(path) for name, path in outputs.items()}})
    write_rows(study.summary_path, rows)
    return study


def test_completed_pilot_resumes_without_dispatch_and_records_actual_invocation_time(tmp_path, monkeypatch, capsys):
    study = completed_study(tmp_path, monkeypatch)
    summary = study.summary_path.read_bytes()
    monkeypatch.setattr(study, "run_job", lambda *args: pytest.fail("Completed pilot must not encode again"))
    monkeypatch.setattr(study, "prepare_yuv", lambda *args: pytest.fail("Completed pilot must not convert again"))
    study.run()
    study.validate()
    study.status()
    assert study.summary_path.read_bytes() == summary
    timing = read_rows(study.timing_path)[0]
    assert timing["recorded_before"] == timing["recorded_after"] == "32"
    assert float(timing["wall_seconds"]) >= 0
    assert timing["run_completed"] == "True"
    assert "Recorded 32/32" in capsys.readouterr().out
    assert not list(study.results.rglob("*.json"))


def test_shared_queue_dispatches_only_the_pilot(tmp_path, monkeypatch):
    study = tiny_study(tmp_path, monkeypatch)
    study.prepare()
    _, pilot, _ = study._load_frozen_inputs()
    calls = []
    monkeypatch.setattr(study, "prepare_yuv", lambda *args: None)
    def fake_job(job, *args):
        calls.append(job.key)
        return {"stimulus": job.stimulus, "qp": job.qp, "mode": job.mode}
    monkeypatch.setattr(study, "run_job", fake_job)
    study.run()
    assert set(calls) == {job.key for job in pilot}
    assert len(calls) == 32 < len(read_rows(study.candidate_plan_path))


@pytest.mark.parametrize("damage", ["artifact", "coverage", "count", "duplicate", "outside_pilot"])
def test_validation_rejects_corrupt_or_unexpected_results(tmp_path, monkeypatch, damage):
    study = completed_study(tmp_path, monkeypatch)
    rows = read_rows(study.summary_path)
    row = rows[0]
    if damage == "artifact":
        output_paths(study.results, row)["bitstream"].write_bytes(b"broken")
    elif damage == "coverage":
        path = output_paths(study.results, row)["partition_csv"]
        write_rows(path, [{"x": 0, "y": 0, "width": 3, "height": 3}])
        row["partition_csv_sha256"] = file_sha256(path)
    elif damage == "count":
        row["cu_count"] = "2"
    elif damage == "duplicate":
        rows.append(dict(row))
    else:
        row["stimulus"] = "not_in_the_pilot"
    write_rows(study.summary_path, rows)
    with pytest.raises(RuntimeError):
        study.validate()


def test_failed_pilot_records_partial_wall_time_without_fake_completion(tmp_path, monkeypatch):
    study = tiny_study(tmp_path, monkeypatch)
    study.prepare()
    def interrupted(*args):
        raise KeyboardInterrupt()
    monkeypatch.setattr(validation.VTMContentPartitionStudy, "run", interrupted)
    with pytest.raises(KeyboardInterrupt):
        study.run()
    row = read_rows(study.timing_path)[0]
    assert row["run_completed"] == "False"
    assert row["recorded_after"] == "0"
    assert float(row["wall_seconds"]) >= 0
