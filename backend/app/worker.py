import asyncio
import json
import logging
import os
import socket
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import httpx
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.chunking import Chunk, plan_chunks
from app.config import Settings
from app.crypto import decrypt_secret
from app.db import Database
from app.errors import ApiError
from app.llm import llm_http_client
from app.media import detect_silences, extract_chunk, normalize_to_opus, probe
from app.models import Job, Provider, Segment, Summary, Transcript, utcnow
from app.summary_runner import LlmFactory, SummaryRunner
from app.stt import SttClient
from app.stt import Segment as SttSegment
from app.stt import Transcription, stt_http_client

log = logging.getLogger("worker")

SttFactory = Callable[[Provider], httpx.AsyncClient]

IDLE_POLL_SECONDS = 2.0

# Failures worth repeating: the connection, not the request.
RETRYABLE_CODES = frozenset({"stt_unreachable", "stt_server_error"})


def worker_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


class Worker:
    """Runs in its own container, sharing only the volume with the API.

    Not in-process: an API restart would kill live jobs, ffmpeg would fight the
    request loop for CPU, and --reload in development would murder every run.
    Not Celery either -- this is dozens of jobs a day, and a broker would be a
    tax on complexity paid for nothing.
    """

    def __init__(
        self,
        settings: Settings,
        database: Database,
        secret: bytes,
        *,
        stt_factory: SttFactory | None = None,
        llm_factory: LlmFactory | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.secret = secret
        self.identity = worker_identity()
        self._stt_factory = stt_factory or self._default_stt_client
        self._llm_factory = llm_factory or self._default_llm_client

    def _api_key(self, provider: Provider) -> str | None:
        if not provider.api_key_encrypted:
            return None
        return decrypt_secret(provider.api_key_encrypted, self.secret)

    def _default_stt_client(self, provider: Provider) -> httpx.AsyncClient:
        return stt_http_client(provider.base_url, self._api_key(provider))

    def _default_llm_client(self, provider: Provider) -> httpx.AsyncClient:
        return llm_http_client(provider.base_url, self._api_key(provider))

    async def recover_stale_jobs(self) -> int:
        """Requeue whatever the previous worker was holding when it died.

        A crashed process leaves a job marked running forever: the claim query
        only looks at queued rows, so nothing will ever pick it up again and it
        sits there looking busy until a human reads the database.
        """
        cutoff = utcnow() - timedelta(seconds=self.settings.heartbeat_stale_seconds)
        stale = or_(Job.heartbeat_at.is_(None), Job.heartbeat_at <= cutoff)

        async with self.database.session_factory() as session:
            requeued = await session.execute(
                update(Job)
                .where(Job.status == "running", stale)
                .values(
                    status="queued",
                    worker_id=None,
                    started_at=None,
                    heartbeat_at=None,
                    progress=0.0,
                )
            )
            # A job whose cancellation was already asked for should not come
            # back to life just because the worker handling it went away.
            await session.execute(
                update(Job)
                .where(Job.status == "cancelling", stale)
                .values(status="cancelled", finished_at=utcnow())
            )
            await session.commit()

        count = requeued.rowcount or 0
        if count:
            log.info("requeued %d job(s) left behind by a previous worker", count)
        return count

    async def run_forever(self) -> None:
        await self.recover_stale_jobs()
        while True:
            if not await self.run_once():
                await asyncio.sleep(IDLE_POLL_SECONDS)

    async def run_once(self) -> bool:
        # Transcription first: a summary is worthless until its transcript
        # exists, and a queue of summaries must not starve new recordings.
        return await self._run_transcription() or await self._run_summary()

    async def _run_summary(self) -> bool:
        summary_id = await self._claim_summary()
        if summary_id is None:
            return False

        async with self.database.session_factory() as session:
            summary = await session.get(Summary, summary_id)
            assert summary is not None
            try:
                await SummaryRunner(self.settings, session, self._llm_factory).run(summary)
                summary.status = "done"
            except ApiError as failure:
                log.warning("summary %s failed: %s", summary.id, failure.message)
                summary.status = "failed"
                summary.error_code = failure.code
                summary.error_message = failure.message
                summary.error_params = json.dumps(failure.params)
            summary.finished_at = utcnow()
            await session.commit()

        return True

    async def _claim_summary(self) -> object | None:
        now = utcnow()
        oldest = (
            select(Summary.id)
            .where(Summary.status == "queued")
            .order_by(Summary.created_at)
            .limit(1)
            .scalar_subquery()
        )
        statement = (
            update(Summary)
            .where(Summary.id == oldest)
            .values(status="running", worker_id=self.identity, heartbeat_at=now)
            .returning(Summary.id)
        )

        async with self.database.session_factory() as session:
            claimed = (await session.execute(statement)).scalar_one_or_none()
            await session.commit()
            return claimed

    async def _run_transcription(self) -> bool:
        job_id = await self._claim()
        if job_id is None:
            return False

        cancelled_by_user = False

        def request_stop() -> None:
            nonlocal cancelled_by_user
            cancelled_by_user = True

        working = asyncio.create_task(self._execute(job_id))
        supervisor = asyncio.create_task(self._supervise(job_id, working, request_stop))
        try:
            await working
        except asyncio.CancelledError:
            if not cancelled_by_user:
                # The process itself is going away. Leave the job and its
                # workspace exactly as they are so a successor can resume;
                # marking it cancelled would tell the user they stopped
                # something they never touched.
                supervisor.cancel()
                raise
            await self._finish(job_id, status="cancelled")

        supervisor.cancel()
        self._clear_workspace(job_id)
        return True

    async def _execute(self, job_id: object) -> None:
        async with self.database.session_factory() as session:
            job = await session.get(Job, job_id)
            assert job is not None
            try:
                await self._process(session, job)
                job.status = "done"
                job.progress = 1.0
            except ApiError as failure:
                log.warning("job %s failed: %s", job.id, failure.message)
                job.status = "failed"
                job.error_code = failure.code
                job.error_message = failure.message
                job.error_params = json.dumps(failure.params)
            else:
                job.finished_at = utcnow()
                await session.commit()
                return
            job.finished_at = utcnow()
            await session.commit()

    async def _supervise(
        self,
        job_id: object,
        working: asyncio.Task[None],
        request_stop: Callable[[], None],
    ) -> None:
        """Keep the heartbeat fresh and stop the work when a cancel arrives.

        The API cannot reach into this process, so the cancel request travels
        through the database and lands here as a task cancellation -- which
        kills ffmpeg and drops the HTTP request to the provider.
        """
        while True:
            await asyncio.sleep(self.settings.cancel_poll_seconds)
            async with self.database.session_factory() as session:
                status = await session.scalar(select(Job.status).where(Job.id == job_id))
                if status == "cancelling":
                    request_stop()
                    working.cancel()
                    return
                await session.execute(
                    update(Job).where(Job.id == job_id).values(heartbeat_at=utcnow())
                )
                await session.commit()

    async def _finish(self, job_id: object, *, status: str) -> None:
        async with self.database.session_factory() as session:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status=status, finished_at=utcnow())
            )
            await session.commit()

    async def _claim(self) -> object | None:
        """Take the oldest queued job in a single statement.

        Two workers running this concurrently cannot both win: the UPDATE holds
        the write lock, and the loser's subquery finds nothing.
        """
        now = utcnow()
        oldest = (
            select(Job.id)
            .where(Job.status == "queued")
            .order_by(Job.created_at)
            .limit(1)
            .scalar_subquery()
        )
        statement = (
            update(Job)
            .where(Job.id == oldest)
            .values(
                status="running",
                worker_id=self.identity,
                started_at=now,
                heartbeat_at=now,
            )
            .returning(Job.id)
        )

        async with self.database.session_factory() as session:
            claimed = (await session.execute(statement)).scalar_one_or_none()
            await session.commit()
            return claimed

    async def _process(self, session: AsyncSession, job: Job) -> None:
        workspace = self.settings.tmp_dir / str(job.id)
        audio = self.settings.media_dir / str(job.id) / "audio.ogg"

        # Normalised audio is the checkpoint: a job resumed after a crash skips
        # straight past ffmpeg, and the original upload is already gone by then.
        if audio.is_file():
            info = await probe(audio)
        else:
            source = self._find_source(job)
            info = await normalize_to_opus(source, audio)
            # The original goes the moment we no longer need it. Keeping video
            # around fills a home server's disk inside a week.
            source.unlink(missing_ok=True)

        job.duration_sec = info.duration_sec

        # A crash between writing the transcript and finishing the job would
        # otherwise collide with the unique constraint on the second attempt.
        await session.execute(delete(Transcript).where(Transcript.job_id == job.id))

        provider, model = await self._resolve_stt(session, job)
        job.stt_provider_id = provider.id
        job.stt_model = model
        await session.commit()

        chunks = await self._plan_chunks(audio, info.duration_sec)
        language = job.language
        collected: list[SttSegment] = []
        raw_parts: list[dict[str, object]] = []

        async with self._stt_factory(provider) as http:
            client = SttClient(http)
            for chunk in chunks:
                piece = audio
                if len(chunks) > 1:
                    piece = workspace / f"chunk-{chunk.index:04d}.ogg"
                    await extract_chunk(audio, piece, start=chunk.start, end=chunk.end)

                result = await self._transcribe_with_retries(
                    client, piece, model=model, language=language, prompt=job.prompt
                )
                # Detected once, then forced. Otherwise chunks of one recording
                # come back in different languages and the result still reads
                # plausibly enough that nobody notices.
                language = language or result.language

                collected.extend(
                    SttSegment(
                        start=segment.start + chunk.start,
                        end=segment.end + chunk.start,
                        text=segment.text,
                    )
                    for segment in result.segments
                )
                raw_parts.append(result.raw)

                if piece is not audio:
                    piece.unlink(missing_ok=True)

                job.progress = (chunk.index + 1) / len(chunks)
                job.heartbeat_at = utcnow()
                await session.commit()

        job.language = language

        raw = raw_parts[0] if len(raw_parts) == 1 else {"chunks": raw_parts}
        transcript = Transcript(job_id=job.id, raw_json=json.dumps(raw), language=language)
        session.add(transcript)
        await session.flush()

        session.add_all(
            Segment(
                transcript_id=transcript.id,
                idx=index,
                start=segment.start,
                end=segment.end,
                text=segment.text,
            )
            for index, segment in enumerate(collected)
        )

    async def _transcribe_with_retries(
        self,
        client: SttClient,
        audio: Path,
        *,
        model: str,
        language: str | None,
        prompt: str | None,
    ) -> Transcription:
        """Retry a single chunk, never the whole recording.

        Only transport-shaped failures are worth repeating: a refused
        connection, a timeout, a 5xx from an inference server that fell over
        under load. A 4xx means the request itself is wrong -- resending it
        wastes time and, on a metered API, money.
        """
        attempts = max(1, self.settings.stt_retry_attempts)
        last: ApiError | None = None

        for attempt in range(attempts):
            try:
                return await client.transcribe(
                    audio, model=model, language=language, prompt=prompt
                )
            except ApiError as failure:
                if failure.code not in RETRYABLE_CODES:
                    raise
                last = failure
                if attempt < attempts - 1:
                    await asyncio.sleep(self.settings.stt_retry_backoff_seconds * 2**attempt)

        assert last is not None
        raise ApiError(
            503,
            "stt_unavailable",
            f"The speech-to-text server failed {attempts} times in a row.",
            attempts=attempts,
            **last.params,
        )

    async def _plan_chunks(self, audio: Path, duration: float) -> list[Chunk]:
        mode = self.settings.stt_chunking
        if mode == "never" or duration <= 0:
            return [Chunk(index=0, start=0.0, end=max(duration, 0.0))]

        if mode == "auto" and duration <= self.settings.chunk_max_seconds:
            return [Chunk(index=0, start=0.0, end=duration)]

        return plan_chunks(
            duration=duration,
            silences=await detect_silences(audio),
            target=self.settings.chunk_target_seconds,
            hard_max=self.settings.chunk_max_seconds,
        )

    def _find_source(self, job: Job) -> Path:
        workspace = self.settings.tmp_dir / str(job.id)
        candidates = sorted(workspace.glob("source*")) if workspace.is_dir() else []
        if not candidates:
            raise ApiError(
                410,
                "source_missing",
                "The uploaded file is no longer on disk.",
                job_id=str(job.id),
            )
        return candidates[0]

    async def _resolve_stt(self, session: AsyncSession, job: Job) -> tuple[Provider, str]:
        provider = await session.scalar(
            select(Provider)
            .where(Provider.kind == "stt")
            .order_by(Provider.is_default.desc(), Provider.created_at)
            .limit(1)
        )
        if provider is None:
            raise ApiError(
                503,
                "no_stt_provider",
                "No speech-to-text provider is configured.",
            )

        model = job.stt_model or provider.default_model
        if not model:
            raise ApiError(
                503,
                "no_stt_model",
                f"No model is set for provider {provider.name}.",
                provider=provider.name,
            )
        return provider, model

    def _clear_workspace(self, job_id: object) -> None:
        workspace = self.settings.tmp_dir / str(job_id)
        if not workspace.is_dir():
            return
        for leftover in workspace.iterdir():
            leftover.unlink(missing_ok=True)
        workspace.rmdir()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = Settings()
    settings.ensure_dirs()

    from app.secrets import load_or_create_secret

    database = Database(settings.db_path)
    worker = Worker(settings, database, load_or_create_secret(settings.secret_key_path))
    log.info("worker %s waiting for jobs", worker.identity)
    try:
        await worker.run_forever()
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())
