# Neutral Scaling-List Value Verification

This report verifies the neutral scaling-list value used by the upstream VVenC code and by the default matrix snapshots in this repository.

## Source Constants

| Constant | Value | Meaning |
| --- | ---: | --- |
| `SCALING_LIST_BITS` | 8 | Bit depth of scaling-list entries. |
| `LOG2_SCALING_LIST_NEUTRAL_VALUE` | 4 | Log2 of the value that has no effect on quantisation. |
| Neutral value | 16 | Computed as `1 << LOG2_SCALING_LIST_NEUTRAL_VALUE`. |

## Default Matrix Snapshots

| File | Entries | Min | Max | All entries are neutral |
| --- | ---: | ---: | ---: | --- |
| `docs/matrices/default_16x16.csv` | 256 | 16 | 16 | True |
| `docs/matrices/default_16x32.csv` | 512 | 16 | 16 | True |
| `docs/matrices/default_32x16.csv` | 512 | 16 | 16 | True |
| `docs/matrices/default_32x32.csv` | 1024 | 16 | 16 | True |
| `docs/matrices/default_4x4.csv` | 16 | 16 | 16 | True |
| `docs/matrices/default_8x8.csv` | 64 | 16 | 16 | True |

## Quant/Dequant Equivalence

In VVC scaling-list syntax, `LOG2_SCALING_LIST_NEUTRAL_VALUE = 4` defines `16` as the no-op scaling-list entry.

For a scaling-list weight `w`, the neutral case is:

```text
w = 1 << LOG2_SCALING_LIST_NEUTRAL_VALUE = 16
```

The practical CSF-off control run verifies that the modified encoder preserves default behavior when CSF scaling lists are disabled.

## Result

- Default matrix snapshots are all neutral: `True`.
- Neutral scaling-list value is `16`: `True`.
