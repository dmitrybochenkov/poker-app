from fastapi.responses import PlainTextResponse

from app.application.exceptions import (
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserNameRequiredError,
  UserRegistrationPendingError,
)
from app.application.use_cases.user.request_registration import RequestRegistrationUseCase
from app.application.use_cases.poker.bet import BetUseCases
from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
  registration_link_review_keyboard as tg_registration_link_review_keyboard,
  registration_review_keyboard as tg_registration_review_keyboard,
)
from app.bot.telegram.notifications import notify_admins_about_registration as notify_tg_admins_about_registration
from app.bot.vk.api import delete_vk_message, send_vk_message, send_vk_message_event_answer
from app.bot.vk.keyboards import (
  admin_main_keyboard,
  betting_keyboard,
  poker_keyboard,
  betting_confirm_keyboard,
  betting_player_keyboard,
  betting_size_keyboard,
  betting_stat_mode_keyboard,
  betting_stat_indicators_keyboard,
  poker_stat_indicators_keyboard,
  betting_tournament_keyboard,
  main_keyboard,
  main_admin_entry_keyboard,
  new_user_keyboard,
  played_before_keyboard,
  registration_candidates_keyboard,
  registration_candidates_page_keyboard,
  registration_link_review_keyboard as vk_registration_link_review_keyboard,
  registration_optional_details_keyboard,
  registration_platform_keyboard,
  registration_review_keyboard as vk_registration_review_keyboard,
)
from app.bot.vk.notifications import notify_admins_about_registration
from app.bot.vk.state import (
  WAITING_FOR_BET_AMOUNT,
  WAITING_FOR_NEW_NAME,
  WAITING_FOR_OPTIONAL_BANK,
  WAITING_FOR_OPTIONAL_DETAILS_ACTION,
  WAITING_FOR_OPTIONAL_PHONE,
  WAITING_FOR_PLAYED_BEFORE,
  vk_user_contexts,
  vk_user_states,
)
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.achievement_repository import AchievementRepository
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.models.user import User
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory


async def _get_vk_user(user_id: int) -> User | None:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    return await repository.get_by_vk_id(user_id)


async def _is_vk_user_approved(user_id: int) -> bool:
  user = await _get_vk_user(user_id)
  return bool(user and user.is_approved)


def _approved_vk_keyboard(user: User) -> str:
  return main_admin_entry_keyboard if user.is_admin else main_keyboard


async def _delete_event_message_if_possible(*, peer_id: int | None, conversation_message_id: int | None) -> None:
  if peer_id is None or conversation_message_id is None:
    return
  try:
    await delete_vk_message(
      peer_id=peer_id,
      conversation_message_id=conversation_message_id,
    )
  except Exception:
    return


def _format_tournament_name(tournament_type: str) -> str:
  return "Регулярный турнир" if tournament_type == "regular" else "Годовой турнир"


