from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.chunking import HARD_MAX_SECONDS, TARGET_SECONDS
from app.summarize import DEFAULT_CONTEXT_TOKENS

AuthMode = Literal["builtin", "proxy", "disabled"]
ChunkingMode = Literal["auto", "always", "never"]


class Settings(BaseSettings):
    """Process configuration. Environment variables carry no prefix: AUTH_MODE, DATA_DIR, ..."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    data_dir: Path = Path("/data")
    frontend_dist: Path | None = None

    max_upload_size: int = 5 * 1024**3

    sse_poll_seconds: float = 1.0
    cancel_poll_seconds: float = 1.0
    heartbeat_stale_seconds: float = 120.0

    stt_retry_attempts: int = 3
    stt_retry_backoff_seconds: float = 2.0

    stt_chunking: ChunkingMode = "auto"
    chunk_target_seconds: float = TARGET_SECONDS
    chunk_max_seconds: float = HARD_MAX_SECONDS

    # Bootstrap seed only. Once a provider row exists the database is the source
    # of truth, so changing a provider never means editing env and restarting.
    stt_base_url: str | None = None
    stt_api_key: str | None = None
    stt_model: str | None = None

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_context_tokens: int = DEFAULT_CONTEXT_TOKENS

    # How often the worker writes streamed summary text back to the database.
    # Every token would hammer SQLite; once a second is smooth enough to read.
    summary_flush_seconds: float = 0.5

    auth_mode: AuthMode = "builtin"
    proxy_user_header: str = "X-Remote-User"
    session_cookie_name: str = "ta_session"
    session_max_age_days: int = 30
    # Turn on once the instance is behind TLS. Off by default because the
    # first thing everyone does is open http://localhost:8927, and a cookie
    # the browser silently drops looks exactly like a broken login.
    session_cookie_secure: bool = False

    @property
    def db_dir(self) -> Path:
        return self.data_dir / "db"

    @property
    def db_path(self) -> Path:
        return self.db_dir / "app.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def secret_key_path(self) -> Path:
        return self.data_dir / "secret.key"

    def ensure_dirs(self) -> None:
        for directory in (self.db_dir, self.media_dir, self.tmp_dir):
            directory.mkdir(parents=True, exist_ok=True)
