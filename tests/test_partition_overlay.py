from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from tools.visualization.partition_overlay import render_partition_overlay


def test_partition_overlay_writes_png_on_source_image(tmp_path: Path) -> None:
    image = tmp_path / "source.png"
    output = tmp_path / "overlay.png"
    source = np.full((32, 32, 3), 180, dtype=np.uint8)
    assert cv2.imwrite(str(image), source)

    render_partition_overlay(
        [{"type": "cu", "x": "4", "y": "4", "width": "16", "height": "16", "depth": "1"}],
        32,
        32,
        output,
        image,
    )

    assert output.exists()
    assert output.stat().st_size > 0
    rendered = cv2.imread(str(output), cv2.IMREAD_COLOR)
    assert rendered is not None
    assert rendered.shape == (32, 32, 3)
