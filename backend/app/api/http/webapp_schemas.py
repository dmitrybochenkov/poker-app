from pydantic import BaseModel


class WebAppBootstrapRead(BaseModel):
    user_row_id: int | None = None
    is_registered: bool
    is_admin: bool
    is_approved: bool
    has_phone: bool
    has_active_poll: bool
    has_active_poker: bool


class WebAppPlayerCardRead(BaseModel):
    player_id: int
    name: str
    tel_number: str | None = None
    bank_name: str | None = None
    games: int
    wins: int
    losses: int
    profit_rub: int
    photo_url: str | None = None


class WebAppPhotoUploadRead(BaseModel):
    photo_url: str


class WebAppPhoneUpdateWrite(BaseModel):
    tel_number: str


class WebAppPhoneUpdateRead(BaseModel):
    tel_number: str


class WebAppBankUpdateWrite(BaseModel):
    bank_name: str


class WebAppBankUpdateRead(BaseModel):
    bank_name: str


class WebAppInfoContentRead(BaseModel):
    title: str
    body_html: str
