from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db_session
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.user_repository import UserRepository

router = APIRouter(prefix="/webapp", tags=["webapp"])


class WebAppBootstrapRead(BaseModel):
  is_registered: bool
  is_admin: bool
  is_approved: bool
  has_phone: bool
  has_active_poll: bool


@router.get("/bootstrap/{telegram_id}", response_model=WebAppBootstrapRead)
async def webapp_bootstrap(
  telegram_id: int,
  session: AsyncSession = Depends(get_db_session),
) -> WebAppBootstrapRead:
  user = await UserRepository(session).get_by_telegram_id(telegram_id=telegram_id)
  has_active_poll = await PollConfigRepository(session).get_active_month() is not None
  if user is None:
    return WebAppBootstrapRead(
      is_registered=False,
      is_admin=False,
      is_approved=False,
      has_phone=False,
      has_active_poll=has_active_poll,
    )
  has_phone = bool(user.tel_number and str(user.tel_number).strip())
  return WebAppBootstrapRead(
    is_registered=True,
    is_admin=bool(user.is_admin),
    is_approved=bool(user.is_approved),
    has_phone=has_phone,
    has_active_poll=has_active_poll,
  )
