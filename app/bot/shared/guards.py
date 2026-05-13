from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user_repository import UserRepository


async def is_tg_admin(*, session: AsyncSession, telegram_id: int) -> bool:
  admin_ids = await UserRepository(session).list_telegram_admin_ids()
  return int(telegram_id) in set(int(item) for item in admin_ids)


async def is_vk_admin(*, session: AsyncSession, vk_id: int) -> bool:
  admin_ids = await UserRepository(session).list_vk_admin_ids()
  return int(vk_id) in set(int(item) for item in admin_ids)
