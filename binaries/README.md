# Binaries

This directory stores the encoder and decoder executables used by the benchmark.

To keep the git repository lightweight, the compiled `.exe` files are **not tracked in git**. Instead, they should be managed via GitHub Releases.

## Option A: Download Binaries (Recommended)
If you have just cloned the repository, you can automatically download all pre-compiled Windows binaries (VVenC baseline, VVenC CSF, VVdeC, VTM) from the GitHub Release using the provided script:

```powershell
python tools/data_prep/download_binaries.py
```

## Option B: Compile Manually
If you are on Linux/macOS, or want to compile the executables yourself, place the suffixless binaries (or `.exe` on Windows) with the following stems in this directory:

| Binary stem | Purpose |
| --- | --- |
| `vvenc_default` | Upstream/default VVenC encoder used as the baseline. Local build from [fraunhoferhhi/vvenc](https://github.com/fraunhoferhhi/vvenc) |
| `vvenc_csf` | Modified VVenC encoder with `--CSFScalingList` support. Local build from the [CSF VVenC branch](https://github.com/For2natop1ua/vvenc/tree/feature-branch) |
| `vvenc_default_trace` | Baseline encoder built with tracing enabled for CU partition maps. |
| `vvenc_csf_trace` | CSF encoder built with tracing enabled for CU partition maps. |
| `vvdecapp` | VVdeC decoder used to verify generated bitstreams. Local build from [Fraunhofer HHI VVdeC](https://github.com/fraunhoferhhi/vvdec) |
| `vtm/EncoderApp` | VTM encoder used for baseline comparisons against published papers. |
| `vtm/DecoderApp` | VTM decoder. |

### Compilation Commands Example (Windows)
```powershell
# Default encoder
git clone https://github.com/fraunhoferhhi/vvenc ..\vvenc_upstream
cd ..\vvenc_upstream
git checkout 6f76748
cmake -S . -B build\release -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release -DVVENC_ENABLE_LINK_TIME_OPT=OFF
cmake --build build\release --target vvencFFapp --parallel 8
Copy-Item bin\release-static\vvencFFapp.exe ..\vvenc_csf_tests\binaries\vvenc_default.exe
```

## How Path Resolution Works
On Windows the files use the `.exe` suffix, for example `vvenc_default.exe`.
On Linux/macOS the scripts expect suffixless files with the same stems, for example `vvenc_default`.
The paths in `configs/image_benchmark.ini` are written without suffixes so the framework can select the correct platform name automatically.
