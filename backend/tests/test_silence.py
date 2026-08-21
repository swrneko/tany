import asyncio
from pathlib import Path

import pytest

from app.media import detect_silences


async def _clip_with_a_gap(target: Path) -> None:
    """Five seconds of tone, muted between the second and third second."""
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-af", "volume=enable='between(t,2,3)':volume=0",
        "-y", str(target),
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    assert process.returncode == 0, stderr.decode()


async def test_a_pause_is_found_where_the_audio_goes_quiet(tmp_path: Path) -> None:
    clip = tmp_path / "gap.wav"
    await _clip_with_a_gap(clip)

    silences = await detect_silences(clip)

    assert len(silences) == 1
    start, end = silences[0]
    assert start == pytest.approx(2.0, abs=0.2)
    assert end == pytest.approx(3.0, abs=0.2)


async def test_continuous_audio_yields_no_pauses(sample_audio: Path) -> None:
    assert await detect_silences(sample_audio) == []


async def test_a_pause_running_to_the_end_is_still_reported(tmp_path: Path) -> None:
    """ffmpeg prints silence_start with no matching silence_end when the file
    ends mid-pause. Dropping that would lose a legitimate cut point."""
    clip = tmp_path / "trailing.wav"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-af", "volume=enable='gte(t,2)':volume=0",
        "-y", str(clip),
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()

    silences = await detect_silences(clip)

    assert len(silences) == 1
    assert silences[0][0] == pytest.approx(2.0, abs=0.2)
    assert silences[0][1] == pytest.approx(4.0, abs=0.3)
