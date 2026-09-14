"""Prepare independent DIV2K validation inputs and run a fixed 32-encode timing pilot."""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.data_prep.generate_distortion_sweep import generate_sweep
from tools.research.complete_vtm_four_qp_study import exclusive_run
from tools.research.run_vtm_content_partition_study import (
    IMPLEMENTATION_FILES, ROOT, StudySettings, VTMContentPartitionStudy,
    job_key, output_paths, read_rows, write_rows,
)
from vvenc_csf.content_partition import ContentPartitionProtocol, StudyJob
from vvenc_csf.core import platform_executable, repo_path
from vvenc_csf.partitions import summarize_partitions
from vvenc_csf.stimuli import file_sha256, read_png, write_png


SOURCE_NAMES = tuple(f"{index:04d}.png" for index in range(801, 901))
SELECTION_SEED = 20260910
SOURCE_COUNT = 48
PILOT_SOURCE_COUNT = 2
CROP_WIDTH, CROP_HEIGHT = 768, 512
QPS = (22, 27, 32, 37)
AWGN_SEEDS = (20260811, 20260812, 20260813)
DOWNLOAD_URL = "https://data.vision.ee.ethz.ch/cvl/DIV2K/DIV2K_valid_HR.zip"
EXPECTED_HASHES = {
    "encoder": "f6673e301575d77826e2e2a0bfc4fc8a81f76c42e16d7de3c38d58c4390d5b21",
    "decoder": "073abd496b427fca6c11302768c3f76f99365467e84cfc3debe05867c976acfe",
    "encoder_config": "0ec6dd9876c269c0832e0a64ab20c015c6c839d266e108c88b30aa28c77391f9",
}
ANALYSIS_SETTINGS = {
    "role": "independent_validation_of_exploratory_Kodak_findings",
    "source_count": SOURCE_COUNT,
    "descriptors": "sobel_si;luma_sd;edge_fraction;glcm_contrast;glcm_entropy;glcm_homogeneity",
    "direction_signs": "1;1;1;1;1;-1",
    "glcm": "8 levels;4 symmetric normalized directions;distance 1",
    "edge_threshold": 150,
    "seed_summary": "equal_mean_of_3_correlations_with_paired_image_indices",
    "resampling_unit": "source_image",
    "resampling": "paired_image_bootstrap_with_reranking",
    "bootstrap_seed": 20260905,
    "bootstrap_resamples": 99999,
    "simultaneous_family": "24 B plus 20 C at sigma 30 across all four QPs",
    "family_alpha": 0.05,
    "interval_method": "basic_maximum_absolute_error",
    "B_definition": "direction_sign*(rho_noisy-rho_clean)",
    "C_definition": "B_homogeneity-B_other",
    "B_bounds": "-2;2",
    "C_bounds": "-4;4",
    "noise_inference": "conditional_on_the_three_fixed_realizations",
    "scene_sensitivity": "repeat B/C with 0854.png and 0864.png jointly resampled as one of 47 clusters",
}


def default_settings(source_dir: Path | None = None, workers: int = 4) -> StudySettings:
    protocol = ContentPartitionProtocol(
        dataset="div2k_validation", source_dir=source_dir or Path("results/vtm_noise_validation/input/DIV2K_valid_HR"),
        results_dir=Path("results/vtm_noise_validation"),
        encoder=Path("binaries/vtm/vtm23/baseline_trace/EncoderApp"),
        decoder=Path("binaries/vtm/vtm23/baseline/DecoderApp"),
        encoder_config=Path("configs/vtm_encoder_intra.cfg"), conversion="opencv_444",
        complexity_qps=QPS, interference_qps=QPS, realization_qp=32,
        awgn_sigmas=(30,), awgn_seeds=AWGN_SEEDS, interference_seed=AWGN_SEEDS[0],
        awgn_generator="numpy.random.PCG64",
        awgn_image_seed="SeedSequence([base_seed, zero_based_sorted_source_index])",
        stripe_amplitudes=(), stripe_period_pixels=16, stripe_phase=0,
        stripe_orientation="horizontal", expected_source_count=SOURCE_COUNT,
    )
    return StudySettings(
        protocol_path=Path(__file__), protocol=protocol, results=ROOT / protocol.results_dir,
        encoder=platform_executable(ROOT / protocol.encoder),
        decoder=platform_executable(ROOT / protocol.decoder),
        encoder_config=ROOT / protocol.encoder_config, workers=workers,
    )


