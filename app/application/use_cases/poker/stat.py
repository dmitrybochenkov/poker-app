class StatUseCases:
  """
  Stage-1 migration shell from legacy StatService.
  """

  async def get_poker_stat(self, *, filters: dict):
    raise NotImplementedError

  async def get_betting_stat(self, *, filters: dict):
    raise NotImplementedError
