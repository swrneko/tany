from pathlib import Path

from app.config import Settings
from tests.conftest import running_client


async def test_disabled_auth_serves_every_request_as_the_local_user(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, auth_mode="disabled", _env_file=None)

    async with running_client(settings) as client:
        me = await client.get("/api/auth/me")

        assert me.status_code == 200
        assert me.json()["is_admin"] is True


async def test_disabled_auth_skips_the_setup_wizard(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, auth_mode="disabled", _env_file=None)

    async with running_client(settings) as client:
        status = await client.get("/api/setup/status")

        assert status.json() == {"needs_setup": False, "auth_mode": "disabled"}


async def test_proxy_auth_trusts_the_identity_header(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, auth_mode="proxy", _env_file=None)

    async with running_client(settings) as client:
        me = await client.get("/api/auth/me", headers={"X-Remote-User": "marina"})

        assert me.status_code == 200
        assert me.json()["username"] == "marina"


async def test_proxy_auth_rejects_a_request_without_the_identity_header(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, auth_mode="proxy", _env_file=None)

    async with running_client(settings) as client:
        me = await client.get("/api/auth/me")

        assert me.status_code == 401
        assert me.json()["error"]["code"] == "not_authenticated"
