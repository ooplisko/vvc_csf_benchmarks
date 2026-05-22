# VVenC CSF Image Benchmark

Цей репозиторій містить image-only перевірку кастомної CSF scaling-list модифікації для VVenC. Тут зібрані бінарники, синтетичні та Kodak-зображення, скрипти прогону, таблиці метрик, RD-чарти й карти розбиття зображень на Coding Unit (CU).

## 1. Структура

| Шлях | Призначення |
| --- | --- |
| `binaries/` | Відтворювані encoder/decoder binaries для цього експерименту. |
| `image_sets/synthetic/png/` | 4 синтетичні PNG-зображення: gradient, texture, edges, mixed content. |
| `image_sets/kodak/png/` | 24 PNG-зображення Kodak image suite. |
| `tools/` | Скрипти генерації зображень, прогону benchmark, звітів, матриць і partition maps. |
| `metrics/image_quality.py` | In-repo luma-реалізації MS-SSIM, FSIM, HaarPSI та PSNR-HVS-M-подібних метрик. |
| `docs/matrices/` | CSV-знімки default/CSF scaling matrices для читання й перевірки; джерелом істини лишається encoder. |
| `docs/image_benchmark/` | CSV-результати, summary-таблиці й RD-чарти. |
| `docs/partition_maps/` | CSV/SVG карти CU-розбиття для synthetic і Kodak. |

## 2. Бінарники

| Файл | Для чого використовується |
| --- | --- |
| `binaries/vvenc_default.exe` | Чистий upstream/default VVenC encoder, без CSF. |
| `binaries/vvenc_csf.exe` | Модифікований VVenC encoder; CSF вмикається через `--CSFScalingList 1`. |
| `binaries/vvenc_default_trace.exe` | Чистий upstream encoder із `VVENC_ENABLE_TRACING=ON`, тільки для карт розбиття. |
| `binaries/vvenc_csf_trace.exe` | CSF encoder із `VVENC_ENABLE_TRACING=ON`, тільки для карт розбиття. |
| `binaries/vvdecapp.exe` | VVdeC decoder для перевірки bitstream/decode. |

Binaries у `binaries/` відповідають двом VVenC деревам: upstream/default VVenC та модифікованій гілці `feature-branch`. Для повторення поточного аналізу достатньо файлів із цієї директорії; локальні шляхи середовища збірки не використовуються.

Якщо потрібно перебудувати binaries самостійно:

```powershell
# default encoder
git clone https://github.com/fraunhoferhhi/vvenc ..\vvenc_upstream
cd ..\vvenc_upstream
git checkout 6f76748
cmake -S . -B build\release -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release -DVVENC_ENABLE_LINK_TIME_OPT=OFF
cmake --build build\release --target vvencFFapp --parallel 8
Copy-Item bin\release-static\vvencFFapp.exe ..\vvenc_csf_tests\binaries\vvenc_default.exe

# default trace encoder for partition maps
cmake -S . -B build\trace -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release -DVVENC_ENABLE_TRACING=ON -DVVENC_ENABLE_LINK_TIME_OPT=OFF
cmake --build build\trace --target vvencFFapp --parallel 8
Copy-Item bin\release-static\vvencFFapp.exe ..\vvenc_csf_tests\binaries\vvenc_default_trace.exe
```

Для CSF encoder треба зібрати VVenC fork/branch з реалізацією `--CSFScalingList`, після чого скопіювати release і trace binaries як `vvenc_csf.exe` та `vvenc_csf_trace.exe`.

## 3. Матриці

Матриці задаються в encoder. У CSF-гілці базова таблиця лежить у `source/Lib/CommonLib/CSFWeights.h`, а застосування до quant/dequant коефіцієнтів виконується в `source/Lib/CommonLib/Quant.cpp`.

`docs/matrices/` містить CSV-знімки default і CSF scaling matrices. Ці файли не керують encoder-ом і не підміняють C++-реалізацію; вони фіксують числовий вигляд матриць для аналізу, порівняння та повторної перевірки результатів. CSV генеруються командою:

```powershell
.\.venv\Scripts\python.exe tools\dump_csf_matrices.py --output docs\matrices
```

Default 8x8 matrix:

```text
16,16,16,16,16,16,16,16
16,16,16,16,16,16,16,16
16,16,16,16,16,16,16,16
16,16,16,16,16,16,16,16
16,16,16,16,16,16,16,16
16,16,16,16,16,16,16,16
16,16,16,16,16,16,16,16
16,16,16,16,16,16,16,16
```

