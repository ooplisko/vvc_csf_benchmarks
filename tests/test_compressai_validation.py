from __future__ import annotations

from tools.validation.vtm.compressai.scripts.build_compressai_validation import (
    compressai_rows,
    load_json,
    nearest_duan_rows,
    validate_monotonic,
)


def test_compressai_reference_is_monotonic() -> None:
    reference = load_json("data/baselines/compressai_kodak_vtm.json")
    checks = validate_monotonic(compressai_rows(reference))

    assert checks == {"bpp": True, "psnr_rgb": True, "msssim_rgb": True}


def test_compressai_reference_overlaps_duan_anchor() -> None:
    reference = load_json("data/baselines/compressai_kodak_vtm.json")
    duan = load_json("data/baselines/kodak_vtm.json")
    overlap = nearest_duan_rows(compressai_rows(reference), duan)

    assert [row["nearest_duan_qp"] for row in overlap[:7]] == [47, 42, 37, 32, 27, 22, 17]
    assert max(abs(float(row["delta_psnr_rgb"])) for row in overlap[:7]) < 0.08
