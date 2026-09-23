from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user_repository import UserRepository


async def resolve_telegram_user_id(
    *,
    session: AsyncSession,
    telegram_id: int,
) -> int | None:
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    return int(user.row_id) if user is not None else None


async def resolve_vk_user_id(
    *,
    session: AsyncSession,
    vk_id: int,
) -> int | None:
    user = await UserRepository(session).get_by_vk_id(vk_id)
    return int(user.row_id) if user is not None else None
