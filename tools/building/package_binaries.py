"""Create the GitHub Release archive for benchmark binaries."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "dist" / "binaries.zip"


def package_binaries(output: Path) -> None:
    """Write a ZIP archive containing the top-level binaries/ folder."""

    binaries_root = ROOT / "binaries"
    if not binaries_root.exists():
        raise FileNotFoundError(f"Missing binaries directory: {binaries_root}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(binaries_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(ROOT).as_posix())

    print(f"Wrote {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Package binaries/ into a release ZIP.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    package_binaries(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
