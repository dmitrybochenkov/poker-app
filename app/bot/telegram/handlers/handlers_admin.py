from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

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
from app.application.use_cases.user.reject_user import RejectUserUseCase
from app.application.use_cases.poker.start_poker import StartPokerUseCase
from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.application.use_cases.poker.calculate_bet_scores import CalculateBetScoresUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
  link_candidates_keyboard,
  link_candidates_page_keyboard,
  make_admin_candidates_keyboard,
  poker_add_player_candidates_keyboard,
  poker_buyin_candidates_keyboard,
  poker_cashout_candidates_keyboard,
  poker_cashier_candidates_keyboard,
  poker_remove_player_candidates_keyboard,
  poker_params_keyboard,
)
from app.bot.telegram.notifications import notify_user_about_approval
from app.bot.telegram.states import AdminPokerState, RegistrationState
from app.bot.vk.api import send_vk_message
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.buyin_data_repository import BuyinDataRepository
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


@router.message(Command("start_poker"))
@router.message(F.text == Buttons.admin_main.START_POKER.value)
async def start_poker_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return

  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.admin.NO_RIGHTS.value)
      return

    use_case = StartPokerUseCase(
      poker_repository=PokerRepository(session),
      poker_param_repository=PokerParamRepository(session),
    )
    can_start, params = await use_case.get_start_data()
    if not can_start:
      await message.answer(Text.admin.POKER_STARTED.value)
      return
    if not params:
      await message.answer(Text.admin.POKER_PARAMS_EMPTY.value)
      return

  await message.answer(
    Text.admin.POKER_PARAMS_CHOOSE.value,
    reply_markup=poker_params_keyboard(params=params),
  )


@router.callback_query(F.data.startswith("pokerstart:"))
async def start_poker_with_param(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  params_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)

  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return

    use_case = StartPokerUseCase(
      poker_repository=PokerRepository(session),
      poker_param_repository=PokerParamRepository(session),
    )
    created = await use_case.execute(params_id=params_id)
    if created is None:
      await callback.answer(Text.admin.POKER_STARTED.value, show_alert=True)
      return

    tg_user_ids = await user_repository.list_approved_tg_ids()
    vk_user_ids = await user_repository.list_approved_vk_ids()

  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is not None:
    for user_id in tg_user_ids:
      await telegram_bot.send_message(chat_id=user_id, text=Text.user.START_POKER.value)
  for user_id in vk_user_ids:
    await send_vk_message(user_id=user_id, message=Text.user.START_POKER.value)

  if callback.message is not None:
    await callback.message.edit_text(Text.admin.POKER_START_SUCCESS.value)
  await callback.answer(Text.admin.POKER_START_SUCCESS.value)


@router.message(Command("finish_poker"))
@router.message(F.text == Buttons.admin_room.FINISH_POKER.value)
async def finish_poker(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.admin.NO_RIGHTS.value)
      return
    poker_repository = PokerRepository(session)
    active = await poker_repository.get_started()
    if active is None:
      await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
      return
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
  await message.answer(Text.admin.POKER_FINISH_SUCCESS.value)


@router.message(Command("start_betting"))
@router.message(F.text == Buttons.admin_room.START_BETTING.value)
async def start_betting(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.admin.NO_RIGHTS.value)
      return
    poker_repository = PokerRepository(session)
    active = await poker_repository.get_started()
    if active is None:
      await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
      return
    poker, _ = active
    if poker.is_bettable:
      await message.answer(Text.admin.BETTING_ALREADY_OPEN.value)
      return
    await poker_repository.start_betting(poker)
    tg_user_ids = await user_repository.list_approved_tg_ids()
    vk_user_ids = await user_repository.list_approved_vk_ids()

  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is not None:
    for user_id in tg_user_ids:
      await telegram_bot.send_message(chat_id=user_id, text=Text.user.START_BETTING.value)
  for user_id in vk_user_ids:
    await send_vk_message(user_id=user_id, message=Text.user.START_BETTING.value)

  await message.answer(Text.admin.BETTING_START_SUCCESS.value)


