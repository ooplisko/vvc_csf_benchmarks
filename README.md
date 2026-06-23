# VVC CSF Benchmarks

<p align="center">
  <a href="https://github.com/ooplisko/vvc_csf_benchmarks/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
  </a>
  <a href="https://github.com/ooplisko/vvc_csf_benchmarks/actions/workflows/build.yml">
    <img src="https://github.com/ooplisko/vvc_csf_benchmarks/actions/workflows/build.yml/badge.svg" alt="Tests">
  </a>
  <a href="https://github.com/ooplisko/vvc_csf_benchmarks/actions">
    <img src="https://img.shields.io/badge/build-validation-brightgreen" alt="Build validation">
  </a>
  <a href="https://github.com/ooplisko/vvc_csf_benchmarks/releases">
    <img src="https://img.shields.io/badge/release-assets-blue" alt="Release assets">
  </a>
</p>

**O. O. Plisko** - [Department of Information and Communication Technologies](https://dict.khai.edu/), National Aerospace University "Kharkiv Aviation Institute"

This repository is a reproducible image-only benchmark for Contrast Sensitivity Function (CSF) scaling-list modifications in VVenC and VTM. It can download or build the required codec binaries, run baseline-vs-CSF experiments, verify decoded bitstreams, compute objective image metrics, render RD charts, and generate Coding Unit (CU) partition-map evidence from trace-enabled encoders.

## What It Does

| Workflow | Output |
| --- | --- |
| Smoke checks | One-image encode/decode checks for VVenC or VTM |
| Full image benchmark | Per-image/per-QP metric CSVs, summaries, XLSX workbooks, and RD charts |
| Partition maps | CU SVG overlays and summaries from `D_QP` traces for VVenC and VTM |
| VTM validation | Historical VTM 18.0 anchor replication plus local VTM 23.0 baseline/CSF curves |
| Report rendering | Root README and detailed benchmark report regenerated from committed artifacts |

## Quick Start

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tools\data_prep\download_binaries.py
.\.venv\Scripts\python.exe run_all.py quick --clean
.\.venv\Scripts\python.exe run_all.py quick --codec vtm --clean
```

Requirements: Python 3.10+, `ffmpeg`, and `ffprobe` in `PATH`. Windows release binaries are not tracked in git; `download_binaries.py` downloads `binaries.zip` from GitHub Releases and extracts the top-level `binaries/` folder into the repository.

## Main Commands

| Task | Command |
| --- | --- |
| Run full VVenC benchmark | `.\.venv\Scripts\python.exe run_all.py full --codec vvenc --clean` |
| Run full VTM benchmark | `.\.venv\Scripts\python.exe run_all.py full --codec vtm --clean` |
| Re-render existing reports | `.\.venv\Scripts\python.exe tools\reporting\render_readme.py` |
| Run tests | `.\.venv\Scripts\python.exe -m pytest -q` |
| Build VVenC encoders | `.\.venv\Scripts\python.exe tools\building\build_vvenc.py all` |
| Build VTM encoders/decoders | `.\.venv\Scripts\python.exe tools\building\build_vtm.py all` |

Full runs are intentionally slow. They regenerate `docs/image_benchmark/{vvenc,vtm}/`, `docs/partition_maps/{vvenc,vtm}/`, and the Markdown reports.

## Binaries

Ready-to-use Windows binaries are provided as a GitHub Release asset named `binaries.zip`. The archive contains the complete `binaries/` folder, including VVenC, VVdeC, VTM 18.0 validation binaries, VTM 23.0 baseline/CSF binaries, and trace-enabled encoders for partition maps.

| Path | Purpose |
| --- | --- |
| `binaries/vvenc/` | VVenC baseline, CSF, trace encoders, and VVdeC decoder |
| `binaries/vtm/vtm18/baseline/` | Historical VTM 18.0 validation encoder/decoder |
| `binaries/vtm/vtm23/baseline/` | Clean VTM 23.0 encoder/decoder |
| `binaries/vtm/vtm23/csf/` | Modified VTM 23.0 CSF encoder |
| `binaries/vtm/vtm23/*_trace/` | Trace-enabled VTM encoders for CU partition maps |

A CSF decoder is intentionally not used. The CSF changes are encoder-side; the clean decoder is the compatibility check. Detailed build and binary-layout notes are in [`binaries/README.md`](binaries/README.md).

## Results

| Artifact | Location |
| --- | --- |
| Detailed benchmark report | [`docs/image_benchmark_report.md`](docs/image_benchmark_report.md) |
| VVenC metrics | [`docs/image_benchmark/vvenc/`](docs/image_benchmark/vvenc/) |
| VTM 23.0 metrics | [`docs/image_benchmark/vtm/`](docs/image_benchmark/vtm/) |
| VVenC partition maps | [`docs/partition_maps/vvenc/`](docs/partition_maps/vvenc/) |
| VTM partition maps | [`docs/partition_maps/vtm/`](docs/partition_maps/vtm/) |
| VTM validation | [`docs/vtm_validation/`](docs/vtm_validation/) |
| Matrix evidence | [`docs/matrices/`](docs/matrices/) |

Current generated results show that CSF bitstreams decode correctly and reconstruction checks pass, but the current CSF matrix does not improve average quality or rate-distortion performance under the fixed image/QP conditions used here. See the detailed report for tables and interpretation.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `configs/` | Benchmark defaults for paths, binaries, QP points, and output options |
| `data/datasets/images/` | Primary grayscale, synthetic, and Kodak PNG inputs |
| `metrics/` | Local visual-quality metric implementations |
| `tools/` | Build, benchmark, validation, reporting, and visualization CLIs |
| `vvenc_csf/` | Reusable command, encoding, config, and benchmark library code |
| `tests/` | Fast unit tests and binary-availability integration checks |
| `docs/` | Generated reports, validation artifacts, matrices, charts, and partition maps |

## Key Documents

| Document | Use |
| --- | --- |
| [`docs/image_benchmark_report.md`](docs/image_benchmark_report.md) | Main scientific report for image benchmark results |
| [`binaries/README.md`](binaries/README.md) | Binary layout, download, and build instructions |
| [`docs/vtm_validation/`](docs/vtm_validation/) | VTM anchor validation and VTM 23.0 cross-checks |
| [`CITATION.cff`](CITATION.cff) | Citation metadata |
