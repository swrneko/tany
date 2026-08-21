from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ApiError
from app.models import User

LOCAL_USERNAME = "local"


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db.session_factory() as session:
        yield session


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_secret(request: Request) -> bytes:
    secret: bytes = request.app.state.secret
    return secret


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
SecretDep = Annotated[bytes, Depends(get_secret)]


async def resolve_user(session: AsyncSession, username: str, *, is_admin: bool) -> User:
    """Look the user up, creating the row on first sight.

    Used by the auth modes that delegate identity elsewhere: every job still
    needs a real owner_id, so an identity from outside has to land in `users`.
    """
    user = await session.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(username=username, password_hash="", is_admin=is_admin)
        session.add(user)
        await session.commit()
    return user


async def get_current_user(
    request: Request, session: SessionDep, settings: SettingsDep
) -> User:
    if settings.auth_mode == "disabled":
        return await resolve_user(session, LOCAL_USERNAME, is_admin=True)

    if settings.auth_mode == "proxy":
        username = request.headers.get(settings.proxy_user_header)
        if not username:
            raise ApiError(401, "not_authenticated", "Sign in to continue.")
        return await resolve_user(session, username, is_admin=False)

    token = request.cookies.get(settings.session_cookie_name)
    user_id = request.app.state.sessions.read(token) if token else None
    user = await session.get(User, user_id) if user_id else None
    if user is None:
        raise ApiError(401, "not_authenticated", "Sign in to continue.")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
