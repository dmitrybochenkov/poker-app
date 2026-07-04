class PokerTableUseCases:
  """
  Stage-1 migration shell from legacy PokerService.
  """

  async def get_poker_start_data(self):
    raise NotImplementedError

  async def get_lobby_status(self, *, user_id: int, current_state: str):
    raise NotImplementedError

  async def process_player_approval(self, *, player_id: int, mode: str, player_name: str):
    raise NotImplementedError

  async def get_buyin_menu_data(self, *, player_id: int):
    raise NotImplementedError

  async def process_buyin(self, *, player_id: int, buyins_count: int):
    raise NotImplementedError
