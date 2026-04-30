from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def create(
    self,
    *,
    name: str,
    telegram_id: int | None = None,
    vk_id: int | None = None,
    tel_number: str | None = None,
    bank_name: str | None = None,
    is_admin: bool = False,
    is_approved: bool = False,
  ) -> User:
    user = User(
      name=name,
      telegram_id=telegram_id,
      vk_id=vk_id,
      tel_number=tel_number,
      bank_name=bank_name,
      is_admin=is_admin,
      is_approved=is_approved,
    )
    self.session.add(user)
    await self.session.commit()
    await self.session.refresh(user)
    return user

  async def get_by_telegram_id(self, telegram_id: int) -> User | None:
    result = await self.session.execute(
      select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()

  async def get_by_vk_id(self, vk_id: int) -> User | None:
    result = await self.session.execute(
      select(User).where(User.vk_id == vk_id)
    )
    return result.scalar_one_or_none()

  async def get_by_row_id(self, row_id: int) -> User | None:
    result = await self.session.execute(
      select(User).where(User.row_id == row_id)
    )
    return result.scalar_one_or_none()

  async def list_telegram_admin_ids(self) -> list[int]:
    result = await self.session.execute(
      select(User.telegram_id)
      .where(User.is_admin.is_(True))
      .where(User.telegram_id.is_not(None))
      .order_by(User.row_id)
    )
    return list(result.scalars().all())

  async def list_vk_admin_ids(self) -> list[int]:
    result = await self.session.execute(
      select(User.vk_id)
      .where(User.is_admin.is_(True))
      .where(User.vk_id.is_not(None))
      .order_by(User.row_id)
    )
    return list(result.scalars().all())

  async def make_admin(self, user: User) -> User:
    user.is_admin = True
    await self.session.commit()
    await self.session.refresh(user)
    return user

  async def link_pending_user(self, existing_user: User, pending_user: User) -> User:
    pending_telegram_id = pending_user.telegram_id
    pending_vk_id = pending_user.vk_id

    await self.session.delete(pending_user)
    await self.session.flush()

    if pending_telegram_id is not None:
      existing_user.telegram_id = pending_telegram_id
    if pending_vk_id is not None:
      existing_user.vk_id = pending_vk_id

    await self.session.commit()
    await self.session.refresh(existing_user)
    return existing_user

  async def approve(self, user: User) -> User:
    user.is_approved = True
    await self.session.commit()
    await self.session.refresh(user)
    return user

  async def correct_name_and_approve(self, user: User, *, corrected_name: str) -> User:
    user.name = corrected_name
    user.is_approved = True
    await self.session.commit()
    await self.session.refresh(user)
    return user

  async def list_approved(self) -> list[User]:
    result = await self.session.execute(
      select(User)
      .where(User.is_approved.is_(True))
      .order_by(User.row_id)
    )
    return list(result.scalars().all())

  async def delete(self, user: User) -> None:
    await self.session.delete(user)
    await self.session.commit()

  async def list_pending(self) -> list[User]:
    result = await self.session.execute(
      select(User)
      .where(User.is_approved.is_(False))
      .order_by(User.row_id)
    )
    return list(result.scalars().all())

  async def list_all(self) -> list[User]:
    result = await self.session.execute(select(User).order_by(User.row_id))
    return list(result.scalars().all())
