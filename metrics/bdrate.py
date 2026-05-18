from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.console import print_section, print_table
from utils.results import latest_run_dir

try:
    import bjontegaard as bd
except ImportError:  # pragma: no cover - depends on optional environment setup
    bd = None


def _default_metrics_csv() -> Path | None:
    latest_all = latest_run_dir("all")
    latest_sweep = latest_run_dir("sweep")
    candidates = []
    if latest_all:
        candidates.append(latest_all / "sweep" / "metrics.csv")
    if latest_sweep:
        candidates.append(latest_sweep / "metrics.csv")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_points(csv_path: Path) -> dict:
    points = defaultdict(lambda: {"baseline": [], "csf": []})
    with csv_path.open("r", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            try:
                points[row["sequence"]][row["mode"]].append(
                    (float(row["bitrate_kbps"]), float(row["psnr_y"]))
                )
            except (KeyError, ValueError):
                continue

    for sequence in points.values():
        for mode in ("baseline", "csf"):
            sequence[mode].sort(key=lambda pair: pair[1])
    return points


def calculate_bdrate(csv_path: Path | None = None, output_csv: Path | None = None) -> bool:
    if bd is None:
        print("  FAIL missing dependency: pip install bjontegaard")
        return False

    csv_path = csv_path or _default_metrics_csv()
    if csv_path is None or not csv_path.exists():
        print("  FAIL metrics.csv not found. Run QP sweep and metrics first.")
        return False

    data = _load_points(csv_path)
    if not data:
        print(f"  FAIL no BD-rate data in {csv_path}")
        return False

    print_section("BD-RATE: PSNR-Y, Akima")

    any_ok = False
    rows = []
    for sequence, modes in sorted(data.items()):
        anchor = modes["baseline"]
        test = modes["csf"]
        if len(anchor) < 2 or len(test) < 2:
            rows.append([sequence, "N/A", "need at least two QP points per mode"])
            continue

        try:
            rate_anchor = [rate for rate, _psnr in anchor]
            psnr_anchor = [psnr for _rate, psnr in anchor]
            rate_test = [rate for rate, _psnr in test]
            psnr_test = [psnr for _rate, psnr in test]
            value = bd.bd_rate(rate_anchor, psnr_anchor, rate_test, psnr_test, "akima")
        except Exception as exc:  # pragma: no cover - package-specific validation
            rows.append([sequence, "ERROR", str(exc)])
            continue

        any_ok = True
        rows.append([sequence, f"{value:+.2f}%", "CSF vs baseline"])

    print_table(["Sequence", "BD-rate", "Note"], rows)
    if output_csv and rows:
        with output_csv.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["sequence", "bd_rate", "note"])
            writer.writerows(rows)
        print(f"\n  BD-rate CSV: {output_csv}")

    return any_ok


if __name__ == "__main__":
    raise SystemExit(0 if calculate_bdrate() else 1)
