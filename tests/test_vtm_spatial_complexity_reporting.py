from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from tools.reporting import report_vtm_spatial_complexity as reporting


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "docs/vtm_content_partition_study/spatial_complexity/tables"


def copy_tables(destination: Path) -> None:
    destination.mkdir()
    for name in reporting.TABLE_DESCRIPTIONS:
        shutil.copyfile(TABLES / f"{name}.csv", destination / f"{name}.csv")


@pytest.mark.parametrize("damage, message", [
    ("missing", "Missing analysis table"),
    ("duplicate_measurement", "Duplicate stimulus/QP"),
    ("nonbaseline", "baseline VTM"),
    ("missing_condition", "Expected 168 primary"),
    ("wrong_descriptor", "Correlation cells do not match"),
    ("wrong_seed_role", "Primary AWGN cells"),
    ("invalid_rho", "Correlations must be finite"),
])
def test_invalid_report_matrix_fails_before_creating_output(tmp_path, damage, message) -> None:
    analysis = tmp_path / "analysis"
    copy_tables(analysis)
    path = analysis / "correlations.csv"
    if damage == "missing":
        path.unlink()
    elif damage in ("duplicate_measurement", "nonbaseline"):
        path = analysis / "joined_measurements.csv"
        table = pd.read_csv(path, float_precision="round_trip")
        if damage == "duplicate_measurement":
            table.iloc[1] = table.iloc[0]
        else:
            table.loc[0, "mode"] = "csf"
        table.to_csv(path, index=False)
    else:
        table = pd.read_csv(path, dtype={"seed": str}, float_precision="round_trip")
        if damage == "missing_condition":
            table = table.iloc[1:]
        elif damage == "wrong_descriptor":
            table.loc[0, "feature"] = "unknown_descriptor"
        elif damage == "wrong_seed_role":
            # Keep the primary count per QP unchanged while swapping seed roles.
            a = table.index[table.seed.eq("20260811") & table.qp.eq(22)][0]
            b = table.index[table.seed.eq("20260812") & table.qp.eq(22)][0]
            table.loc[[a, b], "primary"] = [False, True]
        else:
            table.loc[0, "rho"] = 1.2
        table.to_csv(path, index=False)
    output = tmp_path / "report"
    with pytest.raises(ValueError, match=message):
        reporting.build(analysis, output)
    assert not output.exists()


def test_csv_only_inputs_generate_one_research_readme_and_no_json(tmp_path) -> None:
    analysis = tmp_path / "analysis"
    copy_tables(analysis)
    output = tmp_path / "report"
    reporting.build(analysis, output)
    text = (output / "README.md").read_text(encoding="utf-8")
    assert sorted(path.name for path in output.glob("*.md")) == ["README.md"]
    assert not list(output.rglob("*.json"))
    assert "| Sobel SD | 0.554 | 0.618 | 0.710 | 0.783 |" in text
    assert "1,248 encodings" in text
    assert "20 candidate-versus-Sobel contrasts and 144 disturbed-versus-clean contrasts" in text
    assert "168 primary correlations" in text
    assert "primary AWGN realization, base seed 20260811" in text
    assert "RQ" not in text
    assert "Paired comparisons quantify the magnitude and uncertainty of the changes" in text
    assert "An asterisk (*) means that the simultaneous confidence interval for B excludes zero" in text
    assert "not estimated from the clean correlations" in text
    assert "[-1.368, +0.031]" in text
    assert "remaining 22 images" in text
    assert "pointwise 95%" in text
    assert "We do not pool seeds as independent images" in text
    assert "| Seed 20260811 | Seed 20260812 | Seed 20260813 |" in text
    assert "| GLCM homogeneity | 30 | 27 |" in text
    for phrase in ("STATISTICS.md", "DEVELOPMENT.md", "BMJ", "CSF modifications", "VVenC results", "provenance.json", "analysis_state.json"):
        assert phrase not in text
    assert "| Table | Rows |" not in text
    assert text.index("<details>") < text.index("Fig3_dependent_clean_comparisons.png")
    tables = reporting.load_tables(analysis)
    supported = tables["contrasts"].query("simultaneous_low > 0 or simultaneous_high < 0")
    for row in supported.itertuples():
        assert f"| {reporting.LABELS[row.feature]} |" in text
    assert len(list((output / "figures").glob("*.png"))) == 9
    assert len(list((output / "figures").glob("*.pdf"))) == 9
    for source in analysis.glob("*.csv"):
        assert (output / "tables" / source.name).read_bytes() == source.read_bytes()
        assert f"tables/{source.name}" in text

    # Main figures and supplementary views have different roles in the reading flow.
    inside_details = False
    placement = {}
    for line in text.splitlines():
        if line == "<details>":
            inside_details = True
        elif line == "</details>":
            inside_details = False
        for name in ("Fig1_clean_correlations", "Fig2_disturbance_correlations", "Fig4_disturbance_changes",
                     "Fig3_dependent_clean_comparisons", "Fig5_all_images_QP32_manuscript", "awgn_correlation_trends"):
            if f"figures/{name}.png" in line:
                placement[name] = inside_details
    assert not any(placement[name] for name in ("Fig1_clean_correlations", "Fig2_disturbance_correlations", "Fig4_disturbance_changes"))
    assert all(placement[name] for name in ("Fig3_dependent_clean_comparisons", "Fig5_all_images_QP32_manuscript", "awgn_correlation_trends"))