@router.message(Command("set_cashier"))
@router.message(F.text == Buttons.admin_room.SET_CASHIER.value)
async def set_cashier_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.admin.NO_RIGHTS.value)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      buyin_data_repository=BuyinDataRepository(session),
    )
    players = await use_case.list_active_poker_players()
    if not players:
      await message.answer(Text.admin.POKER_PLAYERS_EMPTY.value)
      return
  await message.answer(
    Text.admin.POKER_CASHIER_CHOOSE.value,
    reply_markup=poker_cashier_candidates_keyboard(players=players),
  )


@router.callback_query(F.data.startswith("pokercashier:"))
async def set_cashier_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  player_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      buyin_data_repository=BuyinDataRepository(session),
    )
    updated = await use_case.set_cashier_for_active_poker(cashier_id=player_id)
    if updated is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
  if callback.message is not None:
    await callback.message.edit_text(Text.admin.POKER_CASHIER_SET.value)
  await callback.answer(Text.admin.POKER_CASHIER_SET.value)


@router.message(Command("add_player"))
@router.message(F.text == Buttons.admin_room.ADD_PLAYER.value)
async def add_player_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.admin.NO_RIGHTS.value)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    players = await use_case.list_active_poker_players()
    active_tg_ids = {int(player.player_id) for player in players}
    approved_users = await user_repository.list_approved()
    candidates = [
      user for user in approved_users
      if user.telegram_id is not None and int(user.telegram_id) not in active_tg_ids
    ]
    if not candidates:
      await message.answer(Text.admin.POKER_ADD_PLAYER_EMPTY.value)
      return
  await message.answer(
    Text.admin.POKER_ADD_PLAYER_CHOOSE.value,
    reply_markup=poker_add_player_candidates_keyboard(users=candidates),
  )


@router.callback_query(F.data.startswith("pokeradd:"))
async def add_player_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
    user = await user_repository.get_by_row_id(row_id)
    if user is None or user.telegram_id is None:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    created = await use_case.add_player_to_active_poker(
      player_id=int(user.telegram_id),
      player_name=user.name,
    )
    if created is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
  if callback.message is not None:
    await callback.message.edit_text(f"{Text.admin.POKER_ADD_PLAYER_SUCCESS.value}\n\nИмя: {user.name}")
  await callback.answer(Text.admin.POKER_ADD_PLAYER_SUCCESS.value)


@router.message(Command("remove_player"))
@router.message(F.text == Buttons.admin_room.REMOVE_PLAYER.value)
async def remove_player_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.admin.NO_RIGHTS.value)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    players = await use_case.list_active_poker_players()
    if not players:
      await message.answer(Text.admin.POKER_PLAYERS_EMPTY.value)
      return
  await message.answer(
    Text.admin.POKER_REMOVE_PLAYER_CHOOSE.value,
    reply_markup=poker_remove_player_candidates_keyboard(players=players),
  )


@router.callback_query(F.data.startswith("pokerremove:"))
async def remove_player_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  player_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    removed = await use_case.remove_player_from_active_poker(player_id=player_id)
    if removed is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    if removed is False:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return
  if callback.message is not None:
    await callback.message.edit_text(Text.admin.POKER_REMOVE_PLAYER_SUCCESS.value)
  await callback.answer(Text.admin.POKER_REMOVE_PLAYER_SUCCESS.value)


@router.message(Command("buyin"))
@router.message(F.text == Buttons.room.BUYIN.value)
async def buyin_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.admin.NO_RIGHTS.value)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    players = await use_case.list_active_poker_players()
    if not players:
      await message.answer(Text.admin.POKER_BUYIN_EMPTY.value)
      return
  await message.answer(
    Text.admin.POKER_BUYIN_CHOOSE.value,
    reply_markup=poker_buyin_candidates_keyboard(players=players),
  )


