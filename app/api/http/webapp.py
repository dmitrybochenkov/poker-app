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
  matched_rows = (
    select(
      User.row_id.label("player_id"),
      User.name.label("player_name"),
      PokerData.row_id.label("poker_row_id"),
      PokerData.money_kopecks.label("money_kopecks"),
    )
    .join(
      PokerData,
      or_(
        User.row_id == PokerData.player_id,
        User.name == PokerData.player_name,
      ),
    )
    .where(User.is_approved.is_(True))
    .distinct()
    .subquery()
  )

  query = (
    select(
      matched_rows.c.player_id,
      matched_rows.c.player_name,
      func.count(matched_rows.c.poker_row_id).label("games_count"),
      func.coalesce(func.sum(matched_rows.c.money_kopecks), 0).label("profit_kopecks"),
    )
    .group_by(matched_rows.c.player_id, matched_rows.c.player_name)
    .order_by(func.sum(matched_rows.c.money_kopecks).desc(), matched_rows.c.player_name.asc())
  )

  rows = (await session.execute(query)).all()
  return [
    WebAppPlayerCardRead(
      player_id=int(row.player_id),
      name=str(row.player_name),
      games=int(row.games_count or 0),
      profit_rub=int(int(row.profit_kopecks or 0) / 100),
    )
    for row in rows
  ]
