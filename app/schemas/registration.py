from pydantic import BaseModel, ConfigDict


class RegistrationRequest(BaseModel):
  name: str
  telegram_id: int | None = None
  vk_id: int | None = None
  tel_number: str | None = None
  bank_name: str | None = None


class RegistrationRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  row_id: int
  name: str
  name_needs_correction: bool
  telegram_id: int | None
  vk_id: int | None
  is_approved: bool
  status: str = "waiting_admin_approval"
