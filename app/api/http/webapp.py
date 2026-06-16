from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image, ImageOps

from app.db.models.poker import Poker
from app.db.dependencies import get_db_session
from app.db.models.poker_data import PokerData
from app.db.models.user import User
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.user_repository import UserRepository

router = APIRouter(prefix="/api/webapp", tags=["webapp"])

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
USER_PHOTOS_DIR = STATIC_DIR / "user_photos"
USER_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


def _build_photo_url(user: User) -> str | None:
  if not user.photo_path:
    return None
  version = int(user.updated_at.timestamp()) if user.updated_at is not None else 0
  return f"/static/{user.photo_path}?v={version}"


class WebAppBootstrapRead(BaseModel):
  user_row_id: int | None = None
  is_registered: bool
  is_admin: bool
  is_approved: bool
  has_phone: bool
  has_active_poll: bool


class WebAppPlayerCardRead(BaseModel):
  player_id: int
  name: str
  tel_number: str | None = None
  games: int
  wins: int
  losses: int
  profit_rub: int
  photo_url: str | None = None


class WebAppPhotoUploadRead(BaseModel):
  photo_url: str


class WebAppPhoneUpdateWrite(BaseModel):
  tel_number: str


class WebAppPhoneUpdateRead(BaseModel):
  tel_number: str


def _normalize_phone(value: str) -> str | None:
  digits = "".join(ch for ch in value if ch.isdigit())
  if digits.startswith("7") and len(digits) == 11:
    return f"+{digits}"
  return None


@router.get("/bootstrap/{telegram_id}", response_model=WebAppBootstrapRead)
async def webapp_bootstrap(
  telegram_id: int,
  session: AsyncSession = Depends(get_db_session),
) -> WebAppBootstrapRead:
  user = await UserRepository(session).get_by_telegram_id(telegram_id=telegram_id)
  has_active_poll = await PollConfigRepository(session).get_active_month() is not None
  if user is None:
    return WebAppBootstrapRead(
      user_row_id=None,
      is_registered=False,
      is_admin=False,
      is_approved=False,
      has_phone=False,
      has_active_poll=has_active_poll,
    )
  has_phone = bool(user.tel_number and str(user.tel_number).strip())
  return WebAppBootstrapRead(
    user_row_id=user.row_id,
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
      select(User.row_id, User.name, User.photo_path, User.updated_at, User.tel_number)
      .where(User.is_approved.is_(True))
      .order_by(User.name.asc())
    )
  ).all()

  completed_pokers = (
    await session.execute(
      select(Poker.winners, Poker.loosers).where(
        or_(
          Poker.winners.is_not(None),
          Poker.loosers.is_not(None),
        )
      )
    )
  ).all()

  wins_by_name: dict[str, int] = {}
  losses_by_name: dict[str, int] = {}
  for winners_csv, losers_csv in completed_pokers:
    winners = {item.strip() for item in str(winners_csv or "").split(",") if item.strip()}
    losers = {item.strip() for item in str(losers_csv or "").split(",") if item.strip()}
    for name in winners:
      wins_by_name[name] = wins_by_name.get(name, 0) + 1
    for name in losers:
      losses_by_name[name] = losses_by_name.get(name, 0) + 1

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
        tel_number=(str(user.tel_number).strip() if user.tel_number else None),
        games=int(stats.games_count or 0),
        wins=wins_by_name.get(str(user.name), 0),
        losses=losses_by_name.get(str(user.name), 0),
        profit_rub=int(int(stats.profit_kopecks or 0) / 100),
        photo_url=(
          f"/static/{user.photo_path}?v={int(user.updated_at.timestamp()) if user.updated_at is not None else 0}"
          if user.photo_path
          else None
        ),
      )
    )

  return sorted(result, key=lambda item: (-item.profit_rub, item.name))


@router.post("/users/{telegram_id}/photo", response_model=WebAppPhotoUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_webapp_user_photo(
  telegram_id: int,
  file: UploadFile = File(...),
  session: AsyncSession = Depends(get_db_session),
) -> WebAppPhotoUploadRead:
  user = await UserRepository(session).get_by_telegram_id(telegram_id=telegram_id)
  if user is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

  if not file.content_type or not file.content_type.startswith("image/"):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image files are supported")

  image_bytes = await file.read()
  if not image_bytes:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
  if len(image_bytes) > 8 * 1024 * 1024:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image is too large")

  try:
    image = Image.open(BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((1200, 1200))
  except Exception as error:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file") from error

  output_name = f"{user.row_id}.webp"
  output_rel_path = f"user_photos/{output_name}"
  output_path = USER_PHOTOS_DIR / output_name
  image.save(output_path, format="WEBP", quality=88, method=6)

  user.photo_path = output_rel_path
  await session.commit()
  await session.refresh(user)

  photo_url = _build_photo_url(user)
  if photo_url is None:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Photo url was not generated")
  return WebAppPhotoUploadRead(photo_url=photo_url)


@router.post("/users/{telegram_id}/phone", response_model=WebAppPhoneUpdateRead)
async def update_webapp_user_phone(
  telegram_id: int,
  payload: WebAppPhoneUpdateWrite,
  session: AsyncSession = Depends(get_db_session),
) -> WebAppPhoneUpdateRead:
  user = await UserRepository(session).get_by_telegram_id(telegram_id=telegram_id)
  if user is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

  normalized_phone = _normalize_phone(payload.tel_number)
  if normalized_phone is None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number")

  user.tel_number = normalized_phone
  await session.commit()
  await session.refresh(user)
  return WebAppPhoneUpdateRead(tel_number=normalized_phone)
