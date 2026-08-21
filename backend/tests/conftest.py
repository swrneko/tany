from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app

ADMIN_CREDENTIALS = {"username": "admin", "password": "correct horse battery staple"}


@asynccontextmanager
async def running_client(settings: Settings) -> AsyncIterator[AsyncClient]:
    """Start the app for real -- lifespan included, so migrations actually run."""
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, auth_mode="builtin", _env_file=None)


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    async with running_client(settings) as ac:
        yield ac


@pytest.fixture
async def admin(client: AsyncClient) -> dict[str, str]:
    """An installation that has already been through the setup wizard."""
    response = await client.post("/api/setup", json=ADMIN_CREDENTIALS)
    assert response.status_code == 201
    return ADMIN_CREDENTIALS
