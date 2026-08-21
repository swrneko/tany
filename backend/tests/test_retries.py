from pathlib import Path

from app.config import Settings
from tests.conftest import running_client
from tests.stubs import SttStub
from tests.test_worker import run_worker_once, upload


def instant_retry_settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        stt_base_url="http://speaches.test/v1",
        stt_model="stub-whisper",
        stt_retry_backoff_seconds=0.0,
        _env_file=None,
    )


async def test_a_server_error_is_retried_until_it_succeeds(
    tmp_path: Path, sample_audio: Path
) -> None:
    """Local inference servers fall over under load and come back seconds
    later. Failing a whole recording over one such blip is not acceptable."""
    settings = instant_retry_settings(tmp_path)
    stub = SttStub(status_for=lambda index: 503 if index < 2 else 200)

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)

        await run_worker_once(settings, stub)

        assert (await client.get(f"/api/jobs/{job['id']}")).json()["status"] == "done"

    assert len(stub.calls) == 3


async def test_a_rejected_request_fails_at_once(tmp_path: Path, sample_audio: Path) -> None:
    """A 4xx means the request itself is wrong -- wrong model, bad key. Sending
    it again just wastes time and, on a metered API, money."""
    settings = instant_retry_settings(tmp_path)
    stub = SttStub(status=400)

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)

        await run_worker_once(settings, stub)

        failed = (await client.get(f"/api/jobs/{job['id']}")).json()
        assert failed["status"] == "failed"
        assert failed["error_code"] == "stt_rejected_request"

    assert len(stub.calls) == 1


async def test_retries_eventually_give_up(tmp_path: Path, sample_audio: Path) -> None:
    settings = instant_retry_settings(tmp_path)
    stub = SttStub(status=503)

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)

        await run_worker_once(settings, stub)

        failed = (await client.get(f"/api/jobs/{job['id']}")).json()
        assert failed["status"] == "failed"
        assert failed["error_code"] == "stt_unavailable"

    assert len(stub.calls) == settings.stt_retry_attempts
