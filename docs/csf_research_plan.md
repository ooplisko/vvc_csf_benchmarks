# CSF research notes

## Scaling matrices

The default VVenC quantization path uses a neutral scaling value of `16` for each coefficient when no explicit scaling list is applied.

The CSF branch uses an 8x8 table from `source/Lib/CommonLib/CSFWeights.h`. For the encoder-side quantization arrays, the table is mapped to the active transform/scaling-list size in `Quant::xSetCSFScalingList`.

For sizes larger than 8x8, the implementation maps coefficient positions back to an 8x8 frequency grid. For 16x16 and 32x32 this means multiple coefficient positions share the same CSF value. Coefficients outside the VVC zero-out threshold are set to `0` in the internal quant/dequant arrays.

Generate the documented matrices:

```powershell
.\.venv\Scripts\python.exe tools\dump_csf_matrices.py --output docs\matrices
```

The generated files include:

```text
docs/matrices/default_8x8.csv
docs/matrices/csf_8x8.csv
docs/matrices/default_16x16.csv
docs/matrices/csf_16x16.csv
docs/matrices/default_32x32.csv
docs/matrices/csf_32x32.csv
```

## Image/block partitioning

VVenC/VVC does not encode an image as one monolithic transform block. Pictures are partitioned into CTUs, then coding units and transform units. The relevant low-level controls are `CTUSize`, `MinQT*`, `MaxMTTDepth*`, `MaxBT*`, `MaxTT*`, and `Log2MaxTbSize`.

The current project does not yet export a real per-picture CU/TU partition map. The map is possible, but it requires either encoder instrumentation around final `CodingStructure::cus/tus` after CTU encoding, or a tracing-enabled build with post-processing. A practical target format is CSV:

```text
poc,ctu_x,ctu_y,type,x,y,width,height,depth,mode,qp
```

This can then be rendered as an SVG/PNG block map.

## Compression degree

For a fixed image/video, fixed preset, fixed frame count, fixed chroma format and fixed bit depth, the single compression-control parameter in the current experiments is:

```text
QP
```

The compression degree is reported as:

```text
compression_ratio = raw_input_bytes / bitstream_bytes
bpp = bitstream_bytes * 8 / (width * height * frames)
```

For 8-bit 4:2:0 YUV:

```text
raw_input_bytes = width * height * 3 / 2 * frames
```

When QP increases, quantization becomes coarser, bitrate usually decreases, compression ratio increases, and quality metrics usually decrease.

## Visual-quality experiment

The standard PSNR-based RD test is not enough for a perceptual CSF modification. A fair follow-up should keep all encoder settings fixed except QP and collect visual metrics for baseline and CSF:

```text
dataset: Kodak or CLIC subset
codec parameter: QP = 22, 27, 32, 37
modes: --CSFScalingList 0 and --CSFScalingList 1
metrics: PSNR-Y, SSIM, XPSNR, VMAF if available
rate: bpp and compression_ratio
```

VVenC writes reconstruction files in the internal 10-bit format in this configuration. Therefore FFmpeg visual-metric comparisons read the source as `yuv420p` and the reconstruction as `yuv420p10le`.

Run an image-only Kodak benchmark:

```powershell
.\.venv\Scripts\python.exe tools\image_csf_benchmark.py `
  --root results\image_kodak `
  --encoder binaries\vvencFFapp.exe `
  --decoder binaries\vvdecapp.exe `
  --download-kodak
```

The output CSV is:

```text
results/image_kodak/image_metrics.csv
```
