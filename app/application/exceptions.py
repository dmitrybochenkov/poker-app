class ApplicationError(Exception):
  """Base application-layer error."""


class UserIdentityRequiredError(ApplicationError):
  """Raised when a user has neither Telegram nor VK identifier."""


class UserAlreadyExistsError(ApplicationError):
  def __init__(self, field: str) -> None:
    self.field = field
    super().__init__(f"User with this {field} already exists")


class UserNotFoundError(ApplicationError):
  def __init__(self, row_id: int) -> None:
    self.row_id = row_id
    super().__init__(f"User with row_id={row_id} not found")


class UserAlreadyApprovedError(ApplicationError):
  def __init__(self, row_id: int) -> None:
    self.row_id = row_id
    super().__init__(f"User with row_id={row_id} is already approved")


class UserAlreadyRegisteredError(ApplicationError):
  def __init__(self, row_id: int) -> None:
    self.row_id = row_id
    super().__init__(f"User with row_id={row_id} is already registered")


class UserRegistrationPendingError(ApplicationError):
  def __init__(self, row_id: int) -> None:
    self.row_id = row_id
    super().__init__(f"User with row_id={row_id} is waiting for approval")
