from fastapi.responses import PlainTextResponse

from app.application.exceptions import (
  UserAlreadyApprovedError,
  UserLinkConflictError,
  UserNameRequiredError,
  UserNotFoundError,
)
from app.application.use_cases.approve_user import ApproveUserUseCase
from app.application.use_cases.correct_user import CorrectUserUseCase
from app.application.use_cases.link_pending_user import LinkPendingUserUseCase
from app.application.use_cases.make_admin import MakeAdminUseCase
from app.application.use_cases.poker.start_poker import StartPokerUseCase
from app.application.use_cases.reject_user import RejectUserUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.telegram.notifications import notify_user_about_approval
from app.bot.vk.api import clear_vk_inline_keyboard, send_vk_message, send_vk_message_event_answer
from app.bot.vk.keyboards import link_candidates_keyboard, main_keyboard, make_admin_candidates_keyboard, poker_params_keyboard
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.bot.vk.state import WAITING_FOR_ADMIN_CORRECTED_NAME, vk_user_contexts, vk_user_states
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory


async def _clear_event_inline_keyboard_if_possible(*, peer_id: int | None, conversation_message_id: int | None) -> None:
  if peer_id is None or conversation_message_id is None:
    return
  try:
    await clear_vk_inline_keyboard(
      peer_id=peer_id,
      conversation_message_id=conversation_message_id,
    )
  except Exception:
    return


async def _process_vk_approve(*, admin_user_id: int, row_id: int) -> str:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_vk_admin_ids()
    if admin_user_id not in admin_ids:
      return Text.admin.NO_RIGHTS.value

    use_case = ApproveUserUseCase(repository)
    try:
      approved_user = await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      return Text.admin.REQUEST_NOT_FOUND.value

  if approved_user.vk_id is not None:
    await send_vk_message(
      user_id=approved_user.vk_id,
      message=Text.user.REGISTRATION_APPROVED.value,
      keyboard=main_keyboard,
    )
  if approved_user.telegram_id is not None:
    await notify_user_about_approval(telegram_id=approved_user.telegram_id, approved=True)

  return (
    f"{Text.admin.APPROVE_ACTION.value}\n\n"
    f"Row ID: {approved_user.row_id}\n"
    f"Имя: {approved_user.name}\n"
    f"Telegram ID: {approved_user.telegram_id}\n"
    f"VK ID: {approved_user.vk_id}"
  )


async def _process_vk_reject(*, admin_user_id: int, row_id: int) -> str:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_vk_admin_ids()
    if admin_user_id not in admin_ids:
      return Text.admin.NO_RIGHTS.value

    pending_user = await repository.get_by_row_id(row_id)
    if pending_user is None:
      return Text.admin.REQUEST_NOT_FOUND.value

    pending_vk_id = pending_user.vk_id
    pending_telegram_id = pending_user.telegram_id
    use_case = RejectUserUseCase(repository)
    try:
      await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      return Text.admin.REQUEST_NOT_FOUND.value
    except UserAlreadyApprovedError:
      return Text.admin.REQUEST_ALREADY_APPROVED.value

  if pending_vk_id is not None:
    await send_vk_message(
      user_id=pending_vk_id,
      message=Text.user.REGISTRATION_NOT_APPROVED.value,
      keyboard=main_keyboard,
    )
  if pending_telegram_id is not None:
    await notify_user_about_approval(telegram_id=pending_telegram_id, approved=False)

  return f"{Text.admin.REJECT_ACTION.value}\n\nRow ID: {row_id}"


async def _process_vk_correct(
  *,
  admin_user_id: int,
  row_id: int,
  corrected_name: str,
) -> str:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_vk_admin_ids()
    if admin_user_id not in admin_ids:
      return Text.admin.NO_RIGHTS.value

    use_case = CorrectUserUseCase(repository)
    try:
      corrected_user = await use_case.execute(
        row_id=row_id,
        corrected_name=corrected_name,
      )
    except UserNotFoundError:
      return Text.admin.REQUEST_NOT_FOUND.value
    except UserNameRequiredError:
      return Text.admin.EMPTY_CORRECTED_NAME.value
    except UserAlreadyApprovedError:
      return Text.admin.REQUEST_ALREADY_APPROVED.value

  if corrected_user.vk_id is not None:
    await send_vk_message(
      user_id=corrected_user.vk_id,
      message=Text.user.REGISTRATION_APPROVED.value,
      keyboard=main_keyboard,
    )
  if corrected_user.telegram_id is not None:
    await notify_user_about_approval(telegram_id=corrected_user.telegram_id, approved=True)

  return (
    f"{Text.admin.CORRECT_ACTION.value}\n\n"
    f"Row ID: {corrected_user.row_id}\n"
    f"Имя: {corrected_user.name}\n"
    f"Telegram ID: {corrected_user.telegram_id}\n"
    f"VK ID: {corrected_user.vk_id}"
  )


