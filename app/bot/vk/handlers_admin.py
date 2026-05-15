from fastapi.responses import PlainTextResponse
from datetime import date
from types import SimpleNamespace
import random

from app.application.exceptions import (
  UserAlreadyApprovedError,
  UserLinkConflictError,
  UserNameRequiredError,
  UserNotFoundError,
)
from app.application.use_cases.user.approve_user import ApproveUserUseCase
from app.application.use_cases.user.correct_user import CorrectUserUseCase
from app.application.use_cases.user.link_pending_user import LinkPendingUserUseCase
from app.application.use_cases.user.make_admin import MakeAdminUseCase
from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.application.use_cases.poker.calculate_bet_scores import CalculateBetScoresUseCase
from app.application.use_cases.poker.start_poker import StartPokerUseCase
from app.application.use_cases.user.reject_user import RejectUserUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import betting_keyboard as tg_betting_keyboard
from app.bot.telegram.keyboards import main_keyboard as tg_main_keyboard
from app.bot.telegram.notifications import notify_user_about_approval
from app.bot.vk.api import delete_vk_message, send_vk_message, send_vk_message_event_answer
from app.bot.vk.keyboards import (
  betting_keyboard,
  link_candidates_keyboard,
  link_candidates_page_keyboard,
  main_keyboard,
  make_admin_candidates_keyboard,
  poker_add_player_candidates_keyboard,
  poker_buyin_candidates_keyboard,
  poker_buyin_count_keyboard,
  poker_cashout_candidates_keyboard,
  poker_cashier_candidates_keyboard,
  poker_remove_player_candidates_keyboard,
  poker_unban_player_candidates_keyboard,
  poker_params_keyboard,
  poll_admin_choose_keyboard,
  poll_admin_other_keyboard,
  room_admin_keyboard,
)
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.bot.vk.state import (
  WAITING_FOR_ADMIN_CASHOUT_AMOUNT,
  WAITING_FOR_ADMIN_CORRECTED_NAME,
  vk_user_contexts,
  vk_user_states,
)
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.session import SessionFactory


def _shift_month(value: date, delta: int) -> date:
  total = value.year * 12 + (value.month - 1) + delta
  year = total // 12
  month = total % 12 + 1
  return date(year, month, 1)


def _parse_month_key(value: str) -> date:
  year_s, month_s = value.split("-")
  return date(int(year_s), int(month_s), 1)


def _format_rub_from_kopecks(value_kopecks: int) -> str:
  rub = int(value_kopecks) // 100
  kop = int(value_kopecks) % 100
  if kop == 0:
    return str(rub)
  return f"{rub}.{kop:02d}"


def _get_reaction(mode: str) -> str:
  winner = ["🍾", "👍", "🔥", "🏆", "👏", "🤩", "🎉"]
  loser = ["👎", "🥴", "😢", "💩", "🤮", "😭", "🤷‍♀"]
  return random.choice(winner if mode == "winner" else loser)


def _calculate_transfers(money_rows: list[dict[str, int | str]]) -> list[str]:
  rows = [{"name": str(item["name"]), "money": int(item["money"])} for item in money_rows]
  lines: list[str] = []
  while True:
    loser = min(rows, key=lambda x: int(x["money"]))
    winner = max(rows, key=lambda x: int(x["money"]))
    if int(loser["money"]) == 0 and int(winner["money"]) == 0:
      break
    transfer = min(-int(loser["money"]), int(winner["money"]))
    if transfer <= 0:
      break
    loser["money"] = int(loser["money"]) + transfer
    winner["money"] = int(winner["money"]) - transfer
    lines.append(f"{loser['name']} ➡️ {winner['name']} {_format_rub_from_kopecks(transfer)} ₽")
  return lines


def _split_names_csv(value: str | None) -> set[str]:
  if not value:
    return set()
  return {item.strip() for item in str(value).split(",") if item.strip()}


def _winner_mark(*, is_streak: bool) -> str:
  return "🛡️💍" if is_streak else "💍"


def _bet_mark(*, amount_kopecks: int, guessed_winner: bool, guessed_loser: bool) -> str:
  size_mark = "🐔" if int(amount_kopecks) >= 40000 else "🐤"
  if guessed_winner and guessed_loser:
    return f"{size_mark}🔮"
  if guessed_winner or guessed_loser:
    return f"{size_mark}🍀"
  return size_mark


async def _notify_players_about_finish(*, players: list) -> None:
  from app.bot.telegram.runtime import telegram_bot

  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    for player in players:
      user = await user_repository.get_by_row_id(int(player.player_id))
      if user is None or user.notification_platform is None:
        continue

      text = Text.user.FINISH_CHIPS_PROMPT.value
      if user.notification_platform == "tg" and user.telegram_id is not None and telegram_bot is not None:
        await telegram_bot.send_message(chat_id=user.telegram_id, text=text)
      elif user.notification_platform == "vk" and user.vk_id is not None:
        await send_vk_message(user_id=user.vk_id, message=text)


