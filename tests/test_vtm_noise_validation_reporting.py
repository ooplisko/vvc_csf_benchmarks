from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from tools.reporting import report_vtm_spatial_complexity as main_report
from tools.reporting import vtm_noise_validation_report as report


def fixture_tables(path):
    path.mkdir()
    sources = pd.DataFrame({"source": [f"{i:04}.png" for i in range(801, 849)]})
    stimuli = pd.DataFrame([{"source": source, "stimulus": f"{source}_{seed}"}
                            for source in sources.source for seed in ("", *report.SEEDS)])
    joined = pd.DataFrame([{**row, "qp": qp} for row in stimuli.to_dict("records") for qp in report.QPS])
    rho = pd.DataFrame([
        {"feature": feature, "qp": qp, "seed": seed, "distortion": "awgn" if seed else "clean",
         "level": 30 if seed else 0, "n_images": 48,
         "rho": (-0.3 if seed else -0.8) if feature == "glcm_homogeneity" else (0.5 if seed else 0.6)}
        for feature in report.FEATURES for qp in report.QPS for seed in ("", *report.SEEDS)])
    rows = []
    for method, critical in (("image", 0.3), ("scene_cluster", 0.45)):
        for (effect_type, feature, qp), value in report.point_effects(rho).items():
            bound = 2 if effect_type == "B" else 4
            low, high = max(-bound, value-critical), min(bound, value+critical)
            rows.append({"resampling": method, "effect_type": effect_type, "feature": feature, "qp": qp,
                         "estimate": value, "n_images": 48, "family_size": 44, "alpha": 0.05,
                         "evaluable": True, "excludes_zero": low > 0 or high < 0,
                         "simultaneous_low": low, "simultaneous_high": high, "critical_value": critical})
    tables = {"selected_sources": sources, "stimulus_features": stimuli, "joined_measurements": joined,
              "correlations": rho, "effects": pd.DataFrame(rows)}
    for name, table in tables.items():
        table.to_csv(path / f"{name}.csv", index=False)
    return tables


@pytest.mark.parametrize("damage", ["missing", "pooled_n", "duplicate", "wrong_effect", "wrong_flag", "wrong_interval", "split_family"])
def test_report_rejects_invalid_validation_tables(tmp_path, damage):
    path = tmp_path / "validation"
    tables = fixture_tables(path)
    if damage == "missing":
        (path / "correlations.csv").unlink()
    else:
        effects = tables["effects"]
        if damage == "pooled_n":
            effects.loc[:, "n_images"] = 144
        elif damage == "duplicate":
            effects.iloc[1] = effects.iloc[0]
        elif damage == "wrong_effect":
            effects.loc[0, "estimate"] += 0.2
        elif damage == "wrong_flag":
            effects.loc[0, "excludes_zero"] = not effects.loc[0, "excludes_zero"]
        elif damage == "wrong_interval":
            effects.loc[0, "simultaneous_low"] -= 0.1
        else:
            effects.loc[effects.effect_type.eq("C"), "family_size"] = 20
        effects.to_csv(path / "effects.csv", index=False)
    with pytest.raises(ValueError):
        report.load_validation_tables(path)


def test_validation_text_and_figures_keep_estimands_and_scales(tmp_path, monkeypatch):
    path = tmp_path / "validation"
    tables = fixture_tables(path)
    loaded = report.load_validation_tables(path)
    text = "\n".join(report.validation_section(loaded, main_report.LABELS))
    assert "all 24 B and 20 C intervals together" in text
    assert "not 144 independent" in text
    assert "20 of the 44 effects" in text
    assert "do not provide joint 95% coverage" in text
    assert "same 44-comparison family" in text
    assert "QP 22 | QP 27 | QP 32 | QP 37" in text
    # Use the same synthetic point correlations for the exploratory panel.
    loaded["correlations"] = tables["correlations"]
    captured = {}
    def capture(figure, path, **kwargs):
        if Path(path).suffix == ".png":
            captured[Path(path).stem] = figure
    monkeypatch.setattr(plt.Figure, "savefig", capture)
    report.plot_validation(loaded, tmp_path / "figures", main_report.LABELS, main_report.QP_STYLES)
    b = captured["Fig6_dataset_noise_changes"]
    for axis in b.axes[:2]:
        assert axis.images[0].get_clim() == (-2, 2)
        assert np.asarray(axis.images[0].get_array()).shape == (6, 4)
    assert not any("*" in text.get_text() for text in b.axes[0].texts)
    assert any("*" in text.get_text() for text in b.axes[1].texts)
    c = captured["Fig7_validation_comparisons"]
    assert c.axes[0].get_xlim() == (-4, 4)
    assert len(c.axes[0].get_yticklabels()) == 20


def test_report_copies_validation_tables_and_links_one_readme(tmp_path, monkeypatch):
    directory = tmp_path / "validation"
    fixture_tables(directory)
    analysis = main_report.ROOT / "docs/vtm_content_partition_study/spatial_complexity/tables"
    tables = main_report.load_tables(analysis, directory)
    monkeypatch.setattr(main_report, "plot_validation", lambda *args: None)
    output = tmp_path / "report"
    main_report.write_report(analysis, output, tables, directory)
    text = (output / "README.md").read_text(encoding="utf-8")
    assert "## Key Findings on Kodak" in text
    assert "## Independent Check on DIV2K" in text
    assert "--validation-dir results/vtm_noise_validation/analysis" in text
    for name in report.TABLES:
        assert (output / "tables/div2k" / f"{name}.csv").read_bytes() == (directory / f"{name}.csv").read_bytes()
    assert len(list(output.rglob("*.md"))) == 1
