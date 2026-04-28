from app.application.exceptions import (
  UserNameCorrectionRequiredError,
  UserNotFoundError,
)
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository


class ApproveUserUseCase:
  def __init__(self, user_repository: UserRepository) -> None:
    self.user_repository = user_repository

  async def execute(self, *, row_id: int) -> User:
    user = await self.user_repository.get_by_row_id(row_id)
    if user is None:
      raise UserNotFoundError(row_id)
    if user.name_needs_correction:
      raise UserNameCorrectionRequiredError(row_id)

    return await self.user_repository.approve(user)
