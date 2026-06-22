# Binaries

This directory stores the encoder and decoder executables used by the benchmark.

To keep the git repository lightweight, the compiled `.exe` files are **not tracked in git**. Instead, they are distributed via GitHub Releases as `binaries.zip`.

## Option A: Download Binaries (Recommended)
If you have just cloned the repository, download all pre-compiled Windows binaries from the GitHub Release using the provided script:

```powershell
python tools/data_prep/download_binaries.py
```

The release archive contains the top-level `binaries/` folder. Manual installation is also valid: download `binaries.zip` from GitHub Releases and extract it into the repository root.

## Option B: Compile Manually
If you are on Linux/macOS, or want to compile the executables yourself, place the suffixless binaries (or `.exe` on Windows) under codec-specific subdirectories:

| Binary stem | Purpose |
| --- | --- |
| `vvenc/vvenc_default` | Upstream/default VVenC encoder used as the baseline. Local build from [fraunhoferhhi/vvenc](https://github.com/fraunhoferhhi/vvenc) |
| `vvenc/vvenc_csf` | Modified VVenC encoder with `--CSFScalingList` support. Local build from the [CSF VVenC branch](https://github.com/For2natop1ua/vvenc/tree/feature-branch) |
| `vvenc/vvenc_default_trace` | Baseline VVenC encoder built with tracing enabled for CU partition maps. |
| `vvenc/vvenc_csf_trace` | CSF VVenC encoder built with tracing enabled for CU partition maps. |
| `vvenc/vvdecapp` | VVdeC decoder used to verify generated VVenC bitstreams. Local build from [Fraunhofer HHI VVdeC](https://github.com/fraunhoferhhi/vvdec) |
| `vtm/vtm18/baseline/EncoderApp` | Clean VTM 18.0 encoder used only by the historical Kodak validation against Duan et al. anchors. |
| `vtm/vtm18/baseline/DecoderApp` | Clean VTM 18.0 decoder used only by the historical Kodak validation. |
| `vtm/vtm23/baseline/EncoderApp` | Clean VTM 23.0 encoder from the official JVET `VTM-23.0` tag. |
| `vtm/vtm23/baseline/DecoderApp` | Clean VTM 23.0 decoder used for normative cross-checks, including CSF bitstreams. |
| `vtm/vtm23/csf/EncoderApp` | Modified VTM 23.0 encoder with `--CSFScalingList=1` support. |
| `vtm/vtm23/baseline_trace/EncoderApp` | Clean VTM 23.0 encoder built with tracing enabled for CU partition maps. |
| `vtm/vtm23/csf_trace/EncoderApp` | Modified VTM 23.0 encoder built with tracing enabled for CU partition maps. |

The VTM CSF change is encoder-side: the modified encoder writes scaling-list data into the bitstream, and the clean VTM 23.0 decoder must decode it. A CSF-specific decoder is intentionally not built or stored.

### Build Helpers

VVenC and VTM encoder binaries are built through helper scripts:

```powershell
python tools\building\build_vvenc.py all
python tools\building\build_vtm.py all
```

`build_vvenc.py all` builds and copies:

```text
binaries/vvenc/vvenc_default.exe
binaries/vvenc/vvenc_csf.exe
binaries/vvenc/vvenc_default_trace.exe
binaries/vvenc/vvenc_csf_trace.exe
```

`build_vtm.py all` builds and copies:

```text
binaries/vtm/vtm18/baseline/EncoderApp.exe
binaries/vtm/vtm18/baseline/DecoderApp.exe
binaries/vtm/vtm23/baseline/EncoderApp.exe
binaries/vtm/vtm23/baseline/DecoderApp.exe
binaries/vtm/vtm23/csf/EncoderApp.exe
binaries/vtm/vtm23/baseline_trace/EncoderApp.exe
binaries/vtm/vtm23/csf_trace/EncoderApp.exe
```

Individual targets are also available:

```powershell
python tools\building\build_vvenc.py vvenc-default
python tools\building\build_vvenc.py vvenc-csf
python tools\building\build_vvenc.py vvenc-default-trace
python tools\building\build_vvenc.py vvenc-csf-trace

python tools\building\build_vtm.py vtm18-validation
python tools\building\build_vtm.py vtm23-baseline
python tools\building\build_vtm.py vtm23-csf
python tools\building\build_vtm.py vtm23-baseline-trace
python tools\building\build_vtm.py vtm23-csf-trace
```

The trace encoders are used only for CU partition maps. They are intentionally separated from the normal RD-metric binaries.

### Release Archive

Create the release archive after building binaries:

```powershell
python tools\building\package_binaries.py
```

This writes `dist/binaries.zip` with the complete `binaries/` folder inside it. Upload this ZIP as the `binaries.zip` asset for the matching GitHub Release.

### Compilation Commands Example (Windows)
```powershell
# VVenC encoders, including trace builds.
python tools\building\build_vvenc.py all

# VVdeC decoder for VVenC bitstreams
git clone https://github.com/fraunhoferhhi/vvdec ..\vvdec
cd ..\vvdec
cmake -S . -B build\release -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release -DVVDEC_ENABLE_LINK_TIME_OPT=OFF
cmake --build build\release --target vvdecapp --parallel 8
Copy-Item bin\release-static\vvdecapp.exe ..\vvenc_csf_tests\binaries\vvenc\vvdecapp.exe

# VTM encoders/decoders, including trace builds.
python tools\building\build_vtm.py all
```

## How Path Resolution Works
On Windows the files use the `.exe` suffix, for example `vvenc/vvenc_default.exe`.
On Linux/macOS the scripts expect suffixless files with the same stems, for example `vvenc/vvenc_default`.
The paths in `configs/image_benchmark.ini` are written without suffixes so the framework can select the correct platform name automatically.
