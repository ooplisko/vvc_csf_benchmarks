from __future__ import annotations

from dataclasses import replace
import hashlib
import threading
from pathlib import Path

import pytest

from tools.research import complete_vtm_four_qp_study as completion
from tools.research.run_vtm_content_partition_study import iter_job_results, output_paths, read_rows, write_rows
from vvenc_csf.content_partition import StudyJob
from vvenc_csf.partitions import summarize_partitions
from vvenc_csf.stimuli import file_sha256


def test_completion_covers_all_seeds_and_qps_without_repeating_existing_encodes():
    conditions = [("clean", 0, "")]
    conditions += [("awgn", level, seed) for level in (5, 15, 30)
                   for seed in ("20260811", "20260812", "20260813")]
    conditions += [("stripes", level, "") for level in (8, 16, 32)]
    manifest = [{"stimulus": f"{source}_{distortion}_{level}_{seed}", "distortion": distortion,
                 "level": level, "seed": seed} for source in range(24) for distortion, level, seed in conditions]
    existing = [{**row, "qp": qp, "mode": "baseline"} for row in manifest for qp in (22, 27, 32, 37)
                if row["distortion"] == "clean" or qp == 32 or (qp in (22, 37) and (
                    row["distortion"] == "stripes" or row["seed"] == "20260811"))]
    plan = completion.completion_plan(manifest, existing)
    assert len(plan) == 576
    assert {qp: sum(job.qp == qp for job in plan) for qp in completion.QPS} == {22: 144, 27: 288, 32: 0, 37: 144}
    old_keys = {completion.job_key(row) for row in existing}
    new_keys = {job.key for job in plan}
    assert not old_keys & new_keys
    assert old_keys | new_keys == {(row["stimulus"], qp, "baseline") for row in manifest for qp in completion.QPS}
    by_stimulus = {row["stimulus"]: row for row in manifest}
    assert all(by_stimulus[job.stimulus]["distortion"] != "clean" for job in plan)
    assert {by_stimulus[job.stimulus]["seed"] for job in plan if by_stimulus[job.stimulus]["distortion"] == "awgn"} == {
        "20260811", "20260812", "20260813",
    }


@pytest.mark.parametrize("damage", ["duplicate", "csf", "unknown"])
def test_completion_rejects_invalid_reuse_keys(damage):
    manifest = [{"stimulus": "a", "distortion": "clean"}]
    existing = [{"stimulus": "a", "qp": 22, "mode": "baseline"}]
    if damage == "duplicate":
        existing *= 2
    elif damage == "csf":
        existing[0]["mode"] = "csf"
    else:
        existing[0]["stimulus"] = "unknown"
    with pytest.raises(ValueError):
        completion.completion_plan(manifest, existing)


def tiny_study(tmp_path):
    reuse, sources, inputs = tmp_path / "results/reuse", tmp_path / "sources", tmp_path / "inputs"
    sources.mkdir()
    inputs.mkdir()
    (sources / "source.png").write_bytes(b"source bytes")
    paths = {}
    for key in ("encoder", "decoder", "encoder_config"):
        path = tmp_path / (key + (".exe" if key != "encoder_config" else ".cfg"))
        path.write_bytes(key.encode())
        paths[key] = path
    defaults = completion.default_settings(1)
    protocol = replace(defaults.protocol, source_dir=sources, expected_source_count=1)
    settings = replace(defaults, protocol=protocol, results=tmp_path / "results", **paths)
    conditions = [("clean", 0, "")]
    conditions += [("awgn", level, str(seed)) for level in (5, 15, 30) for seed in (20260811, 20260812, 20260813)]
    conditions += [("stripes", level, "") for level in (8, 16, 32)]
    manifest = []
    for index, (distortion, level, seed) in enumerate(conditions):
        image = inputs / f"{index}.png"
        image.write_bytes(f"stimulus {index}".encode())
        manifest.append({"dataset": "kodak", "source": "source.png", "stimulus": str(index),
                         "distortion": distortion, "level": level, "seed": seed, "path": str(image),
                         "sha256": file_sha256(image), "width": 3, "height": 3})
    old_protocol = replace(protocol, interference_qps=(22, 32, 37))
    by_stimulus = {row["stimulus"]: row for row in manifest}
    existing = [{**by_stimulus[job.stimulus], "qp": job.qp, "mode": "baseline", "conversion": "opencv_444",
                 "encoder_sha256": file_sha256(settings.encoder), "config_sha256": file_sha256(settings.encoder_config),
                 "yuv_sha256": hashlib.sha256(b"yuv" * 9).hexdigest(),
                 "reconstruction_verified": True, "cu_coverage_verified": True}
                for job in old_protocol.plan(manifest)]
    write_rows(reuse / "stimulus_features.csv", manifest)
    write_rows(reuse / "joined_measurements.csv", existing)
    return completion.FourQPCompletion(settings)


def test_prepare_is_encode_free_and_preserves_csv_plan_on_resume(tmp_path, monkeypatch):
    study = tiny_study(tmp_path)
    monkeypatch.setattr(study.encoder, "encode", lambda *args, **kwargs: pytest.fail("prepare must not encode"))
    monkeypatch.setattr(study.converter, "to_yuv444p_opencv", lambda *args: pytest.fail("prepare must not convert"))
    study.prepare()
    saved = study.plan_path.read_bytes()
    _, plan, _ = study._load_frozen_inputs()
    assert len(plan) == 24
    assert not (study.results / "encoded").exists()
    assert not (study.results / "yuv").exists()
    study.prepare()
    assert study.plan_path.read_bytes() == saved
    assert not list(study.results.rglob("*.json"))
    restarted = completion.FourQPCompletion(study.settings)
    assert len(restarted._load_frozen_inputs()[1]) == 24
    # A changed current encoder must not silently reuse previous outputs.
    study.settings.encoder.write_bytes(b"different encoder")
    with pytest.raises(ValueError, match="verified baseline"):
        study.prepare()
    assert study.plan_path.read_bytes() == saved


