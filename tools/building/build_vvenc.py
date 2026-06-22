"""Build VVenC encoder binaries used by the benchmark workflows."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent


@dataclass(frozen=True)
class BuildTarget:
    """Description of one VVenC source tree and output executable."""

    name: str
    source_dir: Path
    build_dir: Path
    output_path: Path
    cmake_args: tuple[str, ...] = ()


TARGETS = {
    "vvenc-default": BuildTarget(
        name="vvenc-default",
        source_dir=WORKSPACE / "vvenc_baseline",
        build_dir=WORKSPACE / "vvenc_baseline" / "build_release",
        output_path=ROOT / "binaries" / "vvenc" / "vvenc_default.exe",
    ),
    "vvenc-csf": BuildTarget(
        name="vvenc-csf",
        source_dir=WORKSPACE / "vvenc",
        build_dir=WORKSPACE / "vvenc" / "build_release",
        output_path=ROOT / "binaries" / "vvenc" / "vvenc_csf.exe",
    ),
    "vvenc-default-trace": BuildTarget(
        name="vvenc-default-trace",
        source_dir=WORKSPACE / "vvenc_baseline",
        build_dir=WORKSPACE / "vvenc_baseline" / "build_trace",
        output_path=ROOT / "binaries" / "vvenc" / "vvenc_default_trace.exe",
        cmake_args=("-DVVENC_ENABLE_TRACING=ON",),
    ),
    "vvenc-csf-trace": BuildTarget(
        name="vvenc-csf-trace",
        source_dir=WORKSPACE / "vvenc",
        build_dir=WORKSPACE / "vvenc" / "build_trace",
        output_path=ROOT / "binaries" / "vvenc" / "vvenc_csf_trace.exe",
        cmake_args=("-DVVENC_ENABLE_TRACING=ON",),
    ),
}


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def configure(target: BuildTarget, generator: str, build_type: str) -> None:
    if not target.source_dir.exists():
        raise FileNotFoundError(f"{target.name} source tree is required but missing: {target.source_dir}")
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
            "-DVVENC_ENABLE_LINK_TIME_OPT=OFF",
            *target.cmake_args,
        ]
    )


def build(target: BuildTarget, parallel: int) -> None:
    run(["cmake", "--build", str(target.build_dir), "--target", "vvencFFapp", "--parallel", str(parallel)])


def copy_output(target: BuildTarget) -> None:
    source = target.source_dir / "bin" / "release-static" / "vvencFFapp.exe"
    if not source.exists():
        raise FileNotFoundError(f"Built executable not found: {source}")
    target.output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Copying {source} -> {target.output_path}")
    shutil.copy2(source, target.output_path)


def build_target(target: BuildTarget, generator: str, build_type: str, parallel: int) -> None:
    print(f"== {target.name} ==")
    configure(target, generator, build_type)
    build(target, parallel)
    copy_output(target)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build VVenC encoder binaries for CSF benchmarking.")
    parser.add_argument(
        "target",
        choices=(*TARGETS.keys(), "all"),
        help="Binary set to build. 'all' builds default, CSF, and trace encoder targets.",
    )
    parser.add_argument("--generator", default="MinGW Makefiles", help="CMake generator.")
    parser.add_argument("--build-type", default="Release", help="CMake build type.")
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
