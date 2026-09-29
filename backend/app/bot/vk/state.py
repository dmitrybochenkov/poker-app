from dataclasses import dataclass
from functools import wraps

from app.db.repositories.user_repository import UserRepository
from app.db.repositories.vk_conversation_state_repository import (
  VkConversationStateRepository,
)
from app.db.session import SessionFactory

vk_user_states: dict[int, str] = {}
vk_user_contexts: dict[int, dict] = {}

WAITING_FOR_PLAYED_BEFORE = "waiting_for_played_before"
WAITING_FOR_NEW_NAME = "waiting_for_new_name"
WAITING_FOR_ADMIN_CORRECTED_NAME = "waiting_for_admin_corrected_name"
WAITING_FOR_OPTIONAL_DETAILS_ACTION = "waiting_for_optional_details_action"
WAITING_FOR_OPTIONAL_BANK = "waiting_for_optional_bank"
WAITING_FOR_OPTIONAL_PHONE = "waiting_for_optional_phone"
WAITING_FOR_ADMIN_CASHOUT_AMOUNT = "waiting_for_admin_cashout_amount"
WAITING_FOR_ADMIN_CASHOUT_TARGET = "waiting_for_admin_cashout_target"
WAITING_FOR_ADMIN_NEW_PLAYER_NAME = "waiting_for_admin_new_player_name"
WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT = "waiting_for_admin_buyin_correct_amount"
WAITING_FOR_BET_AMOUNT = "waiting_for_bet_amount"
WAITING_FOR_BET_PAYMENT_RECEIPT = "waiting_for_bet_payment_receipt"
WAITING_FOR_POLL_CUSTOM_DAY = "waiting_for_poll_custom_day"


@dataclass(frozen=True)
class DurableVkState:
  state_type: str
  payload: dict
  user_row_id: int | None


async def load_durable_vk_state(vk_user_id: int) -> DurableVkState | None:
  async with SessionFactory() as session:
    row = await VkConversationStateRepository(session).get(vk_user_id=vk_user_id)
    if row is None:
      return None
    return DurableVkState(row.state_type, dict(row.payload), row.user_row_id)


async def replace_durable_vk_state(
  vk_user_id: int, *, state_type: str, payload: dict
) -> None:
  async with SessionFactory() as session, session.begin():
    user = await UserRepository(session).get_by_vk_id(vk_user_id)
    await VkConversationStateRepository(session).replace_without_commit(
      vk_user_id=vk_user_id,
      user_row_id=int(user.row_id) if user is not None else None,
      state_type=state_type,
      payload=payload,
    )


async def clear_durable_vk_state(vk_user_id: int) -> None:
  async with SessionFactory() as session, session.begin():
    await VkConversationStateRepository(session).clear_without_commit(
      vk_user_id=vk_user_id
    )


LEGACY_DURABLE_STATE_TYPES = {
  WAITING_FOR_PLAYED_BEFORE,
  WAITING_FOR_NEW_NAME,
  WAITING_FOR_ADMIN_CORRECTED_NAME,
  WAITING_FOR_OPTIONAL_DETAILS_ACTION,
  WAITING_FOR_OPTIONAL_BANK,
  WAITING_FOR_OPTIONAL_PHONE,
  WAITING_FOR_ADMIN_NEW_PLAYER_NAME,
  WAITING_FOR_BET_AMOUNT,
  WAITING_FOR_BET_PAYMENT_RECEIPT,
  WAITING_FOR_POLL_CUSTOM_DAY,
}


async def hydrate_legacy_vk_state(vk_user_id: int) -> None:
  row = await load_durable_vk_state(vk_user_id)
  if row is None or row.state_type not in LEGACY_DURABLE_STATE_TYPES:
    return
  vk_user_states[vk_user_id] = row.state_type
  vk_user_contexts[vk_user_id] = dict(row.payload)


async def persist_legacy_vk_state(vk_user_id: int) -> None:
  state_type = vk_user_states.get(vk_user_id)
  if state_type in LEGACY_DURABLE_STATE_TYPES:
    await replace_durable_vk_state(
      vk_user_id,
      state_type=state_type,
      payload=dict(vk_user_contexts.get(vk_user_id, {})),
    )
    return
  existing = await load_durable_vk_state(vk_user_id)
  if existing is not None and existing.state_type in LEGACY_DURABLE_STATE_TYPES:
    await clear_durable_vk_state(vk_user_id)


def durable_vk_workflow(handler):
  @wraps(handler)
  async def wrapped(*args, **kwargs):
    user_id = kwargs.get("user_id")
    if user_id is None:
      event_object = kwargs.get("event_object")
      if event_object is None and args:
        event_object = args[0]
      if isinstance(event_object, dict):
        user_id = event_object.get("user_id")
    if not isinstance(user_id, int):
      return await handler(*args, **kwargs)
    await hydrate_legacy_vk_state(user_id)
    try:
      return await handler(*args, **kwargs)
    finally:
      await persist_legacy_vk_state(user_id)

  return wrapped
