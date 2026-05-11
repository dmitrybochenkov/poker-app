class PlayerUseCases:
  """
  Stage-1 migration shell from legacy PlayerService.
  Keep method names close to old service to migrate handlers incrementally.
  """

  async def check_registration_status(self, *, tg_id: int | None = None, vk_id: int | None = None):
    raise NotImplementedError

  async def get_exist_tg_and_new_vk_users(self):
    raise NotImplementedError

  def format_admin_reg_message(self, *, profile: object, entered_name: str, platform: str = "TG") -> str:
    raise NotImplementedError
