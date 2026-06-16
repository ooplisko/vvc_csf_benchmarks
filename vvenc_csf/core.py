from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


# ====================================================================================================================
# Command execution
# ====================================================================================================================


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    stdout: str
    returncode: int


class CommandRunner:
    """Runs external tools and optionally captures their output into log files.

    Parameters
    ----------
    cwd : Path, optional
        The working directory where commands will be executed. Defaults to the repository root.

    Examples
    --------
    >>> runner = CommandRunner()
    >>> result = runner.run(["echo", "hello"])
    >>> print(result.stdout.strip())
    hello
    """

    def __init__(self, cwd: Path = ROOT) -> None:
        self.cwd = cwd

    def run(self, cmd: list[str], log_file: Path | None = None) -> CommandResult:
        result = subprocess.run(cmd, cwd=self.cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text("[COMMAND] " + " ".join(cmd) + "\n\n" + result.stdout, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stdout}")
        return CommandResult(cmd, result.stdout, result.returncode)


# ====================================================================================================================
# Repository and file helpers
# ====================================================================================================================


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def resolve_project_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def executable_name(stem: str) -> str:
    return f"{stem}.exe" if sys.platform == "win32" else stem


def platform_executable(path: Path) -> Path:
    if path.suffix:
        return path
    return path.with_name(executable_name(path.name))


def parse_qps(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item.strip()]


def ffprobe_size(path: Path, runner: CommandRunner | None = None) -> tuple[int, int]:
    runner = runner or CommandRunner()
    out = runner.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=s=x:p=0",
            str(path),
        ]
    ).stdout
    width, height = out.strip().split("x")
    return int(width), int(height)


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def files_equal(left: Path, right: Path) -> bool:
    return left.exists() and right.exists() and left.stat().st_size == right.stat().st_size and file_md5(left) == file_md5(right)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
