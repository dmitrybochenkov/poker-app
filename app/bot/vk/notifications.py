from app.bot.shared.texts.texts import Text
from app.bot.vk.api import send_vk_message
from app.db.models.user import User


async def notify_admins_about_registration(
  *,
  name: str,
  vk_id: int | None,
  telegram_id: int | None = None,
  requester_platform: str,
  admin_ids: list[int],
  linked_to_user: User | None = None,
  keyboard: str | None = None,
) -> None:
  if not admin_ids:
    return

  kind_line = (
    Text.admin.NEW_REGISTRATION_KIND_LINK.value
    if linked_to_user is not None
    else Text.admin.NEW_REGISTRATION_KIND_NEW.value
  )
  text = (
    f"{Text.admin.NEW_REGISTRATION.value}\n\n"
    f"{kind_line}\n"
    f"Имя: {name}\n"
    f"Платформа: {requester_platform.upper()}\n"
  )
  if vk_id is not None:
    text = f"{text}{Text.admin.PROFILE_LINK_LABEL.value}: https://vk.com/id{vk_id}\n"
  elif telegram_id is not None:
    text = f"{text}{Text.admin.PROFILE_LINK_LABEL.value}: tg://user?id={telegram_id}\n"
  if linked_to_user is not None:
    text = f"{text}Существующая запись: {linked_to_user.name}\n"
  for admin_id in admin_ids:
    await send_vk_message(
      user_id=admin_id,
      message=text,
      keyboard=keyboard,
    )
