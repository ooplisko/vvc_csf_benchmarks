# VTM Content-Partition Study

Versatile Video Coding (VVC) adapts coding-unit (CU) sizes and shapes to the input image and quantization parameter (QP). This study examines how source spatial detail, QP, noise and periodic interference relate to final luma CU partitioning in the [VVC Test Model (VTM) 23.0 reference encoder](https://vcgit.hhi.fraunhofer.de/jvet/VVCSoftware_VTM/-/tree/VTM-23.0).

The experiment uses all 24 [Kodak images](https://r0k.us/graphics/kodak/). It first compares clean images using Sobel-based spatial information, then adds additive white Gaussian noise (AWGN) or sinusoidal interference, and finally checks how different AWGN realizations affect the same image. Several QPs show how these relationships depend on the coding setting.

The separate [spatial-complexity study](../vtm_spatial_complexity_study/README.md) compares six descriptors with CU count and covers every Kodak condition and three AWGN realizations at QP 22, 27, 32 and 37. The present report retains the original experiment: four QPs for clean images, three QPs for the disturbance comparison and QP 32 for realization variability.

## Key Findings

- Mean CU area increases from QP 22 to QP 37 for every Kodak image. At fixed QP, the Spearman correlation of source Sobel-based spatial information with CU density ranges from 0.554 to 0.783: greater spatial detail generally accompanies more, smaller CUs.
- Partition responses depend on image content as well as disturbance type, strength and QP. Under AWGN with σ = 30 at QP 32, mean CU area increases for 15 images and decreases for 9. Under sinusoidal interference with A = 32, it increases for all 24 images at each tested disturbance QP.
- Different AWGN realizations produce different CU counts in all 72 tested image–sigma combinations at QP 32. The largest mean-normalized range is 12.293%; this is the observed maximum, not a typical response.

## Experimental Protocol

| Item | Setting |
| --- | --- |
| Encoder | VTM 23.0 `EncoderApp`, single-frame all-intra coding |
| Configuration | [`configs/vtm_encoder_intra.cfg`](../../configs/vtm_encoder_intra.cfg) |
| Dataset | All 24 Kodak images; 393,216 pixels per image |
| Input | OpenCV conversion from PNG to planar YUV 4:4:4, 8-bit input and 10-bit internal processing |
| Clean-image QPs | 22, 27, 32, 37 |
| Noise and periodic interference | Clean control; AWGN with σ = 5, 15, 30; sinusoidal interference with A = 8, 16, 32; QP 22, 32, 37 |
| AWGN realizations | σ = 5, 15, 30; PCG64 base seeds 20260811, 20260812, 20260813; QP 32 |
| CU measurement | Final leaf luma CU coordinates and dimensions from `D_QP` traces; chroma units and candidate splits are excluded |
| Consistency checks | The [decoded-output verification in the study runner](../../tools/research/run_vtm_content_partition_study.py#L313-L315) requires byte-identical decoder output and encoder reconstruction; [CU coverage validation](../../vvenc_csf/partitions.py#L36-L56) rejects gaps and overlaps |

The protocol is defined in [`vtm_content_partition_study.json`](../../configs/vtm_content_partition_study.json). Input conversion is implemented in [`ImageConverter.to_yuv444p_opencv()`](../../vvenc_csf/encoding.py), stimulus generation and Sobel measurements in [`stimuli.py`](../../vvenc_csf/stimuli.py), and CU parsing in [`partitions.py`](../../vvenc_csf/partitions.py).

## Measurements

Coding units are reported according to the terminology of [ITU-T H.266](https://www.itu.int/rec/T-REC-H.266). VVC QT/MTT partitioning produces both square and rectangular CUs. Mean CU area is the coded-frame area divided by CU count; every Kodak frame has a coded area of 393,216 pixels.

`SI_Sobel` is the population standard deviation (SD) of the magnitude of a 3 × 3 Sobel response on the Y component of the original 8-bit PNG, excluding a one-pixel border. It is computed before PNG-to-YUV conversion and before VTM encoding. The measure follows the principle of spatial information but omits the preprocessing specified by [ITU-T P.910:2023](https://www.itu.int/rec/T-REC-P.910-202310-I/en); it is therefore reported as a Sobel-based SI measure, not as a complete P.910 implementation.

`RMS(ΔY)` is the root mean square of the pixelwise Y-component difference between a disturbed image and its corresponding control, expressed in 8-bit code values.

AWGN samples are generated with NumPy PCG64 as independent zero-mean normal values with nominal standard deviation σ. The same noise field is added to the three color channels, after which values are rounded and clipped to 0–255. The stated σ describes the noise before rounding and clipping. Sinusoidal interference varies between rows and is constant along each row, producing horizontal bands with a 16-pixel period, zero initial phase and nominal peak amplitude A. It is also added equally to the three color channels; AWGN and sinusoidal interference are separate conditions.

Relative CU-area change is measured against the corresponding undisturbed control. The mean-normalized across-realization CU-count range is the difference between the largest and smallest CU counts divided by the mean of the three realizations and expressed as a percentage.

## Results

### Source Spatial Information and QP

Artifacts: [complete CU measurements for all Kodak images and QPs](tables/clean_cu_measurements.csv).

At each fixed QP, 24 paired observations were formed from source-PNG `SI_Sobel` and post-encoding CU density for the same image. CU density is CU count per million coded pixels. The Spearman rank coefficients are 0.554, 0.618, 0.710, and 0.783 at QP 22, 27, 32, and 37, respectively. Each value is one coefficient across the 24 Kodak images at a fixed QP; it is neither a per-image result nor an average of separate coefficients.

CU count decreases and mean CU area increases monotonically with QP for every image. `kodim02.png` and `kodim08.png` are shown below because they have the lowest and highest observed `SI_Sobel`, respectively.

| Lowest `SI_Sobel` | Highest `SI_Sobel` |
| :---: | :---: |
| <img src="examples/sources/kodim02.png" width="360" alt="kodim02, lowest Sobel-based SI"> | <img src="examples/sources/kodim08.png" width="360" alt="kodim08, highest Sobel-based SI"> |

<details>
<summary>Per-QP counts, mean areas and partition maps for images 02 and 08</summary>

<table align="center">
  <thead>
    <tr>
      <th align="center">Image</th>
      <th align="center">QP</th>
      <th align="center">CU count</th>
      <th align="center">Mean CU area, pixels²</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="4" align="center" valign="middle"><code>kodim02.png</code>, <code>SI_Sobel = 51.754</code></td>
      <td align="center">22</td>
      <td align="center">6,700</td>
      <td align="center">58.69</td>
    </tr>
    <tr>
      <td align="center">27</td>
      <td align="center">4,660</td>
      <td align="center">84.38</td>
    </tr>
    <tr>
      <td align="center">32</td>
      <td align="center">2,747</td>
      <td align="center">143.14</td>
    </tr>
    <tr>
      <td align="center">37</td>
      <td align="center">1,593</td>
      <td align="center">246.84</td>
    </tr>
    <tr>
      <td rowspan="4" align="center" valign="middle"><code>kodim08.png</code>, <code>SI_Sobel = 157.114</code></td>
      <td align="center">22</td>
      <td align="center">9,176</td>
      <td align="center">42.85</td>
    </tr>
    <tr>
      <td align="center">27</td>
      <td align="center">8,115</td>
      <td align="center">48.46</td>
    </tr>
    <tr>
      <td align="center">32</td>
      <td align="center">6,732</td>
      <td align="center">58.41</td>
    </tr>
    <tr>
      <td align="center">37</td>
      <td align="center">5,296</td>
      <td align="center">74.25</td>
    </tr>
  </tbody>
</table>

At QP 32, the mean CU area of `kodim08.png` is 59.2% smaller than that of `kodim02.png`. The QP effect also differs by content: mean CU area grows by a factor of 4.21 from QP 22 to QP 37 for `kodim02.png`, compared with 1.73 for `kodim08.png`.

The CU boundaries below are reconstructed directly from VTM partition traces.

| QP | `kodim02.png` | `kodim08.png` |
| :---: | :---: | :---: |
| 22 | <img src="examples/partition_maps/complexity/kodim02/QP22.png" width="360" alt="kodim02 CU partition map at QP 22"> | <img src="examples/partition_maps/complexity/kodim08/QP22.png" width="360" alt="kodim08 CU partition map at QP 22"> |
| 27 | <img src="examples/partition_maps/complexity/kodim02/QP27.png" width="360" alt="kodim02 CU partition map at QP 27"> | <img src="examples/partition_maps/complexity/kodim08/QP27.png" width="360" alt="kodim08 CU partition map at QP 27"> |
| 32 | <img src="examples/partition_maps/complexity/kodim02/QP32.png" width="360" alt="kodim02 CU partition map at QP 32"> | <img src="examples/partition_maps/complexity/kodim08/QP32.png" width="360" alt="kodim08 CU partition map at QP 32"> |
| 37 | <img src="examples/partition_maps/complexity/kodim02/QP37.png" width="360" alt="kodim02 CU partition map at QP 37"> | <img src="examples/partition_maps/complexity/kodim08/QP37.png" width="360" alt="kodim08 CU partition map at QP 37"> |

</details>

### Noise and Periodic Interference

Artifacts: [complete CU measurements for every image, disturbance, level, and QP](tables/interference_cu_measurements.csv) and [full 24-image response chart](figures/interference_cu_area_change.png).

Here, *disturbance* covers two distinct additive signals: stochastic AWGN and deterministic spatial sinusoidal interference. The chart reports each of the 24 Kodak images separately. Each line connects the three tested levels for one image; the horizontal zero line is the corresponding undisturbed control reference. Positive values indicate larger mean CUs than the control, while negative values indicate smaller mean CUs.

<p align="center">
  <img src="figures/interference_cu_area_change.png" width="100%" alt="Relative mean-CU-area change for all Kodak images">
</p>

The AWGN response is heterogeneous. At σ = 30 and QP 32, mean CU area increases for 15 images and decreases for 9. At σ = 15 and QP 37, it decreases for all 24 images. For the strongest tested sinusoidal interference, A = 32, mean CU area increases for every image at each tested QP. The partition response therefore depends jointly on disturbance type, disturbance level, QP, and image content.

<details>
<summary>Kodim20: inputs and partition maps at each disturbance level</summary>

`kodim20.png` illustrates the complete sequence of disturbance levels. The values below are specific to this image and are not presented as aggregate Kodak results.

| Disturbance | Nominal level | `RMS(ΔY)` | QP 22: CU count / mean area | QP 32: CU count / mean area | QP 37: CU count / mean area |
| :---: | :---: | :---: | :---: | :---: | :---: |
| Control | 0 | 0.000 | 3,991 / 98.53 | 2,611 / 150.60 | 1,912 / 205.66 |
| AWGN | σ = 5 | 4.379 | 4,878 / 80.61 | 2,688 / 146.29 | 1,952 / 201.44 |
| AWGN | σ = 15 | 12.922 | 5,498 / 71.52 | 3,467 / 113.42 | 2,424 / 162.22 |
| AWGN | σ = 30 | 25.212 | 6,360 / 61.83 | 3,772 / 104.25 | 2,919 / 134.71 |
| Sinusoidal interference | A = 8 | 4.905 | 3,926 / 100.16 | 2,682 / 146.61 | 1,913 / 205.55 |
| Sinusoidal interference | A = 16 | 9.810 | 3,736 / 105.25 | 2,521 / 155.98 | 1,868 / 210.50 |
| Sinusoidal interference | A = 32 | 19.581 | 3,406 / 115.45 | 2,390 / 164.53 | 1,803 / 218.09 |

Stimuli

| Control | AWGN, σ = 5 | AWGN, σ = 15 | AWGN, σ = 30 |
| :---: | :---: | :---: | :---: |
| <img src="examples/stimuli/interference/kodim20/without_interference.png" width="220" alt="kodim20 control"> | <img src="examples/stimuli/interference/kodim20/awgn_sigma_5.png" width="220" alt="kodim20 with AWGN sigma 5"> | <img src="examples/stimuli/interference/kodim20/awgn_sigma_15.png" width="220" alt="kodim20 with AWGN sigma 15"> | <img src="examples/stimuli/interference/kodim20/awgn_sigma_30.png" width="220" alt="kodim20 with AWGN sigma 30"> |

| Control | Sinusoidal interference, A = 8 | A = 16 | A = 32 |
| :---: | :---: | :---: | :---: |
| <img src="examples/stimuli/interference/kodim20/without_interference.png" width="220" alt="kodim20 control"> | <img src="examples/stimuli/interference/kodim20/stripes_amplitude_8.png" width="220" alt="kodim20 with sinusoidal interference amplitude 8"> | <img src="examples/stimuli/interference/kodim20/stripes_amplitude_16.png" width="220" alt="kodim20 with sinusoidal interference amplitude 16"> | <img src="examples/stimuli/interference/kodim20/stripes_amplitude_32.png" width="220" alt="kodim20 with sinusoidal interference amplitude 32"> |

CU partition-map overlays

| QP | Control | AWGN, σ = 30 | Sinusoidal interference, A = 32 |
| :---: | :---: | :---: | :---: |
| 22 | <img src="examples/partition_maps/interference/kodim20/QP22/without_interference.png" width="300" alt="kodim20 control partition map at QP 22"> | <img src="examples/partition_maps/interference/kodim20/QP22/awgn_sigma_30.png" width="300" alt="kodim20 AWGN sigma 30 partition map at QP 22"> | <img src="examples/partition_maps/interference/kodim20/QP22/stripes_amplitude_32.png" width="300" alt="kodim20 sinusoidal interference amplitude 32 partition map at QP 22"> |
| 32 | <img src="examples/partition_maps/interference/kodim20/QP32/without_interference.png" width="300" alt="kodim20 control partition map at QP 32"> | <img src="examples/partition_maps/interference/kodim20/QP32/awgn_sigma_30.png" width="300" alt="kodim20 AWGN sigma 30 partition map at QP 32"> | <img src="examples/partition_maps/interference/kodim20/QP32/stripes_amplitude_32.png" width="300" alt="kodim20 sinusoidal interference amplitude 32 partition map at QP 32"> |
| 37 | <img src="examples/partition_maps/interference/kodim20/QP37/without_interference.png" width="300" alt="kodim20 control partition map at QP 37"> | <img src="examples/partition_maps/interference/kodim20/QP37/awgn_sigma_30.png" width="300" alt="kodim20 AWGN sigma 30 partition map at QP 37"> | <img src="examples/partition_maps/interference/kodim20/QP37/stripes_amplitude_32.png" width="300" alt="kodim20 sinusoidal interference amplitude 32 partition map at QP 37"> |

</details>

### AWGN Realization Variability

Artifacts: [per-realization CU measurements](tables/awgn_realization_cu_measurements.csv), [per-image variability summary](tables/awgn_realization_variability.csv), and [full 24-image variability chart](figures/awgn_realization_cu_count_variability.png).

Each Kodak image was encoded at QP 32 for three nominal σ values and three PCG64 base seeds. All 72 `image × σ` combinations produce non-identical CU counts across the three realizations. The mean-normalized CU-count range is 0.937–8.158% at σ = 5, 0.639–9.955% at σ = 15, and 1.034–12.293% at σ = 30.

<p align="center">
  <img src="figures/awgn_realization_cu_count_variability.png" width="100%" alt="Across-realization CU-count variability for all Kodak images">
</p>

This result shows that a reproducible statement about AWGN for a specific image and QP must either identify the noise-field realization or summarize multiple realizations.

<details>
<summary>Kodim02: the largest observed across-realization range</summary>

The largest observed range occurs for `kodim02.png` at σ = 30. This case was selected after analyzing all 72 combinations to illustrate the maximum observed variability; it is not presented as a typical Kodak response.

| PCG64 base seed | `RMS(ΔY)` | CU count | Mean CU area, pixels² |
| :---: | :---: | :---: | :---: |
| 20260811 | 28.670 | 2,687 | 146.34 |
| 20260812 | 28.658 | 2,448 | 160.63 |
| 20260813 | 28.682 | 2,772 | 141.85 |

| 20260811 | 20260812 | 20260813 |
| :---: | :---: | :---: |
| <img src="examples/stimuli/noise_realizations/kodim02/sigma_30_seed_20260811.png" width="300" alt="kodim02 AWGN sigma 30, base seed 20260811"> | <img src="examples/stimuli/noise_realizations/kodim02/sigma_30_seed_20260812.png" width="300" alt="kodim02 AWGN sigma 30, base seed 20260812"> | <img src="examples/stimuli/noise_realizations/kodim02/sigma_30_seed_20260813.png" width="300" alt="kodim02 AWGN sigma 30, base seed 20260813"> |
| <img src="examples/partition_maps/noise_realizations/kodim02/QP32/sigma_30_seed_20260811.png" width="300" alt="kodim02 partition map for base seed 20260811"> | <img src="examples/partition_maps/noise_realizations/kodim02/QP32/sigma_30_seed_20260812.png" width="300" alt="kodim02 partition map for base seed 20260812"> | <img src="examples/partition_maps/noise_realizations/kodim02/QP32/sigma_30_seed_20260813.png" width="300" alt="kodim02 partition map for base seed 20260813"> |

</details>

## Interpretation and Limitations

The results connect source detail and coding settings with the partition selected by VTM. CU count and mean CU area describe the final partition; they are not direct measurements of reconstructed-image quality, compressed size or encoder search cost.

The same RGB noise field changes only luma before rounding and clipping, while subsequent processing can also affect chroma. Channel-independent noise was not evaluated. The sinusoid has one orientation, period and phase. Three AWGN realizations at QP 32 demonstrate realization dependence but do not describe its full distribution. Repeated conditions do not increase the independent sample beyond 24 images.

The conclusions concern these Kodak images and this VTM configuration. Other image domains, VVC implementations and inter-frame coding need their own checks. The [six-descriptor comparison](../vtm_spatial_complexity_study/README.md) examines the related question of which whole-image measures remain associated with CU count across QPs, noise and periodic interference.

## Reproduction

Run commands from the repository root. With completed encoding results available locally, regenerate this study's CSV files, charts and example maps:

```powershell
python tools/reporting/report_vtm_content_partition_study.py
```

This reporter reads `results/vtm_content_partition_study/` and writes artifacts into `docs/vtm_content_partition_study/`. The README is maintained alongside the results. Reading the committed tables and figures does not require encoding again.

<details>
<summary>Run the full original experiment from a fresh clone</summary>

Install the Python dependencies listed in the root README, then download the codec binaries and run the original protocol:

```powershell
python tools/data_prep/download_binaries.py
python tools/research/run_vtm_content_partition_study.py all
python tools/reporting/report_vtm_content_partition_study.py
```

Intermediate bitstreams, reconstructions, traces, and progress files are written under `results/`.

</details>

For the separate four-QP descriptor comparison, use its own [reproduction commands](../vtm_spatial_complexity_study/README.md#reproduction).
