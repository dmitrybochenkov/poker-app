from app.bot.shared.texts import Text
from app.bot.vk.api import send_vk_message


async def notify_admins_about_registration(
  *,
  row_id: int,
  name: str,
  vk_id: int,
  admin_ids: list[int],
) -> None:
  if not admin_ids:
    return

  text = (
    f"{Text.admin.NEW_REGISTRATION.value}\n\n"
    f"Row ID: {row_id}\n"
    f"Имя: {name}\n"
    f"VK ID: {vk_id}"
  )
  for admin_id in admin_ids:
    await send_vk_message(user_id=admin_id, message=text)
