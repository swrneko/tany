import asyncio
import json
import logging
import os
import socket
from collections.abc import Callable
from pathlib import Path

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.crypto import decrypt_secret
from app.db import Database
from app.errors import ApiError
from app.media import normalize_to_opus
from app.models import Job, Provider, Segment, Transcript, utcnow
from app.stt import SttClient, stt_http_client

log = logging.getLogger("worker")

SttFactory = Callable[[Provider], httpx.AsyncClient]

IDLE_POLL_SECONDS = 2.0


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
    ) -> None:
        self.settings = settings
        self.database = database
        self.secret = secret
        self.identity = worker_identity()
        self._stt_factory = stt_factory or self._default_stt_client

    def _default_stt_client(self, provider: Provider) -> httpx.AsyncClient:
        api_key = (
            decrypt_secret(provider.api_key_encrypted, self.secret)
            if provider.api_key_encrypted
            else None
        )
        return stt_http_client(provider.base_url, api_key)

    async def run_forever(self) -> None:
        while True:
            if not await self.run_once():
                await asyncio.sleep(IDLE_POLL_SECONDS)

    async def run_once(self) -> bool:
        job_id = await self._claim()
        if job_id is None:
            return False

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
            finally:
                job.finished_at = utcnow()
                await session.commit()
                self._clear_workspace(job_id)

        return True

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
        source = self._find_source(job)
        audio = self.settings.media_dir / str(job.id) / "audio.ogg"

        info = await normalize_to_opus(source, audio)
        job.duration_sec = info.duration_sec
        # The original is gone the moment we no longer need it. Keeping video
        # around fills a home server's disk inside a week.
        source.unlink(missing_ok=True)

        provider, model = await self._resolve_stt(session, job)
        async with self._stt_factory(provider) as http:
            result = await SttClient(http).transcribe(
                audio, model=model, language=job.language, prompt=job.prompt
            )

        job.stt_provider_id = provider.id
        job.stt_model = model
        job.language = result.language

        transcript = Transcript(
            job_id=job.id, raw_json=json.dumps(result.raw), language=result.language
        )
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
            for index, segment in enumerate(result.segments)
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