async def _notify_about_buyin(*, session, poker, updated_player, buyins_count: int) -> None:
  from app.bot.telegram.runtime import telegram_bot

  user_repository = UserRepository(session)
  recipients: dict[int, object] = {}

  if poker.cashier_id is not None:
    cashier = await user_repository.get_by_row_id(int(poker.cashier_id))
    if cashier is not None:
      recipients[int(cashier.row_id)] = cashier

  users = await user_repository.list_approved()
  for user in users:
    if user.is_admin:
      recipients[int(user.row_id)] = user

  text = (
    "🏦 Новый закуп\n"
    f"Игрок: {updated_player.player_name}\n"
    f"Количество: +{buyins_count}\n"
    f"Итого закупов: {updated_player.buyins}"
  )
  for user in recipients.values():
    if user.notification_platform == "tg" and user.telegram_id is not None and telegram_bot is not None:
      await telegram_bot.send_message(chat_id=user.telegram_id, text=text)
    elif user.notification_platform == "vk" and user.vk_id is not None:
      await send_vk_message(user_id=user.vk_id, message=text)


async def _notify_user_removed_from_room(*, user) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if user.telegram_id is not None and telegram_bot is not None:
    await telegram_bot.send_message(chat_id=user.telegram_id, text=Text.user.ROOM_REMOVED_BY_ADMIN.value)
  if user.vk_id is not None:
    await send_vk_message(user_id=user.vk_id, message=Text.user.ROOM_REMOVED_BY_ADMIN.value)


async def _notify_user_unbanned_for_room(*, user) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if user.notification_platform == "tg" and user.telegram_id is not None and telegram_bot is not None:
    await telegram_bot.send_message(chat_id=user.telegram_id, text=Text.user.ROOM_UNBANNED_BY_ADMIN.value)
  elif user.notification_platform == "vk" and user.vk_id is not None:
    await send_vk_message(user_id=user.vk_id, message=Text.user.ROOM_UNBANNED_BY_ADMIN.value)


async def _clear_event_inline_keyboard_if_possible(*, peer_id: int | None, conversation_message_id: int | None) -> None:
  if peer_id is None or conversation_message_id is None:
    return
  try:
    await delete_vk_message(
      peer_id=peer_id,
      conversation_message_id=conversation_message_id,
    )
  except Exception:
    return


async def _ensure_vk_admin_message(*, session, user_id: int) -> bool:
  return await is_vk_admin(session=session, vk_id=user_id)


async def _process_vk_approve(*, admin_user_id: int, row_id: int) -> str:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    if not await is_vk_admin(session=session, vk_id=admin_user_id):
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
    if not await is_vk_admin(session=session, vk_id=admin_user_id):
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
    if not await is_vk_admin(session=session, vk_id=admin_user_id):
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
    if not await is_vk_admin(session=session, vk_id=admin_user_id):
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