CSF 8x8 matrix:

```text
16,16,16,19,22,26,32,40
16,16,17,20,24,30,38,48
16,17,19,23,28,35,45,58
19,20,23,28,34,43,56,72
22,24,28,34,43,55,71,92
26,30,35,43,55,71,92,119
32,38,45,56,71,92,119,155
40,48,58,72,92,119,155,200
```

Для матриць не 8x8 encoder не вставляє окрему вручну задану таблицю. Поточна CSF-логіка бере 8x8 CSF-таблицю і мапить її на потрібний Transform Unit (TU), тобто блок перетворення, до якого застосовується quant/dequant. Для квадратних TU використовується масштабування індексів до `min(size, 8)`. Для прямокутних TU використовується більша сторона блока, співвідношення сторін і окремі `ratioH/ratioW`, щоб отримати координати в базовій CSF-таблиці. Для коефіцієнтів поза zero-out threshold encoder записує нулі, як у стандартній scaling-list логіці.

## 4. Розбиття зображення на блоки

VVenC кодує кадр через Coding Tree Unit (CTU) і рекурсивно вибирає CU-розбиття через RD-пошук. Фінальна структура копіюється в picture-level coding structure:

```cpp
partitioner->initCtu( area, CH_L, *cs.slice );
xCompressCU( tempCS, bestCS, *partitioner );
cs.useSubStructure( *bestCS, partitioner->chType, TREE_D,
  CS::getArea( *bestCS, area, partitioner->chType, partitioner->treeType ) );
```

Карти в цьому репозиторії взяті не з припущень, а з VVenC trace `D_QP`. У `CABACWriter.cpp` encoder пише фінальні luma CU:

```cpp
DTRACE_COND( ( isEncoding() ), g_trace_ctx, D_QP,
  "x=%d, y=%d, w=%d, h=%d, qp=%d\n",
  cu.Y().x, cu.Y().y, cu.Y().width, cu.Y().height, cu.qp );
```

Baseline maps згенеровані `vvenc_default_trace.exe`, CSF maps - `vvenc_csf_trace.exe`. Тобто карта показує фактичний encoder decision при однаковому зображенні, QP і preset.

## 5. Відтворення прогону

Створити локальне Python-оточення:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
```

`.venv` не є частиною репозиторію; це локальна директорія, яку створює користувач. Також потрібні `ffmpeg`, `ffprobe` і `curl.exe` у PATH.

Згенерувати synthetic images:

```powershell
.\.venv\Scripts\python.exe tools\generate_synthetic_images.py --output image_sets\synthetic\png
```

Запустити benchmark для synthetic:

```powershell
.\.venv\Scripts\python.exe tools\image_csf_benchmark.py `
  --root results\image_synthetic_full `
  --png-dir image_sets\synthetic\png `
  --qps 22,27,32,37
```

Запустити benchmark для Kodak:

```powershell
.\.venv\Scripts\python.exe tools\image_csf_benchmark.py `
  --root results\image_kodak_full `
  --png-dir image_sets\kodak\png `
  --download-kodak `
  --qps 22,27,32,37
```

Згенерувати таблиці й чарти:

```powershell
.\.venv\Scripts\python.exe tools\report_image_benchmark.py `
  docs\image_benchmark\combined_image_metrics.csv `
  --output docs\image_benchmark\combined
```

Згенерувати partition maps:

```powershell
.\.venv\Scripts\python.exe tools\build_partition_evidence.py --qp 32
```

## 6. Умови експерименту

Фіксовані умови:

| Параметр | Значення |
| --- | --- |
| Dataset | 4 synthetic + 24 Kodak PNG |
| Кадри | 1 frame per image |
| Pixel format для encode | `yuv420p`, 8-bit |
| QP points | 22, 27, 32, 37 |
| Preset | `medium` |
| Baseline mode | `vvenc_default.exe`, без `--CSFScalingList` |
| CSF mode | `vvenc_csf.exe --CSFScalingList 1` |
| Decoder | `vvdecapp.exe` |

Параметр, який керує ступенем стиснення в цьому експерименті, один: `QP`. Усі інші умови зафіксовані. Менший QP дає більший bitrate і кращу якість, більший QP дає сильніше стиснення.

Ступінь стиснення для конкретних умов `image + QP + mode` розраховується так:

```text
raw_bytes = width * height * 3 / 2
compression_ratio = raw_bytes / bitstream_bytes
bpp = bitstream_bytes * 8 / (width * height)
```

