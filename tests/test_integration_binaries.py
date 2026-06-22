from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.integration
def test_vvenc_binaries_are_available(require_vvenc_binaries: dict[str, Path]) -> None:
    assert set(require_vvenc_binaries) == {"baseline_encoder", "csf_encoder", "decoder"}


@pytest.mark.integration
def test_vtm_binaries_are_available(require_vtm_binaries: dict[str, Path]) -> None:
    assert set(require_vtm_binaries) == {"baseline_encoder", "csf_encoder", "baseline_decoder"}


def test_vtm18_validation_binaries_are_available(require_vtm18_binaries: dict[str, Path]) -> None:
    assert set(require_vtm18_binaries) == {"encoder", "decoder"}


@pytest.mark.integration
def test_trace_binaries_are_available(require_trace_binaries: dict[str, Path]) -> None:
    assert set(require_trace_binaries) == {"baseline_trace_encoder", "csf_trace_encoder"}


@pytest.mark.integration
def test_vtm_trace_binaries_are_available(require_vtm_trace_binaries: dict[str, Path]) -> None:
    assert set(require_vtm_trace_binaries) == {"baseline_trace_encoder", "csf_trace_encoder"}
