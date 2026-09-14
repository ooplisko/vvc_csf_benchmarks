from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from tools.research import complete_vtm_noise_validation as completion
from tools.research import run_vtm_noise_validation as pilot_module
from tools.research.run_vtm_content_partition_study import job_key, output_paths, read_rows, write_rows
from vvenc_csf.partitions import summarize_partitions
from vvenc_csf.stimuli import file_sha256, write_png


def artifact_row(study, job, stimulus, snapshot):
    """Create structurally valid tiny outputs without launching either codec."""
    yuv = study._yuv_path(stimulus)
    yuv.parent.mkdir(parents=True, exist_ok=True)
    yuv.write_bytes(b"yuv" * 12)
    outputs = output_paths(study.results, job)
    for path in outputs.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test artifact")
    partitions = [{"x": 0, "y": 0, "width": 4, "height": 3}]
    write_rows(outputs["partition_csv"], partitions)
    return {**stimulus, **snapshot, "qp": job.qp, "mode": "baseline",
            "image_sha256": stimulus["sha256"], "yuv_sha256": file_sha256(yuv),
            "conversion": "opencv_444", "trace_rule": "D_QP:poc==0", "encode_seconds": 1.0,
            "reconstruction_verified": True, "cu_coverage_verified": True,
            **summarize_partitions(partitions, 4, 3),
            **{f"{name}_sha256": file_sha256(path) for name, path in outputs.items()}}


def prepared_completion(tmp_path, monkeypatch, full_matrix=False):
    if not full_matrix:
        monkeypatch.setattr(pilot_module, "SOURCE_NAMES", ("0801.png", "0802.png", "0803.png", "0804.png"))
        monkeypatch.setattr(pilot_module, "SOURCE_COUNT", 3)
    monkeypatch.setattr(pilot_module, "CROP_WIDTH", 4)
    monkeypatch.setattr(pilot_module, "CROP_HEIGHT", 3)
    sources = tmp_path / "originals"
    for index, name in enumerate(pilot_module.SOURCE_NAMES):
        write_png(sources / name, (np.arange(6 * 8 * 3).reshape(6, 8, 3) + index).astype(np.uint8))
    binaries = {}
    for name in pilot_module.EXPECTED_HASHES:
        path = tmp_path / f"{name}.stub"
        path.write_bytes(name.encode())
        binaries[name] = path
    monkeypatch.setattr(pilot_module, "EXPECTED_HASHES", {name: file_sha256(path) for name, path in binaries.items()})
    settings = replace(pilot_module.default_settings(sources, workers=1), results=tmp_path / "results", **binaries)
    pilot = pilot_module.NoiseValidationPilot(settings)
    monkeypatch.setattr(pilot.encoder, "encode", lambda *args, **kwargs: pytest.fail("No real encoder"))
    pilot.prepare()
    manifest, plan, snapshot = pilot._load_frozen_inputs()
    by_stimulus = {row["stimulus"]: row for row in manifest}
    write_rows(pilot.summary_path, [artifact_row(pilot, job, by_stimulus[job.stimulus], snapshot) for job in plan])
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text("frozen test wrapper", encoding="utf-8")
    study = completion.NoiseValidationCompletion(replace(settings, protocol_path=wrapper))
    monkeypatch.setattr(study.encoder, "encode", lambda *args, **kwargs: pytest.fail("No real encoder"))
    study.prepare()
    return study


def add_completed(study, count):
    manifest, plan, snapshot = study._load_frozen_inputs()
    by_stimulus = {row["stimulus"]: row for row in manifest}
    rows = read_rows(study.summary_path)
    known = {job_key(row) for row in rows}
    added = [job for job in plan if job.key not in known][:count]
    rows.extend(artifact_row(study, job, by_stimulus[job.stimulus], snapshot) for job in added)
    write_rows(study.summary_path, sorted(rows, key=job_key))
    return added


def test_preparation_reuses_pilot_and_freezes_separate_full_records(tmp_path, monkeypatch):
    study = prepared_completion(tmp_path, monkeypatch)
    pilot_bytes = study.pilot.summary_path.read_bytes()
    checks_bytes = study.pilot.checks_path.read_bytes()
    assert read_rows(study.summary_path) == read_rows(study.pilot.summary_path)
    frozen = {row["name"]: row["sha256"] for row in read_rows(study.checks_path)}
    assert frozen["pilot_summary"] == file_sha256(study.pilot.summary_path)
    assert frozen["candidate_plan"] == file_sha256(study.pilot.candidate_plan_path)
    assert study.summary_path != study.pilot.summary_path
    study.prepare()
    study.status()
    assert study.pilot.summary_path.read_bytes() == pilot_bytes
    assert study.pilot.checks_path.read_bytes() == checks_bytes
    assert not list(study.results.rglob("*.json"))
    assert completion.default_settings().workers == 20


def test_full_matrix_dispatches_736_jobs_and_preserves_all_32_pilot_rows(tmp_path, monkeypatch):
    study = prepared_completion(tmp_path, monkeypatch, full_matrix=True)
    manifest, plan, snapshot = study._load_frozen_inputs()
    assert len(manifest) == 192 and len(plan) == 768
    pilot_bytes = study.pilot.summary_path.read_bytes()
    pilot_rows = dict(study.pilot_rows)
    calls = []
    monkeypatch.setattr(study, "prepare_yuv", lambda *args: None)
    def fake_job(job, stimulus, supplied_snapshot):
        calls.append(job.key)
        assert supplied_snapshot == snapshot
        return {**stimulus, **snapshot, "qp": job.qp, "mode": job.mode}
    monkeypatch.setattr(study, "run_job", fake_job)
    study.run()
    assert len(calls) == 736
    assert set(calls) == {job.key for job in plan} - set(pilot_rows)
    rows = read_rows(study.summary_path)
    assert len(rows) == 768
    assert {job_key(row): row for row in rows if job_key(row) in pilot_rows} == pilot_rows
    assert study.pilot.summary_path.read_bytes() == pilot_bytes
    assert snapshot["protocol_sha256"] != study.pilot_snapshot["protocol_sha256"]
    assert snapshot["job_plan_sha256"] != study.pilot_snapshot["job_plan_sha256"]
    timing = read_rows(study.timing_path)[0]
    assert timing["recorded_before"] == "32" and timing["recorded_after"] == "768"
    assert float(timing["wall_seconds"]) >= 0