`raw_bytes` відповідає одному 8-bit YUV420 кадру. `bitstream_bytes` береться з розміру `.vvc` bitstream після encode. Усі значення записані в `docs/image_benchmark/combined_image_metrics.csv`: колонки `bitstream_bytes`, `compression_ratio`, `bpp`, `image`, `qp`, `mode`.

## 7. Метрики візуальної якості

Поведінка encoder-а у стандартних умовах досліджується двома способами:

1. Same-QP comparison: baseline і CSF порівнюються при однакових QP 22/27/32/37.
2. Equal-bpp comparison: значення CSF інтерполюється на bpp-точки baseline, щоб оцінити якість при близькому bitrate.

Luma означає яскравісну Y-компоненту у YUV-представленні зображення. У цьому benchmark input і reconstruction зберігаються як YUV420, тому локальні MS-SSIM/FSIM/HaarPSI/PSNR-HVS-M колонки рахуються саме по Y-площині. Такий підхід добре узгоджується з PSNR-Y/XPSNR-Y і дає стабільне порівняння baseline vs CSF для структури, контурів і текстур, які найбільше проявляються в яскравісному каналі.

Ці локальні luma-метрики не є повною заміною pinned зовнішніх реалізацій. Вони потрібні для відтворюваного in-repo аналізу без важких залежностей і рахуються однаково для обох encoder modes. Зовнішні реалізації MS-SSIM/FSIM/HaarPSI/PSNR-HVS-M можуть відрізнятися деталями: RGB або YUV input, обробкою chroma, padding, масштабуванням, фільтрами, вагами multi-scale рівнів, реалізацією phase congruency або Haar wavelet частини. Тому поточні колонки треба читати як локальні luma-only індикатори для порівняння всередині цього експерименту, а не як bit-exact відповідність конкретній сторонній бібліотеці.

Метрики:

| Метрика | Джерело |
| --- | --- |
| PSNR-Y/U/V | Парситься з VVenC encode log. |
| SSIM | `ffmpeg -lavfi ssim`. |
| XPSNR-Y | `ffmpeg -lavfi xpsnr`. |
| VMAF | `ffmpeg -lavfi libvmaf`, якщо ffmpeg зібраний з libvmaf. |
| MS-SSIM | Локальний luma-розрахунок у `metrics/image_quality.py`. |
| FSIM | Локальний luma-розрахунок у `metrics/image_quality.py`. |
| HaarPSI | Локальний luma-розрахунок у `metrics/image_quality.py`. |
| PSNR-HVS-M | Локальний luma-розрахунок у `metrics/image_quality.py`. |

## 8. Підсумок same-QP

CSV: `docs/image_benchmark/combined/same_qp_summary.csv`

| Метрика | Mean | Min | Max |
| --- | --- | --- | --- |
| psnr_y_delta | -0.515987 | -1.286700 | 0.498400 |
| ssim_delta | -0.002323 | -0.011512 | 0.000771 |
| xpsnr_y_delta | -0.473405 | -1.281300 | 0.286200 |
| vmaf_delta | -0.019329 | -1.386822 | 1.076791 |
| msssim_luma_delta | -0.000044 | -0.000349 | 0.000008 |
| fsim_luma_delta | -0.003933 | -0.015175 | 0.003091 |
| haarpsi_luma_delta | -0.003413 | -0.018561 | 0.001788 |
| psnr_hvs_m_luma_delta | -0.476527 | -1.255171 | 0.456938 |

## 9. Підсумок equal-bpp

CSV: `docs/image_benchmark/combined/equal_bpp_metric_summary.csv`

| Метрика | Mean | Min | Max |
| --- | --- | --- | --- |
| psnr_y_equal_bpp_delta | -0.867397 | -6.534639 | 0.000000 |
| ssim_equal_bpp_delta | -0.002734 | -0.009478 | 0.000000 |
| xpsnr_y_equal_bpp_delta | -0.765944 | -5.767764 | 0.000000 |
| vmaf_equal_bpp_delta | -0.055951 | -0.821547 | 0.198170 |
| msssim_luma_equal_bpp_delta | -0.000066 | -0.000703 | 0.000000 |
| fsim_luma_equal_bpp_delta | -0.004466 | -0.012932 | 0.000000 |
| haarpsi_luma_equal_bpp_delta | -0.003950 | -0.013726 | 0.000000 |
| psnr_hvs_m_luma_equal_bpp_delta | -0.701116 | -4.082148 | 0.000000 |

