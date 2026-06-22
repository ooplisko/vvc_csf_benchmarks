# VTM Partition Maps

VTM partition maps are generated from `D_QP` trace output produced by trace-enabled VTM 23.0 encoders:

```text
binaries/vtm/vtm23/baseline_trace/EncoderApp
binaries/vtm/vtm23/csf_trace/EncoderApp
```

The trace parser reads final luma CU lines in the form `x=..., y=..., w=..., h=..., qp=...`. Chroma-specific trace lines are ignored. The normal clean decoder remains `binaries/vtm/vtm23/baseline/DecoderApp`; a CSF decoder is not required because the CSF change is encoder-side and must produce a bitstream accepted by the clean decoder.

Generate the VTM partition maps through the full VTM benchmark:

```powershell
python run_all.py full --codec vtm --clean
```

For a short smoke run against the first image of each dataset:

```powershell
python tools\visualization\build_partition_evidence.py --codec vtm --limit 1 --output results\partition_smoke\vtm_docs --work-dir results\partition_smoke\vtm
```
