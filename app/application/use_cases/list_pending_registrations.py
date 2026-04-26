from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository


class ListPendingRegistrationsUseCase:
  def __init__(self, user_repository: UserRepository) -> None:
    self.user_repository = user_repository

  async def execute(self) -> list[User]:
    return await self.user_repository.list_pending()
