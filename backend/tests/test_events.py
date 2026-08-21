import asyncio
import json
from pathlib import Path
from typing import Any

from httpx import AsyncClient

from app.config import Settings
from tests.conftest import running_client
from tests.stubs import SttStub
from tests.test_worker import run_worker_once, settings_with_stt, upload


async def collect_events(client: AsyncClient, job_id: str) -> list[dict[str, Any]]:
    """Read the stream to its end. It closes itself once the job is terminal."""
    events: list[dict[str, Any]] = []
    async with client.stream("GET", f"/api/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line.removeprefix("data: ")))
    return events


async def test_the_stream_of_a_finished_job_reports_it_and_closes(
    tmp_path: Path, sample_audio: Path
) -> None:
    settings = settings_with_stt(tmp_path)

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)
        await run_worker_once(settings, SttStub())

        events = await asyncio.wait_for(collect_events(client, job["id"]), timeout=5)

    assert events, "a stream must open with the current state, not with silence"
    assert events[-1]["status"] == "done"
    assert events[-1]["progress"] == 1.0


async def test_the_stream_follows_a_job_to_completion(
    tmp_path: Path, sample_audio: Path
) -> None:
    settings = settings_with_stt(tmp_path).model_copy(update={"sse_poll_seconds": 0.05})

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)

        working = asyncio.create_task(run_worker_once(settings, SttStub()))
        events = await asyncio.wait_for(collect_events(client, job["id"]), timeout=10)
        await working

    statuses = [event["status"] for event in events]
    assert statuses[0] in {"queued", "running"}
    assert statuses[-1] == "done"


async def test_one_stream_covers_the_whole_list(tmp_path: Path, sample_audio: Path) -> None:
    """Ten queued files must not mean ten connections: browsers cap concurrent
    requests per origin, and the surplus would simply never open."""
    settings = settings_with_stt(tmp_path).model_copy(update={"sse_poll_seconds": 0.05})

    async with running_client(settings) as client:
        await upload(client, sample_audio)
        with sample_audio.open("rb") as handle:
            await client.post("/api/jobs", files={"file": ("second.wav", handle, "audio/wav")})

        working = asyncio.create_task(_drain_queue(settings))

        batches: list[list[dict[str, Any]]] = []
        async with client.stream("GET", "/api/jobs/events") as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    batches.append(json.loads(line.removeprefix("data: ")))

        await working

    assert batches, "the stream opens with the current state"
    assert {job["status"] for job in batches[-1]} == {"done"}
    assert len(batches[-1]) == 2


async def _drain_queue(settings: Settings) -> None:
    while await run_worker_once(settings, SttStub()):
        pass


async def test_the_stream_is_private(tmp_path: Path, sample_audio: Path) -> None:
    settings = Settings(data_dir=tmp_path, auth_mode="proxy", _env_file=None)

    async with running_client(settings) as client:
        with sample_audio.open("rb") as handle:
            job = (
                await client.post(
                    "/api/jobs",
                    files={"file": ("meeting.wav", handle, "audio/wav")},
                    headers={"X-Remote-User": "marina"},
                )
            ).json()

        stranger = await client.get(
            f"/api/jobs/{job['id']}/events", headers={"X-Remote-User": "pavel"}
        )

        assert stranger.status_code == 404
