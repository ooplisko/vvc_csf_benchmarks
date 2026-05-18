from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config import RESULTS_DIR, RUNS_DIR


def make_run_dir(label: str, parent: Path | None = None) -> Path:
    root = parent or RUNS_DIR
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = root / f"{timestamp}_{label}"
    run_dir.mkdir(parents=True, exist_ok=False)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    latest_file = RESULTS_DIR / f"LATEST_{label}.txt"
    latest_file.write_text(str(run_dir), encoding="utf-8")
    return run_dir


def latest_run_dir(label: str) -> Path | None:
    latest_file = RESULTS_DIR / f"LATEST_{label}.txt"
    if not latest_file.exists():
        return None

    path = Path(latest_file.read_text(encoding="utf-8").strip())
    return path if path.exists() else None