## 10. Таблиця по всіх зображеннях

Таблиця нижче агрегує 4 QP-точки для кожного зображення. Повний per-image/QP/mode CSV лежить у `docs/image_benchmark/combined_image_metrics.csv`, а per-image summary - у `docs/image_benchmark/combined/per_image_summary.csv`.

| Зображення | bpp CSF vs base, % | Compression ratio CSF vs base, % | PSNR-Y | SSIM | XPSNR-Y | VMAF | MS-SSIM | FSIM | HaarPSI | PSNR-HVS-M |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fine_texture_512x512 | 10.39 | -9.07 | -0.898 | -0.00398 | -0.878 | 0.489 | -0.000102 | -0.00541 | -0.00653 | -0.853 |
| kodim01 | -0.93 | 0.96 | -0.810 | -0.00429 | -0.741 | 0.093 | -0.000132 | -0.00580 | -0.00583 | -0.767 |
| kodim02 | 1.30 | -1.14 | -0.409 | -0.00251 | -0.369 | 0.196 | -0.000098 | -0.00563 | -0.00341 | -0.384 |
| kodim03 | 2.96 | -2.82 | -0.380 | -0.00140 | -0.302 | 0.288 | -0.000023 | -0.00449 | -0.00288 | -0.348 |
| kodim04 | -0.80 | 0.87 | -0.574 | -0.00308 | -0.535 | 0.280 | -0.000058 | -0.00620 | -0.00437 | -0.546 |
| kodim05 | -0.77 | 0.78 | -0.575 | -0.00181 | -0.529 | -0.085 | -0.000043 | -0.00251 | -0.00265 | -0.538 |
| kodim06 | 0.51 | -0.50 | -0.673 | -0.00339 | -0.620 | -0.106 | -0.000031 | -0.00491 | -0.00488 | -0.622 |
| kodim07 | 1.92 | -1.83 | -0.282 | -0.00039 | -0.252 | -0.092 | -0.000022 | -0.00151 | -0.00131 | -0.253 |
| kodim08 | -1.07 | 1.08 | -0.751 | -0.00246 | -0.695 | -0.035 | -0.000033 | -0.00275 | -0.00360 | -0.700 |
| kodim09 | 1.21 | -1.08 | -0.351 | -0.00112 | -0.316 | -0.164 | -0.000029 | -0.00248 | -0.00211 | -0.308 |
| kodim10 | 1.57 | -1.43 | -0.300 | -0.00090 | -0.263 | 0.140 | -0.000022 | -0.00199 | -0.00156 | -0.269 |
| kodim11 | -0.49 | 0.51 | -0.603 | -0.00336 | -0.538 | -0.183 | -0.000056 | -0.00444 | -0.00374 | -0.557 |
| kodim12 | 1.04 | -0.91 | -0.448 | -0.00228 | -0.415 | -0.239 | -0.000025 | -0.00393 | -0.00244 | -0.415 |
| kodim13 | -1.44 | 1.48 | -0.990 | -0.00590 | -0.955 | -0.092 | -0.000087 | -0.00649 | -0.00711 | -0.937 |
| kodim14 | -1.17 | 1.20 | -0.631 | -0.00325 | -0.583 | -0.194 | -0.000051 | -0.00472 | -0.00373 | -0.594 |
| kodim15 | -0.38 | 0.47 | -0.612 | -0.00273 | -0.529 | 0.019 | -0.000009 | -0.00612 | -0.00424 | -0.562 |
| kodim16 | 0.21 | -0.19 | -0.594 | -0.00325 | -0.554 | -0.190 | -0.000046 | -0.00568 | -0.00439 | -0.559 |
| kodim17 | 0.98 | -0.89 | -0.340 | -0.00112 | -0.249 | -0.405 | -0.000016 | -0.00250 | -0.00197 | -0.301 |
| kodim18 | -2.49 | 2.56 | -0.801 | -0.00381 | -0.705 | -0.072 | -0.000115 | -0.00551 | -0.00524 | -0.758 |
| kodim19 | -1.41 | 1.48 | -0.629 | -0.00340 | -0.619 | -0.120 | -0.000049 | -0.00500 | -0.00397 | -0.589 |
| kodim20 | 0.60 | -0.53 | -0.584 | -0.00227 | -0.570 | -0.008 | -0.000008 | -0.00576 | -0.00401 | -0.529 |
| kodim21 | -0.12 | 0.12 | -0.607 | -0.00193 | -0.566 | -0.057 | -0.000062 | -0.00445 | -0.00474 | -0.544 |
| kodim22 | -1.52 | 1.56 | -0.632 | -0.00392 | -0.581 | -0.034 | -0.000067 | -0.00697 | -0.00518 | -0.594 |
| kodim23 | 3.34 | -3.09 | -0.264 | -0.00050 | -0.207 | -0.282 | -0.000010 | -0.00189 | -0.00152 | -0.221 |
| kodim24 | -0.07 | 0.07 | -0.647 | -0.00230 | -0.541 | 0.116 | -0.000036 | -0.00371 | -0.00455 | -0.569 |
| mixed_content_512x512 | 33.52 | -24.53 | -0.019 | 0.00019 | -0.049 | 0.152 | -0.000001 | -0.00001 | -0.00003 | -0.039 |
| sharp_edges_512x512 | 30.36 | -23.11 | -0.043 | 0.00012 | -0.092 | 0.043 | 0.000001 | 0.00075 | 0.00043 | 0.012 |
| smooth_gradient_512x512 | 262.71 | -70.55 | 0.000 | 0.00000 | 0.000 | 0.000 | 0.000000 | 0.00000 | 0.00000 | 0.000 |