@router.callback_query(F.data.startswith("pokerbuyin:"))
async def buyin_select_callback(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  player_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
  await state.set_state(AdminPokerState.waiting_for_buyin_count)
  await state.update_data(buyin_player_id=player_id)
  if callback.message is not None:
    await callback.message.answer(Text.admin.POKER_BUYIN_PROMPT.value)
  await callback.answer()


@router.message(AdminPokerState.waiting_for_buyin_count)
async def buyin_count_input(message: Message, state: FSMContext) -> None:
  if message.from_user is None or not message.text:
    await message.answer(Text.admin.POKER_BUYIN_INVALID.value)
    return
  if not message.text.isdigit() or int(message.text) <= 0:
    await message.answer(Text.admin.POKER_BUYIN_INVALID.value)
    return
  buyins_count = int(message.text)
  data = await state.get_data()
  player_id = data.get("buyin_player_id")
  if player_id is None:
    await state.clear()
    await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
    return
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await state.clear()
      await message.answer(Text.admin.NO_RIGHTS.value)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      buyin_data_repository=BuyinDataRepository(session),
    )
    updated = await use_case.add_buyin_to_active_player(player_id=int(player_id), buyins_count=buyins_count)
    if updated is None:
      await state.clear()
      await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
      return
  await state.clear()
  await message.answer(f"{Text.admin.POKER_BUYIN_SAVED.value}\n\n{updated.player_name}: {updated.buyins}")


@router.message(Command("cashout"))
@router.message(F.text == Buttons.admin_room.CASHOUT.value)
async def cashout_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.admin.NO_RIGHTS.value)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    players = await use_case.list_active_poker_players()
    if not players:
      await message.answer(Text.admin.POKER_CASHOUT_EMPTY.value)
      return
  await message.answer(
    Text.admin.POKER_CASHOUT_CHOOSE.value,
    reply_markup=poker_cashout_candidates_keyboard(players=players),
  )


@router.callback_query(F.data.startswith("pokercashout:"))
async def cashout_select_callback(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  player_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
  await state.set_state(AdminPokerState.waiting_for_cashout_amount)
  await state.update_data(cashout_player_id=player_id)
  if callback.message is not None:
    await callback.message.answer(Text.admin.POKER_CASHOUT_PROMPT.value)
  await callback.answer()


@router.message(AdminPokerState.waiting_for_cashout_amount)
async def cashout_amount_input(message: Message, state: FSMContext) -> None:
  if message.from_user is None or not message.text:
    await message.answer(Text.admin.POKER_CASHOUT_INVALID.value)
    return
  if not message.text.isdigit() or int(message.text) < 0:
    await message.answer(Text.admin.POKER_CASHOUT_INVALID.value)
    return
  money_rub = int(message.text)
  money_kopecks = money_rub * 100
  data = await state.get_data()
  player_id = data.get("cashout_player_id")
  if player_id is None:
    await state.clear()
    await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
    return
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    admin_ids = await user_repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await state.clear()
      await message.answer(Text.admin.NO_RIGHTS.value)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    updated = await use_case.set_cashout_for_active_player(player_id=int(player_id), money_kopecks=money_kopecks)
    if updated is None:
      await state.clear()
      await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
      return
  await state.clear()
  await message.answer(
    f"{Text.admin.POKER_CASHOUT_SAVED.value}\n\n"
    f"{updated.player_name}: {_format_rub_from_kopecks(updated.money_kopecks)} ₽"
  )


@router.message(Command("make_admin"))
async def make_admin_command(message: Message) -> None:
  if message.from_user is None or message.text is None:
    await message.answer(Text.admin.MAKE_ADMIN_USAGE.value)
    return

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.admin.NO_RIGHTS.value)
      return

    approved_users = await repository.list_approved()
    candidates = [user for user in approved_users if not user.is_admin]
    if not candidates:
      await message.answer(Text.admin.MAKE_ADMIN_EMPTY.value)
      return

  await message.answer(
    Text.admin.MAKE_ADMIN_PROMPT.value,
    reply_markup=make_admin_candidates_keyboard(users=candidates),
  )


