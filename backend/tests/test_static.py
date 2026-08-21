from pathlib import Path

import pytest

from app.config import Settings
from tests.conftest import running_client

SPA_MARKER = "<html>spa</html>"


@pytest.fixture
def settings_with_spa(tmp_path: Path) -> Settings:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(SPA_MARKER)
    (dist / "assets" / "app.js").write_text("console.log(1)")
    return Settings(data_dir=tmp_path / "data", frontend_dist=dist, _env_file=None)


async def test_unknown_ui_route_serves_the_spa(settings_with_spa: Settings) -> None:
    async with running_client(settings_with_spa) as client:
        response = await client.get("/jobs/some-id")

        assert response.status_code == 200
        assert response.text == SPA_MARKER


async def test_unknown_api_route_stays_json(settings_with_spa: Settings) -> None:
    async with running_client(settings_with_spa) as client:
        response = await client.get("/api/does-not-exist")

        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")
