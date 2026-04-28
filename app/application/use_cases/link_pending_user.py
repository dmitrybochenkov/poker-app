from app.application.exceptions import UserLinkConflictError, UserNotFoundError
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository


class LinkPendingUserUseCase:
  def __init__(self, user_repository: UserRepository) -> None:
    self.user_repository = user_repository

  async def execute(self, *, pending_row_id: int, existing_row_id: int) -> User:
    pending_user = await self.user_repository.get_by_row_id(pending_row_id)
    if pending_user is None:
      raise UserNotFoundError(pending_row_id)

    existing_user = await self.user_repository.get_by_row_id(existing_row_id)
    if existing_user is None:
      raise UserNotFoundError(existing_row_id)

    if pending_user.telegram_id is not None and existing_user.telegram_id is not None:
      raise UserLinkConflictError("telegram_id")

    if pending_user.vk_id is not None and existing_user.vk_id is not None:
      raise UserLinkConflictError("vk_id")

    return await self.user_repository.link_pending_user(existing_user, pending_user)
