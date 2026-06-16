from __future__ import annotations

import argparse
import binascii
import math
import random
import struct
import zlib
from pathlib import Path


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(tag)
    crc = binascii.crc32(data, crc)
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, pixels: list[list[tuple[int, int, int]]]) -> None:
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for red, green, blue in row:
            raw.extend((red, green, blue))

    payload = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _chunk(b"IDAT", zlib.compress(bytes(raw), level=9)),
            _chunk(b"IEND", b""),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def clamp(value: float) -> int:
    return max(0, min(255, int(round(value))))


def smooth_gradient(width: int, height: int) -> list[list[tuple[int, int, int]]]:
    pixels = []
    for y in range(height):
        row = []
        for x in range(width):
            luma = 32 + 190 * (0.65 * x / (width - 1) + 0.35 * y / (height - 1))
            row.append((clamp(luma), clamp(luma + 8), clamp(luma + 14)))
        pixels.append(row)
    return pixels


def sharp_edges(width: int, height: int) -> list[list[tuple[int, int, int]]]:
    palette = [(30, 42, 57), (230, 236, 242), (192, 52, 64), (48, 132, 93), (242, 188, 84)]
    pixels = []
    for y in range(height):
        row = []
        for x in range(width):
            if abs(x - y) < 5 or abs((width - x) - y) < 5:
                row.append((250, 250, 250))
            else:
                band = (x * len(palette)) // width
                value = palette[band]
                if (x // 32 + y // 32) % 2 == 0:
                    value = tuple(clamp(channel * 0.74) for channel in value)
                row.append(value)
        pixels.append(row)
    return pixels


def fine_texture(width: int, height: int) -> list[list[tuple[int, int, int]]]:
    rng = random.Random(20260520)
    pixels = []
    for y in range(height):
        row = []
        for x in range(width):
            wave = 18 * math.sin(x * 0.37) + 16 * math.cos(y * 0.41) + 12 * math.sin((x + y) * 0.23)
            noise = rng.randrange(-22, 23)
            luma = 128 + wave + noise
            row.append((clamp(luma + 7), clamp(luma), clamp(luma - 5)))
        pixels.append(row)
    return pixels


def mixed_content(width: int, height: int) -> list[list[tuple[int, int, int]]]:
    pixels = smooth_gradient(width, height)
    for y in range(height):
        for x in range(width):
            if width // 8 < x < width * 7 // 8 and height // 8 < y < height * 7 // 8:
                if (x // 16 + y // 16) % 2 == 0:
                    pixels[y][x] = (42, 61, 82)
                else:
                    pixels[y][x] = (214, 221, 229)
            if (x - width // 2) ** 2 + (y - height // 2) ** 2 < (min(width, height) // 5) ** 2:
                angle = math.atan2(y - height // 2, x - width // 2)
                radius = math.hypot(x - width // 2, y - height // 2)
                value = 128 + 80 * math.sin(radius * 0.17 + angle * 8)
                pixels[y][x] = (clamp(value + 22), clamp(value + 4), clamp(value - 18))
    return pixels


GENERATORS = {
    "smooth_gradient": smooth_gradient,
    "sharp_edges": sharp_edges,
    "fine_texture": fine_texture,
    "mixed_content": mixed_content,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic synthetic PNG set for CSF image metrics.")
    parser.add_argument("--output", type=Path, default=Path("data/datasets/images/synthetic/png"), help="Output PNG directory.")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    args = parser.parse_args()

    for name, generator in GENERATORS.items():
        path = args.output / f"{name}_{args.width}x{args.height}.png"
        write_png(path, args.width, args.height, generator(args.width, args.height))
        print(f"Wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