## 11. RD-чарти

![PSNR-Y RD](docs/image_benchmark/combined/charts/rd_psnr_y.svg)

![SSIM RD](docs/image_benchmark/combined/charts/rd_ssim.svg)

![XPSNR-Y RD](docs/image_benchmark/combined/charts/rd_xpsnr_y.svg)

![VMAF RD](docs/image_benchmark/combined/charts/rd_vmaf.svg)

![MS-SSIM RD](docs/image_benchmark/combined/charts/rd_msssim_luma.svg)

![FSIM RD](docs/image_benchmark/combined/charts/rd_fsim_luma.svg)

![HaarPSI RD](docs/image_benchmark/combined/charts/rd_haarpsi_luma.svg)

![PSNR-HVS-M RD](docs/image_benchmark/combined/charts/rd_psnr_hvs_m_luma.svg)

## 12. Partition maps: summary

Карта показує фінальні luma CU, які encoder реально закодував при `QP=32`, `preset=medium`, `1 frame`.

Synthetic:

| Зображення | Розмір | CU baseline | CU CSF | Delta, % | Домінуючі baseline | Домінуючі CSF |
| --- | --- | --- | --- | --- | --- | --- |
| fine_texture_512x512 | 512x512 | 351 | 16094 | 4485.19 | 32x32:191; 16x32:58; 16x16:53; 32x16:43; 32x8:2; 8x16:2 | 4x4:15820; 4x8:160; 8x4:106; 4x16:8 |
| mixed_content_512x512 | 512x512 | 549 | 540 | -1.64 | 16x16:107; 32x32:82; 8x8:61; 4x4:38; 4x16:32; 8x16:31 | 16x16:116; 32x32:63; 8x8:61; 4x4:46; 4x16:37; 64x64:30 |
| sharp_edges_512x512 | 512x512 | 577 | 576 | -0.17 | 16x16:115; 32x32:114; 16x32:67; 8x8:56; 16x8:40; 4x32:36 | 16x16:145; 32x32:112; 16x32:67; 8x8:55; 4x32:36; 8x16:33 |
| smooth_gradient_512x512 | 512x512 | 64 | 64 | 0.00 | 64x64:64 | 64x64:64 |

Kodak:

