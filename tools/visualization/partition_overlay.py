from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


COLORS_BGR = {
    "ctu": (107, 114, 128),
    "cu": (235, 99, 37),
    "tu": (74, 163, 22),
    "pu": (234, 51, 147),
}


def row_int(row: dict[str, str], name: str, default: int = 0) -> int:
    value = row.get(name, "")
    return int(value) if value not in ("", None) else default


def render_partition_overlay(
    blocks: list[dict[str, str]],
    width: int,
    height: int,
    output: Path,
    image: Path | None = None,
) -> None:
    """Render codec partition blocks as a PNG overlay on top of the source image."""

    canvas = _load_canvas(image, width, height)
    shaded = cv2.addWeighted(canvas, 0.72, np.full_like(canvas, 255), 0.28, 0)
    overlay = shaded.copy()

    for row in blocks:
        kind = row.get("type", "cu").lower()
        color = COLORS_BGR.get(kind, (17, 24, 39))
        x = row_int(row, "x")
        y = row_int(row, "y")
        block_width = row_int(row, "width")
        block_height = row_int(row, "height")
        depth = row_int(row, "depth")
        thickness = 2 if kind == "ctu" else 1
        alpha = max(0.38, 0.9 - depth * 0.08)
        layer = overlay.copy()
        cv2.rectangle(layer, (x, y), (x + block_width - 1, y + block_height - 1), color, thickness, lineType=cv2.LINE_AA)
        overlay = cv2.addWeighted(layer, alpha, overlay, 1.0 - alpha, 0)

    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), overlay, [cv2.IMWRITE_PNG_COMPRESSION, 3]):
        raise RuntimeError(f"Could not write partition overlay: {output}")


def _load_canvas(image: Path | None, width: int, height: int) -> np.ndarray:
    if image is None:
        return np.full((height, width, 3), 248, dtype=np.uint8)

    data = cv2.imread(str(image), cv2.IMREAD_COLOR)
    if data is None:
        raise RuntimeError(f"Could not read source image for partition overlay: {image}")
    if data.shape[1] != width or data.shape[0] != height:
        data = cv2.resize(data, (width, height), interpolation=cv2.INTER_AREA)
    return data
