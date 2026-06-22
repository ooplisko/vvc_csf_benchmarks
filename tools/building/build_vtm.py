"""Build VTM binary sets used by the benchmark and validation workflows."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent
VTM_REMOTE = "https://vcgit.hhi.fraunhofer.de/jvet/VVCSoftware_VTM.git"


@dataclass(frozen=True)
class BuildTarget:
    """Description of one VTM source tree and output binary set."""

    name: str
    version: str
    source_dir: Path
    build_dir: Path
    output_dir: Path
    outputs: dict[str, str]
    cmake_args: tuple[str, ...] = ()
    apply_gcc13_compat: bool = False
    require_existing_source: bool = False


TARGETS = {
    "vtm18-validation": BuildTarget(
        name="vtm18-validation",
        version="VTM-18.0",
        source_dir=WORKSPACE / "VVCSoftware_VTM_18",
        build_dir=WORKSPACE / "VVCSoftware_VTM_18" / "build",
        output_dir=ROOT / "binaries" / "vtm" / "vtm18" / "baseline",
        outputs={"EncoderApp.exe": "EncoderApp.exe", "DecoderApp.exe": "DecoderApp.exe"},
        apply_gcc13_compat=True,
    ),
    "vtm23-baseline": BuildTarget(
        name="vtm23-baseline",
        version="VTM-23.0",
        source_dir=WORKSPACE / "VVCSoftware_VTM_baseline",
        build_dir=WORKSPACE / "VVCSoftware_VTM_baseline" / "build",
        output_dir=ROOT / "binaries" / "vtm" / "vtm23" / "baseline",
        outputs={"EncoderApp.exe": "EncoderApp.exe", "DecoderApp.exe": "DecoderApp.exe"},
        require_existing_source=True,
    ),
    "vtm23-csf": BuildTarget(
        name="vtm23-csf",
        version="feature/csf-scaling-list",
        source_dir=WORKSPACE / "VVCSoftware_VTM",
        build_dir=WORKSPACE / "VVCSoftware_VTM" / "build",
        output_dir=ROOT / "binaries" / "vtm" / "vtm23" / "csf",
        outputs={"EncoderApp.exe": "EncoderApp.exe"},
        require_existing_source=True,
    ),
    "vtm23-baseline-trace": BuildTarget(
        name="vtm23-baseline-trace",
        version="VTM-23.0",
        source_dir=WORKSPACE / "VVCSoftware_VTM_baseline",
        build_dir=WORKSPACE / "VVCSoftware_VTM_baseline" / "build_trace",
        output_dir=ROOT / "binaries" / "vtm" / "vtm23" / "baseline_trace",
        outputs={"EncoderApp.exe": "EncoderApp.exe"},
        cmake_args=("-DENABLE_TRACING=ON",),
        require_existing_source=True,
    ),
    "vtm23-csf-trace": BuildTarget(
        name="vtm23-csf-trace",
        version="feature/csf-scaling-list",
        source_dir=WORKSPACE / "VVCSoftware_VTM",
        build_dir=WORKSPACE / "VVCSoftware_VTM" / "build_trace",
        output_dir=ROOT / "binaries" / "vtm" / "vtm23" / "csf_trace",
        outputs={"EncoderApp.exe": "EncoderApp.exe"},
        cmake_args=("-DENABLE_TRACING=ON",),
        require_existing_source=True,
    ),
}


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def ensure_source(target: BuildTarget) -> None:
    if target.source_dir.exists():
        return
    if target.require_existing_source:
        raise FileNotFoundError(f"{target.name} source tree is required but missing: {target.source_dir}")
    run(["git", "clone", "--depth", "1", "--branch", target.version, VTM_REMOTE, str(target.source_dir)])


def ensure_gcc13_compatibility(source_dir: Path) -> None:
    """Patch old VTM 18.0 headers to include fixed-width integer definitions."""

    patches = (
        (source_dir / "source" / "Lib" / "CommonLib" / "TypeDef.h", "#include <cstddef>\n"),
        (source_dir / "source" / "Lib" / "CommonLib" / "dtrace.h", "#include <cstdarg>\n"),
        (source_dir / "source" / "Lib" / "Utilities" / "program_options_lite.h", "#include <map>\n"),
    )
    for path, anchor in patches:
        text = path.read_text(encoding="utf-8")
        if "#include <cstdint>" in text:
            continue
        path.write_text(text.replace(anchor, f"{anchor}#include <cstdint>\n"), encoding="utf-8", newline="\n")


def configure(target: BuildTarget, generator: str, build_type: str) -> None:
    run(
        [
            "cmake",
            "-S",
            str(target.source_dir),
            "-B",
            str(target.build_dir),
            "-G",
            generator,
            f"-DCMAKE_BUILD_TYPE={build_type}",
            *target.cmake_args,
        ]
    )


def build(target: BuildTarget, build_type: str, parallel: int) -> None:
    run(["cmake", "--build", str(target.build_dir), "--config", build_type, "--parallel", str(parallel)])


def copy_outputs(target: BuildTarget) -> None:
    target.output_dir.mkdir(parents=True, exist_ok=True)
    for source_name, output_name in target.outputs.items():
        matches = sorted((target.source_dir / "bin").rglob(source_name))
        if not matches:
            raise FileNotFoundError(f"Built executable not found under {target.source_dir / 'bin'}: {source_name}")
        source = matches[-1]
        destination = target.output_dir / output_name
        print(f"Copying {source} -> {destination}")
        shutil.copy2(source, destination)


def build_target(target: BuildTarget, generator: str, build_type: str, parallel: int) -> None:
    print(f"== {target.name} ==")
    ensure_source(target)
    if target.apply_gcc13_compat:
        ensure_gcc13_compatibility(target.source_dir)
    configure(target, generator, build_type)
    build(target, build_type, parallel)
    copy_outputs(target)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build VTM binaries for validation and CSF benchmarking.")
    parser.add_argument(
        "target",
        choices=(*TARGETS.keys(), "all"),
        help="Binary set to build. 'all' builds validation, baseline, CSF, and trace encoder targets.",
    )
    parser.add_argument("--generator", default="MinGW Makefiles", help="CMake generator.")
    parser.add_argument("--build-type", default="Release", help="CMake build type/configuration.")
    parser.add_argument("--parallel", type=int, default=8, help="Parallel build jobs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    names = TARGETS.keys() if args.target == "all" else (args.target,)
    for name in names:
        build_target(TARGETS[name], args.generator, args.build_type, args.parallel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
