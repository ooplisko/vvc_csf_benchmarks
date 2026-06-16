import os
import urllib.request
import zipfile
import argparse
from pathlib import Path

DEFAULT_BINARIES_URL = "https://github.com/For2natop1ua/vvenc_csf_tests/releases/download/v1.0.0/binaries.zip"

def download_and_extract(url: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "binaries.zip"
    
    print(f"Downloading binaries from {url}...")
    try:
        urllib.request.urlretrieve(url, zip_path)
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        print("Please check the URL or your internet connection.")
        return
        
    print(f"Extracting to {output_dir}...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        print("Extraction complete.")
    except zipfile.BadZipFile:
        print("Downloaded file is not a valid zip archive.")
    finally:
        if zip_path.exists():
            zip_path.unlink()

def main():
    parser = argparse.ArgumentParser(description="Download and extract benchmark binaries from GitHub Releases.")
    parser.add_argument("--url", type=str, default=DEFAULT_BINARIES_URL, help="URL of the binaries zip file.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] / "binaries", help="Output directory for the binaries.")
    args = parser.parse_args()

    download_and_extract(args.url, args.output)

if __name__ == "__main__":
    main()
