import asyncio
import json
from pathlib import Path

from httpx import AsyncClient

from app.config import Settings
from app.db import Database
from app.secrets import load_or_create_secret
from app.worker import Worker
from tests.conftest import running_client
from tests.stubs import LlmStub, SttStub
from tests.test_worker import upload


def settings_with_both(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(
        data_dir=tmp_path,
        stt_base_url="http://speaches.test/v1",
        stt_model="stub-whisper",
        llm_base_url="http://ollama.test/v1",
        llm_model="stub-llm",
        _env_file=None,
        **overrides,
    )


async def drain(settings: Settings, stt: SttStub, llm: LlmStub) -> None:
    """Run the worker until there is nothing left to do."""
    database = Database(settings.db_path)
    worker = Worker(
        settings,
        database,
        load_or_create_secret(settings.secret_key_path),
        stt_factory=lambda _provider: stt.http_client(),
        llm_factory=lambda _provider: llm.http_client(),
    )
    try:
        while await worker.run_once():
            pass
    finally:
        await database.dispose()


async def transcribed_job(client: AsyncClient, settings: Settings, sample_audio: Path) -> dict:
    job = await upload(client, sample_audio)
    await drain(settings, SttStub(), LlmStub())
    return job


async def first_preset(client: AsyncClient) -> dict:
    return (await client.get("/api/presets")).json()[0]


async def test_a_preset_turns_a_transcript_into_a_summary(
    tmp_path: Path, sample_audio: Path
) -> None:
    settings = settings_with_both(tmp_path)
    llm = LlmStub(reply_for=lambda _index: "They argued about the database.")

    async with running_client(settings) as client:
        job = await transcribed_job(client, settings, sample_audio)
        preset = await first_preset(client)

        created = await client.post(
            f"/api/jobs/{job['id']}/summaries", json={"preset_id": preset["id"]}
        )
        assert created.status_code == 201
        assert created.json()["status"] == "queued"

        await drain(settings, SttStub(), llm)

        [summary] = (await client.get(f"/api/jobs/{job['id']}/summaries")).json()
        assert summary["status"] == "done"
        assert summary["content"] == "They argued about the database."
        assert summary["model_used"] == "stub-llm"

    # The transcript really reached the model, rather than the template alone.
    assert "Hello there." in llm.calls[0].user
    assert "{transcript}" not in llm.calls[0].user


async def test_a_transcript_too_large_for_the_context_is_summarised_in_stages(
    tmp_path: Path, sample_audio: Path
) -> None:
    """Ollama with a small context truncates the input without a word and
    answers confidently about the first third. Splitting is the only defence."""
    settings = settings_with_both(tmp_path, llm_context_tokens=300)
    llm = LlmStub(reply_for=lambda index: f"part {index}")

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)
        # A transcript long enough that it cannot go in one request.
        long_stub = SttStub(
            payload={
                "language": "en",
                "text": "x",
                "segments": [
                    {"start": float(i), "end": float(i) + 1, "text": f"sentence number {i} " * 12}
                    for i in range(40)
                ],
            }
        )
        await drain(settings, long_stub, llm)

        preset = await first_preset(client)
        await client.post(f"/api/jobs/{job['id']}/summaries", json={"preset_id": preset["id"]})
        await drain(settings, SttStub(), llm)

        [summary] = (await client.get(f"/api/jobs/{job['id']}/summaries")).json()

    assert summary["status"] == "done"
    assert len(llm.calls) > 2, "several map calls and one reduce"
    # Partials are kept: reduce fails often, and redoing every part is not on.
    partials = json.loads(summary["partials_json"])
    assert len(partials) == len(llm.calls) - 1
    assert all(part in llm.calls[-1].user for part in partials)


async def test_every_run_is_kept_so_results_can_be_compared(
    tmp_path: Path, sample_audio: Path
) -> None:
    settings = settings_with_both(tmp_path)
    llm = LlmStub(reply_for=lambda index: f"summary {index}")

    async with running_client(settings) as client:
        job = await transcribed_job(client, settings, sample_audio)
        presets = (await client.get("/api/presets")).json()

        for preset in presets[:2]:
            await client.post(
                f"/api/jobs/{job['id']}/summaries", json={"preset_id": preset["id"]}
            )
        await drain(settings, SttStub(), llm)

        summaries = (await client.get(f"/api/jobs/{job['id']}/summaries")).json()

        assert len(summaries) == 2
        assert {summary["content"] for summary in summaries} == {"summary 0", "summary 1"}
        assert {summary["preset_name"] for summary in summaries} == {
            preset["name"] for preset in presets[:2]
        }


