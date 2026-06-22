from __future__ import annotations

from pathlib import Path

import pytest

from vvenc_csf.core import platform_executable


ROOT = Path(__file__).resolve().parents[1]


VVENC_BINARIES = {
    "baseline_encoder": platform_executable(ROOT / "binaries" / "vvenc" / "vvenc_default"),
    "csf_encoder": platform_executable(ROOT / "binaries" / "vvenc" / "vvenc_csf"),
    "decoder": platform_executable(ROOT / "binaries" / "vvenc" / "vvdecapp"),
}


VTM_BINARIES = {
    "baseline_encoder": platform_executable(ROOT / "binaries" / "vtm" / "vtm23" / "baseline" / "EncoderApp"),
    "csf_encoder": platform_executable(ROOT / "binaries" / "vtm" / "vtm23" / "csf" / "EncoderApp"),
    "baseline_decoder": platform_executable(ROOT / "binaries" / "vtm" / "vtm23" / "baseline" / "DecoderApp"),
}

VTM18_BINARIES = {
    "encoder": platform_executable(ROOT / "binaries" / "vtm" / "vtm18" / "baseline" / "EncoderApp"),
    "decoder": platform_executable(ROOT / "binaries" / "vtm" / "vtm18" / "baseline" / "DecoderApp"),
}


TRACE_BINARIES = {
    "baseline_trace_encoder": platform_executable(ROOT / "binaries" / "vvenc" / "vvenc_default_trace"),
    "csf_trace_encoder": platform_executable(ROOT / "binaries" / "vvenc" / "vvenc_csf_trace"),
}

VTM_TRACE_BINARIES = {
    "baseline_trace_encoder": platform_executable(ROOT / "binaries" / "vtm" / "vtm23" / "baseline_trace" / "EncoderApp"),
    "csf_trace_encoder": platform_executable(ROOT / "binaries" / "vtm" / "vtm23" / "csf_trace" / "EncoderApp"),
}


def _binary_skip_reason(path: Path) -> str | None:
    if not path.exists():
        return f"missing binary: {path}"
    return None


def _require_binaries(paths: dict[str, Path]) -> dict[str, Path]:
    reasons = [reason for reason in (_binary_skip_reason(path) for path in paths.values()) if reason]
    if reasons:
        pytest.skip("; ".join(reasons))
    return paths


@pytest.fixture
def require_vvenc_binaries() -> dict[str, Path]:
    return _require_binaries(VVENC_BINARIES)


@pytest.fixture
def require_vtm_binaries() -> dict[str, Path]:
    return _require_binaries(VTM_BINARIES)


@pytest.fixture
def require_vtm18_binaries() -> dict[str, Path]:
    return _require_binaries(VTM18_BINARIES)


@pytest.fixture
def require_trace_binaries() -> dict[str, Path]:
    return _require_binaries(TRACE_BINARIES)


@pytest.fixture
def require_vtm_trace_binaries() -> dict[str, Path]:
    return _require_binaries(VTM_TRACE_BINARIES)