def test_omission_check_reranks_remaining_images_and_reports_influence():
    table = reporting.image_omission_sensitivity(reporting.load_tables(TABLES))
    assert len(table) == 24 and table.n_images_reduced.eq(22).all()
    assert table.omitted_sources.eq("kodim02.png;kodim08.png").all()
    values = table.pivot(index="feature", columns="qp", values="rho_omitted")
    # Independently calculated SciPy values from the reviewed 22-image sample.
    np.testing.assert_allclose(values.loc["luma_sd"], [0.098814, 0.097685, 0.099944, 0.081875], atol=5e-7, rtol=0)
    np.testing.assert_allclose(values.loc["edge_fraction"], [0.856578, 0.843027, 0.859966, 0.883682], atol=5e-7, rtol=0)
    assert (np.sign(table.rho_full) == np.sign(table.rho_omitted)).all()
    assert values.idxmax().eq("edge_fraction").all()
    entropy = table[table.feature.eq("glcm_entropy") & table.qp.isin([32, 37])]
    assert entropy.leave_one_out_difference_min.lt(0).all()
    assert entropy.leave_one_out_difference_max.gt(0).all()
    assert table[table.feature.eq("sobel_si")].difference_from_sobel_omitted.isna().all()


def test_change_map_stars_follow_comparison_intervals_and_use_difference_scale(tmp_path, monkeypatch):
    tables = reporting.load_tables(TABLES)
    captured = {}

    def capture(figure, output, name):
        if name == "Fig4_disturbance_changes":
            for axis in figure.axes[:4]:
                qp = int(axis.get_title().split()[-1])
                assert axis.images[0].get_clim() == (-2, 2)
                selected = tables["contrasts"].query("family == 'RQ2' and qp == @qp")
                assert sum(text.get_text().endswith("*") for text in axis.texts) == int(
                    ((selected.simultaneous_low > 0) | (selected.simultaneous_high < 0)).sum())
                captured[qp] = axis.texts[-4].get_text()  # Homogeneity / AWGN30.
            assert "interval for B excludes zero" in figure._suptitle.get_text()
        plt.close(figure)

    monkeypatch.setattr(reporting, "save", capture)
    reporting.build(TABLES, tmp_path / "report")
    assert captured == {22: "-0.83*", 27: "-0.67", 32: "-0.75*", 37: "-0.57"}


def test_noise_plots_keep_all_four_qps_signed_ranges_and_clean_references(tmp_path, monkeypatch) -> None:
    tables = reporting.load_tables(TABLES)
    captured = {}

    def capture(figure, output, name):
        zoomed = name.endswith("_zoomed")
        for axis in figure.axes:
            assert [line.get_label() for line in axis.lines[:4]] == ["QP 22", "QP 27", "QP 32", "QP 37"]
            values = np.concatenate([line.get_ydata() for line in axis.lines[:4]])
            lower, upper = axis.get_ylim()
            assert lower <= values.min() <= values.max() <= upper
            if zoomed:
                assert upper - lower < 1.3
                if values.min() >= 0:
                    assert lower >= 0
            else:
                assert (lower, upper) == (-1, 1)
                np.testing.assert_array_equal(axis.get_yticks(), [-1, -0.5, 0, 0.5, 1])
                np.testing.assert_array_equal(axis.lines[4].get_ydata(), [0, 0])
            assert any(label.get_visible() for label in axis.get_yticklabels())
        if name == "awgn_correlation_trends_zoomed":
            lower, upper = figure.axes[5].get_ylim()
            assert lower < 0 < upper
        captured[name] = [[(line.get_xdata(), line.get_ydata()) for line in axis.lines[:4]] for axis in figure.axes]
        plt.close(figure)

    monkeypatch.setattr(reporting, "save", capture)
    reporting.plot_disturbance_trends(tables["correlations"], tmp_path)
    assert set(captured) == {"awgn_correlation_trends", "sine_correlation_trends",
                             "awgn_correlation_trends_zoomed", "sine_correlation_trends_zoomed"}
    for name in ("awgn_correlation_trends", "sine_correlation_trends"):
        for common, zoomed in zip(captured[name], captured[name + "_zoomed"], strict=True):
            np.testing.assert_array_equal(common, zoomed)
    awgn, sine = captured["awgn_correlation_trends"][5], captured["sine_correlation_trends"][5]
    np.testing.assert_array_equal(awgn[0][0], [0, 5, 15, 30])
    np.testing.assert_array_equal(sine[0][0], [0, 8, 16, 32])
    clean = tables["correlations"].query("distortion == 'clean' and feature == 'glcm_homogeneity'").set_index("qp")
    np.testing.assert_allclose([line[1][0] for line in awgn], clean.loc[[22, 27, 32, 37], "rho"])
    np.testing.assert_array_equal([line[1][0] for line in awgn], [line[1][0] for line in sine])
    assert awgn[0][1][-1] == pytest.approx(0.119156341151248)
    assert awgn[2][1][-1] == pytest.approx(-0.051304347826087)