@router.callback_query(F.data.startswith("makeadmin:"))
async def make_admin_select_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return

    use_case = MakeAdminUseCase(repository)
    try:
      user = await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return

  if callback.message is not None:
    await callback.message.edit_text(
      f"{Text.admin.MAKE_ADMIN_SUCCESS.value}\n\n"
      f"Имя: {user.name}"
    )
  await callback.answer(Text.admin.MAKE_ADMIN_SUCCESS.value)


@router.callback_query(F.data.startswith("approve:"))
async def approve_registration_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return

    use_case = ApproveUserUseCase(repository)
    try:
      user = await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
      return

  if user.telegram_id is not None:
    await notify_user_about_approval(telegram_id=user.telegram_id, approved=True)

  if callback.message is not None:
    await callback.message.edit_text(
      f"Заявка #{row_id} одобрена.\nИмя: {user.name}\nTelegram ID: {user.telegram_id}",
    )
  await callback.answer(Text.admin.APPROVE_ACTION.value)


@router.callback_query(F.data.startswith("correct:"))
async def correct_registration_callback(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return

    user = await repository.get_by_row_id(row_id)
    if user is None:
      await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
      return
    if user.is_approved:
      await callback.answer(Text.admin.REQUEST_ALREADY_APPROVED.value, show_alert=True)
      return

  review_chat_id = callback.message.chat.id if callback.message is not None else None
  review_message_id = callback.message.message_id if callback.message is not None else None

  await state.set_state(RegistrationState.waiting_for_corrected_name)
  await state.update_data(
    pending_row_id=row_id,
    review_chat_id=review_chat_id,
    review_message_id=review_message_id,
  )
  if callback.message is None:
    await callback.answer(Text.admin.CORRECT_PROMPT.value, show_alert=True)
    return

  await callback.answer(Text.admin.CORRECT_FLOW_STARTED.value)
  await callback.message.answer(
    f"{Text.admin.CORRECT_PROMPT.value}\n\n"
    f"Текущее имя: {user.name}"
  )


@router.message(RegistrationState.waiting_for_corrected_name)
async def finish_correct_user(message: Message, state: FSMContext) -> None:
  if message.from_user is None or message.text is None:
    await message.answer(Text.admin.EMPTY_CORRECTED_NAME.value)
    return

  corrected_name = " ".join(message.text.split())
  if not corrected_name:
    await message.answer(Text.admin.EMPTY_CORRECTED_NAME.value)
    return

  data = await state.get_data()
  pending_row_id = data.get("pending_row_id")
  review_chat_id = data.get("review_chat_id")
  review_message_id = data.get("review_message_id")

  if pending_row_id is None:
    await state.clear()
    await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
    return

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await state.clear()
      await message.answer(Text.admin.NO_RIGHTS.value)
      return

    use_case = CorrectUserUseCase(repository)
    try:
      user = await use_case.execute(
        row_id=pending_row_id,
        corrected_name=corrected_name,
      )
    except UserNotFoundError:
      await state.clear()
      await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
      return
    except UserNameRequiredError:
      await message.answer(Text.admin.EMPTY_CORRECTED_NAME.value)
      return
    except UserAlreadyApprovedError:
      await state.clear()
      await message.answer(Text.admin.REQUEST_ALREADY_APPROVED.value)
      return

  if user.telegram_id is not None:
    await notify_user_about_approval(telegram_id=user.telegram_id, approved=True)

  if review_chat_id is not None and review_message_id is not None:
    from app.bot.telegram.runtime import telegram_bot

    if telegram_bot is not None:
      await telegram_bot.edit_message_text(
        chat_id=review_chat_id,
        message_id=review_message_id,
        text=(
          f"{Text.admin.CORRECT_ACTION.value}\n\n"
          f"Row ID: {user.row_id}\n"
          f"Имя: {user.name}\n"
          f"Telegram ID: {user.telegram_id}\n"
          f"VK ID: {user.vk_id}"
        ),
      )

  await state.clear()
  await message.answer(
    f"{Text.admin.CORRECT_ACTION.value}\n\n"
    f"Row ID: {user.row_id}\n"
    f"Имя: {user.name}\n"
    f"Telegram ID: {user.telegram_id}\n"
    f"VK ID: {user.vk_id}",
  )


@router.callback_query(F.data.startswith("reject:"))
async def reject_registration_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return

    user = await repository.get_by_row_id(row_id)
    if user is None:
      await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
      return

    user_telegram_id = user.telegram_id
    user_name = user.name

    use_case = RejectUserUseCase(repository)
    try:
      await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
      return
    except UserAlreadyApprovedError:
      await callback.answer(Text.admin.REQUEST_ALREADY_APPROVED.value, show_alert=True)
      return

  if user_telegram_id is not None:
    await notify_user_about_approval(telegram_id=user_telegram_id, approved=False)

  if callback.message is not None:
    await callback.message.edit_text(
      f"Заявка #{row_id} отклонена.\nИмя: {user_name}\nTelegram ID: {user_telegram_id}",
    )
  await callback.answer(Text.admin.REJECT_ACTION.value)


@router.callback_query(F.data.startswith("link:"))
async def link_registration_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return

    approved_users = await repository.list_approved()

  await callback.answer(Text.admin.LINK_ACTION.value)
  if callback.message is not None:
    await callback.message.answer(Text.admin.LINK_PROMPT.value)
    await callback.message.answer(
      Text.admin.LINK_CHOICES_TITLE.value,
      reply_markup=link_candidates_keyboard(
        pending_row_id=row_id,
        users=approved_users,
      ),
    )


@router.callback_query(F.data.startswith("linkto:"))
async def choose_link_target_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  _, pending_row_id_text, existing_row_id_text = callback.data.split(":", 2)
  await _clear_inline_keyboard(callback)
  pending_row_id = int(pending_row_id_text)
  existing_row_id = int(existing_row_id_text)

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return

    use_case = LinkPendingUserUseCase(repository)
    try:
      user = await use_case.execute(
        pending_row_id=pending_row_id,
        existing_row_id=existing_row_id,
      )
    except UserNotFoundError:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return
    except UserLinkConflictError:
      await callback.answer(Text.admin.LINK_CONFLICT.value, show_alert=True)
      return

  if callback.message is not None:
    await callback.message.edit_text(
      f"{Text.admin.LINK_SUCCESS.value}\n\n"
      f"Pending row_id: {pending_row_id}\n"
      f"Linked to row_id: {user.row_id}\n"
      f"Имя: {user.name}\n"
      f"Telegram ID: {user.telegram_id}\n"
      f"VK ID: {user.vk_id}"
    )
  await callback.answer(Text.admin.LINK_SUCCESS.value)


@router.callback_query(F.data.startswith("linkto_page:"))
async def choose_link_target_page_callback(callback: CallbackQuery) -> None:
  if callback.message is None:
    await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
    return
  _, pending_row_id_text, page_text = callback.data.split(":", 2)
  pending_row_id = int(pending_row_id_text)
  page = int(page_text)
  async with SessionFactory() as session:
    repository = UserRepository(session)
    approved_users = await repository.list_approved()
  await callback.message.edit_reply_markup(
    reply_markup=link_candidates_page_keyboard(
      pending_row_id=pending_row_id,
      users=approved_users,
      page=page,
    )
  )
  await callback.answer()
