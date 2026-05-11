from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import (
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserNameRequiredError,
  UserRegistrationPendingError,
)
from app.application.use_cases.user.request_registration import RequestRegistrationUseCase
from app.application.use_cases.poker.bet import BetUseCases
from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
  main_keyboard,
  betting_keyboard,
  betting_tournament_keyboard,
  played_before_keyboard,
  registration_candidates_keyboard,
  registration_candidates_page_keyboard,
  registration_link_review_keyboard,
  registration_optional_details_keyboard,
  registration_platform_keyboard,
  registration_review_keyboard,
)
from app.bot.telegram.notifications import notify_admins_about_registration
from app.bot.telegram.states import RegistrationState
from app.bot.vk.keyboards import (
  registration_link_review_keyboard as vk_registration_link_review_keyboard,
  registration_review_keyboard as vk_registration_review_keyboard,
)
from app.bot.vk.notifications import notify_admins_about_registration as notify_vk_admins_about_registration
from app.db.models.user import User
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

router = Router()


async def _clear_inline_keyboard(callback: CallbackQuery) -> None:
  if callback.message is None:
    return
  try:
    await callback.message.edit_reply_markup(reply_markup=None)
  except Exception:
    return


async def _delete_message_if_possible(callback: CallbackQuery) -> None:
  if callback.message is None:
    return
  try:
    await callback.message.delete()
  except Exception:
    return


REGISTRATION_USER_STATES = {
  RegistrationState.waiting_for_played_before_answer.state,
  RegistrationState.waiting_for_new_name.state,
  RegistrationState.waiting_for_registration_platform_choice.state,
  RegistrationState.waiting_for_optional_details_action.state,
  RegistrationState.waiting_for_bank_name.state,
  RegistrationState.waiting_for_phone.state,
}


def _format_tournament_name(tournament_type: str) -> str:
  return "Регулярный турнир" if tournament_type == "regular" else "Годовой турнир"


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
  await state.clear()
  await message.answer(
    Text.user.BOT_INFO.value,
    reply_markup=main_keyboard,
  )


@router.message(F.text == Buttons.new_user.REGISTRATION.value)
async def start_registration(message: Message, state: FSMContext) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
    return

  current_state = await state.get_state()
  if current_state in REGISTRATION_USER_STATES:
    await message.answer(Text.user.REGISTRATION_IN_PROGRESS.value)
    return

  async with SessionFactory() as session:
    repository = UserRepository(session)
    existing_user = await repository.get_by_telegram_id(message.from_user.id)

  if existing_user is not None:
    await state.clear()
    if existing_user.is_approved:
      await message.answer(Text.user.REGISTRATION_EXIST.value, reply_markup=main_keyboard)
      return
    await message.answer(Text.user.REGISTRATION_PENDING.value, reply_markup=main_keyboard)
    return

  await state.set_state(RegistrationState.waiting_for_played_before_answer)
  await message.answer(
    Text.user.REGISTRATION_PLAYED_BEFORE_Q.value,
    reply_markup=played_before_keyboard(),
  )