async def _submit_registration_request(
  *,
  user_id: int,
  name: str,
  success_message: str,
  linked_to_user: User | None = None,
  bank_name: str | None = None,
  tel_number: str | None = None,
  notification_platform: str | None = None,
) -> None:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    use_case = RequestRegistrationUseCase(repository)
    try:
      user = await use_case.execute(
        name=name,
        vk_id=user_id,
        bank_name=bank_name,
        tel_number=tel_number,
        notification_platform=notification_platform,
      )
    except UserIdentityRequiredError:
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_ID_ERROR.value)
      return
    except UserNameRequiredError:
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_EMPTY_NAME.value)
      return
    except UserAlreadyRegisteredError:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      existing_user = await repository.get_by_vk_id(user_id)
      keyboard = _approved_vk_keyboard(existing_user) if existing_user and existing_user.is_approved else new_user_keyboard
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_EXIST.value, keyboard=keyboard)
      return
    except UserRegistrationPendingError:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PENDING.value, keyboard=new_user_keyboard)
      return

    admin_ids = await repository.list_admin_vk_ids()
    tg_admin_chat_ids = await repository.list_admin_tg_ids()

  vk_user_states.pop(user_id, None)
  vk_user_contexts.pop(user_id, None)
  await notify_tg_admins_about_registration(
    name=name,
    telegram_id=None,
    vk_id=user_id,
    requester_platform="vk",
    admin_chat_ids=tg_admin_chat_ids,
    linked_to_user=linked_to_user,
    reply_markup=(
      tg_registration_link_review_keyboard(row_id=user.row_id)
      if linked_to_user is not None
      else tg_registration_review_keyboard(row_id=user.row_id)
    ),
  )
  await notify_admins_about_registration(
    name=name,
    vk_id=user_id,
    requester_platform="vk",
    admin_ids=admin_ids,
    linked_to_user=linked_to_user,
    keyboard=(
      vk_registration_link_review_keyboard(row_id=user.row_id)
      if linked_to_user is not None
      else vk_registration_review_keyboard(row_id=user.row_id)
    ),
  )
  await send_vk_message(user_id=user_id, message=success_message, keyboard=main_keyboard)


def _normalize_phone(value: str) -> str | None:
  digits = "".join(ch for ch in value if ch.isdigit())
  if digits.startswith("7") and len(digits) == 11:
    return f"+{digits}"
  return None


