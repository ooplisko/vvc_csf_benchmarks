from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vvenc_csf.core import CommandRunner


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    width: int
    height: int

    @property
    def name(self) -> str:
        return self.path.stem


@dataclass(frozen=True)
class EncodeJob:
    encoder: Path
    yuv: Path
    width: int
    height: int
    qp: int
    preset: str
    bitstream: Path
    recon: Path
    log: Path
    extra_args: tuple[str, ...] = ()


class ImageConverter:
    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    def to_yuv420p(self, image: Path, output: Path) -> None:
        if output.exists():
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        self.runner.run(["ffmpeg", "-y", "-v", "error", "-i", str(image), "-pix_fmt", "yuv420p", "-frames:v", "1", str(output)])


class EncoderRunner:
    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    def encode(self, job: EncodeJob) -> str:
        job.bitstream.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(job.encoder),
            "--InputFile",
            str(job.yuv),
            "--SourceWidth",
            str(job.width),
            "--SourceHeight",
            str(job.height),
            "--FrameRate",
            "1",
            "--FramesToBeEncoded",
            "1",
            "--QP",
            str(job.qp),
            "--preset",
            job.preset,
            "--BitstreamFile",
            str(job.bitstream),
            "--ReconFile",
            str(job.recon),
            *job.extra_args,
        ]
        return self.runner.run(cmd, job.log).stdout


class DecoderRunner:
    def __init__(self, decoder: Path, runner: CommandRunner | None = None) -> None:
        self.decoder = decoder
        self.runner = runner or CommandRunner()

    def decode(self, bitstream: Path, output: Path, log: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        self.runner.run([str(self.decoder), "-b", str(bitstream), "-o", str(output)], log)