def test_resumption_skips_new_completed_jobs_as_well_as_pilot(tmp_path, monkeypatch):
    study = prepared_completion(tmp_path, monkeypatch)
    added = add_completed(study, 2)
    original_rows = {job_key(row): row for row in read_rows(study.summary_path)}
    calls = []
    monkeypatch.setattr(study, "prepare_yuv", lambda *args: None)
    def fake_job(job, stimulus, snapshot):
        calls.append(job.key)
        return artifact_row(study, job, stimulus, snapshot)
    monkeypatch.setattr(study, "run_job", fake_job)
    study.run()
    assert len(calls) == 14
    assert not set(calls).intersection(original_rows)
    assert not {job.key for job in added}.intersection(calls)
    saved = {job_key(row): row for row in read_rows(study.summary_path)}
    assert all(saved[key] == row for key, row in original_rows.items())
    study.validate()
    monkeypatch.setattr(study, "run_job", lambda *args: pytest.fail("All jobs are already valid"))
    study.run()
    assert read_rows(study.timing_path)[-1]["recorded_before"] == "48"


@pytest.mark.parametrize("damage", ["original", "stimulus", "pilot_input_checks", "pilot_summary", "wrapper", "candidate_plan", "missing_check"])
def test_changed_frozen_inputs_are_rejected(tmp_path, monkeypatch, damage):
    study = prepared_completion(tmp_path, monkeypatch)
    if damage == "original":
        path = study.protocol.source_dir / pilot_module.SOURCE_NAMES[0]
    elif damage == "stimulus":
        path = Path(read_rows(study.manifest_path)[0]["path"])
    elif damage == "wrapper":
        path = study.settings.protocol_path
    elif damage == "missing_check":
        write_rows(study.checks_path, read_rows(study.checks_path)[1:])
        path = None
    else:
        path = study._input_paths()[damage]
    if path is not None:
        path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(RuntimeError, match="changed"):
        study.prepare()


@pytest.mark.parametrize("damage", ["pilot_row", "missing_pilot", "duplicate", "outside_plan", "old_provenance", "wrong_plan"])
def test_registry_rejects_wrong_mixed_provenance_and_keys(tmp_path, monkeypatch, damage):
    study = prepared_completion(tmp_path, monkeypatch)
    added = add_completed(study, 1)
    rows = read_rows(study.summary_path)
    pilot_row = next(row for row in rows if job_key(row) in study.pilot_rows)
    new_row = next(row for row in rows if job_key(row) == added[0].key)
    if damage == "pilot_row":
        pilot_row["encode_seconds"] = "999"
    elif damage == "missing_pilot":
        rows.remove(pilot_row)
    elif damage == "duplicate":
        rows.append(dict(new_row))
    elif damage == "outside_plan":
        new_row["qp"] = "26"
    elif damage == "old_provenance":
        new_row["protocol_sha256"] = study.pilot_snapshot["protocol_sha256"]
    else:
        new_row["job_plan_sha256"] = study.pilot_snapshot["job_plan_sha256"]
    write_rows(study.summary_path, rows)
    with pytest.raises(RuntimeError):
        study._load_frozen_inputs()


def test_pilot_artifact_corruption_blocks_continuation_instead_of_reencoding(tmp_path, monkeypatch):
    study = prepared_completion(tmp_path, monkeypatch)
    pilot_row = next(iter(study.pilot_rows.values()))
    output_paths(study.results, pilot_row)["bitstream"].write_bytes(b"broken")
    monkeypatch.setattr(study, "run_job", lambda *args: pytest.fail("Do not replace the pilot"))
    with pytest.raises(RuntimeError, match="original pilot encode is invalid"):
        study.run()
    assert read_rows(study.timing_path)[-1]["run_completed"] == "False"


def test_validator_checks_all_full_run_artifacts_and_incomplete_summary(tmp_path, monkeypatch):
    study = prepared_completion(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="incomplete"):
        study.validate()
    added = add_completed(study, 16)
    study.validate()
    output_paths(study.results, added[0])["bitstream"].write_bytes(b"broken")
    with pytest.raises(RuntimeError, match="Invalid completed full-study encode"):
        study.validate()
    repaired = []
    monkeypatch.setattr(study, "prepare_yuv", lambda *args: None)
    def repair_job(job, stimulus, snapshot):
        repaired.append(job.key)
        return artifact_row(study, job, stimulus, snapshot)
    monkeypatch.setattr(study, "run_job", repair_job)
    study.run()
    assert repaired == [added[0].key]
    study.validate()


def test_interrupted_prepare_can_resume_unchanged_pilot_only_registry(tmp_path, monkeypatch):
    study = prepared_completion(tmp_path, monkeypatch)
    summary = study.summary_path.read_bytes()
    study.checks_path.unlink()
    study.prepare()
    assert study.summary_path.read_bytes() == summary
    add_completed(study, 1)
    study.checks_path.unlink()
    with pytest.raises(RuntimeError, match="no frozen continuation checks"):
        study.prepare()
