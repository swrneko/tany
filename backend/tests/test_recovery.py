import asyncio
from contextlib import suppress
from pathlib import Path

from app.config import Settings
from app.db import Database
from app.secrets import load_or_create_secret
from app.worker import Worker
from tests.conftest import running_client
from tests.stubs import SttStub
from tests.test_worker import settings_with_stt, upload


def make_worker(settings: Settings, stub: SttStub) -> tuple[Worker, Database]:
    database = Database(settings.db_path)
    worker = Worker(
        settings,
        database,
        load_or_create_secret(settings.secret_key_path),
        stt_factory=lambda _provider: stub.http_client(),
    )
    return worker, database


async def test_a_job_abandoned_by_a_dead_worker_is_picked_up_again(
    tmp_path: Path, sample_audio: Path
) -> None:
    """kill -9 leaves a job marked running forever. Nothing else will ever
    claim it, so it sits there looking busy until someone reads the database."""
    settings = settings_with_stt(tmp_path).model_copy(
        update={"heartbeat_stale_seconds": 0.0, "cancel_poll_seconds": 0.05}
    )
    stalled = SttStub(hold=asyncio.Event())

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)

        doomed, doomed_db = make_worker(settings, stalled)
        in_flight = asyncio.create_task(doomed.run_once())
        await asyncio.wait_for(stalled.received.wait(), timeout=5)
        in_flight.cancel()  # the process disappears; nothing gets to tidy up
        with suppress(asyncio.CancelledError):
            await in_flight
        await doomed_db.dispose()

        assert (await client.get(f"/api/jobs/{job['id']}")).json()["status"] == "running"

        successor, successor_db = make_worker(settings, SttStub())
        assert await successor.recover_stale_jobs() == 1
        assert await successor.run_once() is True
        await successor_db.dispose()

        assert (await client.get(f"/api/jobs/{job['id']}")).json()["status"] == "done"


async def test_a_live_job_is_left_alone(tmp_path: Path, sample_audio: Path) -> None:
    settings = settings_with_stt(tmp_path)  # the default staleness window

    async with running_client(settings) as client:
        await upload(client, sample_audio)

        worker, database = make_worker(settings, SttStub())
        await worker.run_once()

        assert await worker.recover_stale_jobs() == 0
        await database.dispose()
