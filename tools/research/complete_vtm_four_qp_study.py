"""Encode missing VTM jobs to cover every saved stimulus at QP 22/27/32/37."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.research.run_vtm_content_partition_study import (
    ROOT, StudySettings, VTMContentPartitionStudy, job_key, output_paths, read_rows, write_rows,
)
from vvenc_csf.content_partition import ContentPartitionProtocol, StudyJob
from vvenc_csf.core import platform_executable
from vvenc_csf.partitions import summarize_partitions
from vvenc_csf.stimuli import file_sha256


QPS = (22, 27, 32, 37)


def default_settings(workers: int = 20) -> StudySettings:
    protocol = ContentPartitionProtocol(
        dataset="kodak", source_dir=Path("data/datasets/images/kodak/png"),
        results_dir=Path("results/vtm_content_partition_four_qp"),
        encoder=Path("binaries/vtm/vtm23/baseline_trace/EncoderApp"),
        decoder=Path("binaries/vtm/vtm23/baseline/DecoderApp"),
        encoder_config=Path("configs/vtm_encoder_intra.cfg"), conversion="opencv_444",
        complexity_qps=QPS, interference_qps=QPS, realization_qp=32,
        awgn_sigmas=(5, 15, 30), awgn_seeds=(20260811, 20260812, 20260813),
        interference_seed=20260811, awgn_generator="numpy.random.PCG64",
        awgn_image_seed="SeedSequence([base_seed, zero_based_sorted_source_index])",
        stripe_amplitudes=(8, 16, 32), stripe_period_pixels=16, stripe_phase=0,
        stripe_orientation="horizontal", expected_source_count=24,
    )
    return StudySettings(
        protocol_path=Path(__file__), protocol=protocol, results=ROOT / protocol.results_dir,
        encoder=platform_executable(ROOT / protocol.encoder),
        decoder=platform_executable(ROOT / protocol.decoder),
        encoder_config=ROOT / protocol.encoder_config, workers=workers,
    )


def completion_plan(manifest: list[dict], existing: list[dict]) -> tuple[StudyJob, ...]:
    """Keep every saved stimulus and seed; subtract unique existing jobs."""
    known = [job_key(row) for row in existing]
    known_keys = set(known)
    if len(known_keys) != len(known) or any(key[2] != "baseline" for key in known):
        raise ValueError("Reuse registry must contain unique baseline jobs only")
    planned = []
    for row in manifest:
        analyses = ("complexity_qp", "interference_qp") if row["distortion"] == "clean" else ("interference_qp",)
        if row["distortion"] == "awgn":
            analyses = ("awgn_realizations", "interference_qp")
        planned.extend(StudyJob(row["stimulus"], qp, analyses) for qp in QPS)
    target = {job.key for job in planned}
    if len(target) != len(planned) or not known_keys.issubset(target):
        raise ValueError("Duplicate stimuli or reuse jobs outside the four-QP target")
    return tuple(sorted(job for job in planned if job.key not in known_keys))


@contextmanager
def exclusive_run(results: Path):
    """OS lock is released even if the process exits unexpectedly."""
    results.mkdir(parents=True, exist_ok=True)
    with (results / ".run.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Another completion process is using this results directory") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


class FourQPCompletion(VTMContentPartitionStudy):
    """Reuse CSV inputs and the existing runner's parallel queue and atomic outputs."""

    def __init__(self, settings):
        super().__init__(settings)
        self.reuse = self.results / "reuse"
        self.expected_yuv: dict[str, str] = {}

    def reference_inputs(self) -> tuple[list[dict], list[dict]]:
        manifest = read_rows(self.reuse / "stimulus_features.csv")
        existing = read_rows(self.reuse / "joined_measurements.csv")
        self._validate_manifest(manifest)
        encoder_hash = file_sha256(self.settings.encoder)
        config_hash = file_sha256(self.settings.encoder_config)
        for row in existing:
            if (row["mode"] != "baseline" or row["conversion"] != self.protocol.conversion
                    or row["encoder_sha256"] != encoder_hash or row["config_sha256"] != config_hash
                    or row["reconstruction_verified"].lower() != "true"
                    or row["cu_coverage_verified"].lower() != "true"):
                raise ValueError("Reuse registry or current encoder/configuration is not the verified baseline")
            previous = self.expected_yuv.setdefault(row["stimulus"], row["yuv_sha256"])
            if previous != row["yuv_sha256"]:
                raise ValueError("Conflicting historical input YUV hashes")
        for row in manifest:
            image = self._project_path(Path(row["path"]))
            if file_sha256(image) != row["sha256"] or row["stimulus"] not in self.expected_yuv:
                raise ValueError(f"Changed or unregistered existing PNG: {image}")
        if len(existing) != self.protocol.expected_source_count * 28:
            raise ValueError("Unexpected size of the existing dataset")
        return manifest, existing

    def _validate_plan(self, plan):
        if len(plan) != self.protocol.expected_source_count * 24 or len({job.key for job in plan}) != len(plan):
            raise ValueError("The missing-job plan does not match the completion size")

    def _snapshot_payload(self):
        # The shared run_job records these hashes directly in partition_summary.csv.
        return {name: file_sha256(path) for name, path in {
            "protocol_sha256": Path(__file__), "manifest_sha256": self.manifest_path,
            "job_plan_sha256": self.plan_path, "encoder_sha256": self.settings.encoder,
            "decoder_sha256": self.settings.decoder,
            "encoder_config_sha256": self.settings.encoder_config,
        }.items()}

    def _preflight(self, require_study_inputs):
        required = [self.settings.encoder, self.settings.decoder, self.settings.encoder_config,
                    self.reuse / "stimulus_features.csv", self.reuse / "joined_measurements.csv"]
        if require_study_inputs:
            required.extend((self.manifest_path, self.plan_path))
        for path in required:
            if not path.is_file():
                raise FileNotFoundError(f"Required study input is missing: {path}")
        if self.settings.workers < 1:
            raise ValueError("workers must be at least 1")

    def prepare(self):
        self._preflight(require_study_inputs=False)
        if self.manifest_path.exists() and self.plan_path.exists():
            self._load_frozen_inputs()
            print(f"Existing completion plan verified: {self.results}", flush=True)
            return self.manifest_path
        if self.summary_path.exists() or (self.results / "encoded").exists():
            raise RuntimeError("Existing encoding outputs have no manifest/job plan")
        manifest, existing = self.reference_inputs()
        plan = completion_plan(manifest, existing)
        self._validate_plan(plan)
        write_rows(self.manifest_path, manifest)
        write_rows(self.plan_path, self._plan_rows(plan))
        print(f"Prepared {len(plan)} missing encodes; reusing {len(existing)} results and {len(manifest)} PNGs.", flush=True)
        print(f"New jobs by QP: {dict(sorted(Counter(job.qp for job in plan).items()))}", flush=True)
        return self.manifest_path

    def _load_frozen_inputs(self):
        self._preflight(require_study_inputs=True)
        manifest, existing = self.reference_inputs()
        plan = completion_plan(manifest, existing)
        self._validate_plan(plan)
        expected_rows = [{key: str(value) for key, value in row.items()} for row in self._plan_rows(plan)]
        if read_rows(self.manifest_path) != manifest or read_rows(self.plan_path) != expected_rows:
            raise RuntimeError("Completion manifest or job plan changed")
        return manifest, plan, self._snapshot_payload()

    def _completed_row_matches(self, row, manifest_by_stimulus, snapshot):
        # Old rows identify the former parameter file. The effective inputs are
        # checked below, so editing this wrapper does not repeat a valid encode.
        checks = dict(snapshot, protocol_sha256=row.get("protocol_sha256", ""))
        if not super()._completed_row_matches(row, manifest_by_stimulus, checks):
            return False
        stimulus = str(row["stimulus"])
        if row["yuv_sha256"] != self.expected_yuv[stimulus]:
            return False
        manifest = manifest_by_stimulus[stimulus]
        try:
            stats = summarize_partitions(read_rows(output_paths(self.results, row)["partition_csv"]),
                                         int(manifest["width"]), int(manifest["height"]))
            return all(float(row[name]) == stats[name] for name in
                       ("cu_count", "coded_width", "coded_height", "coded_area", "padding_area",
                        "cu_density_per_mpixel"))
        except (KeyError, ValueError):
            return False

    def _write_progress(self, total, completed, job, complete):
        # run() prints each completion; the summary CSV is the resume record.
        pass

    def validate(self):
        manifest, plan, hashes = self._load_frozen_inputs()
        rows = read_rows(self.summary_path) if self.summary_path.is_file() else []
        actual = [job_key(row) for row in rows]
        if len(actual) != len(set(actual)) or set(actual) != {job.key for job in plan}:
            raise RuntimeError("Completion summary has missing, duplicate or unexpected jobs")
        by_stimulus = {row["stimulus"]: row for row in manifest}
        for row in rows:
            if not self._completed_row_matches(row, by_stimulus, hashes):
                raise RuntimeError(f"Invalid completed encode: {job_key(row)}")
        print(f"Verified {len(rows)} completed encodes and their output artifacts.", flush=True)
        return self.summary_path

    def status(self):
        _, plan, _ = self._load_frozen_inputs()
        rows = read_rows(self.summary_path) if self.summary_path.is_file() else []
        actual = [job_key(row) for row in rows]
        expected = {job.key for job in plan}
        if len(actual) != len(set(actual)) or not set(actual).issubset(expected):
            raise RuntimeError("Completion summary contains duplicate or unexpected jobs")
        print(f"Recorded {len(actual)}/{len(plan)} encodes; {len(plan) - len(actual)} pending. "
              "Use validate to check output artifacts.")

    def prepare_yuv(self, manifest_row):
        yuv = super().prepare_yuv(manifest_row)
        if file_sha256(yuv) != self.expected_yuv[manifest_row["stimulus"]]:
            raise RuntimeError("Converted YUV differs from the historically verified input for this stimulus")
        return yuv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "validate", "status"))
    parser.add_argument("--workers", type=int, default=20)
    args = parser.parse_args()
    study = FourQPCompletion(default_settings(args.workers))
    if args.action == "status":
        study.status()
        return 0
    with exclusive_run(study.results):
        if args.action == "prepare":
            study.prepare()
        elif args.action == "run":
            study.prepare()
            study.run()
            study.validate()
        else:
            study.validate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
