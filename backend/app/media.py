import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from app.errors import ApiError

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

# Opus at 16 kHz mono, 32 kbps: roughly 14 MB per hour against 115 MB for WAV.
# The codec was designed for speech, costs nothing in recognition accuracy, and
# keeps a two-hour recording inside the 25 MB limit cloud endpoints impose.
TARGET_SAMPLE_RATE = 16_000
TARGET_BITRATE = "32k"


@dataclass(frozen=True)
class MediaInfo:
    duration_sec: float
    codec: str | None
    sample_rate: int | None
    channels: int | None

    @property
    def has_audio(self) -> bool:
        return self.codec is not None


async def run(program: str, *args: str) -> tuple[int, bytes]:
    """Run an ffmpeg-family tool, returning its exit code and stdout.

    stderr is captured and folded into the raised error rather than discarded:
    ffmpeg's diagnostics are the only clue when a container is malformed.
    """
    process = await asyncio.create_subprocess_exec(
        program,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        return process.returncode or 1, stderr
    return 0, stdout


async def probe(path: Path) -> MediaInfo:
    """Read what a file actually is. A pure reader: a media file with no audio
    track is a valid answer here, and the caller decides whether that is fatal."""
    code, output = await run(
        FFPROBE,
        "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    )
    if code != 0:
        raise ApiError(
            415,
            "unsupported_media",
            "This file is not audio or video that ffmpeg can read.",
            filename=path.name,
        )

    payload = json.loads(output)
    streams = payload.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = payload.get("format", {}).get("duration")
    if duration is None and audio is not None:
        duration = audio.get("duration")

    return MediaInfo(
        duration_sec=float(duration or 0.0),
        codec=audio.get("codec_name") if audio else None,
        sample_rate=int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        channels=int(audio["channels"]) if audio and audio.get("channels") else None,
    )


async def normalize_to_opus(source: Path, target: Path) -> MediaInfo:
    """Extract audio and re-encode it to the one format the rest of the
    pipeline knows about. Returns the probe of the result."""
    info = await probe(source)
    if not info.has_audio:
        raise ApiError(
            422,
            "no_audio_stream",
            "This file has no audio track to transcribe.",
            filename=source.name,
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    code, stderr = await run(
        FFMPEG,
        "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", str(source),
        "-vn",
        "-map", "0:a:0",
        "-ac", "1",
        "-ar", str(TARGET_SAMPLE_RATE),
        "-c:a", "libopus",
        "-b:a", TARGET_BITRATE,
        "-application", "voip",
        "-y", str(target),
    )
    if code != 0:
        target.unlink(missing_ok=True)
        raise ApiError(
            422,
            "normalisation_failed",
            "ffmpeg could not convert this file.",
            detail=stderr.decode(errors="replace").strip()[:500],
        )

    return await probe(target)
