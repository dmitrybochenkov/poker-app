from app.bot.shared.registration_hints import build_similar_users_hint
from app.bot.shared.texts import Text
from app.bot.vk.api import send_vk_message
from app.db.models.user import User


def format_link_candidates(users: list[User]) -> str:
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
  vk_id: int,
  admin_ids: list[int],
  all_users: list[User],
  approved_users: list[User],
) -> None:
  if not admin_ids:
    return

  similar_users_hint = build_similar_users_hint(
    row_id=row_id,
    name=name,
    users=all_users,
  )
  text = (
    f"{Text.admin.NEW_REGISTRATION.value}\n\n"
    f"Row ID: {row_id}\n"
    f"Имя: {name}\n"
    f"VK ID: {vk_id}\n"
    f"{Text.admin.PROFILE_LINK_LABEL.value}: https://vk.com/id{vk_id}\n\n"
    f"{Text.admin.APPROVE_COMMAND_USAGE.value}\n"
    f"Пример: approve {row_id}\n"
    f"{Text.admin.CORRECT_COMMAND_USAGE.value}\n"
    f"Пример: correct {row_id} Иван Петров\n"
    f"{Text.admin.REJECT_COMMAND_USAGE.value}\n"
    f"Пример: reject {row_id}\n"
    f"{Text.admin.LINK_COMMAND_USAGE.value}\n"
    f"Пример: link {row_id} 3"
  )
  text = f"{text}\n\n{format_link_candidates(approved_users)}"
  if similar_users_hint:
    text = f"{text}\n\n{similar_users_hint}"
  for admin_id in admin_ids:
    await send_vk_message(user_id=admin_id, message=text)