| Зображення | Розмір | CU baseline | CU CSF | Delta, % | Домінуючі baseline | Домінуючі CSF |
| --- | --- | --- | --- | --- | --- | --- |
| kodim01 | 768x512 | 5627 | 12897 | 129.20 | 8x8:1162; 8x4:870; 4x4:862; 4x8:645; 16x4:639; 16x8:445 | 4x4:8890; 8x4:1494; 4x8:781; 8x8:577; 16x4:349; 4x16:280 |
| kodim02 | 768x512 | 3739 | 4614 | 23.40 | 8x8:769; 4x4:462; 8x4:425; 4x8:344; 16x4:315; 4x16:294 | 4x4:1268; 8x8:607; 8x4:554; 4x8:408; 16x4:406; 4x16:327 |
| kodim03 | 768x512 | 2633 | 3645 | 38.44 | 8x8:438; 4x4:412; 16x16:326; 8x4:322; 4x8:196; 16x8:162 | 4x4:1268; 8x4:599; 8x8:414; 16x16:271; 4x8:255; 16x8:138 |
| kodim04 | 512x768 | 2405 | 3210 | 33.47 | 8x8:425; 16x16:307; 4x4:276; 16x8:185; 8x4:181; 4x8:169 | 4x4:820; 8x8:490; 8x4:336; 16x16:303; 4x8:246; 16x8:202 |
| kodim05 | 768x512 | 8976 | 11959 | 33.23 | 4x4:3556; 8x8:1597; 4x8:1420; 8x4:1356; 4x16:234; 16x4:210 | 4x4:7162; 8x4:1511; 4x8:1348; 8x8:1171; 16x4:206; 16x16:147 |
| kodim06 | 768x512 | 3558 | 7936 | 123.05 | 4x4:716; 8x4:610; 8x8:569; 16x4:370; 16x8:362; 4x8:220 | 4x4:3790; 8x4:2037; 16x4:661; 8x8:474; 16x8:283; 4x8:230 |
| kodim07 | 768x512 | 4513 | 5277 | 16.93 | 4x4:1236; 8x8:857; 8x4:589; 4x8:575; 16x16:280; 16x8:191 | 4x4:1964; 8x8:828; 8x4:739; 4x8:619; 16x16:306; 16x8:193 |
| kodim08 | 768x512 | 7384 | 10710 | 45.04 | 4x4:2250; 8x8:1242; 4x8:1176; 8x4:1025; 4x16:631; 16x4:328 | 4x4:5944; 4x8:1415; 8x4:1165; 8x8:815; 4x16:563; 16x4:272 |
| kodim09 | 512x768 | 2640 | 3282 | 24.32 | 4x4:458; 8x8:442; 4x8:298; 8x4:251; 16x8:192; 16x16:191 | 4x4:962; 8x4:432; 8x8:394; 4x8:385; 16x16:169; 16x4:165 |
| kodim10 | 512x768 | 3378 | 4164 | 23.27 | 8x8:652; 4x4:512; 8x4:366; 4x8:360; 16x16:283; 8x16:242 | 4x4:1202; 8x8:627; 4x8:427; 8x4:426; 16x16:292; 16x4:225 |
| kodim11 | 768x512 | 4466 | 6737 | 50.85 | 4x4:966; 8x8:775; 8x4:637; 4x8:480; 16x4:353; 16x8:261 | 4x4:3002; 8x4:992; 4x8:607; 8x8:582; 16x4:564; 16x8:220 |
| kodim12 | 768x512 | 2530 | 3209 | 26.84 | 8x8:498; 4x4:304; 16x16:243; 8x4:233; 16x8:203; 4x8:195 | 4x4:756; 8x8:466; 8x4:386; 16x4:267; 4x8:246; 16x16:236 |
| kodim13 | 768x512 | 6178 | 16261 | 163.21 | 4x4:1576; 8x8:1212; 8x4:1193; 16x4:596; 4x8:457; 16x8:443 | 4x4:13388; 8x4:1316; 4x8:606; 8x8:420; 16x16:163; 16x4:132 |
| kodim14 | 768x512 | 6840 | 9313 | 36.15 | 4x4:1984; 8x4:1289; 8x8:1238; 4x8:707; 16x4:551; 16x8:449 | 4x4:4794; 8x4:1826; 8x8:911; 4x8:555; 16x4:395; 16x8:312 |
| kodim15 | 768x512 | 2400 | 3729 | 55.38 | 8x8:521; 4x4:280; 16x16:253; 4x8:243; 8x16:212; 8x4:165 | 4x4:1500; 8x8:495; 4x8:385; 8x4:307; 16x16:247; 8x16:161 |
| kodim16 | 768x512 | 2713 | 4200 | 54.81 | 8x8:478; 8x4:322; 4x4:320; 16x8:299; 16x4:280; 16x16:233 | 4x4:1022; 8x4:907; 16x4:712; 8x8:379; 16x8:313; 16x16:209 |
| kodim17 | 512x768 | 4303 | 5301 | 23.19 | 8x8:1049; 4x4:818; 8x4:514; 4x8:511; 16x16:275; 8x16:271 | 4x4:1846; 8x8:915; 8x4:705; 4x8:592; 16x16:270; 8x16:234 |
| kodim18 | 512x768 | 4540 | 8135 | 79.19 | 4x4:988; 8x8:933; 4x8:589; 8x4:519; 16x16:368; 8x16:268 | 4x4:5216; 8x8:631; 8x4:609; 4x8:593; 16x16:342; 8x16:179 |
| kodim19 | 512x768 | 3078 | 4455 | 44.74 | 4x4:788; 8x8:438; 4x8:410; 8x4:310; 16x16:224; 4x16:162 | 4x4:2082; 8x4:491; 4x8:474; 8x8:376; 16x16:192; 16x4:168 |
| kodim20 | 768x512 | 2722 | 3912 | 43.72 | 4x4:674; 8x8:527; 8x4:407; 4x8:238; 16x16:181; 16x4:148 | 4x4:1682; 8x4:601; 8x8:480; 4x8:354; 16x16:167; 16x8:161 |
| kodim21 | 768x512 | 3883 | 7694 | 98.15 | 4x4:908; 8x4:721; 8x8:714; 16x4:428; 16x8:349; 4x8:235 | 4x4:5220; 8x4:1020; 8x8:362; 4x8:274; 16x4:268; 16x8:163 |
| kodim22 | 768x512 | 3600 | 5730 | 59.17 | 8x8:712; 4x4:636; 8x4:364; 16x16:348; 4x8:344; 8x16:280 | 4x4:2628; 8x8:653; 8x4:563; 4x8:559; 16x16:326; 8x16:237 |
| kodim23 | 768x512 | 2111 | 2473 | 17.15 | 8x8:394; 4x4:274; 8x16:256; 16x16:239; 4x8:172; 8x4:135 | 4x4:572; 8x8:365; 16x16:250; 8x4:237; 4x8:217; 8x16:212 |
| kodim24 | 768x512 | 5728 | 9720 | 69.69 | 8x8:1348; 4x4:1288; 8x4:757; 4x8:711; 8x16:395; 4x16:324 | 4x4:5834; 8x8:936; 4x8:932; 8x4:769; 4x16:289; 16x16:279 |

