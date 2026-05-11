from app.application.exceptions import (
  UserAlreadyApprovedError,
  UserNameRequiredError,
  UserNotFoundError,
)
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository


class CorrectUserUseCase:
  def __init__(self, user_repository: UserRepository) -> None:
    self.user_repository = user_repository

  async def execute(self, *, row_id: int, corrected_name: str) -> User:
    normalized_name = " ".join(corrected_name.split())
    if not normalized_name:
      raise UserNameRequiredError

    user = await self.user_repository.get_by_row_id(row_id)
    if user is None:
      raise UserNotFoundError(row_id)
    if user.is_approved:
      raise UserAlreadyApprovedError(row_id)

    return await self.user_repository.correct_name_and_approve(
      user,
      corrected_name=normalized_name,
    )
