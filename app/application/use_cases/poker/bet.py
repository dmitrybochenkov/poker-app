class BetUseCases:
  """
  Stage-1 migration shell from legacy BetService.
  """

  async def get_initial_betting_data(self, *, player_id: int):
    raise NotImplementedError

  async def get_players_and_history(self):
    raise NotImplementedError

  async def create_bet(self, *, player_id: int, state_data: dict):
    raise NotImplementedError
