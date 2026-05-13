from fastapi.responses import PlainTextResponse

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
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import betting_keyboard as tg_betting_keyboard
from app.bot.telegram.keyboards import main_keyboard as tg_main_keyboard
from app.bot.telegram.notifications import notify_user_about_approval
from app.bot.vk.api import clear_vk_inline_keyboard, send_vk_message, send_vk_message_event_answer
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
from app.db.session import SessionFactory


def _format_rub_from_kopecks(value_kopecks: int) -> str:
  rub = int(value_kopecks) // 100
  kop = int(value_kopecks) % 100
  if kop == 0:
    return str(rub)
  return f"{rub}.{kop:02d}"


async def _notify_players_about_finish(*, players: list) -> None:
  from app.bot.telegram.runtime import telegram_bot

  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    for player in players:
      user = await user_repository.get_by_telegram_id(int(player.player_id))
      if user is None:
        user = await user_repository.get_by_vk_id(int(player.player_id))
      if user is None or user.notification_platform is None:
        continue

      text = Text.user.FINISH_POKER.value.format(
        buyins=player.buyins,
        cashout_rub=_format_rub_from_kopecks(player.money_kopecks),
      )
      if user.notification_platform == "tg" and user.telegram_id is not None and telegram_bot is not None:
        await telegram_bot.send_message(chat_id=user.telegram_id, text=text)
      elif user.notification_platform == "vk" and user.vk_id is not None:
        await send_vk_message(user_id=user.vk_id, message=text)


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
    return None

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
      admin_ids = await user_repository.list_vk_admin_ids()
      if admin_user_id not in admin_ids:
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
            player_id=int(user.vk_id),
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
      admin_ids = await user_repository.list_vk_admin_ids()
      if admin_user_id not in admin_ids:
        result_text = Text.admin.NO_RIGHTS.value
      else:
        use_case = ManagePokerPlayersUseCase(
          poker_repository=PokerRepository(session),
          poker_data_repository=PokerDataRepository(session),
          user_repository=user_repository,
          poker_room_denied_repository=PokerRoomDeniedRepository(session),
        )
        removed = await use_case.remove_player_from_active_poker(player_id=int(player_id))
        if removed is None:
          result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
        elif removed is False:
          result_text = Text.admin.USER_NOT_FOUND.value
        else:
          result_text = Text.admin.POKER_REMOVE_PLAYER_SUCCESS.value
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
    player_id = callback_payload.get("player_id")
    if not isinstance(player_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if admin_user_id not in admin_ids:
        result_text = Text.admin.NO_RIGHTS.value
      else:
        use_case = ManagePokerPlayersUseCase(
          poker_repository=PokerRepository(session),
          poker_data_repository=PokerDataRepository(session),
          poker_room_denied_repository=PokerRoomDeniedRepository(session),
          user_repository=user_repository,
        )
        removed = await use_case.remove_denied_for_active_poker(player_id=int(player_id))
        result_text = Text.admin.POKER_UNBAN_PLAYER_SUCCESS.value if removed else Text.admin.POKER_UNBAN_PLAYER_EMPTY.value
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
    player_id = callback_payload.get("player_id")
    if not isinstance(player_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if admin_user_id not in admin_ids:
        result_text = Text.admin.NO_RIGHTS.value
      else:
        use_case = ManagePokerPlayersUseCase(
          poker_repository=PokerRepository(session),
          poker_data_repository=PokerDataRepository(session),
        )
        updated = await use_case.set_cashier_for_active_poker(cashier_id=player_id)
        result_text = Text.admin.POKER_CASHIER_SET.value if updated is not None else Text.admin.POKER_ACTIVE_NOT_FOUND.value
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
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if admin_user_id not in admin_ids:
        result_text = Text.admin.NO_RIGHTS.value
        result_keyboard = None
      else:
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
          result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
          result_keyboard = None
        else:
          _, params = active
          result_text = Text.admin.POKER_BUYIN_PROMPT.value
          result_keyboard = poker_buyin_count_keyboard(
            player_id=int(player_id),
            max_buyins=int(params.max_buyins),
            big_buyin_pic=params.big_buyin_pic,
            king_buyin_pic=params.king_buyin_pic,
            super_buyin_pic=params.super_buyin_pic,
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
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if admin_user_id not in admin_ids:
        result_text = Text.admin.NO_RIGHTS.value
      else:
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
          result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
        else:
          poker, params = active
          poker_data_repository = PokerDataRepository(session)
          prev_player = await poker_data_repository.get_player(date=poker.date, player_id=int(player_id))
          prev_buyins = int(prev_player.buyins) if prev_player is not None else 0
          new_buyins_total = prev_buyins + int(buyins_count)
          is_special_mode = int(params.max_buyins) == 2
          big_count = 0
          super_count = 0
          if is_special_mode:
            for buyin_no in range(prev_buyins + 1, new_buyins_total + 1):
              if buyin_no == 3:
                big_count += 1
              elif buyin_no >= 5:
                super_count += 1
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
          )
          if updated is None:
            result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
          else:
            result_text = f"{Text.admin.POKER_BUYIN_SAVED.value}\n\n{updated.player_name}: {updated.buyins}"
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
      admin_ids = await user_repository.list_vk_admin_ids()
      if admin_user_id not in admin_ids:
        result_text = Text.admin.NO_RIGHTS.value
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
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if user_id not in admin_ids:
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
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
    vk_user_states.pop(user_id, None)
    vk_user_contexts.pop(user_id, None)
    await send_vk_message(
      user_id=user_id,
      message=(
        f"{Text.admin.POKER_CASHOUT_SAVED.value}\n\n"
        f"{updated.player_name}: {updated.chips} фишек"
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

  if text == Buttons.admin_main.START_POKER.value:
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

  if text == Buttons.admin_room.FINISH_POKER.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if user_id not in admin_ids:
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      poker_repository = PokerRepository(session)
      active = await poker_repository.get_started()
      if active is None:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value)
        return PlainTextResponse("ok")
      poker, _ = active
      poker_data_repository = PokerDataRepository(session)
      players = await poker_data_repository.list_players(date=poker.date)
      await CalculateBetScoresUseCase(
        bet_repository=BetRepository(session),
        bet_param_repository=BetParamRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_data_repository=poker_data_repository,
      ).execute(
        poker_id=poker.row_id,
        poker_date=poker.date,
      )
      await poker_repository.finish(poker)
    await _notify_players_about_finish(players=players)
    await send_vk_message(user_id=user_id, message=Text.admin.POKER_FINISH_SUCCESS.value)
    if players:
      await send_vk_message(
        user_id=user_id,
        message=Text.admin.POKER_CASHOUT_CHOOSE.value,
        keyboard=poker_cashout_candidates_keyboard(players=players),
      )
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.START_BETTING.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if user_id not in admin_ids:
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      poker_repository = PokerRepository(session)
      active = await poker_repository.get_started()
      if active is None:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value)
        return PlainTextResponse("ok")
      poker, _ = active
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

  if text == Buttons.admin_room.ADD_PLAYER.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if user_id not in admin_ids:
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
      admin_ids = await user_repository.list_vk_admin_ids()
      if user_id not in admin_ids:
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
      admin_ids = await user_repository.list_vk_admin_ids()
      if user_id not in admin_ids:
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
        user = await user_repository.get_by_telegram_id(int(item.player_id))
        if user is None:
          user = await user_repository.get_by_vk_id(int(item.player_id))
        name = user.name if user is not None else f"ID {int(item.player_id)}"
        candidates.append({"player_id": int(item.player_id), "name": name})
    await send_vk_message(
      user_id=user_id,
      message=Text.admin.POKER_UNBAN_PLAYER_CHOOSE.value,
      keyboard=poker_unban_player_candidates_keyboard(players=candidates),
    )
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.SET_CASHIER.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if user_id not in admin_ids:
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
      message=Text.admin.POKER_CASHIER_CHOOSE.value,
      keyboard=poker_cashier_candidates_keyboard(players=players),
    )
    return PlainTextResponse("ok")

  if text == Buttons.room.BUYIN.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if user_id not in admin_ids:
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
      use_case = ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      players = await use_case.list_active_poker_players()
      if not players:
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_BUYIN_EMPTY.value)
        return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.admin.POKER_BUYIN_CHOOSE.value,
      keyboard=poker_buyin_candidates_keyboard(players=players),
    )
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.TO_ROOM.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      admin_ids = await user_repository.list_vk_admin_ids()
      if user_id not in admin_ids:
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message="Покер рум.",
      keyboard=room_admin_keyboard,
    )
    return PlainTextResponse("ok")

  return None
