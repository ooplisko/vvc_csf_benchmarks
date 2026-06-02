# VVenC CSF Image Benchmark

<p align="center">
  <a href="https://github.com/For2natop1ua/vvenc_csf_tests/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
  </a>
  <a href="https://github.com/For2natop1ua/vvenc_csf_tests/actions/workflows/build.yml">
    <img src="https://github.com/For2natop1ua/vvenc_csf_tests/actions/workflows/build.yml/badge.svg" alt="Tests">
  </a>
  <a href="https://github.com/For2natop1ua/vvenc_csf_tests/actions">
    <img src="https://img.shields.io/badge/build-validation-brightgreen" alt="Build validation">
  </a>
  <a href="https://github.com/For2natop1ua/vvenc_csf_tests/releases">
    <img src="https://img.shields.io/badge/release-source%20package-blue" alt="Release package">
  </a>
</p>

**O. O. Plisko** · [Department of Information and Communication Technologies](https://dict.khai.edu/), National Aerospace University «Kharkiv Aviation Institute»

Image-only benchmark for a custom Contrast Sensitivity Function (CSF) scaling-list modification in VVenC. The repository contains pinned binaries, image sets, scripts, generated metric tables, RD charts, matrix evidence, and Coding Unit (CU) partition maps.

## Status

| Item | Current state |
| --- | --- |
| Primary control images | 5 standard grayscale images: BABOON, BARBARA, goldhill, lenna, peppers |
| Additional images | 4 synthetic images and 24 Kodak images |
| QP points | 22, 27, 32, 37 |
| Compared modes | `vvenc_default.exe` vs `vvenc_csf.exe --CSFScalingList 1` |
| Neutral value check | `16` verified from VVenC source and by a practical CSF-off control run |
| Current outcome | CSF bitstreams decode correctly and reconstruction checks pass, but the current CSF matrix does not outperform the default encoder on average |

## Documentation

| Document | Content |
| --- | --- |
| [Full benchmark report](docs/image_benchmark_report.md) | Binaries, matrices, reproduce steps, metrics, tables, charts, and partition maps |
| [Neutral 16 source verification](docs/matrices/neutral_16_verification.md) | Why scaling-list value `16` is neutral in the current VVenC code |
| [Neutral 16 control run](docs/matrices/neutral_16_control.md) | Default encoder vs CSF encoder with `--CSFScalingList 0`, compared byte-for-byte |
| [Combined metrics CSV](docs/image_benchmark/combined_image_metrics.csv) | All image/QP/mode measurements |
| [Partition summary CSV](docs/partition_maps/summary.csv) | CU counts and dominant block sizes |
| [Citation metadata](CITATION.cff) | Citation information for academic use |

## Repository Layout

| Path | Purpose |
| --- | --- |
| `binaries/` | Encoder and decoder binaries used by the benchmark |
| `image_sets/standard_grayscale/` | Primary grayscale control images, stored as BMP sources and PNG benchmark inputs |
| `image_sets/synthetic/png/` | Deterministic synthetic PNG images |
| `image_sets/kodak/png/` | Kodak image suite |
| `configs/` | INI defaults for benchmark paths, binaries, QP points, and smoke settings |
| `run_all.py` | Image-only orchestrator for smoke checks, neutral-value checks, benchmark runs, and report regeneration |
| `vvenc_csf/` | Reusable benchmark, encoding, neutral-value, and shared command-running classes |
| `tools/` | Thin CLI wrappers for dataset, benchmark, report, matrix, and partition-map utilities |
| `metrics/` | Local visual-quality metric implementations |
| `tests/` | Fast unit tests for helpers, command construction, config loading, and report builders |
| `docs/` | Generated evidence, tables, charts, and detailed reports |

## Quick Start

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
.\.venv\Scripts\python.exe run_all.py quick --clean
```

`ffmpeg`, `ffprobe`, and `curl.exe` must be available in `PATH`. The `.venv` and `results/` directories are local and are not committed. `quick` runs console sanity checks: smoke encode/decode and neutral-16 verification. `full` runs all image benchmarks and regenerates CSV reports, charts, partition maps, and Markdown documentation.

Benchmark defaults are stored in `configs/image_benchmark.ini`. Command-line arguments still override the config values.

<details>
<summary>Full reproduction commands</summary>

```powershell
.\.venv\Scripts\python.exe run_all.py full --clean
```

</details>

## Run vs Re-render

| Task | Command | What it does |
| --- | --- | --- |
| Quick validation | `.\.venv\Scripts\python.exe run_all.py quick --clean` | Runs smoke encode/decode and neutral-16 checks |
| Full run | `.\.venv\Scripts\python.exe run_all.py full --clean` | Runs encoders, decoder checks, metrics, CSV summaries, charts, partition maps, and Markdown rendering |
| Re-render reports only | `.\.venv\Scripts\python.exe tools\report_image_benchmark.py docs\image_benchmark\combined_image_metrics.csv --output docs\image_benchmark\combined` | Regenerates summary CSVs and RD charts from an existing metrics CSV |
| Re-render README/report | `.\.venv\Scripts\python.exe tools\render_readme.py` | Rebuilds README and the detailed benchmark report from existing docs artifacts |
| Run unit tests | `.\.venv\Scripts\python.exe -m pytest -q` | Runs the fast test suite used by CI |

## Result Snapshot

Same-QP and equal-bpp summaries are generated from `docs/image_benchmark/combined_image_metrics.csv`. Negative deltas mean the current CSF result is lower than the default encoder under the same comparison method.

| Metric | Mean | Min | Max |
| --- | --- | --- | --- |
| psnr_y_delta | -0.542548 | -1.437300 | 0.498400 |
| ssim_delta | -0.002447 | -0.011512 | 0.000771 |
| xpsnr_y_delta | -0.500045 | -1.377400 | 0.286200 |
| vmaf_delta | -0.039329 | -1.386822 | 1.076791 |
| msssim_luma_delta | -0.000044 | -0.000349 | 0.000008 |
| fsim_luma_delta | -0.003970 | -0.015175 | 0.003091 |
| haarpsi_luma_delta | -0.003477 | -0.018561 | 0.001788 |
| psnr_hvs_m_luma_delta | -0.501798 | -1.352777 | 0.456938 |

<details>
<summary>RD charts</summary>

The charts are rendered by `tools/report_image_benchmark.py` from `docs/image_benchmark/combined_image_metrics.csv`. The x-axis is bitrate in bpp, and each y-axis is one quality metric averaged over the combined image set.

| Chart | Chart |
| --- | --- |
| **PSNR-Y, dB**<br><img src="docs/image_benchmark/combined/charts/rd_psnr_y.svg" width="360"> | **SSIM index**<br><img src="docs/image_benchmark/combined/charts/rd_ssim.svg" width="360"> |
| **XPSNR-Y, dB**<br><img src="docs/image_benchmark/combined/charts/rd_xpsnr_y.svg" width="360"> | **VMAF score**<br><img src="docs/image_benchmark/combined/charts/rd_vmaf.svg" width="360"> |
| **MS-SSIM luma index**<br><img src="docs/image_benchmark/combined/charts/rd_msssim_luma.svg" width="360"> | **FSIM luma index**<br><img src="docs/image_benchmark/combined/charts/rd_fsim_luma.svg" width="360"> |
| **HaarPSI luma index**<br><img src="docs/image_benchmark/combined/charts/rd_haarpsi_luma.svg" width="360"> | **PSNR-HVS-M luma, dB**<br><img src="docs/image_benchmark/combined/charts/rd_psnr_hvs_m_luma.svg" width="360"> |

</details>

<details>
<summary>Standard grayscale metric-vs-QP charts</summary>

These charts are rendered from the `standard_grayscale` rows produced by `tools/image_csf_benchmark.py` and summarized by `tools/report_image_benchmark.py`. Each chart shows one measured metric as a function of QP for one image.

### baboon

| Metric vs QP | Metric vs QP |
| --- | --- |
| **PSNR-Y, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/baboon/qp_psnr_y.svg" width="360"> | **SSIM index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/baboon/qp_ssim.svg" width="360"> |
| **XPSNR-Y, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/baboon/qp_xpsnr_y.svg" width="360"> | **VMAF score**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/baboon/qp_vmaf.svg" width="360"> |
| **MS-SSIM luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/baboon/qp_msssim_luma.svg" width="360"> | **FSIM luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/baboon/qp_fsim_luma.svg" width="360"> |
| **HaarPSI luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/baboon/qp_haarpsi_luma.svg" width="360"> | **PSNR-HVS-M luma, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/baboon/qp_psnr_hvs_m_luma.svg" width="360"> |

### barbara

| Metric vs QP | Metric vs QP |
| --- | --- |
| **PSNR-Y, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/barbara/qp_psnr_y.svg" width="360"> | **SSIM index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/barbara/qp_ssim.svg" width="360"> |
| **XPSNR-Y, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/barbara/qp_xpsnr_y.svg" width="360"> | **VMAF score**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/barbara/qp_vmaf.svg" width="360"> |
| **MS-SSIM luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/barbara/qp_msssim_luma.svg" width="360"> | **FSIM luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/barbara/qp_fsim_luma.svg" width="360"> |
| **HaarPSI luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/barbara/qp_haarpsi_luma.svg" width="360"> | **PSNR-HVS-M luma, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/barbara/qp_psnr_hvs_m_luma.svg" width="360"> |

### goldhill

| Metric vs QP | Metric vs QP |
| --- | --- |
| **PSNR-Y, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/goldhill/qp_psnr_y.svg" width="360"> | **SSIM index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/goldhill/qp_ssim.svg" width="360"> |
| **XPSNR-Y, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/goldhill/qp_xpsnr_y.svg" width="360"> | **VMAF score**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/goldhill/qp_vmaf.svg" width="360"> |
| **MS-SSIM luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/goldhill/qp_msssim_luma.svg" width="360"> | **FSIM luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/goldhill/qp_fsim_luma.svg" width="360"> |
| **HaarPSI luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/goldhill/qp_haarpsi_luma.svg" width="360"> | **PSNR-HVS-M luma, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/goldhill/qp_psnr_hvs_m_luma.svg" width="360"> |

### lenna

| Metric vs QP | Metric vs QP |
| --- | --- |
| **PSNR-Y, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/lenna/qp_psnr_y.svg" width="360"> | **SSIM index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/lenna/qp_ssim.svg" width="360"> |
| **XPSNR-Y, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/lenna/qp_xpsnr_y.svg" width="360"> | **VMAF score**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/lenna/qp_vmaf.svg" width="360"> |
| **MS-SSIM luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/lenna/qp_msssim_luma.svg" width="360"> | **FSIM luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/lenna/qp_fsim_luma.svg" width="360"> |
| **HaarPSI luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/lenna/qp_haarpsi_luma.svg" width="360"> | **PSNR-HVS-M luma, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/lenna/qp_psnr_hvs_m_luma.svg" width="360"> |

### peppers

| Metric vs QP | Metric vs QP |
| --- | --- |
| **PSNR-Y, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/peppers/qp_psnr_y.svg" width="360"> | **SSIM index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/peppers/qp_ssim.svg" width="360"> |
| **XPSNR-Y, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/peppers/qp_xpsnr_y.svg" width="360"> | **VMAF score**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/peppers/qp_vmaf.svg" width="360"> |
| **MS-SSIM luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/peppers/qp_msssim_luma.svg" width="360"> | **FSIM luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/peppers/qp_fsim_luma.svg" width="360"> |
| **HaarPSI luma index**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/peppers/qp_haarpsi_luma.svg" width="360"> | **PSNR-HVS-M luma, dB**<br><img src="docs/image_benchmark/standard_grayscale/qp_charts/peppers/qp_psnr_hvs_m_luma.svg" width="360"> |


</details>

<details>
<summary>Standard grayscale partition maps</summary>

The maps are generated by `tools/build_partition_evidence.py` from VVenC `D_QP` traces at `QP=32`, `preset=medium`, and one encoded frame.

| Image | Original | Baseline | CSF |
| --- | --- | --- | --- |
| baboon | <img src="image_sets/standard_grayscale/png/baboon.png" width="180"> | <img src="docs/partition_maps/standard_grayscale/baboon_baseline.svg" width="240"> | <img src="docs/partition_maps/standard_grayscale/baboon_csf.svg" width="240"> |
| barbara | <img src="image_sets/standard_grayscale/png/barbara.png" width="180"> | <img src="docs/partition_maps/standard_grayscale/barbara_baseline.svg" width="240"> | <img src="docs/partition_maps/standard_grayscale/barbara_csf.svg" width="240"> |
| goldhill | <img src="image_sets/standard_grayscale/png/goldhill.png" width="180"> | <img src="docs/partition_maps/standard_grayscale/goldhill_baseline.svg" width="240"> | <img src="docs/partition_maps/standard_grayscale/goldhill_csf.svg" width="240"> |
| lenna | <img src="image_sets/standard_grayscale/png/lenna.png" width="180"> | <img src="docs/partition_maps/standard_grayscale/lenna_baseline.svg" width="240"> | <img src="docs/partition_maps/standard_grayscale/lenna_csf.svg" width="240"> |
| peppers | <img src="image_sets/standard_grayscale/png/peppers.png" width="180"> | <img src="docs/partition_maps/standard_grayscale/peppers_baseline.svg" width="240"> | <img src="docs/partition_maps/standard_grayscale/peppers_csf.svg" width="240"> |

</details>

## Conclusion

The benchmark pipeline verifies three things: CSF bitstreams decode through VVdeC, encoder reconstructions match decoded output, and the neutral scaling-list value `16` behaves as the default no-op matrix value. Under the fixed image/QP conditions used here, the active CSF matrix shape does not show an average quality advantage over the default encoder.
