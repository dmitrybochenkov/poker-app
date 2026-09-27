from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.security.telegram_webapp import verify_telegram_init_data
from app.config.settings import settings
from app.db.dependencies import get_db_session
from app.db.repositories.user_repository import UserRepository

TELEGRAM_INIT_DATA_MAX_AGE_SECONDS = 3600


@dataclass(frozen=True)
class WebAppIdentity:
    platform: Literal["telegram", "vk"]
    external_user_id: int
    user_row_id: int | None
    is_admin: bool
    is_approved: bool


async def resolve_webapp_identity(
    *, session: AsyncSession, platform: str, telegram_init_data: str | None
) -> WebAppIdentity:
    if platform != "telegram":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="WebApp platform authentication is unsupported",
        )
    external_id = verify_telegram_init_data(
        telegram_init_data or "",
        bot_token=settings.telegram_bot_token,
        max_age_seconds=TELEGRAM_INIT_DATA_MAX_AGE_SECONDS,
    )
    user = await UserRepository(session).get_by_telegram_id(telegram_id=external_id)
    return WebAppIdentity(
        platform="telegram",
        external_user_id=external_id,
        user_row_id=int(user.row_id) if user is not None else None,
        is_admin=bool(user.is_admin) if user is not None else False,
        is_approved=bool(user.is_approved) if user is not None else False,
    )


async def get_webapp_identity(
    session: AsyncSession = Depends(get_db_session),
    x_webapp_platform: str = Header(default="telegram"),
    x_telegram_init_data: str | None = Header(default=None),
) -> WebAppIdentity:
    return await resolve_webapp_identity(
        session=session,
        platform=x_webapp_platform,
        telegram_init_data=x_telegram_init_data,
    )


def require_authenticated_principal(
    identity: WebAppIdentity = Depends(get_webapp_identity),
) -> WebAppIdentity:
    if identity.user_row_id is None or not identity.is_approved:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not registered")
    return identity


def require_admin_principal(
    principal: WebAppIdentity = Depends(require_authenticated_principal),
) -> WebAppIdentity:
    if not principal.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return principal