async def test_a_summary_can_be_watched_while_it_is_written(
    tmp_path: Path, sample_audio: Path
) -> None:
    settings = settings_with_both(
        tmp_path, sse_poll_seconds=0.05, summary_flush_seconds=0.0
    )
    llm = LlmStub(reply_for=lambda _index: "one two three four five")

    async with running_client(settings) as client:
        job = await transcribed_job(client, settings, sample_audio)
        preset = await first_preset(client)
        summary = (
            await client.post(
                f"/api/jobs/{job['id']}/summaries", json={"preset_id": preset["id"]}
            )
        ).json()

        working = asyncio.create_task(drain(settings, SttStub(), llm))

        events = []
        async with client.stream("GET", f"/api/summaries/{summary['id']}/events") as response:
            assert response.headers["content-type"].startswith("text/event-stream")
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line.removeprefix("data: ")))
        await working

    assert events[0]["status"] in {"queued", "running"}
    assert events[-1]["status"] == "done"
    assert events[-1]["content"] == "one two three four five"


async def test_someone_elses_summary_is_invisible(tmp_path: Path, sample_audio: Path) -> None:
    settings = settings_with_both(tmp_path, auth_mode="proxy")

    async with running_client(settings) as client:
        with sample_audio.open("rb") as handle:
            job = (
                await client.post(
                    "/api/jobs",
                    files={"file": ("meeting.wav", handle, "audio/wav")},
                    headers={"X-Remote-User": "marina"},
                )
            ).json()
        await drain(settings, SttStub(), LlmStub())

        preset = (await client.get("/api/presets", headers={"X-Remote-User": "marina"})).json()[0]
        summary = (
            await client.post(
                f"/api/jobs/{job['id']}/summaries",
                json={"preset_id": preset["id"]},
                headers={"X-Remote-User": "marina"},
            )
        ).json()

        stranger = await client.get(
            f"/api/summaries/{summary['id']}", headers={"X-Remote-User": "pavel"}
        )

        assert stranger.status_code == 404


async def test_a_summary_can_be_deleted(tmp_path: Path, sample_audio: Path) -> None:
    settings = settings_with_both(tmp_path)

    async with running_client(settings) as client:
        job = await transcribed_job(client, settings, sample_audio)
        preset = await first_preset(client)
        summary = (
            await client.post(
                f"/api/jobs/{job['id']}/summaries", json={"preset_id": preset["id"]}
            )
        ).json()

        assert (await client.delete(f"/api/summaries/{summary['id']}")).status_code == 204
        assert (await client.get(f"/api/jobs/{job['id']}/summaries")).json() == []


async def test_summarising_without_a_language_model_fails_with_a_code(
    tmp_path: Path, sample_audio: Path
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        stt_base_url="http://speaches.test/v1",
        stt_model="stub-whisper",
        _env_file=None,
    )

    async with running_client(settings) as client:
        job = await transcribed_job(client, settings, sample_audio)
        preset = await first_preset(client)
        await client.post(f"/api/jobs/{job['id']}/summaries", json={"preset_id": preset["id"]})

        await drain(settings, SttStub(), LlmStub())

        [summary] = (await client.get(f"/api/jobs/{job['id']}/summaries")).json()
        assert summary["status"] == "failed"
        assert summary["error_code"] == "no_llm_provider"


async def test_a_summary_cannot_be_asked_for_before_the_transcript_exists(
    tmp_path: Path, sample_audio: Path
) -> None:
    settings = settings_with_both(tmp_path)

    async with running_client(settings) as client:
        job = await upload(client, sample_audio)
        preset = await first_preset(client)

        refused = await client.post(
            f"/api/jobs/{job['id']}/summaries", json={"preset_id": preset["id"]}
        )

        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "transcript_not_ready"
