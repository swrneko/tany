import asyncio
from pathlib import Path

from app.config import Settings
from app.db import Database
from app.secrets import load_or_create_secret
from app.worker import Worker
from tests.conftest import running_client
from tests.stubs import SttStub
from tests.test_worker import run_worker_once, settings_with_stt, upload


async def test_a_queued_job_is_cancelled_before_a_worker_sees_it(
    tmp_path: Path, sample_audio: Path
) -> None:
    settings = settings_with_stt(tmp_path)
    stub = SttStub()

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)

        cancelled = await client.post(f"/api/jobs/{job['id']}/cancel")
        assert cancelled.status_code == 200

        assert await run_worker_once(settings, stub) is False, "nothing left to claim"
        assert (await client.get(f"/api/jobs/{job['id']}")).json()["status"] == "cancelled"

    assert stub.calls == []


async def test_cancelling_a_running_job_aborts_the_work_in_flight(
    tmp_path: Path, sample_audio: Path
) -> None:
    """A flag alone is not a cancellation: the request has to be dropped, or the
    transcription keeps burning someone's GPU after they clicked stop."""
    settings = settings_with_stt(tmp_path).model_copy(update={"cancel_poll_seconds": 0.05})
    hold = asyncio.Event()
    stub = SttStub(hold=hold)

    database = Database(settings.db_path)
    worker = Worker(
        settings,
        database,
        load_or_create_secret(settings.secret_key_path),
        stt_factory=lambda _provider: stub.http_client(),
    )

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)

        working = asyncio.create_task(worker.run_once())
        await asyncio.wait_for(stub.received.wait(), timeout=5)

        await client.post(f"/api/jobs/{job['id']}/cancel")
        await asyncio.wait_for(working, timeout=5)

        assert (await client.get(f"/api/jobs/{job['id']}")).json()["status"] == "cancelled"

    hold.set()
    await database.dispose()


async def test_a_finished_job_cannot_be_cancelled(tmp_path: Path, sample_audio: Path) -> None:
    settings = settings_with_stt(tmp_path)

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)
        await run_worker_once(settings, SttStub())

        refused = await client.post(f"/api/jobs/{job['id']}/cancel")

        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "job_not_cancellable"


async def test_cancelling_leaves_no_transcript_behind(
    tmp_path: Path, sample_audio: Path
) -> None:
    settings = settings_with_stt(tmp_path)

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)
        await client.post(f"/api/jobs/{job['id']}/cancel")
        await run_worker_once(settings, SttStub())

        transcript = await client.get(f"/api/jobs/{job['id']}/transcript")
        assert transcript.status_code == 404