async def handle_message_event(event_object: dict) -> PlainTextResponse | None:
  admin_user_id = event_object.get("user_id")
  peer_id = event_object.get("peer_id")
  event_id = event_object.get("event_id")
  conversation_message_id = event_object.get("conversation_message_id")
  callback_payload = event_object.get("payload") or {}
  action = callback_payload.get("action")

  if not admin_user_id or not peer_id or not event_id:
    return None

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
    return None

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
    return None

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
    return None

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
    return None

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
    return None

  if action == "link_page":
    pending_row_id = callback_payload.get("pending_row_id")
    page = callback_payload.get("page")
    if not isinstance(pending_row_id, int) or not isinstance(page, int):
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
      keyboard=link_candidates_page_keyboard(
        pending_row_id=pending_row_id,
        users=approved_users,
        page=page,
      ),
    )
    return None

  if action == "make_admin_select":
    row_id = callback_payload.get("row_id")
    if not isinstance(row_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
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
    return None

  if action == "poker_start_param":
    params_id = callback_payload.get("params_id")
    if not isinstance(params_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        result_text = Text.admin.NO_RIGHTS.value
      else:
        use_case = StartPokerUseCase(
          poker_repository=PokerRepository(session),
          poker_param_repository=PokerParamRepository(session),
          poker_room_denied_repository=PokerRoomDeniedRepository(session),
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
          await telegram_bot.send_message(
            chat_id=user_id,
            text=Text.user.START_POKER.value,
            reply_markup=tg_main_keyboard,
          )
      for user_id in vk_user_ids:
        await send_vk_message(user_id=user_id, message=Text.user.START_POKER.value, keyboard=main_keyboard)
    return None

  if action == "poker_add_player_select":
    row_id = callback_payload.get("row_id")
    if not isinstance(row_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        result_text = Text.admin.NO_RIGHTS.value
      else:
        user = await user_repository.get_by_row_id(row_id)
        if user is None or user.vk_id is None:
          result_text = Text.admin.USER_NOT_FOUND.value
        else:
          use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
          )
          created = await use_case.add_player_to_active_poker(
            player_id=int(user.row_id),
            player_name=user.name,
          )
          if created is None:
            result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
          else:
            result_text = f"{Text.admin.POKER_ADD_PLAYER_SUCCESS.value}\n\nИмя: {user.name}"
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return None

  if action == "poker_remove_player_select":
    player_id = callback_payload.get("player_id")
    if not isinstance(player_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        result_text = Text.admin.NO_RIGHTS.value
      else:
        use_case = ManagePokerPlayersUseCase(
          poker_repository=PokerRepository(session),
          poker_data_repository=PokerDataRepository(session),
          user_repository=user_repository,
          poker_room_denied_repository=PokerRoomDeniedRepository(session),
        )
        removed_user = await user_repository.get_by_row_id(int(player_id))
        removed = await use_case.remove_player_from_active_poker(player_id=int(player_id))
        if removed is None:
          result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
        elif removed is False:
          result_text = Text.admin.USER_NOT_FOUND.value
        else:
          result_text = Text.admin.POKER_REMOVE_PLAYER_SUCCESS.value
          if removed_user is not None:
            await _notify_user_removed_from_room(user=removed_user)
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

  if action == "poker_unban_player_select":
    user_row_id = callback_payload.get("player_id")
    if not isinstance(user_row_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        result_text = Text.admin.NO_RIGHTS.value
      else:
        use_case = ManagePokerPlayersUseCase(
          poker_repository=PokerRepository(session),
          poker_data_repository=PokerDataRepository(session),
          poker_room_denied_repository=PokerRoomDeniedRepository(session),
          user_repository=user_repository,
        )
        unbanned_user = await user_repository.get_by_row_id(int(user_row_id))
        removed = await use_case.remove_denied_for_active_poker(user_row_id=int(user_row_id))
        result_text = Text.admin.POKER_UNBAN_PLAYER_SUCCESS.value if removed else Text.admin.POKER_UNBAN_PLAYER_EMPTY.value
        if removed and unbanned_user is not None:
          await _notify_user_unbanned_for_room(user=unbanned_user)
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

  if action == "poker_set_cashier_select":
    user_row_id = callback_payload.get("player_id")
    if not isinstance(user_row_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        result_text = Text.admin.NO_RIGHTS.value
      else:
        use_case = ManagePokerPlayersUseCase(
          poker_repository=PokerRepository(session),
          poker_data_repository=PokerDataRepository(session),
        )
        updated = await use_case.set_cashier_for_active_poker(cashier_id=user_row_id)
        if updated is None:
          result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
        else:
          cashier_user = await user_repository.get_by_row_id(user_row_id)
          cashier_name = cashier_user.name if cashier_user is not None else f"ID {user_row_id}"
          result_text = f"{cashier_name} выбран кассиром."
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

  if action == "poker_buyin_select":
    player_id = callback_payload.get("player_id")
    if not isinstance(player_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        result_text = Text.admin.NO_RIGHTS.value
        result_keyboard = None
      else:
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
          result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
          result_keyboard = None
        else:
          poker, params = active
          if poker.is_ready_for_chips_entering:
            result_text = Text.user.FINISH_CHIPS_NOT_READY.value
            result_keyboard = None
            await send_vk_message_event_answer(
              event_id=event_id,
              user_id=admin_user_id,
              peer_id=peer_id,
              text=result_text,
            )
            await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
            await send_vk_message(user_id=admin_user_id, message=result_text)
            return PlainTextResponse("ok")
          if poker.cashier_id is None:
            result_text = Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value
            result_keyboard = None
            await send_vk_message_event_answer(
              event_id=event_id,
              user_id=admin_user_id,
              peer_id=peer_id,
              text=result_text,
            )
            await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
            await send_vk_message(user_id=admin_user_id, message=result_text)
            return PlainTextResponse("ok")
          player = await PokerDataRepository(session).get_player(date=poker.date, player_id=int(player_id))
          include_king_buyin = bool(player is not None and player.is_prev_winner)
          current_big_buyin_count = int(player.big_buyin_count) if player is not None else 0
          current_super_buyin_count = int(player.super_buyin_count) if player is not None else 0
          result_text = Text.admin.POKER_BUYIN_PROMPT.value
          result_keyboard = poker_buyin_count_keyboard(
            player_id=int(player_id),
            max_buyins=int(params.max_buyins),
            big_buyin=params.big_buyin,
            king_buyin=params.king_buyin,
            super_buyin=params.super_buyin,
            big_buyin_pic=params.big_buyin_pic,
            king_buyin_pic=params.king_buyin_pic,
            super_buyin_pic=params.super_buyin_pic,
            include_king_buyin=include_king_buyin,
            current_big_buyin_count=current_big_buyin_count,
            current_super_buyin_count=current_super_buyin_count,
          )
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text, keyboard=result_keyboard)
    return PlainTextResponse("ok")

  if action == "poker_buyin_count_select":
    player_id = callback_payload.get("player_id")
    buyins_count = callback_payload.get("count")
    if not isinstance(player_id, int) or not isinstance(buyins_count, int) or buyins_count <= 0:
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      is_admin = await is_vk_admin(session=session, vk_id=admin_user_id)
      requester = await UserRepository(session).get_by_vk_id(admin_user_id)
      requester_row_id = int(requester.row_id) if requester is not None else -1
      if not is_admin and int(player_id) != requester_row_id:
        result_text = Text.admin.NO_RIGHTS.value
      else:
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
          result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
        else:
          poker, params = active
          if poker.is_ready_for_chips_entering:
            result_text = Text.user.FINISH_CHIPS_NOT_READY.value
            await send_vk_message_event_answer(
              event_id=event_id,
              user_id=admin_user_id,
              peer_id=peer_id,
              text=result_text,
            )
            await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
            await send_vk_message(user_id=admin_user_id, message=result_text)
            return PlainTextResponse("ok")
          if poker.cashier_id is None:
            result_text = Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value
            await send_vk_message_event_answer(
              event_id=event_id,
              user_id=admin_user_id,
              peer_id=peer_id,
              text=result_text,
            )
            await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
            await send_vk_message(user_id=admin_user_id, message=result_text)
            return PlainTextResponse("ok")
          poker_data_repository = PokerDataRepository(session)
          prev_player = await poker_data_repository.get_player(date=poker.date, player_id=int(player_id))
          is_special_mode = int(params.max_buyins) == 2
          include_king_buyin = bool(prev_player is not None and prev_player.is_prev_winner)
          big_threshold = int(params.big_buyin or 5)
          super_threshold = int(params.super_buyin or 10)
          king_threshold = int(params.king_buyin or 15)
          current_big_count = int(prev_player.big_buyin_count) if prev_player is not None else 0
          current_super_count = int(prev_player.super_buyin_count) if prev_player is not None else 0
          if is_special_mode:
            allowed_special_amounts: set[int] = set()
            if current_super_count == 0 and current_big_count < 2:
              allowed_special_amounts.add(big_threshold)
            if current_super_count == 0 and current_big_count == 0:
              allowed_special_amounts.add(super_threshold)
              if include_king_buyin:
                allowed_special_amounts.add(king_threshold)
            if int(buyins_count) > int(params.max_buyins) and int(buyins_count) not in allowed_special_amounts:
              result_text = Text.admin.POKER_BUYIN_INVALID.value
              await send_vk_message_event_answer(
                event_id=event_id,
                user_id=admin_user_id,
                peer_id=peer_id,
                text=result_text,
              )
              await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
              await send_vk_message(user_id=admin_user_id, message=result_text)
              return PlainTextResponse("ok")
          big_count = 0
          super_count = 0
          if is_special_mode:
            if include_king_buyin and current_big_count == 0 and current_super_count == 0 and int(buyins_count) >= king_threshold:
              big_count += 1
              super_count += 1
            elif int(buyins_count) >= super_threshold:
              if current_big_count == 0 and current_super_count == 0:
                super_count += 1
              elif current_super_count == 0 and current_big_count < 2 and int(buyins_count) >= big_threshold:
                big_count += 1
            elif current_super_count == 0 and current_big_count < 2 and int(buyins_count) >= big_threshold:
              big_count += 1
          use_case = ManagePokerPlayersUseCase(
            poker_repository=poker_repository,
            poker_data_repository=poker_data_repository,
            buyin_data_repository=BuyinDataRepository(session),
          )
          updated = await use_case.add_buyin_to_active_player(
            player_id=int(player_id),
            buyins_count=int(buyins_count),
            big_buyin_count=big_count,
            super_buyin_count=super_count,
            poker_date=poker.date,
          )
          if updated is None:
            result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
          else:
            result_text = f"{Text.admin.POKER_BUYIN_SAVED.value}\n\n{updated.player_name}: {updated.buyins}"
            await _notify_about_buyin(
              session=session,
              poker=poker,
              updated_player=updated,
              buyins_count=int(buyins_count),
            )
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

  if action == "poker_buyin_cancel":
    result_text = Buttons.betting_inline.CONFIRM_NO.value
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

  if action == "poker_cashout_select":
    player_id = callback_payload.get("player_id")
    if not isinstance(player_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        result_text = Text.admin.NO_RIGHTS.value
      else:
        ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
        if ready is None:
          result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
        else:
          poker, params = ready
          pdata = PokerDataRepository(session)
          player = await pdata.get_player(date=poker.date, player_id=int(player_id))
          chips_raw = vk_user_contexts.get(admin_user_id, {}).get("cashout_input_value")
          if chips_raw is not None and player is not None:
            chips = int(chips_raw)
            bb_size = max(1, int(params.bb_size_chips or 10))
            step = max(1, bb_size // 2)
            if chips % step != 0:
              vk_user_contexts.setdefault(admin_user_id, {}).pop("cashout_input_value", None)
              result_text = Text.user.FINISH_CHIPS_INVALID.value.format(step=step)
            else:
              money_kopecks = ((chips - int(player.buyins) * int(params.buyin_size_chips)) * int(params.buyin_size_kopecks)) // int(params.buyin_size_chips)
              updated = await pdata.set_chips(date=poker.date, player_id=int(player_id), chips=chips)
              if updated is not None:
                await pdata.set_cashout(date=poker.date, player_id=int(player_id), money_kopecks=int(money_kopecks))
              vk_user_contexts.setdefault(admin_user_id, {}).pop("cashout_input_value", None)
              result_text = (
                f"{Text.admin.POKER_CASHOUT_SAVED.value}\n\n"
                f"{player.player_name}: {chips} фишек\n"
                f"Итог: {_format_rub_from_kopecks(int(money_kopecks))} ₽"
              )
          else:
            vk_user_states[admin_user_id] = WAITING_FOR_ADMIN_CASHOUT_AMOUNT
            vk_user_contexts[admin_user_id] = {"cashout_player_id": str(player_id)}
            result_text = Text.admin.POKER_CASHOUT_PROMPT.value
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

  if action == "polladmin_other":
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.admin.NO_RIGHTS.value,
        )
        return PlainTextResponse("ok")
    current = date.today().replace(day=1)
    months = [current, _shift_month(current, 1), _shift_month(current, 2)]
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=admin_user_id,
      message="Выбери месяц для опроса:",
      keyboard=poll_admin_other_keyboard(months=months),
    )
    return PlainTextResponse("ok")

  if action == "polladmin_month":
    month_key = callback_payload.get("month")
    if not isinstance(month_key, str):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.admin.NO_RIGHTS.value,
        )
        return PlainTextResponse("ok")
      month = _parse_month_key(month_key)
      await PollConfigRepository(session).set_active_month(month=month)
      await session.commit()
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=f"Опрос на {month:%m.%Y} создан.")
    return PlainTextResponse("ok")

  return None


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

  if vk_user_states.get(user_id) == WAITING_FOR_ADMIN_CASHOUT_AMOUNT:
    if not text.isdigit() or int(text) < 0:
      await send_vk_message(user_id=user_id, message=Text.admin.POKER_CASHOUT_INVALID.value)
      return PlainTextResponse("ok")
    chips = int(text)
    player_id = vk_user_contexts.get(user_id, {}).get("cashout_player_id")
    if player_id is None:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message(user_id=user_id, message=Text.admin.REQUEST_NOT_FOUND.value)
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=user_id):
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      user_repository = UserRepository(session)
      ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
      if ready is None:
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value)
        return PlainTextResponse("ok")
      poker, params = ready
      bb_size = max(1, int(params.bb_size_chips or 10))
      step = max(1, bb_size // 2)
      if chips % step != 0:
        await send_vk_message(user_id=user_id, message=Text.user.FINISH_CHIPS_INVALID.value.format(step=step))
        return PlainTextResponse("ok")
      use_case = ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      updated = await use_case.set_chips_for_ready_poker_player(player_id=int(player_id), chips=chips)
      if updated is None:
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value)
        return PlainTextResponse("ok")
      money_kopecks = ((chips - int(updated.buyins) * int(params.buyin_size_chips)) * int(params.buyin_size_kopecks)) // int(params.buyin_size_chips)
      await PokerDataRepository(session).set_cashout(
        date=poker.date,
        player_id=int(player_id),
        money_kopecks=int(money_kopecks),
      )
    vk_user_states.pop(user_id, None)
    vk_user_contexts.pop(user_id, None)
    await send_vk_message(
      user_id=user_id,
      message=(
        f"{Text.admin.POKER_CASHOUT_SAVED.value}\n\n"
        f"{updated.player_name}: {updated.chips} фишек\n"
        f"Итог: {_format_rub_from_kopecks(int(money_kopecks))} ₽"
      ),
    )
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

  if text == Buttons.admin_main.MAKE_ADMIN.value:
    async with SessionFactory() as session:
      repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=user_id):
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

  if text == Buttons.admin_main.START_POKER.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      use_case = StartPokerUseCase(
        poker_repository=PokerRepository(session),
        poker_param_repository=PokerParamRepository(session),
        poker_room_denied_repository=PokerRoomDeniedRepository(session),
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

  if text == Buttons.admin_room.FINISH_POKER.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      poker_repository = PokerRepository(session)
      active = await poker_repository.get_started()
      if active is None:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value)
        return PlainTextResponse("ok")
      poker, params = active
      poker_data_repository = PokerDataRepository(session)
      players = await poker_data_repository.list_players(date=poker.date)
      await poker_repository.finish(poker)
    await _notify_players_about_finish(players=players)
    await send_vk_message(user_id=user_id, message=Text.admin.POKER_FINISH_SUCCESS.value)
    if players:
      waiting = "\n".join(f"- {p.player_name}" for p in players)
      await send_vk_message(user_id=user_id, message=Text.admin.POKER_CHIPS_WAITING.value.format(players=waiting))
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.CALCULATE_POKER.value:
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      user_repository = UserRepository(session)
      poker_repository = PokerRepository(session)
      ready = await poker_repository.get_latest_ready_for_chips_with_params()
      if ready is None:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_CASHOUT_EMPTY.value)
        return PlainTextResponse("ok")
      poker, params = ready
      poker_data_repository = PokerDataRepository(session)
      players = await poker_data_repository.list_players(date=poker.date)
      if not players:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_CASHOUT_EMPTY.value)
        return PlainTextResponse("ok")

      chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
      chips_entered = sum(int(p.chips) for p in players)
      diff = chips_entered - chips_in_game
      if diff != 0:
        mismatch_text = Text.admin.POKER_CALC_BALANCE_MISMATCH.value.format(
          in_game=chips_in_game,
          entered=chips_entered,
          diff=diff,
        )
        admins = [u for u in await user_repository.list_approved() if u.is_admin]
        from app.bot.telegram.runtime import telegram_bot
        for admin in admins:
          if admin.notification_platform == "tg" and admin.telegram_id is not None and telegram_bot is not None:
            await telegram_bot.send_message(chat_id=admin.telegram_id, text=mismatch_text)
          elif admin.notification_platform == "vk" and admin.vk_id is not None:
            await send_vk_message(user_id=admin.vk_id, message=mismatch_text)
        await send_vk_message(user_id=user_id, message=mismatch_text)
        return PlainTextResponse("ok")

      money_rows: list[dict[str, int | str]] = []
      for player in players:
        money_kopecks = (
          (int(player.chips) - int(player.buyins) * int(params.buyin_size_chips)) * int(params.buyin_size_kopecks)
        ) // int(params.buyin_size_chips)
        await poker_data_repository.set_cashout(
          date=poker.date,
          player_id=int(player.player_id),
          money_kopecks=int(money_kopecks),
        )
        money_rows.append({"name": player.player_name, "money": int(money_kopecks)})

      max_money = max(int(item["money"]) for item in money_rows)
      min_money = min(int(item["money"]) for item in money_rows)
      winners = [str(item["name"]) for item in money_rows if int(item["money"]) == max_money]
      loosers = [str(item["name"]) for item in money_rows if int(item["money"]) == min_money]
      winners_text = ", ".join(winners)
      loosers_text = ", ".join(loosers)
      transfers = _calculate_transfers(money_rows)

      await CalculateBetScoresUseCase(
        bet_repository=BetRepository(session),
        bet_param_repository=BetParamRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_data_repository=poker_data_repository,
      ).execute(
        poker_id=poker.row_id,
        poker_date=poker.date,
      )
      bets = await BetRepository(session).list_for_poker(date=poker.date)

      all_pokers = await poker_repository.list_all()
      prev_completed = None
      for old in sorted(all_pokers, key=lambda x: int(x.row_id), reverse=True):
        if int(old.row_id) == int(poker.row_id):
          continue
        if bool(old.winners):
          prev_completed = old
          break
      prev_winners = _split_names_csv(prev_completed.winners if prev_completed is not None else None)
      winner_line = ", ".join(f"{name} {_winner_mark(is_streak=(name in prev_winners))}" for name in winners)
      loser_line = ", ".join(f"{name} ❌" for name in loosers)

      approved_users = await user_repository.list_approved()
      transfer_lines: list[str] = []
      for line in transfers:
        recipient_name = line.split(" ➡️ ")[1].split(" ")[0:2]
        recipient_name_joined = " ".join(recipient_name).strip()
        recipient_user = next((u for u in approved_users if u.name.startswith(recipient_name_joined)), None)
        extra = ""
        if recipient_user is not None and recipient_user.tel_number:
          bank = f" ({recipient_user.bank_name})" if recipient_user.bank_name else ""
          extra = f" [{recipient_user.tel_number}{bank}]"
        transfer_lines.append(f"{line}{extra}")

      bet_lines: list[str] = []
      for bet in sorted(bets, key=lambda x: int(x.row_id)):
        guessed_winner = bool(bet.winner_name) and bet.winner_name in winners
        guessed_loser = bool(bet.loser_name) and bet.loser_name in loosers
        mark = _bet_mark(
          amount_kopecks=int(bet.amount_kopecks),
          guessed_winner=guessed_winner,
          guessed_loser=guessed_loser,
        )
        winner_guess = bet.winner_name or "-"
        loser_guess = bet.loser_name or "-"
        bet_lines.append(
          f"{bet.better_name}: {_format_rub_from_kopecks(int(bet.amount_kopecks))} ₽ | "
          f"💍 {winner_guess} / ❌ {loser_guess} | {mark} +{int(bet.score)}"
        )
      await poker_repository.finish_chips_entering(
        poker,
        winners=winners_text,
        loosers=loosers_text,
      )

      result_lines = [
        Text.admin.POKER_CALC_SUCCESS.value,
        "",
        f"{winner_line}",
        f"{loser_line}",
        "",
        "💲 Переводы:",
      ]
      result_lines.extend(transfer_lines if transfer_lines else ["Переводы не требуются"])
      result_lines.append("")
      result_lines.append("🍀 Ставки:")
      result_lines.extend(bet_lines if bet_lines else ["Ставок не было"])
      result_text = "\n".join(result_lines)
      await send_vk_message(user_id=user_id, message=result_text)

      from app.bot.telegram.runtime import telegram_bot
      recipient_row_ids = {int(p.player_id) for p in players} | {int(b.better_id) for b in bets}
      for row_id in sorted(recipient_row_ids):
        user = await user_repository.get_by_row_id(row_id)
        if user is None:
          continue
        money = 0
        player = next((p for p in players if int(p.player_id) == row_id), None)
        if player is not None:
          money = next((int(item["money"]) for item in money_rows if str(item["name"]) == player.player_name), 0)
        reaction = _get_reaction("winner" if money >= 0 else "loser")
        player_text = (
          f"Твой итог по игре: {_format_rub_from_kopecks(money)} ₽ {reaction}\n"
          f"Победители: {winners_text}\n"
          f"Проигравшие: {loosers_text}"
        )
        if bets:
          own_bets = [b for b in bets if int(b.better_id) == int(row_id)]
          if own_bets:
            details = []
            for b in own_bets:
              guessed_winner = bool(b.winner_name) and b.winner_name in winners
              guessed_loser = bool(b.loser_name) and b.loser_name in loosers
              mark = _bet_mark(
                amount_kopecks=int(b.amount_kopecks),
                guessed_winner=guessed_winner,
                guessed_loser=guessed_loser,
              )
              details.append(f"{_format_rub_from_kopecks(int(b.amount_kopecks))} ₽ | {mark} +{int(b.score)}")
            player_text += "\nСтавки: " + "; ".join(details)
        if user.notification_platform == "tg" and user.telegram_id is not None and telegram_bot is not None:
          await telegram_bot.send_message(chat_id=user.telegram_id, text=player_text)
        elif user.notification_platform == "vk" and user.vk_id is not None:
          await send_vk_message(user_id=user.vk_id, message=player_text)
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.START_BETTING.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      poker_repository = PokerRepository(session)
      active = await poker_repository.get_started()
      if active is None:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value)
        return PlainTextResponse("ok")
      poker, _ = active
      if poker.is_ready_for_chips_entering:
        await send_vk_message(user_id=user_id, message=Text.user.FINISH_CHIPS_NOT_READY.value)
        return PlainTextResponse("ok")
      if poker.is_bettable:
        await send_vk_message(user_id=user_id, message=Text.admin.BETTING_ALREADY_OPEN.value)
        return PlainTextResponse("ok")
      await poker_repository.start_betting(poker)
      tg_user_ids = await user_repository.list_approved_tg_ids()
      vk_user_ids = await user_repository.list_approved_vk_ids()

    from app.bot.telegram.runtime import telegram_bot

    if telegram_bot is not None:
      for recipient_id in tg_user_ids:
        await telegram_bot.send_message(
          chat_id=recipient_id,
          text=Text.user.START_BETTING.value,
          reply_markup=tg_betting_keyboard,
        )
    for recipient_id in vk_user_ids:
      await send_vk_message(user_id=recipient_id, message=Text.user.START_BETTING.value, keyboard=betting_keyboard)

    await send_vk_message(user_id=user_id, message=Text.admin.BETTING_START_SUCCESS.value)
    return PlainTextResponse("ok")

  if text == Buttons.admin_main.CREATE_POLL.value:
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
    next_month = _shift_month(date.today().replace(day=1), 1)
    await send_vk_message(
      user_id=user_id,
      message="Выбери месяц для опроса:",
      keyboard=poll_admin_choose_keyboard(next_month=next_month),
    )
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.ADD_PLAYER.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      use_case = ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      players = await use_case.list_active_poker_players()
      active_vk_ids = {int(player.player_id) for player in players}
      approved_users = await user_repository.list_approved()
      candidates = [
        user for user in approved_users
        if user.vk_id is not None and int(user.vk_id) not in active_vk_ids
      ]
      if not candidates:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_ADD_PLAYER_EMPTY.value)
        return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.admin.POKER_ADD_PLAYER_CHOOSE.value,
      keyboard=poker_add_player_candidates_keyboard(users=candidates),
    )
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.REMOVE_PLAYER.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      use_case = ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      players = await use_case.list_active_poker_players()
      if not players:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_PLAYERS_EMPTY.value)
        return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.admin.POKER_REMOVE_PLAYER_CHOOSE.value,
      keyboard=poker_remove_player_candidates_keyboard(players=players),
    )
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.UNBAN_PLAYER.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      use_case = ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
        poker_room_denied_repository=PokerRoomDeniedRepository(session),
        user_repository=user_repository,
      )
      denied = await use_case.list_denied_for_active_poker()
      if not denied:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_UNBAN_PLAYER_EMPTY.value)
        return PlainTextResponse("ok")
      candidates: list[dict[str, int | str]] = []
      for item in denied:
        user = await user_repository.get_by_row_id(int(item.user_row_id))
        name = user.name if user is not None else f"ID {int(item.user_row_id)}"
        candidates.append({"player_id": int(item.user_row_id), "name": name})
    await send_vk_message(
      user_id=user_id,
      message=Text.admin.POKER_UNBAN_PLAYER_CHOOSE.value,
      keyboard=poker_unban_player_candidates_keyboard(players=candidates),
    )
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.SET_CASHIER.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      use_case = ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      active_players = await use_case.list_active_poker_players()
      if not active_players:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_PLAYERS_EMPTY.value)
        return PlainTextResponse("ok")
      players: list[SimpleNamespace] = []
      for player in active_players:
        user = await user_repository.get_by_row_id(int(player.player_id))
        if user is None:
          continue
        players.append(SimpleNamespace(player_id=int(user.row_id), player_name=player.player_name))
      if not players:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_PLAYERS_EMPTY.value)
        return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.admin.POKER_CASHIER_CHOOSE.value,
      keyboard=poker_cashier_candidates_keyboard(players=players),
    )
    return PlainTextResponse("ok")

  if text == Buttons.room.BUYIN.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      user = await user_repository.get_by_vk_id(user_id)
      if user is None or not user.is_approved:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value)
        return PlainTextResponse("ok")
      poker_repository = PokerRepository(session)
      active = await poker_repository.get_started()
      if active is None:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value)
        return PlainTextResponse("ok")
      poker, _ = active
      if poker.is_ready_for_chips_entering:
        await send_vk_message(user_id=user_id, message=Text.user.FINISH_CHIPS_NOT_READY.value)
        return PlainTextResponse("ok")
      if poker.cashier_id is None:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value)
        return PlainTextResponse("ok")
      is_admin = await is_vk_admin(session=session, vk_id=user_id)
      poker_data_repository = PokerDataRepository(session)
      players = await poker_data_repository.list_players(date=poker.date)
      if not players:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_BUYIN_EMPTY.value)
        return PlainTextResponse("ok")

      if is_admin:
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.POKER_BUYIN_CHOOSE.value,
          keyboard=poker_buyin_candidates_keyboard(players=players),
        )
        return PlainTextResponse("ok")

      poker, params = active
      self_player = await poker_data_repository.get_player(date=poker.date, player_id=int(user.row_id))
      if self_player is None:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_NOT_ADDED.value)
        return PlainTextResponse("ok")
      include_king_buyin = bool(self_player.is_prev_winner)
      await send_vk_message(
        user_id=user_id,
        message=Text.admin.POKER_BUYIN_PROMPT.value,
        keyboard=poker_buyin_count_keyboard(
          player_id=int(user.row_id),
          max_buyins=int(params.max_buyins),
          big_buyin=params.big_buyin,
          king_buyin=params.king_buyin,
          super_buyin=params.super_buyin,
          big_buyin_pic=params.big_buyin_pic,
          king_buyin_pic=params.king_buyin_pic,
          super_buyin_pic=params.super_buyin_pic,
          include_king_buyin=include_king_buyin,
          current_big_buyin_count=int(self_player.big_buyin_count),
          current_super_buyin_count=int(self_player.super_buyin_count),
        ),
      )
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.TO_ROOM.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message="Покер рум.",
      keyboard=room_admin_keyboard,
    )
    return PlainTextResponse("ok")

  return None
