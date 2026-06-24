from __future__ import annotations

import argparse
import re
from pathlib import Path


LOCAL_SVG_LINK = re.compile(r"(?P<prefix>[(\"'])(?P<target>(?![a-zA-Z][a-zA-Z0-9+.-]*:)[^()\"']+?\.svg)(?P<suffix>[)\"'])")


def convert_svg_to_png(svg_path: Path, png_path: Path) -> None:
    try:
        from reportlab.graphics import renderPM
        from svglib.svglib import svg2rlg
    except ImportError as exc:
        raise RuntimeError("SVG migration requires svglib and reportlab. Install requirements.txt first.") from exc

    drawing = svg2rlg(str(svg_path))
    if drawing is None:
        raise RuntimeError(f"Could not parse SVG: {svg_path}")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    renderPM.drawToFile(drawing, str(png_path), fmt="PNG")
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise RuntimeError(f"PNG conversion produced an empty file: {png_path}")


def update_markdown_links(root: Path) -> int:
    changed = 0
    for markdown in root.rglob("*.md"):
        if ".git" in markdown.parts:
            continue
        text = markdown.read_text(encoding="utf-8")
        updated = LOCAL_SVG_LINK.sub(lambda match: f"{match.group('prefix')}{match.group('target')[:-4]}.png{match.group('suffix')}", text)
        if updated != text:
            markdown.write_text(updated, encoding="utf-8", newline="\n")
            changed += 1
    return changed


def migrate(root: Path, delete_svg: bool, update_md: bool) -> tuple[int, int]:
    converted = 0
    deleted = 0
    for svg in sorted(root.rglob("*.svg")):
        if ".git" in svg.parts:
            continue
        png = svg.with_suffix(".png")
        convert_svg_to_png(svg, png)
        converted += 1
        if delete_svg:
            svg.unlink()
            deleted += 1
    markdown_changed = update_markdown_links(root) if update_md else 0
    return converted, deleted + markdown_changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert generated SVG artifacts to PNG and optionally remove SVG files.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--keep-svg", action="store_true", help="Keep SVG files after successful PNG conversion.")
    parser.add_argument("--no-markdown", action="store_true", help="Do not rewrite Markdown .svg references to .png.")
    args = parser.parse_args()

    converted, changed = migrate(args.root, delete_svg=not args.keep_svg, update_md=not args.no_markdown)
    print(f"Converted {converted} SVG files; changed/deleted {changed} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