def test_supported_conclusions_are_generated_from_actual_intervals(tmp_path) -> None:
    analysis = tmp_path / "analysis"
    copy_tables(analysis)
    tables = reporting.load_tables(analysis)
    contrasts = tables["contrasts"]
    contrasts.loc[contrasts.family.eq("RQ2"), ["simultaneous_low", "simultaneous_high"]] = [-0.5, 0.5]
    selected = (contrasts.family.eq("RQ2") & contrasts.qp.eq(27) & contrasts.distortion.eq("stripes")
                & contrasts.level.eq(32) & contrasts.feature.eq("glcm_contrast"))
    contrasts.loc[selected, ["simultaneous_low", "simultaneous_high"]] = [0.1, 0.5]
    output = tmp_path / "report"
    reporting.write_report(analysis, output, tables)
    text = (output / "README.md").read_text(encoding="utf-8")
    assert "GLCM contrast under sinusoidal bands at level 32 has a stronger direction-adjusted association at QP 27" in text
    assert "| GLCM contrast | Sine, level 32 versus clean | 27 |" in text
    assert "| GLCM homogeneity | AWGN" not in text


def test_exploratory_noise_section_is_separate_and_keeps_four_qps(tmp_path) -> None:
    from tools.research import analyze_vtm_noise_sensitivity as noise

    analysis = tmp_path / "analysis"
    copy_tables(analysis)
    rows = noise.read_rows(analysis / "joined_measurements.csv")
    cells, _, x, y = noise.build_cells(rows)
    observed = noise.spearman_last_axis(x, y)
    noise.write_rows(analysis / "exploratory_noise_comparisons.csv",
                     noise.noise_comparisons(cells, observed, np.tile(observed, (3, 1))))
    noise.write_rows(analysis / "noise_rank_diagnostics.csv", noise.noise_rank_diagnostics(rows))
    tables = reporting.load_tables(analysis)
    output = tmp_path / "report"
    reporting.write_report(analysis, output, tables)
    text = (output / "README.md").read_text(encoding="utf-8")
    assert "selected after inspecting the original results" in text
    assert "do not provide a joint error guarantee across both summaries" in text
    assert "conditional on these three realizations" in text
    assert "| GLCM homogeneity | 0.549 |" in text
    assert "CU-count ranks have a clean–noisy correlation of 0.762" in text
    assert "7.7–8.3% of its clean-image value" in text
    assert "24 out of 24" in text
    assert "analyze_vtm_noise_sensitivity.py --output" in text
    assert text.index("## Key Findings") < text.index("Exploratory comparison of descriptor responses")
    for name in reporting.NOISE_TABLES:
        assert (output / "tables" / f"{name}.csv").read_bytes() == (analysis / f"{name}.csv").read_bytes()
    comparisons = tables["exploratory_noise_comparisons"]
    comparisons.loc[0, "excludes_zero"] = not comparisons.loc[0, "excludes_zero"]
    comparisons.to_csv(analysis / "exploratory_noise_comparisons.csv", index=False)
    with pytest.raises(ValueError, match="flags"):
        reporting.load_tables(analysis)
    (analysis / "noise_rank_diagnostics.csv").unlink()
    with pytest.raises(ValueError, match="required together"):
        reporting.load_tables(analysis)
