from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AuthMode = Literal["builtin", "proxy", "disabled"]


class Settings(BaseSettings):
    """Process configuration. Environment variables carry no prefix: AUTH_MODE, DATA_DIR, ..."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    data_dir: Path = Path("/data")
    frontend_dist: Path | None = None

    auth_mode: AuthMode = "builtin"
    proxy_user_header: str = "X-Remote-User"
    session_cookie_name: str = "ta_session"
    session_max_age_days: int = 30

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