async def handle_user_message_event(event_object: dict) -> PlainTextResponse | None:
  user_id = event_object.get("user_id")
  peer_id = event_object.get("peer_id")
  event_id = event_object.get("event_id")
  conversation_message_id = event_object.get("conversation_message_id")
  callback_payload = event_object.get("payload") or {}
  action = callback_payload.get("action")
  if not user_id or not peer_id or not event_id:
    return PlainTextResponse("ok")

  if action == "registration_existing":
    selected_row_id = callback_payload.get("row_id")
    if not isinstance(selected_row_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      repository = UserRepository(session)
      selected_user = await repository.get_by_row_id(selected_row_id)
      if selected_user is None or not selected_user.is_approved or selected_user.vk_id is not None:
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=user_id,
          peer_id=peer_id,
          text=Text.user.REGISTRATION_CHOOSE_FROM_LIST.value,
        )
        return PlainTextResponse("ok")

    context = vk_user_contexts.setdefault(user_id, {})
    context["linked_user_row_id"] = str(selected_user.row_id)
    context["linked_user_name"] = selected_user.name
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_PLATFORM_PROMPT.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PLATFORM_PROMPT.value, keyboard=registration_platform_keyboard())
    return PlainTextResponse("ok")

  if action in {"registration_played_before_yes", "registration_played_before_no"}:
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    if action == "registration_played_before_yes":
      async with SessionFactory() as session:
        repository = UserRepository(session)
        candidates = await repository.list_approved_without_vk_id()
      vk_user_states.pop(user_id, None)
      if not candidates:
        vk_user_states[user_id] = WAITING_FOR_NEW_NAME
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=user_id,
          peer_id=peer_id,
          text=Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value,
        )
        await send_vk_message(
          user_id=user_id,
          message=Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value,
        )
        return PlainTextResponse("ok")
      await send_vk_message_event_answer(
        event_id=event_id,
        user_id=user_id,
        peer_id=peer_id,
        text=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
      )
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
        keyboard=registration_candidates_keyboard(users=candidates),
      )
      return PlainTextResponse("ok")

    vk_user_states[user_id] = WAITING_FOR_NEW_NAME
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=user_id,
      peer_id=peer_id,
      text=Text.user.REGISTRATION_NEW_NAME_PROMPT.value,
    )
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
    return PlainTextResponse("ok")

  if action == "registration_existing_page":
    page = callback_payload.get("page")
    if not isinstance(page, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      repository = UserRepository(session)
      candidates = await repository.list_approved_without_vk_id()
    if not candidates:
      await send_vk_message_event_answer(
        event_id=event_id,
        user_id=user_id,
        peer_id=peer_id,
        text=Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value,
      )
      await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value,
      )
      return PlainTextResponse("ok")
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=user_id,
      peer_id=peer_id,
      text=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
    )
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
      keyboard=registration_candidates_page_keyboard(users=candidates, page=page),
    )
    return PlainTextResponse("ok")

  if action == "registration_new_name":
    vk_user_states[user_id] = WAITING_FOR_NEW_NAME
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
    return PlainTextResponse("ok")

  if action in {"registration_platform_tg", "registration_platform_vk"}:
    context = vk_user_contexts.get(user_id, {})
    selected_name = context.get("linked_user_name")
    selected_row_id = context.get("linked_user_row_id")
    if not selected_name or not selected_row_id:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    platform = "tg" if action.endswith("_tg") else "vk"
    async with SessionFactory() as session:
      repository = UserRepository(session)
      linked_user = await repository.get_by_row_id(int(selected_row_id))
      if linked_user is None:
        await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
        return PlainTextResponse("ok")
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_WAIT.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await _submit_registration_request(
      user_id=user_id,
      name=selected_name,
      success_message=Text.user.REGISTRATION_WAIT.value,
      linked_to_user=linked_user,
      notification_platform=platform,
    )
    return PlainTextResponse("ok")

  if action == "registration_optional_bank":
    if "registration_name" not in vk_user_contexts.get(user_id, {}):
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    vk_user_states[user_id] = WAITING_FOR_OPTIONAL_BANK
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_BANK_PROMPT.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_BANK_PROMPT.value)
    return PlainTextResponse("ok")

  if action == "registration_optional_phone":
    if "registration_name" not in vk_user_contexts.get(user_id, {}):
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    vk_user_states[user_id] = WAITING_FOR_OPTIONAL_PHONE
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_PHONE_PROMPT.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PHONE_PROMPT.value)
    return PlainTextResponse("ok")

  if action == "registration_optional_skip":
    context = vk_user_contexts.get(user_id, {})
    registration_name = context.get("registration_name")
    if not registration_name:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_WAIT.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await _submit_registration_request(
      user_id=user_id,
      name=registration_name,
      success_message=Text.user.REGISTRATION_WAIT.value,
      bank_name=context.get("bank_name"),
      tel_number=context.get("tel_number"),
    )
    return PlainTextResponse("ok")

  if action in {"bet_tournament_regular", "bet_tournament_year"}:
    if not await _is_vk_user_approved(user_id):
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STATUS_PENDING.value)
      return PlainTextResponse("ok")
    tournament_type = "regular" if action.endswith("regular") else "year"
    async with SessionFactory() as session:
      use_case = BetUseCases(
        user_repository=UserRepository(session),
        poker_repository=PokerRepository(session),
        bet_repository=BetRepository(session),
        bet_param_repository=BetParamRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      bet_params, players, status = await use_case.get_bet_draft_data(
        better_id=user_id,
        tournament_type=tournament_type,
      )
    if status != "ok" or bet_params is None:
      await send_vk_message_event_answer(
        event_id=event_id,
        user_id=user_id,
        peer_id=peer_id,
        text=Text.user.BETTING_NOT_OPEN.value,
      )
      await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_NOT_OPEN.value, keyboard=betting_keyboard)
      return PlainTextResponse("ok")
    context = vk_user_contexts.setdefault(user_id, {})
    context["bet_tournament_type"] = tournament_type
    context["bet_players"] = "|".join([p.player_name for p in players])
    vk_user_states[user_id] = WAITING_FOR_BET_AMOUNT
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=user_id,
      peer_id=peer_id,
      text=Text.user.BETTING_SIZE_CHOOSE.value,
    )
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_SIZE_CHOOSE.value,
      keyboard=betting_size_keyboard(
        small_size_kopecks=bet_params.small_size_kopecks,
        big_size_kopecks=bet_params.big_size_kopecks,
      ),
    )
    return PlainTextResponse("ok")

  if action == "bet_size":
    if not await _is_vk_user_approved(user_id):
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STATUS_PENDING.value)
      return PlainTextResponse("ok")
    amount_kopecks = callback_payload.get("amount_kopecks")
    if not isinstance(amount_kopecks, int):
      return PlainTextResponse("ok")
    context = vk_user_contexts.setdefault(user_id, {})
    players_str = context.get("bet_players", "")
    players = [p for p in players_str.split("|") if p]
    if not players:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    context["bet_amount_kopecks"] = str(amount_kopecks)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_WINNER_CHOOSE.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_WINNER_CHOOSE.value,
      keyboard=betting_player_keyboard(action="winner", players=players),
    )
    return PlainTextResponse("ok")

  if action == "bet_winner":
    if not await _is_vk_user_approved(user_id):
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STATUS_PENDING.value)
      return PlainTextResponse("ok")
    winner_name = callback_payload.get("player_name")
    if not isinstance(winner_name, str):
      return PlainTextResponse("ok")
    context = vk_user_contexts.setdefault(user_id, {})
    players = [p for p in context.get("bet_players", "").split("|") if p]
    if winner_name not in players:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    context["bet_winner_name"] = winner_name
    losers = [p for p in players if p != winner_name]
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_LOSER_CHOOSE.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_LOSER_CHOOSE.value,
      keyboard=betting_player_keyboard(action="loser", players=losers),
    )
    return PlainTextResponse("ok")

  if action == "bet_loser":
    if not await _is_vk_user_approved(user_id):
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STATUS_PENDING.value)
      return PlainTextResponse("ok")
    loser_name = callback_payload.get("player_name")
    if not isinstance(loser_name, str):
      return PlainTextResponse("ok")
    context = vk_user_contexts.setdefault(user_id, {})
    winner_name = context.get("bet_winner_name")
    if not winner_name or winner_name == loser_name:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    context["bet_loser_name"] = loser_name
    tournament_type = context.get("bet_tournament_type", "regular")
    amount_kopecks = int(context.get("bet_amount_kopecks", "0"))
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_CONFIRM.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_CONFIRM.value.format(
        tournament=_format_tournament_name(tournament_type),
        amount_rub=amount_kopecks // 100,
        winner=winner_name,
        loser=loser_name,
      ),
      keyboard=betting_confirm_keyboard(),
    )
    return PlainTextResponse("ok")

  if action in {"bet_confirm_yes", "bet_confirm_no"}:
    if not await _is_vk_user_approved(user_id):
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STATUS_PENDING.value)
      return PlainTextResponse("ok")
    if action.endswith("_no"):
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_MENU.value)
      await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_MENU.value, keyboard=betting_keyboard)
      return PlainTextResponse("ok")
    context = vk_user_contexts.get(user_id, {})
    tournament_type = context.get("bet_tournament_type")
    winner_name = context.get("bet_winner_name")
    loser_name = context.get("bet_loser_name")
    amount_kopecks = int(context.get("bet_amount_kopecks", "0"))
    if tournament_type not in {"regular", "year"} or not winner_name or not loser_name or amount_kopecks <= 0:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      use_case = BetUseCases(
        user_repository=UserRepository(session),
        poker_repository=PokerRepository(session),
        bet_repository=BetRepository(session),
        bet_param_repository=BetParamRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      created, status = await use_case.create_bet(
        better_id=user_id,
        tournament_type=tournament_type,
        amount_kopecks=amount_kopecks,
        winner_name=winner_name,
        loser_name=loser_name,
      )
    vk_user_states.pop(user_id, None)
    vk_user_contexts.pop(user_id, None)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    if status == "already_bet":
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_ALREADY_EXISTS.value, keyboard=betting_keyboard)
    elif status in {"betting_closed", "user_not_approved", "invalid_tournament", "missing_params"}:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_NOT_OPEN.value, keyboard=betting_keyboard)
    elif status == "invalid_amount" or created is None:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_AMOUNT_INVALID.value)
    else:
      await send_vk_message(
        user_id=user_id,
        message=Text.user.BETTING_CREATED.value.format(
          tournament=_format_tournament_name(tournament_type),
          amount_rub=amount_kopecks // 100,
        ),
        keyboard=betting_keyboard,
      )
    return PlainTextResponse("ok")

  if action == "betstat_page":
    page = callback_payload.get("page")
    if not isinstance(page, int):
      return PlainTextResponse("ok")
    user_ctx = vk_user_contexts.get(user_id, {})
    mode = user_ctx.get("betstat_mode", "all")
    selected_ids = [int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x]
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    if mode != "all":
      indicators = [item for item in indicators if item.for_current_tournaments in {"yes", "only"}]
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_STAT_INDICATORS.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_STAT_INDICATORS.value,
      keyboard=betting_stat_indicators_keyboard(indicators=indicators, page=page, selected_ids=selected_ids),
    )
    return PlainTextResponse("ok")

  if action == "betstat_toggle":
    indicator_id = callback_payload.get("indicator_id")
    page = callback_payload.get("page", 0)
    if not isinstance(indicator_id, int):
      return PlainTextResponse("ok")
    mode = vk_user_contexts.get(user_id, {}).get("betstat_mode", "all")
    selected = {int(x) for x in vk_user_contexts.get(user_id, {}).get("betstat_selected_ids", "").split(",") if x}
    if indicator_id in selected:
      selected.remove(indicator_id)
    else:
      selected.add(indicator_id)
    vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ",".join(str(x) for x in sorted(selected))
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    if mode != "all":
      indicators = [item for item in indicators if item.for_current_tournaments in {"yes", "only"}]
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_STAT_INDICATORS.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_STAT_INDICATORS.value,
      keyboard=betting_stat_indicators_keyboard(indicators=indicators, page=int(page) if isinstance(page, int) else 0, selected_ids=list(selected)),
    )
    return PlainTextResponse("ok")

  if action == "betstat_done":
    user_ctx = vk_user_contexts.get(user_id, {})
    mode = user_ctx.get("betstat_mode", "all")
    selected_ids = {int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x}
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
      if mode != "all":
        indicators = [item for item in indicators if item.for_current_tournaments in {"yes", "only"}]
      selected = [item for item in indicators if int(item.row_id) in selected_ids]
      report = await StatUseCases(
        bet_repository=BetRepository(session),
        achievement_repository=AchievementRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_repository=PokerRepository(session),
      ).get_betting_stat(indicators=selected, mode=mode)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_STAT_REPORT.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.BETTING_STAT_REPORT.value.format(report=report))
    return PlainTextResponse("ok")

  if action == "betstat_mode":
    mode = callback_payload.get("mode")
    if mode not in {"all", "regular", "year"}:
      return PlainTextResponse("ok")
    vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = mode
    vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    if mode != "all":
      indicators = [item for item in indicators if item.for_current_tournaments in {"yes", "only"}]
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_STAT_INDICATORS.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    if not indicators:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_CURRENT_EMPTY.value)
      return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_STAT_INDICATORS.value,
      keyboard=betting_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
    )
    return PlainTextResponse("ok")

  if action == "pokerstat_page":
    page = callback_payload.get("page")
    if not isinstance(page, int):
      return PlainTextResponse("ok")
    selected_ids = [int(x) for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",") if x]
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.POKER_STAT_INDICATORS.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.POKER_STAT_INDICATORS.value,
      keyboard=poker_stat_indicators_keyboard(indicators=indicators, page=page, selected_ids=selected_ids),
    )
    return PlainTextResponse("ok")

  if action == "pokerstat_toggle":
    indicator_id = callback_payload.get("indicator_id")
    page = callback_payload.get("page", 0)
    if not isinstance(indicator_id, int):
      return PlainTextResponse("ok")
    selected = {int(x) for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",") if x}
    if indicator_id in selected:
      selected.remove(indicator_id)
    else:
      selected.add(indicator_id)
    vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ",".join(str(x) for x in sorted(selected))
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.POKER_STAT_INDICATORS.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.POKER_STAT_INDICATORS.value,
      keyboard=poker_stat_indicators_keyboard(indicators=indicators, page=int(page) if isinstance(page, int) else 0, selected_ids=list(selected)),
    )
    return PlainTextResponse("ok")

  if action == "pokerstat_done":
    selected_ids = {int(x) for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",") if x}
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
      selected = [item for item in indicators if int(item.row_id) in selected_ids]
      report = await StatUseCases(
        bet_repository=BetRepository(session),
        poker_data_repository=PokerDataRepository(session),
        achievement_repository=AchievementRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_repository=PokerRepository(session),
      ).get_poker_stat(indicators=selected)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.POKER_STAT_REPORT.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.POKER_STAT_REPORT.value.format(report=report), keyboard=poker_keyboard)
    return PlainTextResponse("ok")

  return None


