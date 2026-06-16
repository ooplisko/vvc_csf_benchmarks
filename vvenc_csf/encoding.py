from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vvenc_csf.core import CommandRunner


# ====================================================================================================================
# Encoding data
# ====================================================================================================================


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


# ====================================================================================================================
# External VVenC/VVdeC commands
# ====================================================================================================================


class ImageConverter:
    """Converts benchmark input images to the YUV format expected by VVenC."""

    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    def to_yuv420p(self, image: Path, output: Path) -> None:
        if output.exists():
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        self.runner.run(["ffmpeg", "-y", "-v", "error", "-i", str(image), "-pix_fmt", "yuv420p", "-frames:v", "1", str(output)])

    def to_yuv444p(self, image: Path, output: Path) -> None:
        if output.exists():
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        self.runner.run(["ffmpeg", "-y", "-v", "error", "-i", str(image), "-pix_fmt", "yuv444p", "-frames:v", "1", str(output)])

    def to_yuv444p_opencv(self, image: Path, output: Path) -> None:
        if output.exists():
            return
        import cv2
        import numpy as np
        output.parent.mkdir(parents=True, exist_ok=True)
        im = cv2.imread(str(image))
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        im = cv2.cvtColor(im, cv2.COLOR_RGB2YUV)
        im = np.transpose(im, axes=(2, 0, 1))
        with open(output, "wb") as f:
            f.write(im.tobytes())



class EncoderRunner:
    """Builds and executes one VVenC encode command.

    Parameters
    ----------
    runner : CommandRunner, optional
        The command runner instance to use for execution.

    Examples
    --------
    >>> encoder = EncoderRunner()
    >>> # encoder.encode(job)
    """

    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    def encode(self, job: EncodeJob) -> str:
        job.bitstream.parent.mkdir(parents=True, exist_ok=True)
        if "EncoderApp" in job.encoder.name:
            return self._encode_vtm(job)
        return self._encode_vvenc(job)

    def _encode_vvenc(self, job: EncodeJob) -> str:
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

    def _encode_vtm(self, job: EncodeJob) -> str:
        # Resolve config relative to project root
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        cfg_file = root / "VVCSoftware_VTM" / "cfg" / "encoder_intra_vtm.cfg"
        
        filtered_extra_args = []
        skip_next = False
        for arg in job.extra_args:
            if skip_next:
                skip_next = False
                continue
            if arg == "--CSFScalingList":
                skip_next = True
                continue
            filtered_extra_args.append(arg)
            
        cmd = [
            str(job.encoder),
            "-c", str(cfg_file),
            "-i", str(job.yuv),
            "-wdt", str(job.width),
            "-hgt", str(job.height),
            "-fr", "1",
            "-f", "1",
            "-q", str(job.qp),
            "-b", str(job.bitstream),
            "-o", str(job.recon),
            "--InputChromaFormat=444",
            "--InputBitDepth=8",
            *filtered_extra_args,
        ]
        return self.runner.run(cmd, job.log).stdout


class DecoderRunner:
    """Runs VVdeC for reconstruction-vs-decoder consistency checks.

    Parameters
    ----------
    decoder : Path
        Path to the VVdeC executable.
    runner : CommandRunner, optional
        The command runner instance to use for execution.

    Examples
    --------
    >>> decoder = DecoderRunner(Path("vvdecapp"))
    >>> # decoder.decode(Path("in.vvc"), Path("out.yuv"), Path("dec.log"))
    """

    def __init__(self, decoder: Path, runner: CommandRunner | None = None) -> None:
        self.decoder = decoder
        self.runner = runner or CommandRunner()

    def decode(self, bitstream: Path, output: Path, log: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        self.runner.run([str(self.decoder), "-b", str(bitstream), "-o", str(output)], log)
