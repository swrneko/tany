import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select

from app.deps import CurrentUserDep, SessionDep, SettingsDep
from app.errors import ApiError
from app.models import Job, Segment, Transcript, User, utcnow
from app.schemas import JobOut, SegmentOut, TranscriptOut
from app.storage import save_upload

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _present(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        title=job.title,
        source_type=job.source_type,
        status=job.status,
        progress=job.progress,
        language=job.language,
        duration_sec=job.duration_sec,
        error_code=job.error_code,
        error_params=json.loads(job.error_params) if job.error_params else {},
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


async def _owned_job(session: SessionDep, user: User, job_id: uuid.UUID) -> Job:
    job = await session.scalar(
        select(Job).where(Job.id == job_id, Job.owner_id == user.id)
    )
    if job is None:
        # Not 403: whether a job exists at all is the owner's business.
        raise ApiError(404, "job_not_found", "No such job.")
    return job


@router.post("", status_code=201)
async def create_job(
    file: UploadFile,
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> JobOut:
    title = Path(file.filename or "upload").name

    job = Job(owner_id=user.id, source_type="upload", source_ref=title, title=title)
    session.add(job)
    await session.flush()

    source = settings.tmp_dir / str(job.id) / f"source{Path(title).suffix}"
    _, job.sha256 = await save_upload(file, source, settings.max_upload_size)

    await session.commit()
    return _present(job)


@router.get("")
async def list_jobs(user: CurrentUserDep, session: SessionDep) -> list[JobOut]:
    jobs = await session.scalars(
        select(Job).where(Job.owner_id == user.id).order_by(Job.created_at.desc())
    )
    return [_present(job) for job in jobs]


TERMINAL_STATUSES = frozenset({"done", "failed", "cancelled"})


def _sse(payload: str) -> str:
    return f"data: {payload}\n\n"


@router.get("/events")
async def job_list_events(
    request: Request,
    user: CurrentUserDep,
    settings: SettingsDep,
) -> StreamingResponse:
    """One stream for the whole list.

    Ten queued files must not mean ten connections: browsers cap concurrent
    requests per origin, and the surplus would simply never open.
    """
    factory = request.app.state.db.session_factory
    owner_id = user.id

    async def stream() -> AsyncIterator[str]:
        previous: str | None = None
        while True:
            async with factory() as poll_session:
                jobs = (
                    await poll_session.scalars(
                        select(Job)
                        .where(Job.owner_id == owner_id)
                        .order_by(Job.created_at.desc())
                    )
                ).all()

            payload = json.dumps([json.loads(_present(job).model_dump_json()) for job in jobs])
            if payload != previous:
                previous = payload
                yield _sse(payload)

            if all(job.status in TERMINAL_STATUSES for job in jobs):
                return

            await asyncio.sleep(settings.sse_poll_seconds)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{job_id}")
async def read_job(job_id: uuid.UUID, user: CurrentUserDep, session: SessionDep) -> JobOut:
    return _present(await _owned_job(session, user, job_id))


@router.get("/{job_id}/events")
async def job_events(
    job_id: uuid.UUID,
    request: Request,
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> StreamingResponse:
    """Server-sent events, not a websocket.

    The traffic only ever flows one way, browsers reconnect a dropped stream by
    themselves, any reverse proxy passes it through without a protocol upgrade,
    and it can be debugged with curl.
    """
    await _owned_job(session, user, job_id)
    factory = request.app.state.db.session_factory

    async def stream() -> AsyncIterator[str]:
        previous: str | None = None
        while True:
            async with factory() as poll_session:
                job = await poll_session.get(Job, job_id)
            if job is None:
                return

            payload = _present(job).model_dump_json()
            if payload != previous:
                previous = payload
                yield _sse(payload)

            if job.status in TERMINAL_STATUSES:
                return

            await asyncio.sleep(settings.sse_poll_seconds)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{job_id}/audio")
async def job_audio(
    job_id: uuid.UUID, user: CurrentUserDep, session: SessionDep, settings: SettingsDep
) -> FileResponse:
    job = await _owned_job(session, user, job_id)

    audio = settings.media_dir / str(job.id) / "audio.ogg"
    if not audio.is_file():
        raise ApiError(404, "audio_unavailable", "The audio for this job is gone.")

    return FileResponse(audio, media_type="audio/ogg", filename=f"{job.title}.ogg")


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: uuid.UUID, user: CurrentUserDep, session: SessionDep) -> JobOut:
    job = await _owned_job(session, user, job_id)

    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = utcnow()
    elif job.status == "running":
        # The worker owns the process; it polls for this and stops the work.
        job.status = "cancelling"
    else:
        raise ApiError(
            409,
            "job_not_cancellable",
            f"A job that is {job.status} cannot be cancelled.",
            status=job.status,
        )

    await session.commit()
    return _present(job)


@router.get("/{job_id}/transcript")
async def read_transcript(
    job_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> TranscriptOut:
    job = await _owned_job(session, user, job_id)

    transcript = await session.scalar(select(Transcript).where(Transcript.job_id == job.id))
    if transcript is None:
        raise ApiError(404, "transcript_not_ready", "This job has no transcript yet.")

    rows = await session.scalars(
        select(Segment).where(Segment.transcript_id == transcript.id).order_by(Segment.idx)
    )
    segments = [
        SegmentOut(
            idx=row.idx,
            start=row.start,
            end=row.end,
            text=row.edited_text if row.edited_text is not None else row.text,
            speaker=row.speaker,
        )
        for row in rows
    ]

    return TranscriptOut(
        job_id=job.id,
        language=transcript.language,
        text=" ".join(segment.text for segment in segments).strip(),
        segments=segments,
    )
