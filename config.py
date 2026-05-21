from __future__ import annotations

import os
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BIN_DIR = PROJECT_ROOT / "binaries"
SEQ_DIR = PROJECT_ROOT / "sequences"
RESULTS_DIR = PROJECT_ROOT / "results"
RUNS_DIR = RESULTS_DIR / "runs"


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default)))


ENCODER_BASELINE = _env_path("VVENC_ENCODER", BIN_DIR / "vvenc_default.exe")
ENCODER_CSF = _env_path("VVENC_CSF_ENCODER", BIN_DIR / "vvenc_csf.exe")
ENCODER_BASELINE_TRACE = _env_path("VVENC_TRACE_ENCODER", BIN_DIR / "vvenc_default_trace.exe")
ENCODER_CSF_TRACE = _env_path("VVENC_CSF_TRACE_ENCODER", BIN_DIR / "vvenc_csf_trace.exe")

DECODER_BASELINE = _env_path("VVDEC_DECODER", BIN_DIR / "vvdecapp.exe")
DECODER_CSF = _env_path("VVDEC_CSF_DECODER", DECODER_BASELINE)


KNOWN_SEQUENCES = {
    "BasketballPass": {
        "file": SEQ_DIR / "BasketballPass_416x240_50.yuv",
        "width": 416,
        "height": 240,
        "fps": 50,
        "class": "D",
        "bit_depth": 8,
    },
    "FourPeople": {
        "file": SEQ_DIR / "FourPeople_1280x720_60.yuv",
        "width": 1280,
        "height": 720,
        "fps": 60,
        "class": "E",
        "bit_depth": 8,
    },
    "Johnny": {
        "file": SEQ_DIR / "Johnny_1280x720_60.yuv",
        "width": 1280,
        "height": 720,
        "fps": 60,
        "class": "E",
        "bit_depth": 8,
    },
    "KristenAndSara": {
        "file": SEQ_DIR / "KristenAndSara_1280x720_60.yuv",
        "width": 1280,
        "height": 720,
        "fps": 60,
        "class": "E",
        "bit_depth": 8,
    },
    "ArenaOfValor": {
        "file": SEQ_DIR / "ArenaOfValor_1920x1080_60.yuv",
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "class": "F",
        "bit_depth": 8,
    },
    "Tango2": {
        "file": SEQ_DIR / "Tango2_3840x2160_60fps_10bit_420.yuv",
        "width": 3840,
        "height": 2160,
        "fps": 60,
        "class": "A1",
        "bit_depth": 10,
    },
}

SEQUENCE_NAME_RE = re.compile(
    r"^(?P<name>.+)_(?P<width>\d+)x(?P<height>\d+)_(?P<fps>\d+)(?:fps)?"
    r"(?:_(?P<bit_depth>\d+)bit)?(?:_.+)?$"
)


def _sequence_from_filename(path: Path) -> tuple[str, dict] | None:
    match = SEQUENCE_NAME_RE.match(path.stem)
    if not match:
        return None

    bit_depth = match.group("bit_depth")
    name = match.group("name")
    return (
        name,
        {
            "file": path,
            "width": int(match.group("width")),
            "height": int(match.group("height")),
            "fps": int(match.group("fps")),
            "class": KNOWN_SEQUENCES.get(name, {}).get("class", "?"),
            "bit_depth": int(bit_depth) if bit_depth else 8,
        },
    )


def discover_sequences() -> dict[str, dict]:
    discovered: dict[str, dict] = {}
    if not SEQ_DIR.exists():
        return discovered

    for path in sorted(SEQ_DIR.glob("*.yuv")):
        known = next(
            ((name, meta) for name, meta in KNOWN_SEQUENCES.items() if meta["file"].name == path.name),
            None,
        )
        if known:
            name, meta = known
            discovered[name] = {**meta, "file": path}
            continue

        parsed = _sequence_from_filename(path)
        if parsed is None:
            continue

        name, meta = parsed
        discovered[name] = meta

    return discovered


SEQUENCES = discover_sequences()

SMOKE_SEQUENCE = "BasketballPass"
SMOKE_FRAMES = 17
SMOKE_QP = 32

QP_SWEEP_FRAMES = 33
QP_SWEEP_QP_POINTS = [22, 27, 32, 37]

VVENC_CFG = None
VVENC_PRESET = "medium"
