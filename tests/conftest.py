from __future__ import annotations

from pathlib import Path

import pytest

from vvenc_csf.core import platform_executable


ROOT = Path(__file__).resolve().parent.parent


BENCHMARK_BINARIES = {
    "baseline_encoder": platform_executable(ROOT / "binaries" / "vvenc_default"),
    "csf_encoder": platform_executable(ROOT / "binaries" / "vvenc_csf"),
    "decoder": platform_executable(ROOT / "binaries" / "vvdecapp"),
}


TRACE_BINARIES = {
    "baseline_trace_encoder": platform_executable(ROOT / "binaries" / "vvenc_default_trace"),
    "csf_trace_encoder": platform_executable(ROOT / "binaries" / "vvenc_csf_trace"),
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
def require_benchmark_binaries() -> dict[str, Path]:
    return _require_binaries(BENCHMARK_BINARIES)


@pytest.fixture
def require_trace_binaries() -> dict[str, Path]:
    return _require_binaries(TRACE_BINARIES)
