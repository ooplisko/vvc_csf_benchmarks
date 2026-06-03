from __future__ import annotations

from pathlib import Path

from vvenc_csf.core import CommandResult, platform_executable
from vvenc_csf.encoding import DecoderRunner, EncodeJob, EncoderRunner


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, cmd: list[str], log_file: Path | None = None) -> CommandResult:
        self.calls.append((cmd, log_file))
        return CommandResult(cmd, "ok", 0)


def test_encoder_runner_builds_vvenc_command(tmp_path: Path) -> None:
    runner = RecordingRunner()
    encoder = platform_executable(Path("vvenc"))
    result = EncoderRunner(runner).encode(
        EncodeJob(
            encoder=encoder,
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
    assert cmd[:2] == [str(encoder), "--InputFile"]
    assert "--QP" in cmd and "32" in cmd
    assert "--CSFScalingList" in cmd and "1" in cmd
    assert log_file == tmp_path / "encode.log"


def test_decoder_runner_builds_vvdec_command(tmp_path: Path) -> None:
    runner = RecordingRunner()
    decoder = platform_executable(Path("vvdecapp"))
    DecoderRunner(decoder, runner).decode(Path("in.vvc"), tmp_path / "decoded.yuv", tmp_path / "decode.log")

    cmd, log_file = runner.calls[0]
    assert cmd == [str(decoder), "-b", "in.vvc", "-o", str(tmp_path / "decoded.yuv")]
    assert log_file == tmp_path / "decode.log"
