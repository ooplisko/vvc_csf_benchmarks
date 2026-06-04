# Binaries

This directory stores the encoder and decoder executables used by the benchmark.

| Binary stem | Purpose |
| --- | --- |
| `vvenc_default` | Upstream/default VVenC encoder used as the baseline. Local build from [fraunhoferhhi/vvenc](https://github.com/fraunhoferhhi/vvenc) |
| `vvenc_csf` | Modified VVenC encoder with `--CSFScalingList` support. Local build from the [CSF VVenC branch](https://github.com/For2natop1ua/vvenc/tree/feature-branch) |
| `vvenc_default_trace` | Baseline encoder built with tracing enabled for CU partition maps. Local build from [fraunhoferhhi/vvenc](https://github.com/fraunhoferhhi/vvenc) |
| `vvenc_csf_trace` | CSF encoder built with tracing enabled for CU partition maps. Local build from the [CSF VVenC branch](https://github.com/For2natop1ua/vvenc/tree/feature-branch) |
| `vvdecapp` | VVdeC decoder used to verify generated bitstreams. Local build from [Fraunhofer HHI VVdeC](https://github.com/fraunhoferhhi/vvdec) |

On Windows the files use the `.exe` suffix, for example `vvenc_default.exe`.
On Linux/macOS the scripts expect suffixless files with the same stems, for example `vvenc_default`.
The paths in `configs/image_benchmark.ini` are written without suffixes so `vvenc_csf.core.platform_executable()` can select the correct platform name.

The current repository artifacts are Windows binaries. A Linux/macOS run requires rebuilding or copying compatible executables into this directory.
Pytest integration checks skip automatically when the required platform binaries are missing.
