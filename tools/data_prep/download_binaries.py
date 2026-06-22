from __future__ import annotations

import argparse
import shutil
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BINARIES_URL = "https://github.com/For2natop1ua/vvenc_csf_tests/releases/download/v1.1.0/binaries.zip"


def _has_binaries_root(zip_file: zipfile.ZipFile) -> bool:
    return any(Path(info.filename).parts[:1] == ("binaries",) for info in zip_file.infolist())


def _extract_root(output: Path, archive_has_binaries_root: bool) -> Path:
    if archive_has_binaries_root:
        return output.parent if output.name.lower() == "binaries" else output
    return output if output.name.lower() == "binaries" else output / "binaries"


def _safe_extract(zip_file: zipfile.ZipFile, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    root = output.resolve()
    for info in zip_file.infolist():
        destination = (root / info.filename).resolve()
        if root != destination and root not in destination.parents:
            raise ValueError(f"Unsafe archive entry outside output directory: {info.filename}")
    zip_file.extractall(root)


def download_and_extract(url: str, output: Path) -> None:
    """Download a release binary archive and extract it into the project."""

    output.mkdir(parents=True, exist_ok=True)
    zip_path = output / "binaries.zip"

    source_path = Path(url)
    if source_path.exists():
        print(f"Copying binaries from {source_path}...")
        shutil.copy2(source_path, zip_path)
    else:
        print(f"Downloading binaries from {url}...")
        urllib.request.urlretrieve(url, zip_path)

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            extract_root = _extract_root(output, _has_binaries_root(zip_file))
            print(f"Extracting to {extract_root}...")
            _safe_extract(zip_file, extract_root)
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"Downloaded file is not a valid zip archive: {zip_path}") from exc
    finally:
        if zip_path.exists():
            zip_path.unlink()

    print("Extraction complete.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and extract benchmark binaries from GitHub Releases.")
    parser.add_argument("--url", default=DEFAULT_BINARIES_URL, help="Release ZIP URL.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT,
        help="Extraction root. By default the archive creates or updates ./binaries.",
    )
    args = parser.parse_args()

    download_and_extract(args.url, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
