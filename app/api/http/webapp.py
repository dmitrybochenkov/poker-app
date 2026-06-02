from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db_session
from app.db.models.poker_data import PokerData
from app.db.models.user import User
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.user_repository import UserRepository

router = APIRouter(prefix="/api/webapp", tags=["webapp"])


class WebAppBootstrapRead(BaseModel):
  is_registered: bool
  is_admin: bool
  is_approved: bool
  has_phone: bool
  has_active_poll: bool


class WebAppPlayerCardRead(BaseModel):
  player_id: int
  name: str
  games: int
  profit_rub: int


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


@router.get("/players", response_model=list[WebAppPlayerCardRead])
async def webapp_players(
  session: AsyncSession = Depends(get_db_session),
) -> list[WebAppPlayerCardRead]:
  approved_users = (
    await session.execute(
      select(User.row_id, User.name)
      .where(User.is_approved.is_(True))
      .order_by(User.name.asc())
    )
  ).all()

  result: list[WebAppPlayerCardRead] = []
  for user in approved_users:
    stats = (
      await session.execute(
        select(
          func.count(PokerData.row_id).label("games_count"),
          func.coalesce(func.sum(PokerData.money_kopecks), 0).label("profit_kopecks"),
        ).where(
          or_(
            PokerData.player_id == user.row_id,
            PokerData.player_name == user.name,
          )
        )
      )
    ).one()

    result.append(
      WebAppPlayerCardRead(
        player_id=int(user.row_id),
        name=str(user.name),
        games=int(stats.games_count or 0),
        profit_rub=int(int(stats.profit_kopecks or 0) / 100),
      )
    )

  return sorted(result, key=lambda item: (-item.profit_rub, item.name))
