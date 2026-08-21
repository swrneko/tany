from pathlib import Path

from app.config import Settings
from tests.conftest import ADMIN_CREDENTIALS, running_client


def settings_with_stt(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        stt_base_url="http://speaches:8000/v1",
        stt_api_key="sk-proj-abcdefgh1234",
        stt_model="Systran/faster-whisper-small",
        _env_file=None,
    )


async def test_the_environment_seeds_a_provider_on_first_start(tmp_path: Path) -> None:
    async with running_client(settings_with_stt(tmp_path)) as client:
        await client.post("/api/setup", json=ADMIN_CREDENTIALS)
        await client.post("/api/auth/login", json=ADMIN_CREDENTIALS)

        providers = await client.get("/api/providers")

        assert providers.status_code == 200
        [provider] = providers.json()
        assert provider["kind"] == "stt"
        assert provider["base_url"] == "http://speaches:8000/v1"
        assert provider["default_model"] == "Systran/faster-whisper-small"
        assert provider["is_default"] is True


async def test_the_api_key_is_never_returned_in_full(tmp_path: Path) -> None:
    async with running_client(settings_with_stt(tmp_path)) as client:
        await client.post("/api/setup", json=ADMIN_CREDENTIALS)
        await client.post("/api/auth/login", json=ADMIN_CREDENTIALS)

        [provider] = (await client.get("/api/providers")).json()

        assert provider["api_key"] == "sk-…1234"
        assert "sk-proj-abcdefgh1234" not in (await client.get("/api/providers")).text


async def test_no_provider_is_invented_without_configuration(tmp_path: Path) -> None:
    async with running_client(Settings(data_dir=tmp_path, _env_file=None)) as client:
        await client.post("/api/setup", json=ADMIN_CREDENTIALS)
        await client.post("/api/auth/login", json=ADMIN_CREDENTIALS)

        assert (await client.get("/api/providers")).json() == []