## 13. Partition maps: synthetic

Baseline і CSF карти виводяться з однаковою шириною. Якщо CSF-карта візуально здається дрібнішою, це не означає інший масштаб зображення. У таких випадках encoder вибрав більше дрібних CU, тому сітка виглядає щільнішою.

| Зображення | Оригінал | Baseline | CSF |
| --- | --- | --- | --- |
| fine_texture_512x512 | <img src="image_sets/synthetic/png/fine_texture_512x512.png" width="220"> | <img src="docs/partition_maps/synthetic/fine_texture_512x512_baseline.svg" width="260"> | <img src="docs/partition_maps/synthetic/fine_texture_512x512_csf.svg" width="260"> |
| mixed_content_512x512 | <img src="image_sets/synthetic/png/mixed_content_512x512.png" width="220"> | <img src="docs/partition_maps/synthetic/mixed_content_512x512_baseline.svg" width="260"> | <img src="docs/partition_maps/synthetic/mixed_content_512x512_csf.svg" width="260"> |
| sharp_edges_512x512 | <img src="image_sets/synthetic/png/sharp_edges_512x512.png" width="220"> | <img src="docs/partition_maps/synthetic/sharp_edges_512x512_baseline.svg" width="260"> | <img src="docs/partition_maps/synthetic/sharp_edges_512x512_csf.svg" width="260"> |
| smooth_gradient_512x512 | <img src="image_sets/synthetic/png/smooth_gradient_512x512.png" width="220"> | <img src="docs/partition_maps/synthetic/smooth_gradient_512x512_baseline.svg" width="260"> | <img src="docs/partition_maps/synthetic/smooth_gradient_512x512_csf.svg" width="260"> |

## 14. Partition maps: Kodak

Baseline і CSF карти мають той самий canvas для кожного Kodak-зображення. Візуальна різниця пов'язана з кількістю та розмірами CU, а не з різним масштабом відображення.

