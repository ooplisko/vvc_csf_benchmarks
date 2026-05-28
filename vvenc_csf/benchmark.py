from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from metrics.image_quality import calculate_luma_metrics
from vvenc_csf.core import CommandRunner, ffprobe_size, files_equal, write_csv
from vvenc_csf.encoding import DecoderRunner, EncodeJob, EncoderRunner, ImageConverter


KODAK_URL = "https://r0k.us/graphics/kodak/kodak/kodim{index:02d}.png"
ENC_RE = re.compile(
    r"\s*1\s+a\s+(?P<bitrate>[0-9.]+)\s+(?P<y>[0-9.]+|inf|nan)\s+(?P<u>[0-9.]+|inf|nan)\s+(?P<v>[0-9.]+|inf|nan)",
    re.IGNORECASE,
)
SSIM_RE = re.compile(r"All:(?P<all>[0-9.]+)")
XPSNR_RE = re.compile(r"XPSNR\s+y:\s*(?P<y>[0-9.]+)")
VMAF_RE = re.compile(r"VMAF score:\s*(?P<vmaf>[0-9.]+)")


@dataclass(frozen=True)
class ImageBenchmarkConfig:
    root: Path
    png_dir: Path
    baseline_encoder: Path
    csf_encoder: Path
    decoder: Path
    qps: list[int]
    preset: str = "medium"


class KodakDownloader:
    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    def download(self, png_dir: Path) -> None:
        png_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, 25):
            out = png_dir / f"kodim{index:02d}.png"
            if out.exists() and out.stat().st_size > 0:
                continue
            self.runner.run(["curl.exe", "-L", KODAK_URL.format(index=index), "-o", str(out)])


class EncoderLogParser:
    def parse(self, text: str) -> dict[str, float]:
        match = ENC_RE.search(text)
        if not match:
            return {"bitrate_kbps": 0.0, "psnr_y": 0.0, "psnr_u": 0.0, "psnr_v": 0.0}
        return {
            "bitrate_kbps": float(match.group("bitrate")),
            "psnr_y": float(match.group("y")),
            "psnr_u": float(match.group("u")),
            "psnr_v": float(match.group("v")),
        }


class VisualMetricCalculator:
    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    def calculate(self, original_yuv: Path, recon_yuv: Path, width: int, height: int) -> dict[str, float]:
        common = [
            "ffmpeg",
            "-v",
            "info",
            "-s",
            f"{width}x{height}",
            "-pix_fmt",
            "yuv420p",
            "-i",
            str(original_yuv),
            "-s",
            f"{width}x{height}",
            "-pix_fmt",
            "yuv420p10le",
            "-i",
            str(recon_yuv),
        ]
        metrics: dict[str, float] = {}

        ssim_out = self.runner.run(common + ["-lavfi", "ssim", "-f", "null", "-"]).stdout
        match = SSIM_RE.search(ssim_out)
        metrics["ssim"] = float(match.group("all")) if match else 0.0

        xpsnr_out = self.runner.run(common + ["-lavfi", "xpsnr", "-f", "null", "-"]).stdout
        match = XPSNR_RE.search(xpsnr_out)
        metrics["xpsnr_y"] = float(match.group("y")) if match else 0.0

        try:
            vmaf_out = self.runner.run(common + ["-lavfi", "libvmaf", "-f", "null", "-"]).stdout
            match = VMAF_RE.search(vmaf_out)
            metrics["vmaf"] = float(match.group("vmaf")) if match else 0.0
        except RuntimeError:
            metrics["vmaf"] = 0.0

        metrics.update(calculate_luma_metrics(original_yuv, recon_yuv, width, height))
        return metrics


class ImageBenchmarkRunner:
    def __init__(
        self,
        config: ImageBenchmarkConfig,
        runner: CommandRunner | None = None,
        converter: ImageConverter | None = None,
        encoder: EncoderRunner | None = None,
        metrics: VisualMetricCalculator | None = None,
        parser: EncoderLogParser | None = None,
    ) -> None:
        self.config = config
        self.runner = runner or CommandRunner()
        self.converter = converter or ImageConverter(self.runner)
        self.encoder = encoder or EncoderRunner(self.runner)
        self.decoder = DecoderRunner(config.decoder, self.runner)
        self.metrics = metrics or VisualMetricCalculator(self.runner)
        self.parser = parser or EncoderLogParser()

    def run(self) -> Path:
        rows = self.collect_rows()
        csv_path = self.config.root / "image_metrics.csv"
        write_csv(csv_path, rows)
        return csv_path

    def collect_rows(self) -> list[dict[str, object]]:
        yuv_dir = self.config.root / "yuv"
        enc_dir = self.config.root / "encoded"
        images = sorted(self.config.png_dir.glob("*.png"))
        if not images:
            raise RuntimeError(f"No PNG files found in {self.config.png_dir}")

        rows: list[dict[str, object]] = []
        for image in images:
            width, height = ffprobe_size(image, self.runner)
            name = image.stem
            yuv = yuv_dir / f"{name}_{width}x{height}_1.yuv"
            self.converter.to_yuv420p(image, yuv)

            raw_bytes = width * height * 3 // 2
            for qp in self.config.qps:
                rows.extend(self._encode_modes(name, yuv, width, height, raw_bytes, qp, enc_dir))
        return rows

    def _encode_modes(self, name: str, yuv: Path, width: int, height: int, raw_bytes: int, qp: int, enc_dir: Path) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for mode, encoder_path, csf_enabled in (
            ("baseline", self.config.baseline_encoder, False),
            ("csf", self.config.csf_encoder, True),
        ):
            out_dir = enc_dir / name / f"QP{qp}" / mode
            bitstream = out_dir / f"{name}_QP{qp}_{mode}.vvc"
            recon = out_dir / f"{name}_QP{qp}_{mode}_rec.yuv"
            decoded = out_dir / f"{name}_QP{qp}_{mode}_dec.yuv"
            extra_args = ("--CSFScalingList", "1") if csf_enabled else ()
            text = self.encoder.encode(
                EncodeJob(
                    encoder=encoder_path,
                    yuv=yuv,
                    width=width,
                    height=height,
                    qp=qp,
                    preset=self.config.preset,
                    bitstream=bitstream,
                    recon=recon,
                    log=out_dir / f"{name}_QP{qp}_{mode}_enc.log",
                    extra_args=extra_args,
                )
            )
            self.decoder.decode(bitstream, decoded, out_dir / f"{name}_QP{qp}_{mode}_dec.log")
            if not files_equal(recon, decoded):
                raise RuntimeError(f"Decoded YUV differs from encoder reconstruction: {decoded}")

            parsed = self.parser.parse(text)
            visual_metrics = self.metrics.calculate(yuv, recon, width, height)
            bytes_out = bitstream.stat().st_size
            rows.append(
                {
                    "image": name,
                    "width": width,
                    "height": height,
                    "qp": qp,
                    "mode": mode,
                    "bitstream_bytes": bytes_out,
                    "compression_ratio": raw_bytes / bytes_out if bytes_out else 0,
                    "bpp": (bytes_out * 8) / (width * height),
                    **parsed,
                    **visual_metrics,
                }
            )
        return rows

