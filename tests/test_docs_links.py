from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_BLOB_PREFIX = "https://github.com/For2natop1ua/vvenc_csf_tests/blob/master/"
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
HTML_SRC = re.compile(r"""<img\s+[^>]*src=["']([^"']+)["']""", re.IGNORECASE)
DEPRECATED_DOC_PATHS = (
    "docs/image_benchmark/combined/",
    "docs/image_benchmark/standard_grayscale/",
    "docs/image_benchmark/synthetic/",
    "docs/image_benchmark/kodak/",
    "docs/partition_maps/standard_grayscale/",
    "docs/partition_maps/synthetic/",
    "docs/partition_maps/kodak/",
)


def markdown_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*.md") if ".git" not in path.parts)


def _target_path(markdown_path: Path, target: str) -> Path | None:
    target = target.split("#", 1)[0].strip()
    if not target:
        return None
    if target.startswith(REPO_BLOB_PREFIX):
        return ROOT / target.removeprefix(REPO_BLOB_PREFIX)
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return None
    return markdown_path.parent / target.replace("%20", " ")


def local_markdown_targets(markdown_path: Path) -> list[tuple[int, str, Path]]:
    targets = []
    text = markdown_path.read_text(encoding="utf-8")
    for pattern in (MARKDOWN_LINK, HTML_SRC):
        for match in pattern.finditer(text):
            target = match.group(1).strip()
            path = _target_path(markdown_path, target)
            if path is None:
                continue
            targets.append((text.count("\n", 0, match.start()) + 1, target, path))
    return targets


def test_markdown_links_point_to_existing_local_files() -> None:
    missing = []
    for markdown_path in markdown_files():
        for line, target, path in local_markdown_targets(markdown_path):
            if not path.exists():
                missing.append(f"{markdown_path.relative_to(ROOT)}:{line} -> {target}")

    assert missing == []


def test_docs_do_not_reference_deprecated_report_roots() -> None:
    offenders = []
    for markdown_path in markdown_files():
        text = markdown_path.read_text(encoding="utf-8")
        for deprecated_path in DEPRECATED_DOC_PATHS:
            if deprecated_path in text:
                offenders.append(f"{markdown_path.relative_to(ROOT)} -> {deprecated_path}")

    assert offenders == []
