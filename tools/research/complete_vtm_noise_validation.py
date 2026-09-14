"""Complete the frozen DIV2K noise study while reusing all verified pilot encodes."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.research import run_vtm_noise_validation as pilot_module
from tools.research.complete_vtm_four_qp_study import exclusive_run
from tools.research.run_vtm_content_partition_study import (
    VTMContentPartitionStudy, job_key, read_rows, write_rows,
)
from vvenc_csf.core import repo_path
from vvenc_csf.stimuli import file_sha256


def default_settings(workers: int = 20):
    return replace(pilot_module.default_settings(workers=workers), protocol_path=Path(__file__).resolve())


class NoiseValidationCompletion(VTMContentPartitionStudy):
    """Use the candidate plan with separate records for mixed pilot/full-run provenance."""

    def __init__(self, settings):
        super().__init__(settings)
        self.pilot = pilot_module.NoiseValidationPilot(replace(
            settings, protocol_path=Path(pilot_module.__file__).resolve(),
        ))
        self.summary_path = self.results / "full_partition_summary.csv"
        self.checks_path = self.results / "full_input_checks.csv"
        self.timing_path = self.results / "full_run_timings.csv"
        self.plan_path = self.pilot.candidate_plan_path
        self.pilot_rows = {}
        self.pilot_snapshot = {}

    def _reference_inputs(self):
        manifest, pilot_plan, self.pilot_snapshot = self.pilot._load_frozen_inputs()
        rows = read_rows(self.pilot.summary_path) if self.pilot.summary_path.is_file() else []
        self.pilot_rows = {job_key(row): row for row in rows}
        if len(rows) != len(self.pilot_rows) or set(self.pilot_rows) != {job.key for job in pilot_plan}:
            raise RuntimeError("The original pilot must be complete before continuing")
        by_stimulus = {row["stimulus"]: row for row in manifest}
        if any(not self.pilot._completed_row_matches(row, by_stimulus, self.pilot_snapshot) for row in rows):
            raise RuntimeError("An original pilot encode is invalid; refusing to replace it")
        return manifest, pilot_module.validation_plan(manifest), rows

    def _input_paths(self):
        return {
            "wrapper": self.settings.protocol_path,
            "pilot_input_checks": self.pilot.checks_path,
            "pilot_summary": self.pilot.summary_path,
            "candidate_plan": self.plan_path,
        }

    def prepare(self):
        if self.checks_path.exists():
            self._load_frozen_inputs()
            print("Existing full-study continuation verified.", flush=True)
            return self.summary_path
        _, plan, pilot_rows = self._reference_inputs()
        if self.summary_path.exists():
            existing = read_rows(self.summary_path)
            if len(existing) != len(pilot_rows) or {job_key(row): row for row in existing} != self.pilot_rows:
                raise RuntimeError("Existing full-study results have no frozen continuation checks")
        else:
            write_rows(self.summary_path, pilot_rows)
        write_rows(self.checks_path, [
            {"name": name, "path": repo_path(path), "sha256": file_sha256(path)}
            for name, path in self._input_paths().items()
        ])
        print(f"Prepared {len(plan)} full-study jobs: {len(pilot_rows)} verified pilot encodes reused; "
              f"{len(plan) - len(pilot_rows)} pending. No encodes launched.", flush=True)
        return self.summary_path

    def _load_frozen_inputs(self):
        if not self.checks_path.is_file() or not self.summary_path.is_file():
            raise RuntimeError("Run prepare before the full-study continuation")
        checks = read_rows(self.checks_path)
        expected_paths = {name: repo_path(path) for name, path in self._input_paths().items()}
        if len(checks) != len(expected_paths) or {row["name"]: row["path"] for row in checks} != expected_paths:
            raise RuntimeError("Frozen continuation check inventory changed")
        for row in checks:
            path = self._project_path(Path(row["path"]))
            if not path.is_file() or file_sha256(path) != row["sha256"]:
                raise RuntimeError(f"Frozen continuation input changed: {row['name']}")
        manifest, plan, _ = self._reference_inputs()
        hashes = {row["name"]: row["sha256"] for row in checks}
        snapshot = dict(self.pilot_snapshot, protocol_sha256=hashes["wrapper"],
                        job_plan_sha256=hashes["candidate_plan"])
        rows = read_rows(self.summary_path)
        keys = [job_key(row) for row in rows]
        if (len(keys) != len(set(keys)) or not set(keys).issubset({job.key for job in plan})
                or not set(self.pilot_rows).issubset(keys)):
            raise RuntimeError("Full summary has duplicate/unexpected jobs or missing pilot rows")
        for row in rows:
            key = job_key(row)
            if key in self.pilot_rows:
                if row != self.pilot_rows[key]:
                    raise RuntimeError(f"Reused pilot row changed: {key}")
            elif any(row.get(name) != value for name, value in snapshot.items()):
                raise RuntimeError(f"Full-study provenance mismatch: {key}")
        return manifest, plan, snapshot

    def _completed_row_matches(self, row, manifest_by_stimulus, snapshot):
        key = job_key(row)
        if key in self.pilot_rows:
            return (row == self.pilot_rows[key]
                    and self.pilot._completed_row_matches(row, manifest_by_stimulus, self.pilot_snapshot))
        return self.pilot._completed_row_matches(row, manifest_by_stimulus, snapshot)

    def _write_progress(self, total, completed, job, complete):
        pass  # Console progress and the atomic summary CSV are written by the shared runner.

    def run(self):
        started = datetime.now(timezone.utc).isoformat()
        before = len(read_rows(self.summary_path)) if self.summary_path.exists() else 0
        wall_start = time.perf_counter()
        complete = False
        try:
            result = super().run()
            complete = True
            return result
        finally:
            elapsed = time.perf_counter() - wall_start
            after = len(read_rows(self.summary_path)) if self.summary_path.exists() else 0
            timings = read_rows(self.timing_path) if self.timing_path.exists() else []
            timings.append({"started_utc": started, "workers": self.settings.workers,
                            "recorded_before": before, "recorded_after": after,
                            "wall_seconds": elapsed, "run_completed": complete})
            write_rows(self.timing_path, timings)
            print(f"Full-study invocation wall time: {elapsed:.1f} s; includes input checks and conversion.",
                  flush=True)

    def validate(self):
        manifest, plan, snapshot = self._load_frozen_inputs()
        rows = read_rows(self.summary_path)
        if {job_key(row) for row in rows} != {job.key for job in plan}:
            raise RuntimeError("Full-study summary is incomplete")
        by_stimulus = {row["stimulus"]: row for row in manifest}
        if any(not self._completed_row_matches(row, by_stimulus, snapshot) for row in rows):
            raise RuntimeError("Invalid completed full-study encode")
        print(f"Verified {len(rows)} full-study encodes, including {len(self.pilot_rows)} unchanged pilot encodes.",
              flush=True)
        return self.summary_path

    def status(self):
        _, plan, _ = self._load_frozen_inputs()
        recorded = len(read_rows(self.summary_path))
        print(f"Recorded {recorded}/{len(plan)} full-study jobs, including {len(self.pilot_rows)} reused pilot jobs; "
              f"{len(plan) - recorded} unrecorded. Use validate to check all completed artifacts.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "status", "validate"))
    parser.add_argument("--workers", type=int, default=20)
    args = parser.parse_args()
    study = NoiseValidationCompletion(default_settings(args.workers))
    with exclusive_run(study.results):
        if args.action == "prepare":
            study.prepare()
        elif args.action == "run":
            study.prepare()
            study.run()
            study.validate()
        elif args.action == "status":
            study.status()
        else:
            study.validate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