def selected_sources() -> tuple[str, ...]:
    """Return the predeclared draw order; noise indices use its sorted order."""
    order = np.random.Generator(np.random.PCG64(SELECTION_SEED)).permutation(len(SOURCE_NAMES))
    return tuple(SOURCE_NAMES[index] for index in order[:SOURCE_COUNT])


def source_inventory(source_dir: Path) -> list[dict]:
    """Reject unsuitable inputs before selecting; never replace images using outcomes."""
    paths = sorted(source_dir.glob("*.png"))
    if tuple(path.name for path in paths) != SOURCE_NAMES:
        raise ValueError(f"Expected DIV2K validation HR files 0801.png through 0900.png in {source_dir}. "
                         f"Official archive: {DOWNLOAD_URL}")
    selection = selected_sources()
    ranks = {name: index + 1 for index, name in enumerate(selection)}
    noise_indices = {name: index for index, name in enumerate(sorted(selection))}
    hashes, pixel_hashes, rows = set(), set(), []
    for path in paths:
        image = read_png(path)
        height, width = image.shape[:2]
        if image.ndim != 3 or image.shape[2] != 3 or width < CROP_WIDTH or height < CROP_HEIGHT:
            raise ValueError(f"Expected RGB 8-bit source at least {CROP_WIDTH}x{CROP_HEIGHT}: {path}")
        digest = file_sha256(path)
        pixel_digest = hashlib.sha256(str(image.shape).encode() + image.tobytes()).hexdigest()
        if digest in hashes or pixel_digest in pixel_hashes:
            raise ValueError(f"Duplicate DIV2K original: {path}; resolve the source pool before selection")
        hashes.add(digest)
        pixel_hashes.add(pixel_digest)
        rows.append({
            "source": path.name, "original_path": repo_path(path), "original_sha256": digest,
            "pixel_sha256": pixel_digest, "original_width": width, "original_height": height,
            "selection_rank": ranks.get(path.name, ""), "source_index": noise_indices.get(path.name, ""),
            "pilot": path.name in selection[:PILOT_SOURCE_COUNT],
            "crop_x": (width - CROP_WIDTH) // 2, "crop_y": (height - CROP_HEIGHT) // 2,
            "crop_width": CROP_WIDTH, "crop_height": CROP_HEIGHT,
        })
    return rows


def validation_plan(manifest: list[dict], sources: set[str] | None = None) -> tuple[StudyJob, ...]:
    jobs = tuple(sorted(
        StudyJob(row["stimulus"], qp, ("noise_validation",))
        for row in manifest if sources is None or row["source"] in sources for qp in QPS
    ))
    if len({job.key for job in jobs}) != len(jobs):
        raise ValueError("Duplicate validation stimuli")
    return jobs


