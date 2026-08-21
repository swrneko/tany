from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.crypto import encrypt_secret
from app.models import Provider


async def seed_providers(session: AsyncSession, settings: Settings, secret: bytes) -> None:
    """Copy the environment into the database once, on an empty installation.

    Environment variables are a convenient way to arrive preconfigured, but a
    terrible way to live: changing a provider should not mean editing a file and
    restarting a container. So env seeds, and the database rules from then on.
    """
    if not settings.stt_base_url:
        return

    existing = await session.scalar(select(func.count()).select_from(Provider))
    if existing:
        return

    session.add(
        Provider(
            kind="stt",
            name="Speech to text",
            base_url=settings.stt_base_url,
            api_key_encrypted=(
                encrypt_secret(settings.stt_api_key, secret) if settings.stt_api_key else None
            ),
            default_model=settings.stt_model,
            is_default=True,
        )
    )
    await session.commit()
