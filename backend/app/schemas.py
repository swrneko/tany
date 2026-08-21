import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

USERNAME_PATTERN = r"^[a-zA-Z0-9._-]+$"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    is_admin: bool


class ProviderOut(BaseModel):
    id: uuid.UUID
    kind: str
    name: str
    base_url: str
    default_model: str | None
    context_tokens: int | None
    is_default: bool
    # Always masked. The full key leaves this process only towards the provider.
    api_key: str | None


class JobOut(BaseModel):
    id: uuid.UUID
    title: str
    source_type: str
    status: str
    progress: float
    language: str | None
    duration_sec: float | None
    # A code the UI translates, plus the values to interpolate into it.
    error_code: str | None
    error_params: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None


class SegmentOut(BaseModel):
    idx: int
    start: float
    end: float
    text: str
    speaker: str | None


class TranscriptOut(BaseModel):
    job_id: uuid.UUID
    language: str | None
    # Derived from the segments, never stored: exports and edits are layers on
    # top of the immutable raw response.
    text: str
    segments: list[SegmentOut]


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=128)
