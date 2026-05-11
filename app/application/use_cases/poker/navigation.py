class NavigationUseCases:
  """
  Stage-1 migration shell from legacy NavigationService.
  """

  def resolve_menu_target(self, *, current_menu: str, action: str) -> str:
    raise NotImplementedError
