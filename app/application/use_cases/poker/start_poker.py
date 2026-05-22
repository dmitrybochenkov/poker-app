from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.poker_repository import PokerRepository


class StartPokerUseCase:
  def __init__(
    self,
    poker_repository: PokerRepository,
    poker_param_repository: PokerParamRepository,
    poker_room_denied_repository: PokerRoomDeniedRepository | None = None,
  ) -> None:
    self.poker_repository = poker_repository
    self.poker_param_repository = poker_param_repository
    self.poker_room_denied_repository = poker_room_denied_repository

  async def get_start_data(self) -> tuple[bool, list]:
    started = await self.poker_repository.get_started()
    if started is not None:
      return False, []
    params = await self.poker_param_repository.list_all()
    return True, params

  async def execute(self, *, params_id: int):
    started = await self.poker_repository.get_started()
    if started is not None:
      return None
    param = await self.poker_param_repository.get_by_row_id(params_id)
    if param is None:
      return None
    return await self.poker_repository.create(params_id=params_id)