def test_changed_stimulus_and_changed_plan_are_rejected(tmp_path):
    study = tiny_study(tmp_path)
    study.prepare()
    plan = study.plan_path.read_bytes()
    study.plan_path.write_bytes(plan.replace(b",27,", b",26,", 1))
    with pytest.raises(RuntimeError, match="job plan changed"):
        study._load_frozen_inputs()
    study.plan_path.write_bytes(plan)
    image = Path(read_rows(study.manifest_path)[0]["path"])
    image.write_bytes(b"changed pixels")
    with pytest.raises(ValueError, match="Changed or unregistered"):
        study._load_frozen_inputs()


def test_historical_yuv_bytes_are_required(tmp_path, monkeypatch):
    study = tiny_study(tmp_path)
    manifest, _ = study.reference_inputs()
    yuv = tmp_path / "input.yuv"
    yuv.write_bytes(b"different conversion")
    monkeypatch.setattr(completion.VTMContentPartitionStudy, "prepare_yuv", lambda *args: yuv)
    with pytest.raises(RuntimeError, match="historically verified input"):
        study.prepare_yuv(manifest[0])
    study.expected_yuv[manifest[0]["stimulus"]] = file_sha256(yuv)
    assert study.prepare_yuv(manifest[0]) == yuv


def test_output_lock_prevents_overlapping_runs_and_releases_after_exit(tmp_path):
    with completion.exclusive_run(tmp_path):
        with pytest.raises(RuntimeError, match="Another completion process"):
            with completion.exclusive_run(tmp_path):
                pytest.fail("The second process must not enter")
    with completion.exclusive_run(tmp_path):
        pass


def completed_study(tmp_path):
    study = tiny_study(tmp_path)
    study.prepare()
    manifest, plan, hashes = study._load_frozen_inputs()
    by_stimulus = {row["stimulus"]: row for row in manifest}
    rows = []
    for job in plan:
        stimulus = by_stimulus[job.stimulus]
        yuv = study._yuv_path(stimulus)
        yuv.parent.mkdir(parents=True, exist_ok=True)
        yuv.write_bytes(b"yuv" * 9)
        paths = output_paths(study.results, job)
        for path in paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"encoded artifact")
        partitions = [{"x": 0, "y": 0, "width": 3, "height": 3}]
        write_rows(paths["partition_csv"], partitions)
        rows.append({**stimulus, **hashes, "qp": job.qp, "mode": "baseline",
                     "protocol_sha256": "former-parameter-file-hash", "image_sha256": stimulus["sha256"],
                     "yuv_sha256": file_sha256(yuv), "conversion": "opencv_444", "trace_rule": "D_QP:poc==0",
                     "reconstruction_verified": True, "cu_coverage_verified": True,
                     **summarize_partitions(partitions, 3, 3),
                     **{f"{name}_sha256": file_sha256(path) for name, path in paths.items()}})
    write_rows(study.summary_path, rows)
    return study


def test_resume_accepts_valid_historical_rows_without_metadata_files(tmp_path, monkeypatch, capsys):
    study = completed_study(tmp_path)
    original = study.summary_path.read_bytes()
    monkeypatch.setattr(study, "prepare_yuv", lambda *args: pytest.fail("No conversion needed"))
    monkeypatch.setattr(study, "run_job", lambda *args: pytest.fail("Must skip valid encodes"))
    study.run()
    assert study.validate() == study.summary_path
    study.status()
    assert "Recorded 24/24" in capsys.readouterr().out
    assert study.summary_path.read_bytes() == original
    assert not list(study.results.rglob("*.json"))


@pytest.mark.parametrize("damage", ["artifact", "yuv", "decoder", "coverage", "cu_count", "density"])
def test_completed_encode_validation_detects_corruption(tmp_path, damage):
    study = completed_study(tmp_path)
    rows = read_rows(study.summary_path)
    row = rows[0]
    if damage == "artifact":
        output_paths(study.results, row)["bitstream"].write_bytes(b"broken bitstream")
    elif damage == "yuv":
        study._yuv_path(row).write_bytes(b"wrong conversion" * 2)
        row["yuv_sha256"] = file_sha256(study._yuv_path(row))
    elif damage == "decoder":
        study.settings.decoder.write_bytes(b"another decoder")
    elif damage == "coverage":
        path = output_paths(study.results, row)["partition_csv"]
        write_rows(path, [{"x": 0, "y": 0, "width": 2, "height": 3},
                          {"x": 1, "y": 0, "width": 2, "height": 3}])
        row["partition_csv_sha256"] = file_sha256(path)
    elif damage == "density":
        row["cu_density_per_mpixel"] = 2
    else:
        row["cu_count"] = 2
    write_rows(study.summary_path, rows)
    with pytest.raises(RuntimeError, match="Invalid completed encode"):
        study.validate()


def test_completion_uses_twenty_concurrent_workers():
    assert completion.default_settings().workers == 20
    barrier = threading.Barrier(20)
    jobs = [StudyJob(str(index), 27, ("interference_qp",)) for index in range(20)]

    def worker(job):
        barrier.wait(timeout=5)
        return job.key

    assert {result for _, result in iter_job_results(jobs, worker, workers=20)} == {job.key for job in jobs}
