class InfoUseCases:
  """
  Stage-1 migration shell from legacy InfoService.
  """

  def get_betting_rules(self) -> str:
    raise NotImplementedError

  def get_poker_info(self) -> str:
    raise NotImplementedError