| Зображення | Оригінал | Baseline | CSF |
| --- | --- | --- | --- |
| kodim01 | <img src="image_sets/kodak/png/kodim01.png" width="220"> | <img src="docs/partition_maps/kodak/kodim01_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim01_csf.svg" width="260"> |
| kodim02 | <img src="image_sets/kodak/png/kodim02.png" width="220"> | <img src="docs/partition_maps/kodak/kodim02_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim02_csf.svg" width="260"> |
| kodim03 | <img src="image_sets/kodak/png/kodim03.png" width="220"> | <img src="docs/partition_maps/kodak/kodim03_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim03_csf.svg" width="260"> |
| kodim04 | <img src="image_sets/kodak/png/kodim04.png" width="220"> | <img src="docs/partition_maps/kodak/kodim04_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim04_csf.svg" width="260"> |
| kodim05 | <img src="image_sets/kodak/png/kodim05.png" width="220"> | <img src="docs/partition_maps/kodak/kodim05_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim05_csf.svg" width="260"> |
| kodim06 | <img src="image_sets/kodak/png/kodim06.png" width="220"> | <img src="docs/partition_maps/kodak/kodim06_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim06_csf.svg" width="260"> |
| kodim07 | <img src="image_sets/kodak/png/kodim07.png" width="220"> | <img src="docs/partition_maps/kodak/kodim07_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim07_csf.svg" width="260"> |
| kodim08 | <img src="image_sets/kodak/png/kodim08.png" width="220"> | <img src="docs/partition_maps/kodak/kodim08_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim08_csf.svg" width="260"> |
| kodim09 | <img src="image_sets/kodak/png/kodim09.png" width="220"> | <img src="docs/partition_maps/kodak/kodim09_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim09_csf.svg" width="260"> |
| kodim10 | <img src="image_sets/kodak/png/kodim10.png" width="220"> | <img src="docs/partition_maps/kodak/kodim10_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim10_csf.svg" width="260"> |
| kodim11 | <img src="image_sets/kodak/png/kodim11.png" width="220"> | <img src="docs/partition_maps/kodak/kodim11_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim11_csf.svg" width="260"> |
| kodim12 | <img src="image_sets/kodak/png/kodim12.png" width="220"> | <img src="docs/partition_maps/kodak/kodim12_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim12_csf.svg" width="260"> |
| kodim13 | <img src="image_sets/kodak/png/kodim13.png" width="220"> | <img src="docs/partition_maps/kodak/kodim13_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim13_csf.svg" width="260"> |
| kodim14 | <img src="image_sets/kodak/png/kodim14.png" width="220"> | <img src="docs/partition_maps/kodak/kodim14_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim14_csf.svg" width="260"> |
| kodim15 | <img src="image_sets/kodak/png/kodim15.png" width="220"> | <img src="docs/partition_maps/kodak/kodim15_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim15_csf.svg" width="260"> |
| kodim16 | <img src="image_sets/kodak/png/kodim16.png" width="220"> | <img src="docs/partition_maps/kodak/kodim16_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim16_csf.svg" width="260"> |
| kodim17 | <img src="image_sets/kodak/png/kodim17.png" width="220"> | <img src="docs/partition_maps/kodak/kodim17_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim17_csf.svg" width="260"> |
| kodim18 | <img src="image_sets/kodak/png/kodim18.png" width="220"> | <img src="docs/partition_maps/kodak/kodim18_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim18_csf.svg" width="260"> |
| kodim19 | <img src="image_sets/kodak/png/kodim19.png" width="220"> | <img src="docs/partition_maps/kodak/kodim19_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim19_csf.svg" width="260"> |
| kodim20 | <img src="image_sets/kodak/png/kodim20.png" width="220"> | <img src="docs/partition_maps/kodak/kodim20_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim20_csf.svg" width="260"> |
| kodim21 | <img src="image_sets/kodak/png/kodim21.png" width="220"> | <img src="docs/partition_maps/kodak/kodim21_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim21_csf.svg" width="260"> |
| kodim22 | <img src="image_sets/kodak/png/kodim22.png" width="220"> | <img src="docs/partition_maps/kodak/kodim22_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim22_csf.svg" width="260"> |
| kodim23 | <img src="image_sets/kodak/png/kodim23.png" width="220"> | <img src="docs/partition_maps/kodak/kodim23_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim23_csf.svg" width="260"> |
| kodim24 | <img src="image_sets/kodak/png/kodim24.png" width="220"> | <img src="docs/partition_maps/kodak/kodim24_baseline.svg" width="260"> | <img src="docs/partition_maps/kodak/kodim24_csf.svg" width="260"> |

## 15. Поточний висновок

Поточна CSF-інтеграція поводиться стабільно як механізм. Encoder приймає `--CSFScalingList 1`, bitstream декодується, матриці сигналізуються, а таблиці, RD-чарти й карти розбиття відтворюються скриптами з цього репозиторію.

У середньому same-QP та equal-bpp дельти для більшості quality metrics залишаються негативними, тому поточна форма матриці не дає переваги над baseline.
