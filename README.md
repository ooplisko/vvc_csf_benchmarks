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

**O. O. Plisko** - [Department of Information and Communication Technologies](https://dict.khai.edu/), National Aerospace University "Kharkiv Aviation Institute"

Image-only benchmark for a custom Contrast Sensitivity Function (CSF) scaling-list modification in VVenC. The repository contains pinned binaries, image sets, scripts, generated metric tables, RD charts, matrix evidence, and Coding Unit (CU) partition maps.

## Status

| Item | Current state |
| --- | --- |
| Primary control images | 5 standard grayscale images: BABOON, BARBARA, goldhill, lenna, peppers |
| Additional images | 4 synthetic images and 24 Kodak images |
| QP points | 22, 27, 32, 37 |
| Compared modes | `vvenc_default` vs `vvenc_csf --CSFScalingList 1` (`.exe` suffix on Windows) |
| Neutral value check | `16` verified from VVenC source and by a practical CSF-off control run |
| Current outcome | CSF bitstreams decode correctly and reconstruction checks pass, but the current CSF matrix does not outperform the default encoder on average |

## Documentation

| Document | Content |
| --- | --- |
| [Full benchmark report](docs/image_benchmark_report.md) | Binaries, matrices, reproduce steps, metrics, tables, charts, and partition maps |
| [Neutral 16 source verification](docs/matrices/neutral_16_verification.md) | Why scaling-list value `16` is neutral in the current VVenC code |
| [Neutral 16 control run](docs/matrices/neutral_16_control.md) | Default encoder vs CSF encoder with `--CSFScalingList 0`, compared byte-for-byte |
| [Combined metrics CSV](docs/image_benchmark/combined_image_metrics.csv) | All image/QP/mode measurements |
| [BD-Rate summary CSV](docs/image_benchmark/combined/bd_rate_summary.csv) | Equal-quality bitrate comparison between baseline and CSF |
| [Partition summary CSV](docs/partition_maps/summary.csv) | CU counts and dominant block sizes |
| [Citation metadata](CITATION.cff) | Citation information for academic use |

## Repository Layout

| Path | Purpose |
| --- | --- |
| `binaries/` | Encoder and decoder binaries used by the benchmark; see `binaries/README.md` |
| `image_sets/` | Primary grayscale, synthetic, and Kodak inputs; see `image_sets/README.md` |
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
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run_all.py quick --clean
```

`ffmpeg`, `ffprobe`, and `curl` must be available in `PATH`. On Windows, `curl.exe` is used automatically. The `.venv` and `results/` directories are local and are not committed. `quick` runs console sanity checks: smoke encode/decode and neutral-16 verification. `full` runs all image benchmarks and regenerates CSV/XLSX reports, charts, partition maps, and Markdown documentation.

Benchmark defaults are stored in `configs/image_benchmark.ini`. Binary paths are configured without a file suffix; the scripts add `.exe` on Windows and use suffixless names on Linux/macOS. Command-line arguments still override the config values.

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
| Full run | `.\.venv\Scripts\python.exe run_all.py full --clean` | Runs encoders, decoder checks, metrics, CSV/XLSX summaries, charts, partition maps, and Markdown rendering |
| Re-render reports only | `.\.venv\Scripts\python.exe tools\report_image_benchmark.py docs\image_benchmark\combined_image_metrics.csv --output docs\image_benchmark\combined --xlsx` | Regenerates summary CSVs, XLSX, RD charts, and per-image QP charts from an existing metrics CSV |
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

BD-Rate is generated from the same metrics CSV and compares CSF against baseline at equal quality. Negative BD-Rate means bitrate saving by CSF; positive BD-Rate means extra bitrate is needed for the same metric level.

| Metric | Valid images | BD-Rate mean, % | BD-Rate min, % | BD-Rate max, % | BD quality mean |
| --- | --- | --- | --- | --- | --- |
| PSNR-Y | 33 | 18.675 | 5.678 | 254.387 | -0.893396 |
| SSIM | 33 | 20.118 | 3.592 | 321.259 | -0.003456 |
| XPSNR-Y | 33 | 18.757 | 5.423 | 266.394 | -0.781452 |
| VMAF | 33 | 12.921 | -4.767 | 313.512 | -0.114842 |
| MS-SSIM | 33 | 15.224 | 1.969 | 276.946 | -0.000111 |
| FSIM | 33 | 21.089 | 6.181 | 275.315 | -0.005387 |
| HaarPSI | 33 | 23.992 | 7.965 | 284.523 | -0.004731 |
| PSNR-HVS-M | 33 | 18.582 | 5.481 | 254.424 | -0.733127 |

<details>
<summary>Show BD-Rate per image</summary>

| Dataset | Image | PSNR-Y, % | SSIM, % | XPSNR-Y, % | VMAF, % | MS-SSIM, % | FSIM, % | HaarPSI, % | PSNR-HVS-M, % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Standard grayscale | baboon | 10.014 | 9.433 | 10.058 | 0.115 | 3.222 | 11.463 | 15.081 | 9.729 |
| Standard grayscale | barbara | 13.160 | 9.491 | 12.171 | 0.297 | 4.442 | 13.564 | 18.828 | 12.382 |
| Standard grayscale | goldhill | 9.410 | 8.727 | 9.062 | 4.543 | 5.335 | 10.478 | 12.532 | 9.271 |
| Standard grayscale | lenna | 10.490 | 9.901 | 10.206 | 7.566 | 7.810 | 12.213 | 13.861 | 10.271 |
| Standard grayscale | peppers | 15.102 | 18.025 | 14.832 | 3.760 | 6.046 | 11.730 | 20.528 | 15.379 |
| Synthetic | fine_texture_512x512 | 28.814 | 52.701 | 29.016 | 1.697 | 26.928 | 49.964 | 55.274 | 28.541 |
| Synthetic | mixed_content_512x512 | 32.919 | 34.768 | 34.015 | 34.928 | 38.323 | 37.607 | 39.866 | 35.097 |
| Synthetic | sharp_edges_512x512 | 31.362 | 33.872 | 31.966 | 34.428 | 35.480 | 33.683 | 33.530 | 33.010 |
| Synthetic | smooth_gradient_512x512 | 254.387 | 321.259 | 266.394 | 313.512 | 276.946 | 275.315 | 284.523 | 254.424 |
| Kodak | kodim01 | 9.251 | 8.590 | 8.893 | -1.231 | 3.506 | 11.185 | 13.321 | 9.051 |
| Kodak | kodim02 | 9.214 | 7.707 | 8.827 | -1.169 | 5.239 | 10.718 | 13.544 | 8.969 |
| Kodak | kodim03 | 9.640 | 8.458 | 8.802 | 2.885 | 6.451 | 12.301 | 14.450 | 9.468 |
| Kodak | kodim04 | 10.650 | 7.384 | 10.105 | -4.767 | 4.124 | 11.395 | 16.391 | 10.424 |
| Kodak | kodim05 | 5.678 | 3.592 | 5.423 | 0.661 | 2.009 | 6.181 | 7.965 | 5.481 |
| Kodak | kodim06 | 9.925 | 7.828 | 9.543 | 2.228 | 3.593 | 10.866 | 13.420 | 9.696 |
| Kodak | kodim07 | 5.941 | 4.239 | 5.700 | 3.771 | 4.765 | 7.157 | 8.344 | 5.891 |
| Kodak | kodim08 | 8.029 | 4.750 | 7.834 | 0.771 | 1.969 | 7.718 | 11.313 | 7.761 |
| Kodak | kodim09 | 9.144 | 7.599 | 8.945 | 6.099 | 6.095 | 9.493 | 11.643 | 8.848 |
| Kodak | kodim10 | 7.575 | 5.254 | 7.201 | 1.937 | 4.910 | 7.397 | 9.103 | 7.358 |
| Kodak | kodim11 | 8.372 | 6.809 | 7.965 | 2.547 | 3.574 | 8.519 | 11.211 | 8.050 |
| Kodak | kodim12 | 9.675 | 8.403 | 9.298 | 3.121 | 5.442 | 10.250 | 12.439 | 9.680 |
| Kodak | kodim13 | 8.787 | 7.859 | 8.813 | -0.269 | 2.402 | 11.141 | 12.971 | 8.495 |
| Kodak | kodim14 | 7.104 | 5.404 | 6.809 | 1.895 | 2.919 | 7.778 | 9.498 | 6.874 |
| Kodak | kodim15 | 10.815 | 8.548 | 9.699 | 3.376 | 4.681 | 12.962 | 15.261 | 10.486 |
| Kodak | kodim16 | 10.300 | 8.764 | 10.071 | -0.554 | 4.512 | 11.322 | 14.403 | 10.091 |
| Kodak | kodim17 | 6.409 | 5.445 | 5.869 | 6.308 | 4.267 | 7.489 | 9.039 | 5.988 |
| Kodak | kodim18 | 8.356 | 4.834 | 7.633 | -1.985 | 2.916 | 8.964 | 11.399 | 8.062 |
| Kodak | kodim19 | 9.917 | 8.810 | 10.500 | 0.273 | 2.966 | 12.982 | 14.702 | 9.925 |
| Kodak | kodim20 | 10.526 | 10.746 | 10.331 | -0.580 | 5.167 | 13.919 | 15.113 | 10.821 |
| Kodak | kodim21 | 8.862 | 6.396 | 8.661 | -0.918 | 3.758 | 10.361 | 12.424 | 8.609 |
| Kodak | kodim22 | 9.355 | 6.505 | 8.797 | -3.218 | 3.099 | 11.815 | 14.651 | 9.149 |
| Kodak | kodim23 | 9.227 | 6.983 | 8.511 | 4.626 | 6.758 | 10.317 | 13.566 | 8.697 |
| Kodak | kodim24 | 7.866 | 4.825 | 7.028 | -0.271 | 2.752 | 7.681 | 11.523 | 7.218 |

</details>

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

## How to Extend

This benchmark is designed to be easily extensible. You can customize the image inputs or add new visual quality metrics.

### Adding a Custom Image Set
1. Create a subdirectory under `image_sets/` containing your input images in PNG format (e.g., `image_sets/custom_set/png/`).
2. Update the paths in `configs/image_benchmark.ini` or pass your custom directory via the `--smoke-dir`, `--synthetic-dir`, or `--kodak-dir` CLI arguments when invoking `run_all.py`.

### Adding a Custom Quality Metric
1. Implement the luma metric calculation function in `metrics/image_quality.py`.
2. Update the `calculate_luma_metrics()` function in `metrics/image_quality.py` to execute your new metric and append its score to the returned dictionary.
3. Add your metric's internal key and label to the `METRICS` list and `METRIC_LABELS` dictionary in `tools/report_image_benchmark.py` and `tools/render_readme.py` to include it in the generated CSV/XLSX summaries and RD charts.

## Conclusion

The benchmark pipeline verifies three things: CSF bitstreams decode through VVdeC, encoder reconstructions match decoded output, and the neutral scaling-list value `16` behaves as the default no-op matrix value. Under the fixed image/QP conditions used here, the active CSF matrix shape does not show an average quality advantage over the default encoder.