class NoiseValidationPilot(VTMContentPartitionStudy):
    """Freeze all candidate inputs while dispatching only the predefined pilot."""

    def __init__(self, settings):
        super().__init__(settings)
        self.inventory_path = self.results / "source_selection.csv"
        self.candidate_plan_path = self.results / "candidate_job_plan.csv"
        self.checks_path = self.results / "input_checks.csv"
        self.analysis_protocol_path = self.results / "analysis_protocol.csv"
        self.timing_path = self.results / "pilot_timings.csv"
        self.crop_dir = self.results / "sources"

    def _preflight(self, require_study_inputs=False):
        if self.settings.workers < 1 or self.settings.force:
            raise ValueError("workers must be positive; forced replacement is not supported")
        for name, expected in EXPECTED_HASHES.items():
            path = getattr(self.settings, name)
            if not path.is_file() or file_sha256(path) != expected:
                raise ValueError(f"The verified VTM 23.0 {name} is missing or changed: {path}")
        if require_study_inputs and not self.checks_path.is_file():
            raise RuntimeError("Run prepare before the pilot")

    def prepare(self):
        self._preflight()
        if self.checks_path.exists():
            self._load_frozen_inputs()
            print("Existing DIV2K selection, stimuli and pilot plan verified.", flush=True)
            return self.manifest_path
        if self.summary_path.exists() or (self.results / "encoded").exists():
            raise RuntimeError("Existing encoding outputs have no frozen input checks")
        inventory = source_inventory(self._project_path(self.protocol.source_dir))
        selected = [row for row in inventory if row["selection_rank"] != ""]
        existing_crops = {path.name for path in self.crop_dir.glob("*.png")}
        if existing_crops - {row["source"] for row in selected}:
            raise RuntimeError("Unexpected crops in the prepared source directory")
        for row in selected:
            image = read_png(self._project_path(Path(row["original_path"])))
            x, y = row["crop_x"], row["crop_y"]
            target = self.crop_dir / row["source"]
            write_png(target, image[y:y + CROP_HEIGHT, x:x + CROP_WIDTH])
            row.update(crop_path=repo_path(target), crop_sha256=file_sha256(target))
        write_rows(self.inventory_path, inventory)
        manifest = generate_sweep(self.crop_dir, self.results / "stimuli", self.protocol.dataset,
                                  (30,), AWGN_SEEDS, (), self.manifest_path)
        manifest = [dict(row, path=repo_path(Path(row["path"]))) for row in manifest]
        self._validate_manifest(manifest)
        write_rows(self.manifest_path, manifest)
        candidate = validation_plan(manifest)
        pilot = validation_plan(manifest, set(selected_sources()[:PILOT_SOURCE_COUNT]))
        write_rows(self.candidate_plan_path, self._plan_rows(candidate))
        write_rows(self.plan_path, self._plan_rows(pilot))
        write_rows(self.analysis_protocol_path, [{"setting": key, "value": value}
                                                for key, value in ANALYSIS_SETTINGS.items()])
        write_rows(self.checks_path, [
            {"name": name, "path": repo_path(path), "sha256": file_sha256(path)}
            for name, path in self._input_paths(inventory, manifest).items()
        ])
        print(f"Prepared {len(selected)} crops, {len(manifest)} stimuli and {len(candidate)} candidate jobs. "
              f"Only {len(pilot)} pilot encodes can be launched by this script.", flush=True)
        return self.manifest_path

    def _input_paths(self, inventory, manifest):
        paths = {
            "selection": self.inventory_path, "manifest": self.manifest_path,
            "candidate_plan": self.candidate_plan_path, "pilot_plan": self.plan_path,
            "analysis_protocol": self.analysis_protocol_path,
            **{name: getattr(self.settings, name) for name in EXPECTED_HASHES},
        }
        paths.update({f"code:{repo_path(path)}": path for path in (
            Path(__file__).resolve(), *IMPLEMENTATION_FILES,
            ROOT / "tools/research/complete_vtm_four_qp_study.py", ROOT / "vvenc_csf/core.py",
            ROOT / "vvenc_csf/spatial_complexity.py", ROOT / "vvenc_csf/study_statistics.py",
        )})
        paths.update({f"original:{row['source']}": self._project_path(Path(row["original_path"])) for row in inventory})
        paths.update({f"crop:{row['source']}": self._project_path(Path(row["crop_path"]))
                      for row in inventory if row["selection_rank"] != ""})
        paths.update({f"stimulus:{row['stimulus']}": self._project_path(Path(row["path"])) for row in manifest})
        return paths

    def _load_frozen_inputs(self):
        self._preflight(require_study_inputs=True)
        checks = read_rows(self.checks_path)
        if len({row["name"] for row in checks}) != len(checks):
            raise RuntimeError("Duplicate frozen input checks")
        for row in checks:
            path = self._project_path(Path(row["path"]))
            if not path.is_file() or file_sha256(path) != row["sha256"]:
                raise RuntimeError(f"Frozen input changed: {row['name']}")
        manifest = read_rows(self.manifest_path)
        inventory = read_rows(self.inventory_path)
        expected_paths = {name: repo_path(path) for name, path in self._input_paths(inventory, manifest).items()}
        if {row["name"]: row["path"] for row in checks} != expected_paths:
            raise RuntimeError("Frozen input check inventory changed")
        self._validate_manifest(manifest)
        selection = selected_sources()
        if {row["source"] for row in manifest} != set(selection):
            raise RuntimeError("Manifest no longer matches the fixed random selection")
        candidate = validation_plan(manifest)
        pilot = validation_plan(manifest, set(selection[:PILOT_SOURCE_COUNT]))
        for path, plan in ((self.candidate_plan_path, candidate), (self.plan_path, pilot)):
            expected = [{key: str(value) for key, value in row.items()} for row in self._plan_rows(plan)]
            if read_rows(path) != expected:
                raise RuntimeError("Frozen job plan changed")
        snapshots = {row["name"]: row["sha256"] for row in checks}
        snapshot = {
            "protocol_sha256": file_sha256(Path(__file__)), "manifest_sha256": snapshots["manifest"],
            "job_plan_sha256": snapshots["pilot_plan"], "encoder_sha256": snapshots["encoder"],
            "decoder_sha256": snapshots["decoder"], "encoder_config_sha256": snapshots["encoder_config"],
        }
        if self.summary_path.exists():
            actual = [job_key(row) for row in read_rows(self.summary_path)]
            if len(actual) != len(set(actual)) or not set(actual).issubset({job.key for job in pilot}):
                raise RuntimeError("Summary contains duplicate or non-pilot jobs")
        return manifest, pilot, snapshot

    def _write_progress(self, total, completed, job, complete):
        pass  # The shared runner prints progress and atomically saves its summary CSV.

    def _completed_row_matches(self, row, manifest_by_stimulus, snapshot):
        if not super()._completed_row_matches(row, manifest_by_stimulus, snapshot):
            return False
        manifest = manifest_by_stimulus[row["stimulus"]]
        try:
            stats = summarize_partitions(read_rows(output_paths(self.results, row)["partition_csv"]),
                                         int(manifest["width"]), int(manifest["height"]))
            return all(float(row[name]) == stats[name] for name in (
                "cu_count", "coded_width", "coded_height", "coded_area", "padding_area", "cu_density_per_mpixel",
            ))
        except (KeyError, ValueError):
            return False

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
            print(f"Pilot invocation wall time: {elapsed:.1f} s; includes input checks and conversion. "
                  "This is a timing measurement, not a full-run ETA.", flush=True)

    def validate(self):
        manifest, plan, snapshot = self._load_frozen_inputs()
        rows = read_rows(self.summary_path) if self.summary_path.exists() else []
        if {job_key(row) for row in rows} != {job.key for job in plan}:
            raise RuntimeError("Pilot summary is incomplete")
        by_stimulus = {row["stimulus"]: row for row in manifest}
        if any(not self._completed_row_matches(row, by_stimulus, snapshot) for row in rows):
            raise RuntimeError("Invalid completed pilot encode")
        print(f"Verified {len(rows)} pilot encodes and their artifacts.", flush=True)
        return self.summary_path

    def status(self):
        _, plan, _ = self._load_frozen_inputs()
        recorded = len(read_rows(self.summary_path)) if self.summary_path.exists() else 0
        print(f"Recorded {recorded}/{len(plan)} pilot jobs. Use validate to verify completed artifacts. "
              "The full candidate study is not enabled.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "prepare", "pilot", "status", "validate"))
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    study = NoiseValidationPilot(default_settings(args.source_dir, args.workers))
    if args.action == "preflight":
        study._preflight()
        inventory = source_inventory(study._project_path(study.protocol.source_dir))
        print(f"Verified {len(inventory)} unique RGB originals with suitable dimensions. No files generated.")
        return 0
    with exclusive_run(study.results):
        if args.action == "prepare":
            study.prepare()
        elif args.action == "pilot":
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
