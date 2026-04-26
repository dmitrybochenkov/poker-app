from app.application.exceptions import UserAlreadyExistsError, UserIdentityRequiredError
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository


class RegisterUserUseCase:
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

    if telegram_id is not None:
      existing_tg_user = await self.user_repository.get_by_telegram_id(telegram_id)
      if existing_tg_user is not None:
        raise UserAlreadyExistsError("telegram_id")

    if vk_id is not None:
      existing_vk_user = await self.user_repository.get_by_vk_id(vk_id)
      if existing_vk_user is not None:
        raise UserAlreadyExistsError("vk_id")

    return await self.user_repository.create(
      name=name,
      telegram_id=telegram_id,
      vk_id=vk_id,
      tel_number=tel_number,
      bank_name=bank_name,
    )
