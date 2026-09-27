from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.http.webapp_schemas import WebAppBootstrapRead
from app.api.security.webapp_auth import WebAppIdentity, get_webapp_identity
from app.db.dependencies import get_db_session
from app.db.models.poker import Poker
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.user_repository import UserRepository

router = APIRouter()


async def _build_bootstrap_response(
    *,
    session: AsyncSession,
    identity: WebAppIdentity,
) -> WebAppBootstrapRead:
    user = (
        await UserRepository(session).get_by_row_id(identity.user_row_id)
        if identity.user_row_id is not None
        else None
    )
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


@router.get("/me/bootstrap", response_model=WebAppBootstrapRead)
async def webapp_bootstrap_by_platform(
    session: AsyncSession = Depends(get_db_session),
    identity: WebAppIdentity = Depends(get_webapp_identity),
) -> WebAppBootstrapRead:
    return await _build_bootstrap_response(session=session, identity=identity)
