from fastapi import APIRouter
from sqlalchemy import select

from app.crypto import decrypt_secret, mask_secret
from app.deps import CurrentUserDep, SecretDep, SessionDep
from app.models import Provider
from app.schemas import ProviderOut

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("")
async def list_providers(
    _user: CurrentUserDep, session: SessionDep, secret: SecretDep
) -> list[ProviderOut]:
    providers = (await session.scalars(select(Provider).order_by(Provider.created_at))).all()
    return [_present(provider, secret) for provider in providers]


def _present(provider: Provider, secret: bytes) -> ProviderOut:
    api_key = (
        mask_secret(decrypt_secret(provider.api_key_encrypted, secret))
        if provider.api_key_encrypted
        else None
    )
    return ProviderOut(
        id=provider.id,
        kind=provider.kind,
        name=provider.name,
        base_url=provider.base_url,
        default_model=provider.default_model,
        context_tokens=provider.context_tokens,
        is_default=provider.is_default,
        api_key=api_key,
    )
