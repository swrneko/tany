import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, health, setup
from app.config import Settings
from app.db import Database
from app.errors import register_error_handlers
from app.migrator import upgrade_to_head
from app.secrets import load_or_create_secret
from app.sessions import SessionSigner
from app.static import mount_frontend


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    settings.ensure_dirs()
    # Migrations run automatically: "exec into the container and upgrade" is a guaranteed bug report
    await asyncio.to_thread(upgrade_to_head, settings.db_path)
    app.state.db = Database(settings.db_path)
    app.state.sessions = SessionSigner(
        load_or_create_secret(settings.secret_key_path), settings.session_max_age_days
    )
    try:
        yield
    finally:
        await app.state.db.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="transcribe-anything", lifespan=lifespan)
    app.state.settings = settings or Settings()
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(setup.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    mount_frontend(app, app.state.settings.frontend_dist)
    return app
