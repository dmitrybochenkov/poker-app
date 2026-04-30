from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
  name: str
  telegram_id: int | None = None
  vk_id: int | None = None
  tel_number: str | None = None
  bank_name: str | None = None


class UserRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  row_id: int
  name: str
  telegram_id: int | None
  vk_id: int | None
  tel_number: str | None
  bank_name: str | None
  is_admin: bool
  is_approved: bool


class UserCorrectionRequest(BaseModel):
  name: str
