import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class UtcDateTime(sa.types.TypeDecorator[datetime]):
    """Store naive UTC, hand back aware UTC.

    SQLite keeps no offset, so an aware value goes in and a naive one comes out.
    That breaks twice: comparing a bound aware timestamp against stored naive
    text gives nonsense, and a naive timestamp handed to a browser renders in
    whatever timezone the viewer happens to be sitting in.
    """

    impl = sa.DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid7)
    username: Mapped[str] = mapped_column(sa.String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255))
    is_admin: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Provider(Base):
    """An OpenAI-compatible endpoint.

    STT and LLM share this table but never share a client: the protocols differ
    (/v1/audio/transcriptions vs /v1/chat/completions) and so do their failures.
    """

    __tablename__ = "providers"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid7)
    kind: Mapped[str] = mapped_column(sa.String(8), index=True)  # stt | llm
    name: Mapped[str] = mapped_column(sa.String(128))
    base_url: Mapped[str] = mapped_column(sa.Text)
    api_key_encrypted: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    default_model: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    context_tokens: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    extra_json: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid7)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    source_type: Mapped[str] = mapped_column(sa.String(16))  # upload | remote_url | ytdlp
    source_ref: Mapped[str] = mapped_column(sa.Text)
    title: Mapped[str] = mapped_column(sa.Text)

    status: Mapped[str] = mapped_column(sa.String(16), default="queued", index=True)
    progress: Mapped[float] = mapped_column(sa.Float, default=0.0)

    language: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    prompt: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    stt_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )
    stt_model: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)

    sha256: Mapped[str | None] = mapped_column(sa.String(64), index=True, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    # An error code the UI can translate; message is the English fallback.
    error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    error_params: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    worker_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid7)
    job_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("jobs.id", ondelete="CASCADE"), unique=True
    )
    # The provider's answer, verbatim and never rewritten. Every export format
    # and every user edit is a layer computed on top of this.
    raw_json: Mapped[str] = mapped_column(sa.Text)
    language: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid7)
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("transcripts.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int] = mapped_column(sa.Integer)
    start: Mapped[float] = mapped_column(sa.Float)
    end: Mapped[float] = mapped_column(sa.Float)
    text: Mapped[str] = mapped_column(sa.Text)
    # Edits live beside the original, never on top of it: this buys "reset my
    # edits" and "re-transcribe with another model, keep the edits to compare".
    edited_text: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    speaker: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
