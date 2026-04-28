from app.bot.shared.texts import Text
from app.bot.vk.api import send_vk_message


def format_link_candidates(users: list) -> str:
  if not users:
    return Text.admin.LINK_CHOICES_EMPTY.value

  lines = [Text.admin.LINK_CHOICES_TITLE.value]
  for user in users[:20]:
    lines.append(f"{user.row_id} — {user.name}")

  if len(users) > 20:
    lines.append("...")

  return "\n".join(lines)


async def notify_admins_about_registration(
  *,
  row_id: int,
  name: str,
  name_needs_correction: bool,
  vk_id: int,
  admin_ids: list[int],
  approved_users: list | None = None,
) -> None:
  if not admin_ids:
    return

  correction_note = (
    f"\n{Text.admin.NAME_REQUIRES_CORRECTION.value}"
    if name_needs_correction
    else ""
  )
  text = (
    f"{Text.admin.NEW_REGISTRATION.value}\n\n"
    f"Row ID: {row_id}\n"
    f"Имя: {name}\n"
    f"VK ID: {vk_id}"
    f"{correction_note}\n\n"
    f"{Text.admin.APPROVE_COMMAND_USAGE.value}\n"
    f"Пример: approve {row_id}\n"
    f"{Text.admin.CORRECT_COMMAND_USAGE.value}\n"
    f"Пример: correct {row_id} Иван Петров\n"
    f"{Text.admin.REJECT_COMMAND_USAGE.value}\n"
    f"Пример: reject {row_id}\n"
    f"{Text.admin.LINK_COMMAND_USAGE.value}\n"
    f"Пример: link {row_id} 3"
  )
  if approved_users is not None:
    text = f"{text}\n\n{format_link_candidates(approved_users)}"
  for admin_id in admin_ids:
    await send_vk_message(user_id=admin_id, message=text)
