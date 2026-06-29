from datetime import datetime
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image, ImageOps

from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.texts.texts import Text
from app.config.settings import settings
from app.db.models.poker import Poker
from app.db.dependencies import get_db_session
from app.db.models.poker_data import PokerData
from app.db.models.user import User
from app.db.repositories.achievement_repository import AchievementRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository
from app.db.repositories.user_repository import UserRepository

router = APIRouter(prefix="/api/webapp", tags=["webapp"])
USER_PHOTOS_DIR = settings.resolved_user_photos_dir
USER_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


def _build_static_url(path: str) -> str:
  base = settings.api_base_url.strip().rstrip("/")
  if base:
    return f"{base}/api/static/{path}"
  return f"/api/static/{path}"


def _build_photo_url(user: User) -> str | None:
  if not user.photo_path:
    return None
  version = int(user.updated_at.timestamp()) if user.updated_at is not None else 0
  return f"{_build_static_url(user.photo_path)}?v={version}"


class WebAppBootstrapRead(BaseModel):
  user_row_id: int | None = None
  is_registered: bool
  is_admin: bool
  is_approved: bool
  has_phone: bool
  has_active_poll: bool
  has_active_poker: bool


class WebAppPlayerCardRead(BaseModel):
  player_id: int
  name: str
  tel_number: str | None = None
  bank_name: str | None = None
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


class WebAppBankUpdateWrite(BaseModel):
  bank_name: str


class WebAppBankUpdateRead(BaseModel):
  bank_name: str


class WebAppInfoContentRead(BaseModel):
  title: str
  body_html: str


def _normalize_phone(value: str) -> str | None:
  digits = "".join(ch for ch in value if ch.isdigit())
  if digits.startswith("7") and len(digits) == 11:
    return f"+{digits}"
  return None


def _normalize_bank_name(value: str) -> str | None:
  normalized = " ".join(value.split()).strip()
  if not normalized:
    return None
  return normalized[:1].upper() + normalized[1:].lower()


def _format_stat_info_report(indicators) -> str:
  if not indicators:
    return "Справка пока пустая."
  lines: list[str] = []
  for item in indicators:
    pic = StatUseCases._prettify_header(str(item.pic or ""))
    lines.append(f"{pic} <b>{item.description}</b>")
    lines.append(f"{item.description_full}")
    lines.append("")
  return "\n".join(lines).strip()


def _format_achievement_description(raw: str) -> tuple[str, str | None]:
  if "_" not in raw:
    return raw, None
  title, detail = raw.split("_", 1)
  return title.strip(), detail.strip() if detail else None


def _format_achievement_info_report(achievements, indicators_by_id: dict[int, tuple[str, str]]) -> str:
  if not achievements:
    return "Справка пока пустая."
  lines: list[str] = []
  for item in achievements:
    title, detail = _format_achievement_description(item.description)
    ach_pic = StatUseCases._prettify_header(str(item.pic or ""))
    lines.append(f"{ach_pic} <b>{title}</b>")
    if detail:
      lines.append(detail)
    indicator_info = indicators_by_id.get(int(item.stat_id))
    if indicator_info:
      indicator_pic, indicator_name = indicator_info
      indicator_pic = StatUseCases._prettify_header(str(indicator_pic or ""))
      lines.append(f"Показатель: {indicator_pic} {indicator_name}".strip())
    lines.append("")
  return "\n".join(lines).strip()


async def _get_user_by_platform(*, session: AsyncSession, platform: Literal["telegram", "vk"], user_id: int) -> User | None:
  repository = UserRepository(session)
  if platform == "telegram":
    return await repository.get_by_telegram_id(telegram_id=user_id)
  return await repository.get_by_vk_id(vk_id=user_id)


