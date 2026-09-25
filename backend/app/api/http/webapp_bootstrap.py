from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.http.webapp_common import _get_user_by_platform
from app.api.http.webapp_schemas import WebAppBootstrapRead
from app.db.dependencies import get_db_session
from app.db.models.poker import Poker
from app.db.repositories.poll_config_repository import PollConfigRepository

router = APIRouter()


async def _build_bootstrap_response(
    *,
    session: AsyncSession,
    platform: Literal["telegram", "vk"],
    user_id: int,
) -> WebAppBootstrapRead:
    user = await _get_user_by_platform(session=session, platform=platform, user_id=user_id)
    has_active_poll = await PollConfigRepository(session).get_active_month() is not None
    active_poker = (
        await session.execute(select(Poker.row_id).where(Poker.is_going.is_(True)).limit(1))
    ).scalar_one_or_none()
    has_active_poker = active_poker is not None
    if user is None:
        return WebAppBootstrapRead(
            user_row_id=None,
            is_registered=False,
            is_admin=False,
            is_approved=False,
            has_phone=False,
            has_active_poll=has_active_poll,
            has_active_poker=has_active_poker,
        )
    has_phone = bool(user.tel_number and str(user.tel_number).strip())
    return WebAppBootstrapRead(
        user_row_id=user.row_id,
        is_registered=True,
        is_admin=bool(user.is_admin),
        is_approved=bool(user.is_approved),
        has_phone=has_phone,
        has_active_poll=has_active_poll,
        has_active_poker=has_active_poker,
    )


@router.get("/bootstrap/{telegram_id}", response_model=WebAppBootstrapRead)
async def webapp_bootstrap(
    telegram_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> WebAppBootstrapRead:
    return await _build_bootstrap_response(
        session=session,
        platform="telegram",
        user_id=telegram_id,
    )


@router.get("/bootstrap/{platform}/{user_id}", response_model=WebAppBootstrapRead)
async def webapp_bootstrap_by_platform(
    platform: Literal["telegram", "vk"],
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> WebAppBootstrapRead:
    return await _build_bootstrap_response(
        session=session,
        platform=platform,
        user_id=user_id,
    )
