from __future__ import annotations

import csv
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.console import print_section, print_table
from utils.results import latest_run_dir


LOG_ROW_RE = re.compile(
    r"\s+\d+\s+"
    r"(?:[a-zA-Z]\s+)?"
    r"(?P<bitrate>\d+(?:\.\d+)?)\s+"
    r"(?P<y>\d+(?:\.\d+)?)\s+"
    r"(?P<u>\d+(?:\.\d+)?)\s+"
    r"(?P<v>\d+(?:\.\d+)?)"
)

TOTAL_TIME_RE = re.compile(r"Total Time:\s+(?P<cpu>\d+(?:\.\d+)?) sec\. \[cpu\]\s+(?P<elapsed>\d+(?:\.\d+)?) sec")


def parse_vvenc_log(log_path: Path) -> dict[str, float] | None:
    lines = log_path.read_text(errors="replace").splitlines()
    total_time: dict[str, float] = {}
    for line in lines:
        match = TOTAL_TIME_RE.search(line)
        if match:
            total_time = {
                "cpu_seconds": float(match.group("cpu")),
                "elapsed_seconds": float(match.group("elapsed")),
            }

    for index, line in enumerate(lines):
        if "Total Frames" in line and "Bitrate" in line and "Y-PSNR" in line:
            if index + 1 >= len(lines):
                return None
            match = LOG_ROW_RE.search(lines[index + 1])
            if not match:
                return None
            return {
                "bitrate_kbps": float(match.group("bitrate")),
                "psnr_y": float(match.group("y")),
                "psnr_u": float(match.group("u")),
                "psnr_v": float(match.group("v")),
                **total_time,
            }
    return None


def _parse_tag(log_path: Path) -> tuple[str, int, str] | None:
    # Expected name: Sequence_QP32_baseline_enc.log
    stem = log_path.stem
    if not stem.endswith("_enc"):
        return None
    parts = stem[:-4].split("_")
    if len(parts) < 3:
        return None

    mode = parts[-1]
    qp_part = parts[-2]
    sequence = "_".join(parts[:-2])
    if not qp_part.startswith("QP"):
        return None

    return sequence, int(qp_part[2:]), mode


def collect_all_metrics(log_dir: Path | None = None, output_csv: Path | None = None) -> bool:
    print_section("METRICS: bitrate and PSNR from encoder logs")
    if log_dir is None:
        latest_all = latest_run_dir("all")
        latest_sweep = latest_run_dir("sweep")
        if latest_all and (latest_all / "sweep").exists():
            log_dir = latest_all / "sweep"
        else:
            log_dir = latest_sweep

    if log_dir is None or not log_dir.exists():
        print("  FAIL no QP sweep result directory found")
        return False

    output_csv = output_csv or (log_dir / "metrics.csv")
    rows = []

    for log_path in sorted(log_dir.rglob("*_enc.log")):
        parsed_tag = _parse_tag(log_path)
        if parsed_tag is None:
            continue

        metrics = parse_vvenc_log(log_path)
        if metrics is None:
            print(f"  WARN could not parse {log_path}")
            continue

        sequence, qp, mode = parsed_tag
        tag = f"{sequence}_QP{qp}_{mode}"
        bitstream = log_path.with_name(f"{tag}.bin")
        rows.append(
            {
                "sequence": sequence,
                "qp": qp,
                "mode": mode,
                **metrics,
                "bitstream_bytes": bitstream.stat().st_size if bitstream.exists() else 0,
                "log": str(log_path),
            }
        )

    if not rows:
        print(f"  FAIL no encoder metrics found in {log_dir}")
        return False

    fieldnames = [
        "sequence",
        "qp",
        "mode",
        "bitrate_kbps",
        "psnr_y",
        "psnr_u",
        "psnr_v",
        "cpu_seconds",
        "elapsed_seconds",
        "bitstream_bytes",
        "log",
    ]
    with output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["sequence"], r["qp"], r["mode"])))

    print(f"  PASS metrics written: {output_csv}")
    print(f"       rows: {len(rows)}")
    _print_delta_table(rows)
    return True


def _print_delta_table(rows: list[dict]) -> None:
    by_key: dict[tuple[str, int], dict[str, dict]] = {}
    for row in rows:
        by_key.setdefault((row["sequence"], row["qp"]), {})[row["mode"]] = row

    table_rows = []
    for (sequence, qp), modes in sorted(by_key.items()):
        baseline = modes.get("baseline")
        csf = modes.get("csf")
        if not baseline or not csf:
            continue

        bitrate_delta = _percent_delta(csf["bitrate_kbps"], baseline["bitrate_kbps"])
        psnr_delta = csf["psnr_y"] - baseline["psnr_y"]
        time_delta = _percent_delta(csf.get("elapsed_seconds", 0), baseline.get("elapsed_seconds", 0))
        table_rows.append(
            [
                sequence,
                qp,
                f"{baseline['bitrate_kbps']:.2f}",
                f"{csf['bitrate_kbps']:.2f}",
                f"{bitrate_delta:+.2f}%",
                f"{psnr_delta:+.3f}",
                f"{time_delta:+.2f}%",
            ]
        )

    if table_rows:
        print("\n  CSF vs baseline")
        print_table(["Sequence", "QP", "BR base", "BR CSF", "BR delta", "Y-PSNR delta", "Time delta"], table_rows)


def _percent_delta(value: float, anchor: float) -> float:
    if anchor == 0:
        return 0.0
    return (value - anchor) * 100.0 / anchor


if __name__ == "__main__":
    raise SystemExit(0 if collect_all_metrics() else 1)
