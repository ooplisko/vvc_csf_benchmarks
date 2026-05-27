# Neutral 16 Control Run

This control checks the practical baseline for the neutral scaling-list value `16`.

Current VVenC application binaries do not expose a `--ScalingListFile` option. Because of that, the external-file test used by VTM-style workflows is not used here. The control is split into two checks:

1. `neutral_16_verification.md` verifies from upstream VVenC source code that `LOG2_SCALING_LIST_NEUTRAL_VALUE = 4`, so the neutral scaling-list entry is `16`.
2. This run verifies that the modified CSF encoder with `--CSFScalingList 0` produces the same bitstream and reconstruction as the default encoder under identical image/QP conditions.

CSV: `docs/matrices/neutral_16_control.csv`

## Summary

| Check | Passed | Total |
| --- | ---: | ---: |
| Bitstream identity | 20 | 20 |
| Reconstruction identity | 20 | 20 |

Overall result: `PASS`.

## Per-Image/QP Results

| Image | QP | Bitstream bytes | Bitstream identical | Reconstruction identical |
| --- | ---: | ---: | --- | --- |
| baboon | 22 | 99281 | True | True |
| baboon | 27 | 71110 | True | True |
| baboon | 32 | 44729 | True | True |
| baboon | 37 | 24307 | True | True |
| barbara | 22 | 43875 | True | True |
| barbara | 27 | 26515 | True | True |
| barbara | 32 | 16409 | True | True |
| barbara | 37 | 9664 | True | True |
| goldhill | 22 | 57189 | True | True |
| goldhill | 27 | 32124 | True | True |
| goldhill | 32 | 15921 | True | True |
| goldhill | 37 | 7598 | True | True |
| lenna | 22 | 37586 | True | True |
| lenna | 27 | 17126 | True | True |
| lenna | 32 | 9046 | True | True |
| lenna | 37 | 4953 | True | True |
| peppers | 22 | 49494 | True | True |
| peppers | 27 | 21724 | True | True |
| peppers | 32 | 8307 | True | True |
| peppers | 37 | 4649 | True | True |
