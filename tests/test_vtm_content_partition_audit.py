from __future__ import annotations

import pytest

from tools.research.audit_vtm_content_partition_data import baseline_rows


def test_audit_excludes_csf_and_collapses_identical_jobs() -> None:
    row = {"dataset": "kodak", "mode": "baseline", "stimulus": "x", "qp": "32", "cu_count": "7"}
    selected, excluded, duplicates = baseline_rows([row, dict(row), dict(row, mode="csf")])
    assert selected == [row]
    assert (excluded, duplicates) == (1, 1)


@pytest.mark.parametrize("field", ["cu_count", "image_sha256", "trace_sha256", "encoder_sha256"])
def test_audit_rejects_conflicting_duplicate_jobs(field: str) -> None:
    row = {"dataset": "kodak", "mode": "baseline", "stimulus": "x", "qp": "32", field: "a"}
    with pytest.raises(ValueError, match="Conflicting baseline duplicate"):
        baseline_rows([row, dict(row, **{field: "b"})])
