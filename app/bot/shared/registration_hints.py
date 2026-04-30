from difflib import SequenceMatcher

from app.db.models.user import User
from app.bot.shared.texts import Text


def build_similar_users_hint(*, row_id: int, name: str, users: list[User]) -> str:
  normalized_name = _normalize_name(name)
  if not normalized_name:
    return ""

  similar_users: list[User] = []
  for user in users:
    if user.row_id == row_id:
      continue
    if _is_similar_name(normalized_name, _normalize_name(user.name)):
      similar_users.append(user)

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
