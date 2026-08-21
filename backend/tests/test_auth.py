from pathlib import Path

from httpx import AsyncClient

from app.config import Settings
from tests.conftest import ADMIN_CREDENTIALS, running_client


async def test_login_grants_access_to_the_current_user(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    login = await client.post("/api/auth/login", json=admin)
    assert login.status_code == 200

    me = await client.get("/api/auth/me")

    assert me.status_code == 200
    assert me.json()["username"] == "admin"
    assert me.json()["is_admin"] is True


async def test_session_cookie_can_be_restricted_to_https(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, session_cookie_secure=True, _env_file=None)

    async with running_client(settings) as client:
        await client.post("/api/setup", json=ADMIN_CREDENTIALS)
        login = await client.post("/api/auth/login", json=ADMIN_CREDENTIALS)

        assert "secure" in login.headers["set-cookie"].lower()


async def test_login_with_a_wrong_password_is_refused(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    login = await client.post(
        "/api/auth/login", json={"username": admin["username"], "password": "wrong"}
    )

    assert login.status_code == 401
    assert login.json()["error"]["code"] == "invalid_credentials"


async def test_current_user_is_refused_without_a_session(client: AsyncClient) -> None:
    me = await client.get("/api/auth/me")

    assert me.status_code == 401
    assert me.json()["error"]["code"] == "not_authenticated"


async def test_logout_ends_the_session(client: AsyncClient, admin: dict[str, str]) -> None:
    await client.post("/api/auth/login", json=admin)

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204

    me = await client.get("/api/auth/me")
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "not_authenticated"
