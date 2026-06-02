from __future__ import annotations

from pathlib import Path

from vvenc_csf.core import CommandResult
from vvenc_csf.encoding import DecoderRunner, EncodeJob, EncoderRunner


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, cmd: list[str], log_file: Path | None = None) -> CommandResult:
        self.calls.append((cmd, log_file))
        return CommandResult(cmd, "ok", 0)


def test_encoder_runner_builds_vvenc_command(tmp_path: Path) -> None:
    runner = RecordingRunner()
    result = EncoderRunner(runner).encode(
        EncodeJob(
            encoder=Path("vvenc.exe"),
            yuv=Path("input.yuv"),
            width=512,
            height=512,
            qp=32,
            preset="medium",
            bitstream=tmp_path / "out.vvc",
            recon=tmp_path / "out.yuv",
            log=tmp_path / "encode.log",
            extra_args=("--CSFScalingList", "1"),
        )
    )

    cmd, log_file = runner.calls[0]
    assert result == "ok"
    assert cmd[:2] == ["vvenc.exe", "--InputFile"]
    assert "--QP" in cmd and "32" in cmd
    assert "--CSFScalingList" in cmd and "1" in cmd
    assert log_file == tmp_path / "encode.log"


def test_decoder_runner_builds_vvdec_command(tmp_path: Path) -> None:
    runner = RecordingRunner()
    DecoderRunner(Path("vvdecapp.exe"), runner).decode(Path("in.vvc"), tmp_path / "decoded.yuv", tmp_path / "decode.log")

    cmd, log_file = runner.calls[0]
    assert cmd == ["vvdecapp.exe", "-b", "in.vvc", "-o", str(tmp_path / "decoded.yuv")]
    assert log_file == tmp_path / "decode.log"
