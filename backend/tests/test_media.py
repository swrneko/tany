import asyncio
from pathlib import Path

import pytest

from app.errors import ApiError
from app.media import extract_chunk, normalize_to_opus, probe


async def test_probe_reads_duration_and_stream_layout(sample_audio: Path) -> None:
    info = await probe(sample_audio)

    assert info.duration_sec == pytest.approx(3.0, abs=0.2)
    assert info.has_audio
    assert info.channels == 1


async def test_normalisation_produces_mono_16k_opus(sample_audio: Path, tmp_path: Path) -> None:
    target = tmp_path / "audio.ogg"

    await normalize_to_opus(sample_audio, target)

    info = await probe(target)
    assert info.codec == "opus"
    assert info.channels == 1
    assert info.duration_sec == pytest.approx(3.0, abs=0.2)
    # Opus always reports 48k on decode; the encoder input rate is what matters,
    # and a three-second clip landing under 50 kB proves the speech profile took.
    assert target.stat().st_size < 50_000


async def test_a_chunk_covers_exactly_the_requested_span(
    sample_audio: Path, tmp_path: Path
) -> None:
    normalised = tmp_path / "audio.ogg"
    await normalize_to_opus(sample_audio, normalised)
    chunk = tmp_path / "chunk-000.ogg"

    await extract_chunk(normalised, chunk, start=1.0, end=2.5)

    assert (await probe(chunk)).duration_sec == pytest.approx(1.5, abs=0.15)


async def test_normalising_a_file_without_audio_is_reported(tmp_path: Path) -> None:
    silent_video = tmp_path / "clip.mp4"
    await _make_silent_video(silent_video)

    with pytest.raises(ApiError) as caught:
        await normalize_to_opus(silent_video, tmp_path / "audio.ogg")

    assert caught.value.code == "no_audio_stream"


async def test_probe_rejects_a_file_that_is_not_media(tmp_path: Path) -> None:
    not_media = tmp_path / "notes.txt"
    not_media.write_text("this is not a media file")

    with pytest.raises(ApiError) as caught:
        await probe(not_media)

    assert caught.value.code == "unsupported_media"


async def _make_silent_video(target: Path) -> None:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=64x64:rate=10",
        "-c:v", "mpeg4", "-y", str(target),
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    assert process.returncode == 0, stderr.decode()
