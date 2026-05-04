from difflib import SequenceMatcher

from app.bot.shared.texts import Text
from app.db.models.user import User


def find_similar_users(*, name: str, users: list[User], excluded_row_id: int | None = None) -> list[User]:
  normalized_name = _normalize_name(name)
  if not normalized_name:
    return []

  similar_users: list[User] = []
  for user in users:
    if excluded_row_id is not None and user.row_id == excluded_row_id:
      continue
    if _is_similar_name(normalized_name, _normalize_name(user.name)):
      similar_users.append(user)
  return similar_users


def build_similar_users_hint(*, row_id: int, name: str, users: list[User]) -> str:
  similar_users = find_similar_users(
    name=name,
    users=users,
    excluded_row_id=row_id,
  )
  if not similar_users:
    return ""

  lines = [Text.admin.SIMILAR_USERS_TITLE.value]
  for user in similar_users[:5]:
    lines.append(f"{user.row_id} — {user.name}")
  if len(similar_users) > 5:
    lines.append("...")
  return "\n".join(lines)


def _normalize_name(name: str) -> str:
  return " ".join(name.lower().split())


def _is_similar_name(left: str, right: str) -> bool:
  if not left or not right:
    return False
  if left == right:
    return True
  if left in right or right in left:
    return True

  left_parts = left.split()
  right_parts = right.split()
  if left_parts and right_parts and left_parts[0] == right_parts[0]:
    return True

  return SequenceMatcher(None, left, right).ratio() >= 0.72
