from app.application.exceptions import (
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserNameRequiredError,
  UserRegistrationPendingError,
)
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository


class RequestRegistrationUseCase:
  def __init__(self, user_repository: UserRepository) -> None:
    self.user_repository = user_repository

  async def execute(
    self,
    *,
    name: str,
    telegram_id: int | None = None,
    vk_id: int | None = None,
    tel_number: str | None = None,
    bank_name: str | None = None,
  ) -> User:
    if telegram_id is None and vk_id is None:
      raise UserIdentityRequiredError
    normalized_name = " ".join(name.split())
    if not normalized_name:
      raise UserNameRequiredError

    existing_user = await self._find_existing_user(
      telegram_id=telegram_id,
      vk_id=vk_id,
    )
    if existing_user is not None:
      if existing_user.is_approved:
        raise UserAlreadyRegisteredError(existing_user.row_id)
      raise UserRegistrationPendingError(existing_user.row_id)

    return await self.user_repository.create(
      name=normalized_name,
      telegram_id=telegram_id,
      vk_id=vk_id,
      tel_number=tel_number,
      bank_name=bank_name,
    )

  async def _find_existing_user(
    self,
    *,
    telegram_id: int | None,
    vk_id: int | None,
  ) -> User | None:
    if telegram_id is not None:
      user = await self.user_repository.get_by_telegram_id(telegram_id)
      if user is not None:
        return user

    if vk_id is not None:
      return await self.user_repository.get_by_vk_id(vk_id)

    return None
