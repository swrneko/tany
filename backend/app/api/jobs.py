import json
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile
from sqlalchemy import select

from app.deps import CurrentUserDep, SessionDep, SettingsDep
from app.errors import ApiError
from app.models import Job, Segment, Transcript, User
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


@router.get("/{job_id}")
async def read_job(job_id: uuid.UUID, user: CurrentUserDep, session: SessionDep) -> JobOut:
    return _present(await _owned_job(session, user, job_id))


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