async def _process_vk_link(
  *,
  admin_user_id: int,
  pending_row_id: int,
  existing_row_id: int,
) -> str:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_vk_admin_ids()
    if admin_user_id not in admin_ids:
      return Text.admin.NO_RIGHTS.value

    use_case = LinkPendingUserUseCase(repository)
    try:
      linked_user = await use_case.execute(
        pending_row_id=pending_row_id,
        existing_row_id=existing_row_id,
      )
    except UserNotFoundError:
      return Text.admin.USER_NOT_FOUND.value
    except UserLinkConflictError:
      return Text.admin.LINK_CONFLICT.value

  if linked_user.vk_id is not None:
    await send_vk_message(
      user_id=linked_user.vk_id,
      message=Text.user.REGISTRATION_APPROVED.value,
      keyboard=main_keyboard,
    )
  if linked_user.telegram_id is not None:
    await notify_user_about_approval(telegram_id=linked_user.telegram_id, approved=True)

  return (
    f"{Text.admin.LINK_SUCCESS.value}\n\n"
    f"Row ID: {linked_user.row_id}\n"
    f"Имя: {linked_user.name}\n"
    f"Telegram ID: {linked_user.telegram_id}\n"
    f"VK ID: {linked_user.vk_id}"
  )


async def handle_message_event(event_object: dict) -> PlainTextResponse:
  admin_user_id = event_object.get("user_id")
  peer_id = event_object.get("peer_id")
  event_id = event_object.get("event_id")
  conversation_message_id = event_object.get("conversation_message_id")
  callback_payload = event_object.get("payload") or {}
  action = callback_payload.get("action")

  if not admin_user_id or not peer_id or not event_id:
    return PlainTextResponse("ok")

  if action == "approve":
    row_id = callback_payload.get("row_id")
    if not isinstance(row_id, int):
      return PlainTextResponse("ok")
    result_text = await _process_vk_approve(admin_user_id=admin_user_id, row_id=row_id)
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=Text.admin.APPROVE_ACTION.value if result_text.startswith(Text.admin.APPROVE_ACTION.value) else result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

  if action == "reject":
    row_id = callback_payload.get("row_id")
    if not isinstance(row_id, int):
      return PlainTextResponse("ok")
    result_text = await _process_vk_reject(admin_user_id=admin_user_id, row_id=row_id)
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=Text.admin.REJECT_ACTION.value if result_text.startswith(Text.admin.REJECT_ACTION.value) else result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

  if action == "correct":
    row_id = callback_payload.get("row_id")
    if not isinstance(row_id, int):
      return PlainTextResponse("ok")
    vk_user_states[admin_user_id] = WAITING_FOR_ADMIN_CORRECTED_NAME
    vk_user_contexts[admin_user_id] = {"pending_row_id": str(row_id)}
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=Text.admin.CORRECT_FLOW_STARTED.value,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=Text.admin.CORRECT_PROMPT.value)
    return PlainTextResponse("ok")

  if action == "link":
    row_id = callback_payload.get("row_id")
    if not isinstance(row_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      repository = UserRepository(session)
      approved_users = await repository.list_approved()
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=Text.admin.LINK_ACTION.value,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=admin_user_id,
      message=Text.admin.LINK_PROMPT.value,
      keyboard=link_candidates_keyboard(pending_row_id=row_id, users=approved_users),
    )
    return PlainTextResponse("ok")

  if action == "link_to":
    pending_row_id = callback_payload.get("pending_row_id")
    existing_row_id = callback_payload.get("existing_row_id")
    if not isinstance(pending_row_id, int) or not isinstance(existing_row_id, int):
      return PlainTextResponse("ok")
    result_text = await _process_vk_link(
      admin_user_id=admin_user_id,
      pending_row_id=pending_row_id,
      existing_row_id=existing_row_id,
    )
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=Text.admin.LINK_SUCCESS.value if result_text.startswith(Text.admin.LINK_SUCCESS.value) else result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

  if action == "make_admin_select":
    row_id = callback_payload.get("row_id")
    if not isinstance(row_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      repository = UserRepository(session)
      admin_ids = await repository.list_vk_admin_ids()
      if admin_user_id not in admin_ids:
        result_text = Text.admin.NO_RIGHTS.value
      else:
        use_case = MakeAdminUseCase(repository)
        try:
          user = await use_case.execute(row_id=row_id)
          result_text = f"{Text.admin.MAKE_ADMIN_SUCCESS.value}\n\nИмя: {user.name}"
        except UserNotFoundError:
          result_text = Text.admin.USER_NOT_FOUND.value
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

  if action == "poker_start_param":
    params_id = callback_payload.get("params_id")
    if not isinstance(params_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if admin_user_id not in admin_ids:
        result_text = Text.admin.NO_RIGHTS.value
      else:
        use_case = StartPokerUseCase(
          poker_repository=PokerRepository(session),
          poker_param_repository=PokerParamRepository(session),
        )
        created = await use_case.execute(params_id=params_id)
        if created is None:
          result_text = Text.admin.POKER_STARTED.value
        else:
          result_text = Text.admin.POKER_START_SUCCESS.value
          tg_user_ids = await user_repository.list_approved_tg_ids()
          vk_user_ids = await user_repository.list_approved_vk_ids()
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    if result_text == Text.admin.POKER_START_SUCCESS.value:
      from app.bot.telegram.runtime import telegram_bot
      if telegram_bot is not None:
        for user_id in tg_user_ids:
          await telegram_bot.send_message(chat_id=user_id, text=Text.user.START_POKER.value)
      for user_id in vk_user_ids:
        await send_vk_message(user_id=user_id, message=Text.user.START_POKER.value)
    return PlainTextResponse("ok")

  return PlainTextResponse("ok")


async def handle_admin_text_commands(*, user_id: int, text: str) -> PlainTextResponse | None:
  if vk_user_states.get(user_id) == WAITING_FOR_ADMIN_CORRECTED_NAME:
    pending_row_id = vk_user_contexts.get(user_id, {}).get("pending_row_id")
    corrected_name = " ".join(text.split())
    if pending_row_id is None:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message(user_id=user_id, message=Text.admin.REQUEST_NOT_FOUND.value)
      return PlainTextResponse("ok")
    result_text = await _process_vk_correct(
      admin_user_id=user_id,
      row_id=int(pending_row_id),
      corrected_name=corrected_name,
    )
    vk_user_states.pop(user_id, None)
    vk_user_contexts.pop(user_id, None)
    await send_vk_message(user_id=user_id, message=result_text)
    return PlainTextResponse("ok")

  if text.lower().startswith("approve "):
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
      await send_vk_message(user_id=user_id, message=Text.admin.APPROVE_COMMAND_USAGE.value)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=await _process_vk_approve(admin_user_id=user_id, row_id=int(parts[1])))
    return PlainTextResponse("ok")

  if text.lower().startswith("correct "):
    parts = text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].strip():
      await send_vk_message(user_id=user_id, message=Text.admin.CORRECT_COMMAND_USAGE.value)
      return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=await _process_vk_correct(
        admin_user_id=user_id,
        row_id=int(parts[1]),
        corrected_name=" ".join(parts[2].split()),
      ),
    )
    return PlainTextResponse("ok")

  if text.lower().startswith("reject "):
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
      await send_vk_message(user_id=user_id, message=Text.admin.REJECT_COMMAND_USAGE.value)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=await _process_vk_reject(admin_user_id=user_id, row_id=int(parts[1])))
    return PlainTextResponse("ok")

  if text.lower().startswith("link "):
    parts = text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
      await send_vk_message(user_id=user_id, message=Text.admin.LINK_COMMAND_USAGE.value)
      return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=await _process_vk_link(
        admin_user_id=user_id,
        pending_row_id=int(parts[1]),
        existing_row_id=int(parts[2]),
      ),
    )
    return PlainTextResponse("ok")

  if text.lower() in {"make_admin", "/make_admin", "make admin"}:
    async with SessionFactory() as session:
      repository = UserRepository(session)
      admin_ids = await repository.list_vk_admin_ids()
      if user_id not in admin_ids:
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      approved_users = await repository.list_approved()
      candidates = [user for user in approved_users if not user.is_admin]
      if not candidates:
        await send_vk_message(user_id=user_id, message=Text.admin.MAKE_ADMIN_EMPTY.value)
        return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.admin.MAKE_ADMIN_PROMPT.value,
      keyboard=make_admin_candidates_keyboard(users=candidates),
    )
    return PlainTextResponse("ok")

  if text == Buttons.admin_main.START_POKER.value or text.lower() in {"start_poker", "/start_poker"}:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if user_id not in admin_ids:
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      use_case = StartPokerUseCase(
        poker_repository=PokerRepository(session),
        poker_param_repository=PokerParamRepository(session),
      )
      can_start, params = await use_case.get_start_data()
      if not can_start:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_STARTED.value)
        return PlainTextResponse("ok")
      if not params:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_PARAMS_EMPTY.value)
        return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.admin.POKER_PARAMS_CHOOSE.value,
      keyboard=poker_params_keyboard(params=params),
    )
    return PlainTextResponse("ok")

  return None