async def handle_user_message_new(*, user_id: int, text: str) -> PlainTextResponse | None:
  if text in {
    Buttons.main.BETTING.value,
    Buttons.betting.TO_MAIN.value,
    Buttons.betting.CURRENT_TOURS.value,
    Buttons.betting.BETTING_STAT.value,
    Buttons.betting.MAKE_BET.value,
    Buttons.main.ROOM.value,
    Buttons.room.STATUS.value,
    Buttons.main.ADMIN.value,
    Buttons.admin_main.TO_MAIN.value,
    Buttons.main.POKER.value,
    Buttons.poker.TO_MAIN.value,
    Buttons.poker.POKER_INFO.value,
    Buttons.poker.POKER_STAT.value,
  }:
    user = await _get_vk_user(user_id)
    if user is None:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    if not user.is_approved:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")

  if text == Buttons.main.ADMIN.value:
    user = await _get_vk_user(user_id)
    if user is None or not user.is_approved:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    if not user.is_admin:
      await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value, keyboard=main_keyboard)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=Text.admin.POKER_PARAMS_CHOOSE.value, keyboard=admin_main_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.admin_main.TO_MAIN.value:
    user = await _get_vk_user(user_id)
    if user is None:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    if not user.is_approved:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=Text.user.BETTING_MENU.value, keyboard=_approved_vk_keyboard(user))
    return PlainTextResponse("ok")

  if text == Buttons.main.BETTING.value:
    await send_vk_message(user_id=user_id, message=Text.user.BETTING_MENU.value, keyboard=betting_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.main.POKER.value:
    await send_vk_message(user_id=user_id, message=Text.user.POKER_MENU.value, keyboard=poker_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.betting.TO_MAIN.value:
    await send_vk_message(user_id=user_id, message=Text.user.BETTING_MENU.value, keyboard=main_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.poker.TO_MAIN.value:
    user = await _get_vk_user(user_id)
    if user is None:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=Text.user.BETTING_MENU.value, keyboard=_approved_vk_keyboard(user))
    return PlainTextResponse("ok")

  if text == Buttons.poker.POKER_INFO.value:
    await send_vk_message(user_id=user_id, message=Text.user.POKER_INFO.value, keyboard=poker_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.poker.POKER_STAT.value:
    vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ""
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    if not indicators:
      await send_vk_message(user_id=user_id, message=Text.user.POKER_STAT_REPORT.value.format(report="Нет данных по покеру."))
      return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.user.POKER_STAT_INDICATORS.value,
      keyboard=poker_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
    )
    return PlainTextResponse("ok")

  if text == Buttons.betting.CURRENT_TOURS.value:
    async with SessionFactory() as session:
      use_case = BetUseCases(
        user_repository=UserRepository(session),
        poker_repository=PokerRepository(session),
        bet_repository=BetRepository(session),
        bet_param_repository=BetParamRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      tournaments = await use_case.list_current_tournaments_with_banks()
      bets = await use_case.list_user_bets_for_current_poker(better_id=user_id)
    if not tournaments:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_CURRENT_EMPTY.value)
      return PlainTextResponse("ok")
    tournament_lines = [f"• {_format_tournament_name(t)} — банк {bank_kopecks // 100} ₽" for t, bank_kopecks in tournaments]
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_CURRENT_LIST.value.format(tournaments="\n".join(tournament_lines)),
    )
    if bets:
      bet_lines = [f"• {_format_tournament_name(b.tournament_type)} — {b.amount_kopecks // 100} ₽" for b in bets]
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_USER_BETS.value.format(bets="\n".join(bet_lines)))
    else:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_USER_BETS_EMPTY.value)
    return PlainTextResponse("ok")

  if text == Buttons.betting.BETTING_STAT.value:
    vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
    vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = "all"
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_STAT_MODE.value,
      keyboard=betting_stat_mode_keyboard(),
    )
    return PlainTextResponse("ok")

  if text == Buttons.betting.MAKE_BET.value:
    async with SessionFactory() as session:
      use_case = BetUseCases(
        user_repository=UserRepository(session),
        poker_repository=PokerRepository(session),
        bet_repository=BetRepository(session),
        bet_param_repository=BetParamRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      tournaments = await use_case.list_current_tournaments()
    if not tournaments:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_NOT_OPEN.value)
      return PlainTextResponse("ok")
    vk_user_states[user_id] = WAITING_FOR_BET_AMOUNT
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_TOURNAMENT_CHOOSE.value,
      keyboard=betting_tournament_keyboard(),
    )
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_BET_AMOUNT:
    await send_vk_message(user_id=user_id, message=Text.user.BETTING_SIZE_CHOOSE.value)
    return PlainTextResponse("ok")

  if text == Buttons.main.ROOM.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      user = await user_repository.get_by_vk_id(user_id)
      if user is None:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value)
        return PlainTextResponse("ok")
      if not user.is_approved:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_PENDING.value)
        return PlainTextResponse("ok")

      use_case = ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      players = await use_case.list_active_poker_players()
      if players:
        already_in_room = any(int(item.player_id) == int(user_id) for item in players)
        if already_in_room:
          await send_vk_message(user_id=user_id, message=Text.user.ROOM_ALREADY_JOINED.value)
          return PlainTextResponse("ok")

      created = await use_case.add_player_to_active_poker(
        player_id=int(user_id),
        player_name=user.name,
      )
      if created is None:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_CLOSED.value)
        return PlainTextResponse("ok")

    await send_vk_message(user_id=user_id, message=Text.user.ROOM_JOINED.value)
    return PlainTextResponse("ok")

  if text == Buttons.room.STATUS.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      user = await user_repository.get_by_vk_id(user_id)
      if user is None:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value)
        return PlainTextResponse("ok")
      if not user.is_approved:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_PENDING.value)
        return PlainTextResponse("ok")

      use_case = ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
      )
      players = await use_case.list_active_poker_players()
      if not players:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_CLOSED.value)
        return PlainTextResponse("ok")

      player = next((item for item in players if int(item.player_id) == int(user_id)), None)
      if player is None:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_NOT_ADDED.value)
        return PlainTextResponse("ok")

    await send_vk_message(user_id=user_id, message=Text.user.STATUS_BUYINS.value.format(buyins=player.buyins))
    return PlainTextResponse("ok")

  if text == Buttons.new_user.REGISTRATION.value:
    if vk_user_states.get(user_id) in {
      WAITING_FOR_PLAYED_BEFORE,
      WAITING_FOR_NEW_NAME,
      WAITING_FOR_OPTIONAL_DETAILS_ACTION,
      WAITING_FOR_OPTIONAL_BANK,
      WAITING_FOR_OPTIONAL_PHONE,
    }:
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_IN_PROGRESS.value)
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      repository = UserRepository(session)
      existing_user = await repository.get_by_vk_id(user_id)
    if existing_user is not None:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_EXIST.value if existing_user.is_approved else Text.user.REGISTRATION_PENDING.value,
        keyboard=_approved_vk_keyboard(existing_user) if existing_user.is_approved else new_user_keyboard,
      )
      return PlainTextResponse("ok")
    vk_user_states[user_id] = WAITING_FOR_PLAYED_BEFORE
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PLAYED_BEFORE_Q.value, keyboard=played_before_keyboard())
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_PLAYED_BEFORE:
    normalized_text = text.lower()
    if normalized_text == Buttons.registration_inline.YES.value.lower():
      async with SessionFactory() as session:
        repository = UserRepository(session)
        candidates = await repository.list_approved_without_vk_id()
      vk_user_states.pop(user_id, None)
      if not candidates:
        vk_user_states[user_id] = WAITING_FOR_NEW_NAME
        await send_vk_message(
          user_id=user_id,
          message=Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value,
        )
        return PlainTextResponse("ok")
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
        keyboard=registration_candidates_keyboard(users=candidates),
      )
      return PlainTextResponse("ok")
    if normalized_text == Buttons.registration_inline.NO.value.lower():
      vk_user_states[user_id] = WAITING_FOR_NEW_NAME
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PLAYED_BEFORE_Q.value, keyboard=played_before_keyboard())
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_NEW_NAME:
    name = " ".join(text.split())
    vk_user_states[user_id] = WAITING_FOR_OPTIONAL_DETAILS_ACTION
    vk_user_contexts[user_id] = {"registration_name": name, "bank_name": "", "tel_number": ""}
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_OPTIONAL_DETAILS_PROMPT.value,
      keyboard=registration_optional_details_keyboard(),
    )
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_OPTIONAL_BANK:
    bank_name = " ".join(text.split()).title()
    if not bank_name:
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_BANK_PROMPT.value)
      return PlainTextResponse("ok")
    context = vk_user_contexts.setdefault(user_id, {})
    context["bank_name"] = bank_name
    existing_phone = context.get("tel_number")
    if existing_phone:
      registration_name = context.get("registration_name")
      if not registration_name:
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_READ_ERROR.value)
        return PlainTextResponse("ok")
      await _submit_registration_request(
        user_id=user_id,
        name=registration_name,
        success_message=Text.user.REGISTRATION_WAIT.value,
        bank_name=bank_name,
        tel_number=existing_phone,
      )
      return PlainTextResponse("ok")
    vk_user_states[user_id] = WAITING_FOR_OPTIONAL_PHONE
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PHONE_PROMPT.value)
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_OPTIONAL_PHONE:
    normalized_phone = _normalize_phone(text)
    if normalized_phone is None:
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PHONE_INVALID.value)
      return PlainTextResponse("ok")
    context = vk_user_contexts.setdefault(user_id, {})
    context["tel_number"] = normalized_phone
    existing_bank = context.get("bank_name")
    if existing_bank:
      registration_name = context.get("registration_name")
      if not registration_name:
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_READ_ERROR.value)
        return PlainTextResponse("ok")
      await _submit_registration_request(
        user_id=user_id,
        name=registration_name,
        success_message=Text.user.REGISTRATION_WAIT.value,
        bank_name=existing_bank,
        tel_number=normalized_phone,
      )
      return PlainTextResponse("ok")
    vk_user_states[user_id] = WAITING_FOR_OPTIONAL_BANK
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_BANK_PROMPT.value)
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_OPTIONAL_DETAILS_ACTION:
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_OPTIONAL_DETAILS_PROMPT.value,
      keyboard=registration_optional_details_keyboard(),
    )
    return PlainTextResponse("ok")

  return None
