from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository

USER_PHOTOS_DIR = settings.resolved_user_photos_dir
USER_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


def _build_static_url(path: str) -> str:
    base = settings.effective_api_base_url
    if base:
        return f"{base}/api/static/{path}"
    return f"/api/static/{path}"


def _build_photo_url(user: User) -> str | None:
    if not user.photo_path:
        return None
    version = int(user.updated_at.timestamp()) if user.updated_at is not None else 0
    return f"{_build_static_url(user.photo_path)}?v={version}"


async def _get_user_by_platform(
    *, session: AsyncSession, platform: Literal["telegram", "vk"], user_id: int
) -> User | None:
    repository = UserRepository(session)
    if platform == "telegram":
        return await repository.get_by_telegram_id(telegram_id=user_id)
    return await repository.get_by_vk_id(vk_id=user_id)
