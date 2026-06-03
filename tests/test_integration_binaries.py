from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.integration
def test_benchmark_binaries_are_available(require_benchmark_binaries: dict[str, Path]) -> None:
    assert set(require_benchmark_binaries) == {"baseline_encoder", "csf_encoder", "decoder"}


@pytest.mark.integration
def test_trace_binaries_are_available(require_trace_binaries: dict[str, Path]) -> None:
    assert set(require_trace_binaries) == {"baseline_trace_encoder", "csf_trace_encoder"}
