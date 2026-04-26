from app.application.exceptions import UserAlreadyApprovedError, UserNotFoundError
from app.db.repositories.user_repository import UserRepository


class RejectUserUseCase:
  def __init__(self, user_repository: UserRepository) -> None:
    self.user_repository = user_repository

  async def execute(self, *, row_id: int) -> None:
    user = await self.user_repository.get_by_row_id(row_id)
    if user is None:
      raise UserNotFoundError(row_id)

    if user.is_approved:
      raise UserAlreadyApprovedError(row_id)

    await self.user_repository.delete(user)
