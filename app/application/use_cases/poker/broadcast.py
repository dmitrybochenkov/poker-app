class BroadcastUseCases:
  """
  Stage-1 migration shell from legacy BroadcastService.
  """

  async def notify_admins(self, *, text: str):
    raise NotImplementedError

  async def notify_users(self, *, user_ids: list[int], text: str):
    raise NotImplementedError