async def _build_bootstrap_response(
  *,
  session: AsyncSession,
  platform: Literal["telegram", "vk"],
  user_id: int,
) -> WebAppBootstrapRead:
  user = await _get_user_by_platform(session=session, platform=platform, user_id=user_id)
  has_active_poll = await PollConfigRepository(session).get_active_month() is not None
  active_poker = (
    await session.execute(
      select(Poker.row_id)
      .where(Poker.is_going.is_(True))
      .limit(1)
    )
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


@router.get("/players", response_model=list[WebAppPlayerCardRead])
async def webapp_players(
  session: AsyncSession = Depends(get_db_session),
) -> list[WebAppPlayerCardRead]:
  approved_users = (
    await session.execute(
      select(User.row_id, User.name, User.photo_path, User.updated_at, User.tel_number, User.bank_name)
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
        bank_name=(str(user.bank_name).strip() if user.bank_name else None),
        games=int(stats.games_count or 0),
        wins=wins_by_name.get(str(user.name), 0),
        losses=losses_by_name.get(str(user.name), 0),
        profit_rub=int(int(stats.profit_kopecks or 0) / 100),
        photo_url=_build_photo_url(user),
      )
    )

  return sorted(
    result,
    key=lambda item: (-(1 if item.wins > 0 else 0), -item.profit_rub, item.name),
  )


@router.get("/info/{section}/{topic}", response_model=WebAppInfoContentRead)
async def webapp_info_content(
  section: Literal["poker", "bets"],
  topic: Literal["root", "rules", "achievements", "metrics"],
  session: AsyncSession = Depends(get_db_session),
) -> WebAppInfoContentRead:
  if topic == "root":
    if section == "poker":
      return WebAppInfoContentRead(title="ℹ️💍 Про покер", body_html=Text.user.POKER_INFO.value)
    return WebAppInfoContentRead(title="ℹ️🍀 Про ставки", body_html=Text.user.BETTING_MENU.value)

  if section == "bets" and topic == "rules":
    return WebAppInfoContentRead(title="📖 Правила", body_html=Text.user.BET_RULES.value)

  if topic == "metrics":
    indicator_type = "poker" if section == "poker" else "betting"
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type=indicator_type)
    return WebAppInfoContentRead(
      title="ℹ️📊 Показатели",
      body_html=_format_stat_info_report(indicators),
    )

  if topic == "achievements":
    achievement_type = "poker" if section == "poker" else "betting"
    achievements = await AchievementRepository(session).list_by_type(achievement_type=achievement_type)
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type=achievement_type)
    indicators_by_id = {
      int(item.row_id): (str(item.pic or ""), str(item.description or ""))
      for item in indicators
    }
    return WebAppInfoContentRead(
      title="ℹ️🌟 Ачивки",
      body_html=_format_achievement_info_report(achievements, indicators_by_id),
    )

  raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Info page not found")


@router.post("/users/{telegram_id}/photo", response_model=WebAppPhotoUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_webapp_user_photo(
  telegram_id: int,
  file: UploadFile = File(...),
  session: AsyncSession = Depends(get_db_session),
) -> WebAppPhotoUploadRead:
  user = await _get_user_by_platform(session=session, platform="telegram", user_id=telegram_id)
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
  user.updated_at = datetime.utcnow()
  await session.commit()
  await session.refresh(user)

  photo_url = _build_photo_url(user)
  if photo_url is None:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Photo url was not generated")
  return WebAppPhotoUploadRead(photo_url=photo_url)


@router.post("/users/{platform}/{user_id}/photo", response_model=WebAppPhotoUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_webapp_user_photo_by_platform(
  platform: Literal["telegram", "vk"],
  user_id: int,
  file: UploadFile = File(...),
  session: AsyncSession = Depends(get_db_session),
) -> WebAppPhotoUploadRead:
  user = await _get_user_by_platform(session=session, platform=platform, user_id=user_id)
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
  user.updated_at = datetime.utcnow()
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
  user = await _get_user_by_platform(session=session, platform="telegram", user_id=telegram_id)
  if user is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

  normalized_phone = _normalize_phone(payload.tel_number)
  if normalized_phone is None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number")

  user.tel_number = normalized_phone
  await session.commit()
  await session.refresh(user)
  return WebAppPhoneUpdateRead(tel_number=normalized_phone)


@router.post("/users/{platform}/{user_id}/phone", response_model=WebAppPhoneUpdateRead)
async def update_webapp_user_phone_by_platform(
  platform: Literal["telegram", "vk"],
  user_id: int,
  payload: WebAppPhoneUpdateWrite,
  session: AsyncSession = Depends(get_db_session),
) -> WebAppPhoneUpdateRead:
  user = await _get_user_by_platform(session=session, platform=platform, user_id=user_id)
  if user is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

  normalized_phone = _normalize_phone(payload.tel_number)
  if normalized_phone is None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number")

  user.tel_number = normalized_phone
  await session.commit()
  await session.refresh(user)
  return WebAppPhoneUpdateRead(tel_number=normalized_phone)


@router.post("/users/{platform}/{user_id}/bank", response_model=WebAppBankUpdateRead)
async def update_webapp_user_bank_by_platform(
  platform: Literal["telegram", "vk"],
  user_id: int,
  payload: WebAppBankUpdateWrite,
  session: AsyncSession = Depends(get_db_session),
) -> WebAppBankUpdateRead:
  user = await _get_user_by_platform(session=session, platform=platform, user_id=user_id)
  if user is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

  normalized_bank = _normalize_bank_name(payload.bank_name)
  if normalized_bank is None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bank name")

  user.bank_name = normalized_bank
  await session.commit()
  await session.refresh(user)
  return WebAppBankUpdateRead(bank_name=normalized_bank)
