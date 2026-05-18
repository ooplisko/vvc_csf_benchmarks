from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import QP_SWEEP_FRAMES, QP_SWEEP_QP_POINTS, SEQUENCES
from utils.console import format_bool, print_section, print_table
from utils.results import make_run_dir


SUITE_CHOICES = ["quick", "all", "smoke", "regression", "cross", "sweep", "metrics", "bdrate"]

TEST_CHECKS = [
    ("Smoke: baseline and CSF encoding", "smoke"),
    ("Decode and rec==dec MD5", "smoke"),
    ("Baseline decoder reads CSF bitstream", "cross"),
    ("--CSFScalingList 0 equals baseline", "regression"),
    ("QP sweep on local sequences", "sweep"),
    ("Parse bitrate and PSNR metrics", "metrics"),
    ("BD-rate from QP sweep points", "bdrate"),
]


def _parse_qps(value: str | None) -> list[int] | None:
    if not value:
        return None
    return [int(item) for item in value.split(",") if item.strip()]


def _prompt_suite() -> str:
    print("Оберіть режим тестування:")
    print("  1 - швидкий прогін: smoke + regression + cross-check")
    print("  2 - повний прогін: quick checks + QP sweep, метрики, BD-rate")
    while True:
        choice = input("Ваш вибір [1/2]: ").strip()
        if choice == "1":
            return "quick"
        if choice == "2":
            return "all"
        print("Будь ласка, введіть 1 або 2.")


def _print_test_plan(suite: str, qps: list[int], frames: int, sequence_names: list[str]) -> None:
    planned = {
        "smoke": suite in ("quick", "all", "smoke"),
        "regression": suite in ("quick", "all", "regression"),
        "cross": suite in ("quick", "all", "cross"),
        "sweep": suite in ("all", "sweep"),
        "metrics": suite in ("all", "metrics"),
        "bdrate": suite in ("all", "bdrate"),
    }

    print_section("TEST PLAN")
    print_table(
        ["No.", "Check", "Run"],
        [
            (index, check, "yes" if planned[key] else "no")
            for index, (check, key) in enumerate(TEST_CHECKS, start=1)
        ],
    )
    print(f"\n  sequences: {', '.join(sequence_names) if sequence_names else 'none'}")
    print(f"  QPs:       {', '.join(str(qp) for qp in qps)}")
    print(f"  frames:    {frames}")


def _print_final_report(results: dict[str, bool], root: Path) -> bool:
    print_section("FINAL REPORT")
    print_table(
        ["No.", "Check", "Result"],
        [
            (index, check, format_bool(results[key]) if key in results else "SKIP")
            for index, (check, key) in enumerate(TEST_CHECKS, start=1)
        ],
    )

    all_ok = all(results.values()) if results else False
    print(f"\nOverall: {format_bool(all_ok)}")
    print(f"Results root: {root}")
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VVenC CSF conformance and quality tests.")
    parser.add_argument(
        "suite",
        nargs="?",
        choices=SUITE_CHOICES,
        help="quick runs smoke/regression/cross. all also runs QP sweep and metrics.",
    )
    parser.add_argument(
        "--sequences",
        nargs="+",
        choices=sorted(SEQUENCES),
        help="Sequence names for QP sweep. Default: all local sequences.",
    )
    parser.add_argument("--qps", default=None, help="Comma-separated QP list, e.g. 22,27,32,37.")
    parser.add_argument("--frames", type=int, default=QP_SWEEP_FRAMES, help="Frames to encode in QP sweep.")
    args = parser.parse_args()

    suite = args.suite or _prompt_suite()
    qps = _parse_qps(args.qps) or QP_SWEEP_QP_POINTS
    selected_sequences = args.sequences or sorted(SEQUENCES)

    root = make_run_dir(suite)
    print(f"Run root: {root}")
    _print_test_plan(suite, qps, args.frames, selected_sequences)

    results: dict[str, bool] = {}

    if suite in ("quick", "all", "smoke"):
        from tests.smoke_test import run_smoke_test

        results["smoke"] = run_smoke_test(root / "smoke")

    if suite in ("quick", "all", "regression"):
        from tests.regression_test import run_regression_test

        results["regression"] = run_regression_test(root / "regression")

    if suite in ("quick", "all", "cross"):
        from tests.cross_check_test import run_cross_check_test

        results["cross"] = run_cross_check_test(root / "cross")

    if suite in ("all", "sweep"):
        from tests.qp_sweep_test import run_qp_sweep_test

        sweep_dir = root if suite == "sweep" else root / "sweep"
        results["sweep"] = run_qp_sweep_test(args.sequences, qps, args.frames, sweep_dir)

    if suite in ("all", "metrics"):
        from metrics.collect_metrics import collect_all_metrics

        sweep_dir = root if suite == "sweep" else root / "sweep"
        results["metrics"] = collect_all_metrics(sweep_dir if sweep_dir.exists() else None)

    if suite in ("all", "bdrate"):
        from metrics.bdrate import calculate_bdrate

        metrics_csv = root / "sweep" / "metrics.csv"
        results["bdrate"] = calculate_bdrate(
            metrics_csv if metrics_csv.exists() else None,
            root / "sweep" / "bdrate.csv",
        )

    if suite in ("all", "metrics", "bdrate"):
        from metrics.report import write_analysis_report

        metrics_csv = root / "sweep" / "metrics.csv"
        write_analysis_report(metrics_csv if metrics_csv.exists() else None, root / "analysis")

    all_ok = _print_final_report(results, root)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