@router.message(F.text == Buttons.room.STATUS.value)
async def show_user_status(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
    return

  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    user = await user_repository.get_by_telegram_id(message.from_user.id)
    if user is None:
      await message.answer(Text.user.STATUS_NEED_REGISTRATION.value)
      return
    if not user.is_approved:
      await message.answer(Text.user.STATUS_PENDING.value)
      return

    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    players = await use_case.list_active_poker_players()
    if not players:
      await message.answer(Text.user.STATUS_ROOM_CLOSED.value)
      return

    player = next((item for item in players if int(item.player_id) == int(message.from_user.id)), None)
    if player is None:
      await message.answer(Text.user.STATUS_ROOM_NOT_ADDED.value)
      return

  await message.answer(Text.user.STATUS_BUYINS.value.format(buyins=player.buyins))


@router.message(F.text == Buttons.main.ROOM.value)
async def join_poker_room(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
    return

  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    user = await user_repository.get_by_telegram_id(message.from_user.id)
    if user is None:
      await message.answer(Text.user.STATUS_NEED_REGISTRATION.value)
      return
    if not user.is_approved:
      await message.answer(Text.user.STATUS_PENDING.value)
      return

    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    players = await use_case.list_active_poker_players()
    if players:
      already_in_room = any(int(item.player_id) == int(message.from_user.id) for item in players)
      if already_in_room:
        await message.answer(Text.user.ROOM_ALREADY_JOINED.value)
        return
    created = await use_case.add_player_to_active_poker(
      player_id=int(message.from_user.id),
      player_name=user.name,
    )
    if created is None:
      await message.answer(Text.user.STATUS_ROOM_CLOSED.value)
      return

  await message.answer(Text.user.ROOM_JOINED.value)


@router.message(F.text == Buttons.main.BETTING.value)
async def open_betting_menu(message: Message) -> None:
  await message.answer(Text.user.BETTING_MENU.value, reply_markup=betting_keyboard)


@router.message(F.text == Buttons.betting.TO_MAIN.value)
async def back_to_main_from_betting(message: Message) -> None:
  await message.answer(Text.user.BETTING_MENU.value, reply_markup=main_keyboard)


@router.message(F.text == Buttons.betting.CURRENT_TOURS.value)
async def show_current_betting_tournaments(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
    return
  async with SessionFactory() as session:
    use_case = BetUseCases(
      user_repository=UserRepository(session),
      poker_repository=PokerRepository(session),
      bet_repository=BetRepository(session),
      bet_tournament_repository=BetTournamentRepository(session),
      bet_tournament_param_repository=BetTournamentParamRepository(session),
    )
    tournaments = await use_case.list_current_tournaments_with_banks()
    bets = await use_case.list_user_bets_for_current_poker(better_id=message.from_user.id)

  if not tournaments:
    await message.answer(Text.user.BETTING_CURRENT_EMPTY.value)
    return

  tournament_lines = [
    f"• {_format_tournament_name(tournament)} — банк {bank_kopecks // 100} ₽"
    for tournament, bank_kopecks in tournaments
  ]
  await message.answer(Text.user.BETTING_CURRENT_LIST.value.format(tournaments="\n".join(tournament_lines)))

  if bets:
    bet_lines = [
      f"• {_format_tournament_name(bet.tournament_type)} — {bet.amount_kopecks // 100} ₽"
      for bet in bets
    ]
    await message.answer(Text.user.BETTING_USER_BETS.value.format(bets="\n".join(bet_lines)))
  else:
    await message.answer(Text.user.BETTING_USER_BETS_EMPTY.value)


@router.message(F.text == Buttons.betting.MAKE_BET.value)
async def start_make_bet(message: Message, state: FSMContext) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
    return

  async with SessionFactory() as session:
    use_case = BetUseCases(
      user_repository=UserRepository(session),
      poker_repository=PokerRepository(session),
      bet_repository=BetRepository(session),
      bet_tournament_repository=BetTournamentRepository(session),
      bet_tournament_param_repository=BetTournamentParamRepository(session),
    )
    tournaments = await use_case.list_current_tournaments()

  if not tournaments:
    await message.answer(Text.user.BETTING_NOT_OPEN.value)
    return

  await state.set_state(RegistrationState.waiting_for_bet_amount)
  await message.answer(
    Text.user.BETTING_TOURNAMENT_CHOOSE.value,
    reply_markup=betting_tournament_keyboard(),
  )


async def _submit_registration_request(
  *,
  message: Message,
  state: FSMContext,
  name: str,
  success_text: str,
  linked_to_user: User | None = None,
  requester_telegram_id: int | None = None,
  bank_name: str | None = None,
  tel_number: str | None = None,
  notification_platform: str | None = None,
) -> None:
  telegram_id = requester_telegram_id if requester_telegram_id is not None else (
    message.from_user.id if message.from_user is not None else None
  )
  if telegram_id is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
    return

  async with SessionFactory() as session:
    repository = UserRepository(session)
    use_case = RequestRegistrationUseCase(repository)

    try:
      user = await use_case.execute(
        name=name,
        telegram_id=telegram_id,
        bank_name=bank_name,
        tel_number=tel_number,
        notification_platform=notification_platform,
      )
    except UserIdentityRequiredError:
      await message.answer(Text.user.REGISTRATION_ID_ERROR.value)
      return
    except UserNameRequiredError:
      await message.answer(Text.user.REGISTRATION_EMPTY_NAME.value)
      return
    except UserAlreadyRegisteredError:
      await message.answer(Text.user.REGISTRATION_EXIST.value, reply_markup=main_keyboard)
      await state.clear()
      return
    except UserRegistrationPendingError:
      await message.answer(
        Text.user.REGISTRATION_PENDING.value,
        reply_markup=main_keyboard,
      )
      await state.clear()
      return

    tg_admin_chat_ids = await repository.list_admin_tg_ids()
    vk_admin_ids = await repository.list_admin_vk_ids()

  await notify_admins_about_registration(
    name=name,
    telegram_id=telegram_id,
    vk_id=None,
    requester_platform="tg",
    admin_chat_ids=tg_admin_chat_ids,
    linked_to_user=linked_to_user,
    reply_markup=(
      registration_link_review_keyboard(row_id=user.row_id)
      if linked_to_user is not None
      else registration_review_keyboard(row_id=user.row_id)
    ),
  )
  await notify_vk_admins_about_registration(
    name=name,
    vk_id=None,
    telegram_id=telegram_id,
    requester_platform="tg",
    admin_ids=vk_admin_ids,
    linked_to_user=linked_to_user,
    keyboard=(
      vk_registration_link_review_keyboard(row_id=user.row_id)
      if linked_to_user is not None
      else vk_registration_review_keyboard(row_id=user.row_id)
    ),
  )
  await state.clear()
  await message.answer(
    success_text,
    reply_markup=main_keyboard,
  )


@router.callback_query(F.data.startswith("registration_played_before:"))
async def choose_registration_branch(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  choice = callback.data.split(":", 1)[1]
  if choice == "yes":
    await _clear_inline_keyboard(callback)
    async with SessionFactory() as session:
      repository = UserRepository(session)
      candidates = await repository.list_approved_without_telegram_id()

    await state.clear()
    await callback.message.edit_text(
      Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
      reply_markup=registration_candidates_keyboard(users=candidates),
    )
  else:
    await _clear_inline_keyboard(callback)
    await state.set_state(RegistrationState.waiting_for_new_name)
    await callback.message.edit_text(Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
  await callback.answer()


@router.message(RegistrationState.waiting_for_played_before_answer)
async def repeat_registration_branch_prompt(message: Message) -> None:
  await message.answer(
    Text.user.REGISTRATION_PLAYED_BEFORE_Q.value,
    reply_markup=played_before_keyboard(),
  )


@router.callback_query(F.data.startswith("registration_existing:"))
async def finish_existing_row_id_registration(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None or callback.from_user is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return

  selected_value = callback.data.split(":", 1)[1]
  await _delete_message_if_possible(callback)
  if selected_value == "new":
    await state.set_state(RegistrationState.waiting_for_new_name)
    if callback.message is not None:
      await callback.message.answer(Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
    await callback.answer()
    return

  selected_row_id = int(selected_value)
  async with SessionFactory() as session:
    repository = UserRepository(session)
    selected_user = await repository.get_by_row_id(selected_row_id)
    if (
      selected_user is None
      or not selected_user.is_approved
      or selected_user.telegram_id is not None
    ):
      await callback.answer(Text.user.REGISTRATION_CHOOSE_FROM_LIST.value, show_alert=True)
      return

  await state.set_state(RegistrationState.waiting_for_registration_platform_choice)
  await state.update_data(
    linked_user_row_id=selected_user.row_id,
    linked_user_name=selected_user.name,
  )
  if callback.message is not None:
    await callback.message.answer(
      Text.user.REGISTRATION_PLATFORM_PROMPT.value,
      reply_markup=registration_platform_keyboard(),
    )
  await callback.answer()


@router.callback_query(F.data.startswith("registration_existing_page:"))
async def registration_existing_page(callback: CallbackQuery) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  page = int(callback.data.split(":", 1)[1])
  async with SessionFactory() as session:
    repository = UserRepository(session)
    candidates = await repository.list_approved_without_telegram_id()
  await callback.message.edit_text(
    Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
    reply_markup=registration_candidates_page_keyboard(users=candidates, page=page),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("registration_platform:"))
async def choose_registration_platform(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None or callback.from_user is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  await _delete_message_if_possible(callback)
  platform = callback.data.split(":", 1)[1]
  if platform not in {"tg", "vk"}:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return

  data = await state.get_data()
  selected_name = data.get("linked_user_name")
  selected_row_id = data.get("linked_user_row_id")
  if not selected_name or not selected_row_id:
    await state.clear()
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return

  async with SessionFactory() as session:
    repository = UserRepository(session)
    linked_user = await repository.get_by_row_id(int(selected_row_id))
    if linked_user is None:
      await state.clear()
      await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
      return

  await _submit_registration_request(
    message=callback.message,
    state=state,
    name=selected_name,
    success_text=Text.user.REGISTRATION_WAIT.value,
    linked_to_user=linked_user,
    requester_telegram_id=callback.from_user.id,
    notification_platform=platform,
  )
  await callback.answer()


@router.message(RegistrationState.waiting_for_new_name)
async def finish_registration(message: Message, state: FSMContext) -> None:
  if message.from_user is None or not message.text:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
    return

  name = " ".join(message.text.split())
  await state.set_state(RegistrationState.waiting_for_optional_details_action)
  await state.update_data(
    registration_name=name,
    bank_name=None,
    tel_number=None,
  )
  await message.answer(
    Text.user.REGISTRATION_OPTIONAL_DETAILS_PROMPT.value,
    reply_markup=registration_optional_details_keyboard(),
  )


def _normalize_phone(value: str) -> str | None:
  digits = "".join(ch for ch in value if ch.isdigit())
  if digits.startswith("7") and len(digits) == 11:
    return f"+{digits}"
  return None


@router.callback_query(F.data.startswith("registration_optional:"))
async def choose_optional_registration_data(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None or callback.from_user is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return

  action = callback.data.split(":", 1)[1]
  await _clear_inline_keyboard(callback)
  if action == "bank":
    await state.set_state(RegistrationState.waiting_for_bank_name)
    await callback.message.answer(Text.user.REGISTRATION_BANK_PROMPT.value)
    await callback.answer()
    return
  if action == "phone":
    await state.set_state(RegistrationState.waiting_for_phone)
    await callback.message.answer(Text.user.REGISTRATION_PHONE_PROMPT.value)
    await callback.answer()
    return

  data = await state.get_data()
  registration_name = data.get("registration_name")
  if not registration_name:
    await state.clear()
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  await _submit_registration_request(
    message=callback.message,
    state=state,
    name=registration_name,
    success_text=Text.user.REGISTRATION_WAIT.value,
    requester_telegram_id=callback.from_user.id,
    bank_name=data.get("bank_name"),
    tel_number=data.get("tel_number"),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("bet_tournament:"))
async def choose_bet_tournament(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  tournament_type = callback.data.split(":", 1)[1]
  if tournament_type not in {"regular", "year"}:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  await _clear_inline_keyboard(callback)
  await state.set_state(RegistrationState.waiting_for_bet_amount)
  await state.update_data(bet_tournament_type=tournament_type)
  await callback.message.answer(Text.user.BETTING_AMOUNT_PROMPT.value)
  await callback.answer()


@router.message(RegistrationState.waiting_for_bet_amount)
async def save_bet_amount(message: Message, state: FSMContext) -> None:
  if message.from_user is None or not message.text:
    await message.answer(Text.user.BETTING_AMOUNT_PROMPT.value)
    return
  amount_text = "".join(ch for ch in message.text if ch.isdigit())
  if not amount_text:
    await message.answer(Text.user.BETTING_AMOUNT_INVALID.value)
    return
  amount_rub = int(amount_text)
  if amount_rub <= 0:
    await message.answer(Text.user.BETTING_AMOUNT_INVALID.value)
    return

  data = await state.get_data()
  tournament_type = data.get("bet_tournament_type")
  if tournament_type not in {"regular", "year"}:
    await state.clear()
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
    return

  async with SessionFactory() as session:
    use_case = BetUseCases(
      user_repository=UserRepository(session),
      poker_repository=PokerRepository(session),
      bet_repository=BetRepository(session),
      bet_tournament_repository=BetTournamentRepository(session),
      bet_tournament_param_repository=BetTournamentParamRepository(session),
    )
    created, status = await use_case.create_bet(
      better_id=message.from_user.id,
      tournament_type=tournament_type,
      amount_kopecks=amount_rub * 100,
    )

  if status == "already_bet":
    await message.answer(Text.user.BETTING_ALREADY_EXISTS.value)
    await state.clear()
    return
  if status in {"betting_closed", "user_not_approved", "invalid_tournament"}:
    await message.answer(Text.user.BETTING_NOT_OPEN.value)
    await state.clear()
    return
  if status == "invalid_amount" or created is None:
    await message.answer(Text.user.BETTING_AMOUNT_INVALID.value)
    return

  await message.answer(
    Text.user.BETTING_CREATED.value.format(
      tournament=_format_tournament_name(tournament_type),
      amount_rub=amount_rub,
    ),
    reply_markup=betting_keyboard,
  )
  await state.clear()


@router.message(RegistrationState.waiting_for_bank_name)
async def save_optional_bank_name(message: Message, state: FSMContext) -> None:
  if not message.text:
    await message.answer(Text.user.REGISTRATION_BANK_PROMPT.value)
    return
  bank_name = " ".join(message.text.split()).title()
  if not bank_name:
    await message.answer(Text.user.REGISTRATION_BANK_PROMPT.value)
    return
  data = await state.get_data()
  await state.update_data(bank_name=bank_name)
  existing_phone = data.get("tel_number")
  if existing_phone:
    registration_name = data.get("registration_name")
    if not registration_name:
      await state.clear()
      await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
      return
    await _submit_registration_request(
      message=message,
      state=state,
      name=registration_name,
      success_text=Text.user.REGISTRATION_WAIT.value,
      bank_name=bank_name,
      tel_number=existing_phone,
    )
    return

  await state.set_state(RegistrationState.waiting_for_phone)
  await message.answer(Text.user.REGISTRATION_PHONE_PROMPT.value)


@router.message(RegistrationState.waiting_for_phone)
async def save_optional_phone(message: Message, state: FSMContext) -> None:
  if not message.text:
    await message.answer(Text.user.REGISTRATION_PHONE_PROMPT.value)
    return
  normalized_phone = _normalize_phone(message.text)
  if normalized_phone is None:
    await message.answer(Text.user.REGISTRATION_PHONE_INVALID.value)
    return
  data = await state.get_data()
  await state.update_data(tel_number=normalized_phone)
  existing_bank = data.get("bank_name")
  if existing_bank:
    registration_name = data.get("registration_name")
    if not registration_name:
      await state.clear()
      await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
      return
    await _submit_registration_request(
      message=message,
      state=state,
      name=registration_name,
      success_text=Text.user.REGISTRATION_WAIT.value,
      bank_name=existing_bank,
      tel_number=normalized_phone,
    )
    return

  await state.set_state(RegistrationState.waiting_for_bank_name)
  await message.answer(Text.user.REGISTRATION_BANK_PROMPT.value)


@router.message(RegistrationState.waiting_for_optional_details_action)
async def repeat_optional_registration_prompt(message: Message) -> None:
  await message.answer(
    Text.user.REGISTRATION_OPTIONAL_DETAILS_PROMPT.value,
    reply_markup=registration_optional_details_keyboard(),
  )
