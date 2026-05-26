from datetime import date, timezone
import random
import logging
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message
from types import SimpleNamespace

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
from app.bot.shared.guards import is_tg_admin
from app.bot.shared.texts.texts import Text
from app.bot.shared.chips_runtime import (
  TG_ADMIN_CHIPS_STATUS_MSG_IDS,
  TG_USER_CHIPS_RESULT_MSG_IDS,
  TG_ADMIN_ROOM_STATUS_MSG_IDS,
  VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.telegram.keyboards import (
  admin_room_correct_keyboard,
  admin_room_keyboard,
  betting_keyboard,
  link_candidates_keyboard,
  link_candidates_page_keyboard,
  main_keyboard,
  make_admin_candidates_keyboard,
  poker_add_player_candidates_keyboard,
  poker_buyin_candidates_keyboard,
  poker_buyin_count_keyboard,
  poker_buyin_correct_confirm_keyboard,
  poker_cashout_candidates_keyboard,
  poker_calc_keyboard,
  bet_receipt_manual_keyboard,
  poker_cashier_candidates_keyboard,
  poker_room_admin_status_keyboard,
  poker_room_manage_player_keyboard,
  poker_remove_player_candidates_keyboard,
  poker_unban_player_candidates_keyboard,
  poker_params_keyboard,
  poll_admin_choose_keyboard,
  poll_admin_other_keyboard,
  room_admin_keyboard,
  main_dynamic_keyboard as tg_main_dynamic_keyboard,
)
from app.bot.telegram.notifications import notify_user_about_approval
from app.bot.telegram.states import AdminPokerState, RegistrationState
from app.bot.vk.api import delete_vk_message_by_id, send_vk_message, send_vk_message_with_id
from app.bot.vk.api import pin_vk_message_by_id, unpin_vk_message
from app.bot.vk.keyboards import betting_keyboard as vk_betting_keyboard
from app.bot.vk.keyboards import main_keyboard as vk_main_keyboard
from app.bot.vk.keyboards import main_dynamic_keyboard as vk_main_dynamic_keyboard
from app.bot.vk.keyboards import poker_room_admin_status_keyboard as vk_poker_room_admin_status_keyboard
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_payment_receipt_repository import BetPaymentReceiptRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.session import SessionFactory
from app.services.buyins_chart import render_buyins_session_chart_png
from app.services.google_backup import backup_tables_to_google

router = Router()
TG_BUYIN_NOTIFY_CASHIER_ONLY: set[tuple[int, int]] = set()
TG_MANUAL_RECEIPT_SELECTIONS: dict[tuple[int, int], set[int]] = {}
logger = logging.getLogger(__name__)


async def _safe_callback_edit_reply_markup(
  callback: CallbackQuery,
  reply_markup: InlineKeyboardMarkup | None,
) -> None:
  if callback.message is None:
    return
  try:
    await callback.message.edit_reply_markup(reply_markup=reply_markup)
  except TelegramBadRequest as exc:
    if "message is not modified" not in str(exc).lower():
      raise


async def _safe_callback_edit_text(
  callback: CallbackQuery,
  text: str,
  reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
  if callback.message is None:
    return
  try:
    await callback.message.edit_text(text=text, reply_markup=reply_markup)
  except TelegramBadRequest as exc:
    if "message is not modified" not in str(exc).lower():
      raise


async def _start_betting_flow(*, admin_tg_id: int) -> str:
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    active = await poker_repository.get_started()
    if active is None:
      return Text.admin.POKER_ACTIVE_NOT_FOUND.value
    poker, _ = active
    if poker.is_ready_for_chips_entering:
      return Text.user.FINISH_CHIPS_NOT_READY.value
    if poker.is_bettable:
      return Text.admin.BETTING_ALREADY_OPEN.value
    await poker_repository.start_betting(poker)
    approved_users = await user_repository.list_approved()

  from app.bot.telegram.runtime import telegram_bot
  if telegram_bot is not None:
    for chat_id, message_id in list(TG_ADMIN_ROOM_STATUS_MSG_IDS.items()):
      try:
        await telegram_bot.unpin_chat_message(chat_id=int(chat_id), message_id=int(message_id))
      except Exception:
        pass
      try:
        await telegram_bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
      except Exception:
        pass
  for peer_id, message_id in list(VK_ADMIN_ROOM_STATUS_MSG_IDS.items()):
    try:
      await unpin_vk_message(peer_id=int(peer_id))
    except Exception:
      pass
    try:
      await delete_vk_message_by_id(peer_id=int(peer_id), message_id=int(message_id))
    except Exception:
      pass
  TG_ADMIN_ROOM_STATUS_MSG_IDS.clear()
  VK_ADMIN_ROOM_STATUS_MSG_IDS.clear()
  if telegram_bot is not None:
    for user_id in tg_user_ids:
      await telegram_bot.send_message(chat_id=user_id, text=Text.user.START_BETTING.value, reply_markup=betting_keyboard)
  for user_id in vk_user_ids:
    await send_vk_message(user_id=user_id, message=Text.user.START_BETTING.value, keyboard=vk_betting_keyboard)
  return Text.admin.BETTING_START_SUCCESS.value


async def _refresh_admin_room_status(*, session) -> None:
  from app.bot.telegram.runtime import telegram_bot

  user_repository = UserRepository(session)
  poker_repository = PokerRepository(session)
  poker_data_repository = PokerDataRepository(session)
  active = await poker_repository.get_started()
  if active is None:
    return
  poker, _ = active
  players = await poker_data_repository.list_players(date=poker.date)
  can_start_betting = bool(
    poker.cashier_id is not None
    and not bool(poker.is_bettable)
    and not bool(poker.is_ready_for_chips_entering)
  )
  if poker.cashier_id is None:
    status_text = (
      "🎲 Ниже список игроков в руме.\n"
      "❌ Лишних можно удалить.\n"
      "❗ После входа большинства игроков выбери кассира."
    )
  else:
    status_text = (
      "🍀 Когда все игроки будут в руме - запусти ставки.\n"
      "❗ Ставки можно делать только на активных игроков."
    )
  player_row_ids = {int(p.player_id) for p in players}
  admins = [u for u in await user_repository.list_approved() if u.is_admin and int(u.row_id) in player_row_ids]
  tg_admins = [int(u.telegram_id) for u in admins if u.telegram_id is not None]
  vk_admins = [int(u.vk_id) for u in admins if u.vk_id is not None]
  if telegram_bot is not None:
    for admin_id in tg_admins:
      prev_mid = TG_ADMIN_ROOM_STATUS_MSG_IDS.get(int(admin_id))
      if prev_mid is not None:
        try:
          await telegram_bot.delete_message(chat_id=int(admin_id), message_id=int(prev_mid))
        except Exception:
          pass
      sent = await telegram_bot.send_message(
        chat_id=int(admin_id),
        text=status_text,
        reply_markup=poker_room_admin_status_keyboard(
          players=[] if poker.cashier_id is not None else players,
          can_start_betting=can_start_betting,
        ),
      )
      try:
        await telegram_bot.pin_chat_message(chat_id=int(admin_id), message_id=int(sent.message_id), disable_notification=True)
      except Exception:
        pass
      TG_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent.message_id)
  for admin_id in vk_admins:
    prev_mid = VK_ADMIN_ROOM_STATUS_MSG_IDS.get(int(admin_id))
    if prev_mid is not None:
      try:
        await delete_vk_message_by_id(peer_id=int(admin_id), message_id=int(prev_mid))
      except Exception:
        pass
    sent_mid = await send_vk_message_with_id(
      user_id=int(admin_id),
      message=status_text,
      keyboard=vk_poker_room_admin_status_keyboard(
        players=[] if poker.cashier_id is not None else players,
        can_start_betting=can_start_betting,
      ),
    )
    if sent_mid is not None:
      try:
        await pin_vk_message_by_id(peer_id=int(admin_id), message_id=int(sent_mid))
      except Exception:
        pass
      VK_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent_mid)


def _shift_month(value: date, delta: int) -> date:
  total = value.year * 12 + (value.month - 1) + delta
  year = total // 12
  month = total % 12 + 1
  return date(year, month, 1)


def _parse_month_key(value: str) -> date:
  year_s, month_s = value.split("-")
  return date(int(year_s), int(month_s), 1)


async def _clear_inline_keyboard(callback: CallbackQuery) -> None:
  if callback.message is None:
    return
  try:
    await _safe_callback_edit_reply_markup(callback, reply_markup=None)
  except Exception:
    return


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
    lines.append(
      f"{loser['name']} ➡️ {winner['name']} {_format_rub_from_kopecks(transfer)} ₽"
    )
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


def _build_chips_status_text(*, players: list, chips_in_game: int, chips_entered: int) -> str:
  def money_from_chips(chips: int, buyins: int, buyin_size_chips: int, buyin_size_kopecks: int) -> int:
    if buyin_size_chips <= 0:
      return 0
    return ((int(chips) - int(buyins) * int(buyin_size_chips)) * int(buyin_size_kopecks)) // int(buyin_size_chips)

  def reaction(money_kopecks: int) -> str:
    return "😎" if int(money_kopecks) >= 0 else "🤮"

  # Fallback values are replaced by real params in _upsert_tg_admin_chips_status.
  buyin_size_chips = 200
  buyin_size_kopecks = 20000
  if players:
    sample = players[0]
    buyin_size_chips = int(getattr(sample, "_buyin_size_chips", buyin_size_chips))
    buyin_size_kopecks = int(getattr(sample, "_buyin_size_kopecks", buyin_size_kopecks))

  remainder = int(chips_in_game) - int(chips_entered)
  lines = [
    "🎰 Ввод фишек.",
    "",
    f"Закуплено: {chips_in_game}. Введено: {chips_entered}. Остаток: {remainder}",
    "",
  ]
  for p in players:
    if p.chips is None:
      lines.append(f"{p.player_name}: еще не ввел фишки")
    else:
      money_kopecks = money_from_chips(
        chips=int(p.chips),
        buyins=int(p.buyins),
        buyin_size_chips=buyin_size_chips,
        buyin_size_kopecks=buyin_size_kopecks,
      )
      lines.append(
        f"{p.player_name}: {int(p.chips)} → {_format_rub_from_kopecks(int(money_kopecks))} ₽ {reaction(int(money_kopecks))}"
      )
  return "\n".join(lines)


async def _build_poker_buyins_session_chart(*, session, poker_date: date) -> bytes | None:
  events = await BuyinDataRepository(session).list_for_date(poker_date=poker_date)
  if not events:
    return None

  cumulative: dict[str, int] = {}
  points: dict[str, list[tuple[int, int]]] = {}
  x_labels: list[str] = []
  msk_tz = ZoneInfo("Europe/Moscow")

  for idx, event in enumerate(events):
    if event.created_at is not None:
      event_dt = event.created_at
      if event_dt.tzinfo is None:
        event_dt = event_dt.replace(tzinfo=timezone.utc)
      event_dt_msk = event_dt.astimezone(msk_tz)
      x_labels.append(event_dt_msk.strftime("%H:%M"))
    else:
      x_labels.append(str(idx + 1))
    for name in list(points.keys()):
      points[name].append((idx, cumulative.get(name, 0)))
    name = str(event.player_name)
    cumulative[name] = cumulative.get(name, 0) + int(event.buyins_count or 0)
    if name not in points:
      points[name] = [(prev_idx, 0) for prev_idx in range(idx)]
      points[name].append((idx, cumulative[name]))
    else:
      points[name][-1] = (idx, cumulative[name])

  points = {name: vals for name, vals in points.items() if vals}
  if not points:
    return None

  return render_buyins_session_chart_png(
    title=f"Закупы за игру {poker_date.strftime('%d.%m.%Y')}",
    series=points,
    x_labels=x_labels,
    legend_value_mode="max",
  )


async def _upsert_tg_admin_chips_status(*, session, poker_date) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is None:
    return
  user_repository = UserRepository(session)
  poker_repository = PokerRepository(session)
  poker_data_repository = PokerDataRepository(session)
  players = await poker_data_repository.list_players(date=poker_date)
  chips_entered = sum(int(p.chips or 0) for p in players)
  chips_in_game = 0
  ready = await poker_repository.get_latest_ready_for_chips_with_params()
  if ready is not None:
    poker, params = ready
    if poker.date == poker_date:
      chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
      for p in players:
        setattr(p, "_buyin_size_chips", int(params.buyin_size_chips))
        setattr(p, "_buyin_size_kopecks", int(params.buyin_size_kopecks))
  text = _build_chips_status_text(players=players, chips_in_game=chips_in_game, chips_entered=chips_entered)
  player_row_ids = {int(p.player_id) for p in players}
  admins = [u for u in await user_repository.list_approved() if u.is_admin and int(u.row_id) in player_row_ids]
  for admin in admins:
    if admin.notification_platform != "tg" or admin.telegram_id is None:
      continue
    prev_msg_id = TG_ADMIN_CHIPS_STATUS_MSG_IDS.get(int(admin.telegram_id))
    if prev_msg_id is not None:
      try:
        await telegram_bot.delete_message(chat_id=admin.telegram_id, message_id=prev_msg_id)
      except Exception:
        pass
    sent = await telegram_bot.send_message(
      chat_id=admin.telegram_id,
      text=text,
      reply_markup=poker_calc_keyboard(),
    )
    TG_ADMIN_CHIPS_STATUS_MSG_IDS[int(admin.telegram_id)] = int(sent.message_id)


async def _upsert_tg_user_chips_result(*, chat_id: int, text: str) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is None:
    return
  prev_msg_id = TG_USER_CHIPS_RESULT_MSG_IDS.get(int(chat_id))
  if prev_msg_id is not None:
    try:
      await telegram_bot.delete_message(chat_id=chat_id, message_id=prev_msg_id)
    except Exception:
      pass
  sent = await telegram_bot.send_message(chat_id=chat_id, text=text)
  TG_USER_CHIPS_RESULT_MSG_IDS[int(chat_id)] = int(sent.message_id)


def _build_user_chips_text(*, chips: int | None, money_kopecks: int | None, reaction: str | None) -> str:
  chips_text = str(chips) if chips is not None else "ты еще не ввел фишки"
  if money_kopecks is None or reaction is None:
    result_text = "ты еще не ввел фишки"
  else:
    result_text = f"{_format_rub_from_kopecks(int(money_kopecks))} ₽ {reaction}"
  return (
    "Покер завершен. Посчитай свои фишки и отправь число мне.\n"
    f"Введено: {chips_text}\n"
    f"Итог: {result_text}"
  )


async def _clear_tg_admin_chips_calc_buttons() -> None:
  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is None:
    TG_ADMIN_CHIPS_STATUS_MSG_IDS.clear()
    return
  for chat_id, message_id in list(TG_ADMIN_CHIPS_STATUS_MSG_IDS.items()):
    try:
      await telegram_bot.edit_message_reply_markup(
        chat_id=int(chat_id),
        message_id=int(message_id),
        reply_markup=None,
      )
    except Exception:
      pass
  TG_ADMIN_CHIPS_STATUS_MSG_IDS.clear()


async def _notify_players_about_finish(*, players: list) -> None:
  from app.bot.telegram.runtime import telegram_bot

  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    for player in players:
      user = await user_repository.get_by_row_id(int(player.player_id))
      if user is None or user.notification_platform is None or bool(user.is_admin):
        continue

      text = _build_user_chips_text(chips=None, money_kopecks=None, reaction=None)
      if user.notification_platform == "tg" and user.telegram_id is not None and telegram_bot is not None:
        await telegram_bot.send_message(
          chat_id=user.telegram_id,
          text=text,
          reply_markup=await tg_main_dynamic_keyboard(user),
        )
      elif user.notification_platform == "vk" and user.vk_id is not None:
        await send_vk_message(
          user_id=user.vk_id,
          message=text,
          keyboard=await vk_main_dynamic_keyboard(user),
        )


async def _notify_about_buyin(
  *,
  session,
  poker,
  updated_player,
  buyins_count: int,
  notify_admins: bool = True,
) -> None:
  from app.bot.telegram.runtime import telegram_bot

  user_repository = UserRepository(session)
  cashier = None
  if poker.cashier_id is not None:
    cashier = await user_repository.get_by_row_id(int(poker.cashier_id))

  text = (
    f"🏦 Новый закуп для {updated_player.player_name}: +{buyins_count}. "
    f"Всего: {updated_player.buyins}."
  )
  if cashier is not None:
    if cashier.notification_platform == "tg" and cashier.telegram_id is not None and telegram_bot is not None:
      await telegram_bot.send_message(chat_id=cashier.telegram_id, text=text)
    elif cashier.notification_platform == "vk" and cashier.vk_id is not None:
      await send_vk_message(user_id=cashier.vk_id, message=text)

  if notify_admins:
    recipients: dict[int, object] = {}
    players = await PokerDataRepository(session).list_players(date=poker.date)
    player_row_ids = {int(p.player_id) for p in players}
    admins = await user_repository.list_approved()
    for user in admins:
      if user.is_admin and int(user.row_id) in player_row_ids:
        recipients[int(user.row_id)] = user
    if cashier is not None:
      recipients.pop(int(cashier.row_id), None)
    for user in recipients.values():
      if user.notification_platform == "tg" and user.telegram_id is not None and telegram_bot is not None:
        await telegram_bot.send_message(chat_id=user.telegram_id, text=text)
      elif user.notification_platform == "vk" and user.vk_id is not None:
        await send_vk_message(user_id=user.vk_id, message=text)

  player_user = await user_repository.get_by_row_id(int(updated_player.player_id))
  if player_user is not None and player_user.notification_platform is not None:
    player_text = f"🏦 Новый закуп: +{buyins_count}. Всего: {updated_player.buyins}."
    if player_user.notification_platform == "tg" and player_user.telegram_id is not None and telegram_bot is not None:
      await telegram_bot.send_message(chat_id=player_user.telegram_id, text=player_text)
    elif player_user.notification_platform == "vk" and player_user.vk_id is not None:
      await send_vk_message(user_id=player_user.vk_id, message=player_text)


async def _notify_admins_about_removed_player(*, session, poker_date, player_name: str, buyins: int) -> None:
  from app.bot.telegram.runtime import telegram_bot

  user_repository = UserRepository(session)
  players = await PokerDataRepository(session).list_players(date=poker_date)
  player_row_ids = {int(p.player_id) for p in players}
  admins = [u for u in await user_repository.list_approved() if u.is_admin and int(u.row_id) in player_row_ids]
  text = f"❌ Игрок удален из покера\n{player_name}: {int(buyins)}"
  for user in admins:
    if user.notification_platform == "tg" and user.telegram_id is not None and telegram_bot is not None:
      await telegram_bot.send_message(chat_id=user.telegram_id, text=text)
    elif user.notification_platform == "vk" and user.vk_id is not None:
      await send_vk_message(user_id=user.vk_id, message=text)


async def _notify_user_removed_from_room(*, user) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if user.telegram_id is not None and telegram_bot is not None:
    await telegram_bot.send_message(
      chat_id=user.telegram_id,
      text=Text.user.ROOM_REMOVED_BY_ADMIN.value,
      reply_markup=main_admin_entry_keyboard if user.is_admin else main_keyboard,
    )
  if user.vk_id is not None:
    await send_vk_message(
      user_id=user.vk_id,
      message=Text.user.ROOM_REMOVED_BY_ADMIN.value,
      keyboard=vk_main_keyboard if not user.is_admin else vk_main_keyboard,
    )


async def _notify_user_unbanned_for_room(*, user) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if user.notification_platform == "tg" and user.telegram_id is not None and telegram_bot is not None:
    await telegram_bot.send_message(chat_id=user.telegram_id, text=Text.user.ROOM_UNBANNED_BY_ADMIN.value)
  elif user.notification_platform == "vk" and user.vk_id is not None:
    await send_vk_message(user_id=user.vk_id, message=Text.user.ROOM_UNBANNED_BY_ADMIN.value)


async def _ensure_tg_admin_message(*, session, user_id: int, message: Message) -> bool:
  if not await is_tg_admin(session=session, telegram_id=user_id):
    await message.answer(Text.admin.NO_RIGHTS.value)
    return False
  return True


async def _ensure_tg_admin_callback(*, session, user_id: int, callback: CallbackQuery) -> bool:
  if not await is_tg_admin(session=session, telegram_id=user_id):
    await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
    return False
  return True


@router.message(F.text == Buttons.admin_main.START_POKER.value)
async def start_poker_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return

  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
    user_repository = UserRepository(session)

    use_case = StartPokerUseCase(
      poker_repository=PokerRepository(session),
      poker_param_repository=PokerParamRepository(session),
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
    )
    can_start, params = await use_case.get_start_data()
    if not can_start:
      await message.answer(Text.admin.POKER_STARTED.value)
      return
    if not params:
      await message.answer(Text.admin.POKER_PARAMS_EMPTY.value)
      return

  await message.answer(
    "\n\n".join(
      [
        Text.admin.POKER_PARAMS_CHOOSE.value,
        *[
          (
            f"🎲 ID: {p.row_id}\n"
            f"Закуп: ⭕ {p.buyin_size_chips} / 💲 {int(p.buyin_size_kopecks) // 100}\n"
            f"ББ: {p.bb_size_chips} | 🔝 Макс закуп: {p.max_buyins}\n"
            f"Большой / Супер закуп: 💸 {p.big_buyin} / 🤑 {p.super_buyin}"
          )
          for p in params
        ],
      ]
    ),
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
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
    user_repository = UserRepository(session)

    use_case = StartPokerUseCase(
      poker_repository=PokerRepository(session),
      poker_param_repository=PokerParamRepository(session),
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
    )
    created = await use_case.execute(params_id=params_id)
    if created is None:
      await callback.answer(Text.admin.POKER_STARTED.value, show_alert=True)
      return
    starter = await user_repository.get_by_telegram_id(callback.from_user.id)
    if starter is not None:
      await ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
      ).add_player_to_active_poker(
        player_id=int(starter.row_id),
        player_name=starter.name,
      )

    tg_user_ids = await user_repository.list_approved_tg_ids()
    vk_user_ids = await user_repository.list_approved_vk_ids()

  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is not None:
    for user in approved_users:
      if user.telegram_id is None:
        continue
      await telegram_bot.send_message(
        chat_id=int(user.telegram_id),
        text=Text.user.START_POKER.value,
        reply_markup=tg_main_dynamic_keyboard(
          is_admin=bool(user.is_admin),
          has_active_poker=True,
          has_active_poll=False,
        ),
      )
  for user in approved_users:
    if user.vk_id is None:
      continue
    await send_vk_message(
      user_id=int(user.vk_id),
      message=Text.user.START_POKER.value,
      keyboard=vk_main_dynamic_keyboard(
        is_admin=bool(user.is_admin),
        has_active_poker=True,
        has_active_poll=False,
      ),
    )

  if callback.message is not None:
    await _safe_callback_edit_text(callback, Text.admin.POKER_START_SUCCESS.value)
  await callback.answer(Text.admin.POKER_START_SUCCESS.value)


@router.message(F.text == Buttons.admin_room.FINISH_POKER.value)
async def finish_poker(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
    user_repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    active = await poker_repository.get_started()
    if active is None:
      await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
      return
    poker, params = active
    poker_data_repository = PokerDataRepository(session)
    players = await poker_data_repository.list_players(date=poker.date)
    await poker_repository.finish(poker)
    await PokerRoomDeniedRepository(session).clear_all()
  await _notify_players_about_finish(players=players)
  await message.answer(Text.admin.POKER_FINISH_SUCCESS.value)
  if players:
    async with SessionFactory() as session:
      await _upsert_tg_admin_chips_status(session=session, poker_date=players[0].date)


@router.message(F.text == Buttons.admin_room.CALCULATE_POKER.value)
async def calculate_poker(message: Message, admin_user_id: int | None = None) -> None:
  initiator_id = int(admin_user_id) if admin_user_id is not None else (int(message.from_user.id) if message.from_user is not None else None)
  if initiator_id is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=initiator_id, message=message):
      return
    user_repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    ready = await poker_repository.get_latest_ready_for_chips_with_params()
    if ready is None:
      await message.answer(Text.admin.POKER_CASHOUT_EMPTY.value)
      return
    poker, params = ready
    poker_data_repository = PokerDataRepository(session)
    players = await poker_data_repository.list_players(date=poker.date)
    if not players:
      await message.answer(Text.admin.POKER_CASHOUT_EMPTY.value)
      return
    chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
    chips_entered = sum(int(p.chips or 0) for p in players)
    diff = chips_entered - chips_in_game
    if diff != 0:
      await message.answer(
        "Количество введенных фишек не совпадает с количеством закупленных\n"
        f"Разница: {diff}"
      )
      return

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

    # Bet scores are calculated only after final winners/losers/money are known.
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

    await poker_repository.finish_chips_entering(
      poker,
      winners=winners_text,
      loosers=loosers_text,
    )
    try:
      await backup_tables_to_google(session=session)
    except Exception:
      logger.exception("Google backup failed after poker calculation (TG).")

    all_pokers = await poker_repository.list_all()
    prev_completed = None
    for old in sorted(all_pokers, key=lambda x: int(x.row_id), reverse=True):
      if int(old.row_id) == int(poker.row_id):
        continue
      if bool(old.winners):
        prev_completed = old
        break
    prev_winners = _split_names_csv(prev_completed.winners if prev_completed is not None else None)

    winner_line = ", ".join(f"{_winner_mark(is_streak=(name in prev_winners))} {name}" for name in winners)
    loser_line = ", ".join(f"❌ {name}" for name in loosers)

    transfer_lines: list[str] = []
    for line in transfers:
      # add recipient bank/phone for convenience
      recipient_name = line.split(" ➡️ ")[1].split(" ")[0:2]
      recipient_name_joined = " ".join(recipient_name).strip()
      recipient_user = next((u for u in await user_repository.list_approved() if u.name.startswith(recipient_name_joined)), None)
      extra = ""
      if recipient_user is not None and recipient_user.tel_number:
        bank = f" ({recipient_user.bank_name})" if recipient_user.bank_name else ""
        extra = f" [{recipient_user.tel_number}{bank}]"
      transfer_lines.append(f"{line}{extra}")

    bet_lines: list[str] = []
    for bet in sorted(bets, key=lambda x: int(x.row_id)):
      guessed_winner = bool(bet.winner_name) and bet.winner_name in winners
      guessed_loser = bool(bet.loser_name) and bet.loser_name in loosers
      if not guessed_winner and not guessed_loser:
        continue
      mark = _bet_mark(
        amount_kopecks=int(bet.amount_kopecks),
        guessed_winner=guessed_winner,
        guessed_loser=guessed_loser,
      )
      bet_lines.append(f"{bet.better_name}: {mark} +{int(bet.score)}")

    lines = [
      Text.admin.POKER_CALC_SUCCESS.value,
      "",
      f"{winner_line}",
      f"{loser_line}",
      "",
      "💲 Переводы:",
    ]
    lines.extend(transfer_lines if transfer_lines else ["Переводы не требуются"])
    lines.append("")
    lines.append("🍀 Ставки:")
    lines.extend(bet_lines if bet_lines else ["Успешных ставок не было"])
    result_text = "\n".join(lines)
    chart_png = await _build_poker_buyins_session_chart(session=session, poker_date=poker.date)

    from app.bot.telegram.runtime import telegram_bot
    recipient_row_ids = {int(p.player_id) for p in players} | {int(b.better_id) for b in bets}
    sent_tg_ids: set[int] = set()
    sent_vk_ids: set[int] = set()
    for row_id in sorted(recipient_row_ids):
      user = await user_repository.get_by_row_id(row_id)
      if user is None:
        continue
      if user.notification_platform == "tg" and user.telegram_id is not None and telegram_bot is not None:
        await telegram_bot.send_message(chat_id=user.telegram_id, text=result_text, reply_markup=main_keyboard)
        if chart_png is not None:
          await telegram_bot.send_photo(
            chat_id=user.telegram_id,
            photo=BufferedInputFile(chart_png, filename="poker_buyins_session.png"),
            caption="📈 Закупы за игру",
            reply_markup=main_keyboard,
          )
        sent_tg_ids.add(int(user.telegram_id))
      elif user.notification_platform == "vk" and user.vk_id is not None:
        await send_vk_message(user_id=user.vk_id, message=result_text, keyboard=vk_main_keyboard)
        if chart_png is not None:
          from app.bot.vk.api import send_vk_photo
          await send_vk_photo(user_id=user.vk_id, image_bytes=chart_png, filename="poker_buyins_session.png")
        sent_vk_ids.add(int(user.vk_id))
    initiator_user = await user_repository.get_by_telegram_id(int(initiator_id))
    if initiator_user is not None:
      if (
        initiator_user.notification_platform == "tg"
        and initiator_user.telegram_id is not None
        and telegram_bot is not None
        and int(initiator_user.telegram_id) not in sent_tg_ids
      ):
        await telegram_bot.send_message(chat_id=initiator_user.telegram_id, text=result_text, reply_markup=main_keyboard)
        if chart_png is not None:
          await telegram_bot.send_photo(
            chat_id=initiator_user.telegram_id,
            photo=BufferedInputFile(chart_png, filename="poker_buyins_session.png"),
            caption="📈 Закупы за игру",
            reply_markup=main_keyboard,
          )
      elif (
        initiator_user.notification_platform == "vk"
        and initiator_user.vk_id is not None
        and int(initiator_user.vk_id) not in sent_vk_ids
      ):
        await send_vk_message(user_id=initiator_user.vk_id, message=result_text, keyboard=vk_main_keyboard)
        if chart_png is not None:
          from app.bot.vk.api import send_vk_photo
          await send_vk_photo(user_id=initiator_user.vk_id, image_bytes=chart_png, filename="poker_buyins_session.png")
    await _clear_tg_admin_chips_calc_buttons()


@router.callback_query(F.data == "pokercalc:run")
async def calculate_poker_inline(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  if callback.message is not None:
    async with SessionFactory() as session:
      if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
        await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
        return
      ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
      if ready is None:
        await callback.answer(Text.admin.POKER_CASHOUT_EMPTY.value, show_alert=True)
        return
      poker, params = ready
      players = await PokerDataRepository(session).list_players(date=poker.date)
      chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
      chips_entered = sum(int(p.chips or 0) for p in players)
      diff = chips_entered - chips_in_game
      if diff != 0:
        await callback.answer(
          "Количество введенных фишек не совпадает с количеством закупленных\n"
          f"Разница: {diff}",
          show_alert=True,
        )
        return
    await calculate_poker(callback.message, admin_user_id=callback.from_user.id)
  await callback.answer()


@router.message(F.text == Buttons.admin_room.START_BETTING.value)
async def start_betting(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
  await message.answer(await _start_betting_flow(admin_tg_id=message.from_user.id))


@router.callback_query(F.data == "pokerstartbetting:inline")
async def start_betting_inline(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
  result_text = await _start_betting_flow(admin_tg_id=callback.from_user.id)
  await callback.answer(result_text, show_alert=True)
  await _clear_inline_keyboard(callback)
  if callback.message is not None:
    try:
      await callback.message.delete()
    except Exception:
      pass


@router.message(F.text == Buttons.admin_main.CREATE_POLL.value)
async def create_poll_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
  current_month = date.today().replace(day=1)
  next_month = _shift_month(current_month, 1)
  await message.answer(
    "Выбери месяц для опроса:",
    reply_markup=poll_admin_choose_keyboard(current_month=current_month, next_month=next_month),
  )


@router.callback_query(F.data == "polladmin_other")
async def create_poll_choose_other(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
  current = date.today().replace(day=1)
  months = [current, _shift_month(current, 1), _shift_month(current, 2)]
  if callback.message is not None:
    await _safe_callback_edit_reply_markup(callback, reply_markup=poll_admin_other_keyboard(months=months))
  await callback.answer()


@router.callback_query(F.data == "polladmin_cancel")
async def create_poll_cancel(callback: CallbackQuery) -> None:
  if callback.message is not None:
    try:
      await callback.message.delete()
    except Exception:
      await _clear_inline_keyboard(callback)
      await callback.message.answer("Создание опроса отменено.")
      await callback.answer("Отменено")
      return
    await callback.message.answer("Создание опроса отменено.")
  await callback.answer("Отменено")


@router.callback_query(F.data.startswith("polladmin_month:"))
async def create_poll_set_month(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
    month = _parse_month_key(str(callback.data).split(":", 1)[1])
    await PollConfigRepository(session).set_active_month(month=month)
    approved_users = await UserRepository(session).list_approved()
    await session.commit()
  notify_text = "📊 Стартовал опрос на дату следующего покера.\n❗ Не забудь проголосовать."
  from app.bot.telegram.runtime import telegram_bot
  if telegram_bot is not None:
    for user in approved_users:
      if user.telegram_id is not None:
        try:
          await telegram_bot.send_message(
            chat_id=int(user.telegram_id),
            text=notify_text,
            reply_markup=await tg_main_dynamic_keyboard(user),
          )
        except Exception:
          pass
  for user in approved_users:
    if user.vk_id is not None:
      try:
        await send_vk_message(
          user_id=int(user.vk_id),
          message=notify_text,
          keyboard=await vk_main_dynamic_keyboard(user),
        )
      except Exception:
        pass
  await _clear_inline_keyboard(callback)
  if callback.message is not None:
    await callback.message.answer(f"Опрос на {month:%m.%Y} создан.")
  await callback.answer("Опрос создан")


@router.message((F.text == Buttons.admin_room.SET_CASHIER.value) | (F.text == Buttons.admin_room_correct.SET_CASHIER.value))
async def set_cashier_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
    user_repository = UserRepository(session)
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      buyin_data_repository=BuyinDataRepository(session),
    )
    active_players = await use_case.list_active_poker_players()
    if not active_players:
      await message.answer(Text.admin.POKER_PLAYERS_EMPTY.value)
      return
    players: list[SimpleNamespace] = []
    for player in active_players:
      user = await user_repository.get_by_row_id(int(player.player_id))
      if user is None:
        continue
      players.append(SimpleNamespace(player_id=int(user.row_id), player_name=player.player_name))
    if not players:
      await message.answer(Text.admin.POKER_PLAYERS_EMPTY.value)
      return
  await message.answer(
    Text.admin.POKER_CASHIER_CHOOSE.value,
    reply_markup=poker_cashier_candidates_keyboard(players=players),
  )


@router.message(F.text == Buttons.admin_room.CORRECT_POKER.value)
async def open_correct_poker_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
  await message.answer("Корректировки покера:", reply_markup=admin_room_correct_keyboard)


@router.message(F.text == Buttons.admin_room_correct.TO_ADMIN_ROOM.value)
async def back_from_correct_poker_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
  await message.answer(Text.admin.ADMIN_PANEL.value, reply_markup=admin_room_keyboard)


@router.callback_query(F.data.startswith("pokercashier:"))
async def set_cashier_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  user_row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
    user_repository = UserRepository(session)
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      buyin_data_repository=BuyinDataRepository(session),
    )
    updated = await use_case.set_cashier_for_active_poker(cashier_id=user_row_id)
    if updated is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    cashier_user = await user_repository.get_by_row_id(user_row_id)
    cashier_name = cashier_user.name if cashier_user is not None else f"ID {user_row_id}"
    cashier_text = f"{cashier_name} выбран кассиром."
    await _refresh_admin_room_status(session=session)
  await callback.answer(cashier_text)


@router.callback_query(F.data.startswith("pokerroomcashier:"))
async def set_cashier_from_room_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  user_row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
    poker_repository = PokerRepository(session)
    active = await poker_repository.get_started()
    if active is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    poker, _ = active
    if poker.cashier_id is not None:
      await callback.answer(
        "Кассир уже назначен. Для переназначения используй 'Корректировать покер'.",
        show_alert=True,
      )
      return
    user_repository = UserRepository(session)
    use_case = ManagePokerPlayersUseCase(
      poker_repository=poker_repository,
      poker_data_repository=PokerDataRepository(session),
      buyin_data_repository=BuyinDataRepository(session),
    )
    updated = await use_case.set_cashier_for_active_poker(cashier_id=user_row_id)
    if updated is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    cashier_user = await user_repository.get_by_row_id(user_row_id)
    cashier_name = cashier_user.name if cashier_user is not None else f"ID {user_row_id}"
    await _refresh_admin_room_status(session=session)
  await callback.answer(f"{cashier_name} выбран кассиром.")


@router.callback_query(F.data.startswith("pokerroommanage:"))
async def poker_room_manage_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  _, player_id_s = str(callback.data).split(":", maxsplit=1)
  if not player_id_s.isdigit():
    await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
    return
  async with SessionFactory() as session:
    if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
  if callback.message is not None:
    try:
      await _safe_callback_edit_reply_markup(
        callback,
        reply_markup=poker_room_manage_player_keyboard(player_id=int(player_id_s)),
      )
    except Exception:
      await callback.message.answer(
        "Управление игроком:",
        reply_markup=poker_room_manage_player_keyboard(player_id=int(player_id_s)),
      )
  await callback.answer()


@router.callback_query(F.data.startswith("pokerroomapprove:"))
async def poker_room_approve_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  _, player_id_s = str(callback.data).split(":", maxsplit=1)
  if not player_id_s.isdigit():
    await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
    return
  user_row_id = int(player_id_s)
  async with SessionFactory() as session:
    if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
    user_repository = UserRepository(session)
    candidate = await user_repository.get_by_row_id(user_row_id)
    if candidate is None:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
    )
    created = await use_case.add_player_to_active_poker(
      player_id=int(candidate.row_id),
      player_name=candidate.name,
    )
    await use_case.remove_denied_for_active_poker(user_row_id=int(candidate.row_id))
    if created is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
  await _clear_inline_keyboard(callback)
  await callback.answer("Вход разрешен")
  if callback.message is not None:
    await callback.message.answer(f"{candidate.name}: вход разрешен")
  if candidate.telegram_id is not None and callback.message is not None:
    await callback.message.bot.send_message(chat_id=int(candidate.telegram_id), text="Вход в покер рум разрешен.")
  elif candidate.vk_id is not None:
    await send_vk_message(user_id=int(candidate.vk_id), message="Вход в покер рум разрешен.")


@router.callback_query(F.data.startswith("pokerroomreject:"))
async def poker_room_reject_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  _, player_id_s = str(callback.data).split(":", maxsplit=1)
  if not player_id_s.isdigit():
    await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
    return
  user_row_id = int(player_id_s)
  async with SessionFactory() as session:
    if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
    user_repository = UserRepository(session)
    candidate = await user_repository.get_by_row_id(user_row_id)
    if candidate is None:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return
    await PokerRoomDeniedRepository(session).add(user_row_id=int(candidate.row_id))
  await _clear_inline_keyboard(callback)
  await callback.answer("Вход запрещен")
  if callback.message is not None:
    await callback.message.answer(f"{candidate.name}: вход запрещен")
  if candidate.telegram_id is not None and callback.message is not None:
    await callback.message.bot.send_message(chat_id=int(candidate.telegram_id), text="Вход в покер рум запрещен.")
  elif candidate.vk_id is not None:
    await send_vk_message(user_id=int(candidate.vk_id), message="Вход в покер рум запрещен.")


@router.message((F.text == Buttons.admin_room.ADD_PLAYER.value) | (F.text == Buttons.admin_room_correct.ADD_PLAYER.value))
async def add_player_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
    user_repository = UserRepository(session)
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      user_repository=user_repository,
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
    )
    players = await use_case.list_active_poker_players()
    active_user_row_ids = {int(player.player_id) for player in players}
    approved_users = await user_repository.list_approved()
    candidates = [
      user for user in approved_users
      if user.telegram_id is not None and int(user.row_id) not in active_user_row_ids
    ]
    text = Text.admin.POKER_ADD_PLAYER_CHOOSE.value
    if not candidates:
      text = f"{Text.admin.POKER_ADD_PLAYER_EMPTY.value}\n\nМожно добавить нового игрока вручную."
  await message.answer(
    text,
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
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
    user_repository = UserRepository(session)
    user = await user_repository.get_by_row_id(row_id)
    if user is None or user.telegram_id is None:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    created = await use_case.add_player_to_active_poker(
      player_id=int(user.row_id),
      player_name=user.name,
    )
    await use_case.remove_denied_for_active_poker(user_row_id=int(user.row_id))
    if created is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    poker, params = await PokerRepository(session).get_started()
    self_player = await PokerDataRepository(session).get_player(date=poker.date, player_id=int(user.row_id))
    include_king_buyin = bool(self_player is not None and self_player.is_prev_winner)
    current_big_buyin_count = int(self_player.big_buyin_count) if self_player is not None else 0
    current_super_buyin_count = int(self_player.super_buyin_count) if self_player is not None else 0
  if callback.message is not None:
    await callback.message.answer(
      f"🎲 В покер добавлен новый игрок\nИмя: {user.name}: {int(self_player.buyins) if self_player is not None else 0}"
    )
    TG_BUYIN_NOTIFY_CASHIER_ONLY.add((int(callback.from_user.id), int(user.row_id)))
    await callback.message.answer(
      Text.admin.POKER_BUYIN_PROMPT.value,
      reply_markup=poker_buyin_count_keyboard(
        player_id=int(user.row_id),
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
      ),
    )
  await callback.answer("Игрок добавлен")


@router.callback_query(F.data.startswith("pokeraddnew:"))
async def add_player_new_callback(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
  await _clear_inline_keyboard(callback)
  await state.set_state(AdminPokerState.waiting_for_new_player_name)
  if callback.message is not None:
    await callback.message.answer("Введи имя нового игрока:")
  await callback.answer()


@router.callback_query(F.data.startswith("pokeraddcancel:"))
async def add_player_cancel_callback(callback: CallbackQuery) -> None:
  await _clear_inline_keyboard(callback)
  await callback.answer(Buttons.betting_inline.CONFIRM_NO.value)


@router.message(AdminPokerState.waiting_for_new_player_name)
async def add_new_player_name_input(message: Message, state: FSMContext) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  name = " ".join((message.text or "").split())
  if not name:
    await message.answer("Имя не может быть пустым. Введи имя нового игрока:")
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      await state.clear()
      return
    user_repository = UserRepository(session)
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      user_repository=user_repository,
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
    )
    tmp_telegram_id = 0
    while True:
      candidate = -random.randint(10_000_000_000, 9_999_999_999_999)
      if await user_repository.get_by_telegram_id(candidate) is None:
        tmp_telegram_id = candidate
        break
    created_user = await user_repository.create(
      name=name,
      telegram_id=tmp_telegram_id,
      vk_id=None,
      is_approved=True,
      notification_platform=None,
    )
    created_user.telegram_id = -int(created_user.row_id)
    created_user.notification_platform = None
    await session.commit()
    created = await use_case.add_player_to_active_poker(
      player_id=int(created_user.row_id),
      player_name=created_user.name,
    )
    await use_case.remove_denied_for_active_poker(user_row_id=int(created_user.row_id))
    if created is None:
      await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
      await state.clear()
      return
    poker, params = await PokerRepository(session).get_started()
    self_player = await PokerDataRepository(session).get_player(date=poker.date, player_id=int(created_user.row_id))
    include_king_buyin = bool(self_player is not None and self_player.is_prev_winner)
    current_big_buyin_count = int(self_player.big_buyin_count) if self_player is not None else 0
    current_super_buyin_count = int(self_player.super_buyin_count) if self_player is not None else 0
  await state.clear()
  await message.answer(
    f"🎲 В покер добавлен новый игрок\nИмя: {created_user.name}: {int(self_player.buyins) if self_player is not None else 0}"
  )
  TG_BUYIN_NOTIFY_CASHIER_ONLY.add((int(message.from_user.id), int(created_user.row_id)))
  await message.answer(
    Text.admin.POKER_BUYIN_PROMPT.value,
    reply_markup=poker_buyin_count_keyboard(
      player_id=int(created_user.row_id),
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
    ),
  )


@router.message((F.text == Buttons.admin_room.REMOVE_PLAYER.value) | (F.text == Buttons.admin_room_correct.REMOVE_PLAYER.value))
async def remove_player_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
    user_repository = UserRepository(session)
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      buyin_data_repository=BuyinDataRepository(session),
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
      user_repository=user_repository,
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
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
    user_repository = UserRepository(session)
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
      user_repository=user_repository,
    )
    removed_user = await user_repository.get_by_row_id(player_id)
    active = await PokerRepository(session).get_started()
    removed_player_name = removed_user.name if removed_user is not None else f"ID {player_id}"
    removed_player_buyins = 0
    poker_date = None
    if active is not None:
      poker_date = active[0].date
      player_before_remove = await PokerDataRepository(session).get_player(date=poker_date, player_id=player_id)
      if player_before_remove is not None:
        removed_player_name = str(player_before_remove.player_name)
        removed_player_buyins = int(player_before_remove.buyins)
    removed = await use_case.remove_player_from_active_poker(player_id=player_id)
    if removed is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    if removed is False:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return
    if removed_user is not None:
      await _notify_user_removed_from_room(user=removed_user)
    if poker_date is not None:
      await _notify_admins_about_removed_player(
        session=session,
        poker_date=poker_date,
        player_name=removed_player_name,
        buyins=removed_player_buyins,
      )
  if callback.message is not None:
    try:
      await callback.message.delete()
    except Exception:
      pass
  await callback.answer(Text.admin.POKER_REMOVE_PLAYER_SUCCESS.value)


@router.message(F.text == Buttons.admin_room.UNBAN_PLAYER.value)
async def unban_player_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
    user_repository = UserRepository(session)
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
      user_repository=user_repository,
    )
    denied = await use_case.list_denied_for_active_poker()
    if not denied:
      await message.answer(Text.admin.POKER_UNBAN_PLAYER_EMPTY.value)
      return
    candidates: list[dict[str, int | str]] = []
    for item in denied:
      user = await user_repository.get_by_row_id(int(item.user_row_id))
      name = user.name if user is not None else f"ID {int(item.user_row_id)}"
      candidates.append({"player_id": int(item.user_row_id), "name": name})
  await message.answer(
    Text.admin.POKER_UNBAN_PLAYER_CHOOSE.value,
    reply_markup=poker_unban_player_candidates_keyboard(players=candidates),
  )


@router.callback_query(F.data.startswith("pokerunban:"))
async def unban_player_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  user_row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
    user_repository = UserRepository(session)
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
      user_repository=user_repository,
    )
    unbanned_user = await user_repository.get_by_row_id(user_row_id)
    removed = await use_case.remove_denied_for_active_poker(user_row_id=user_row_id)
    if not removed:
      await callback.answer(Text.admin.POKER_UNBAN_PLAYER_EMPTY.value, show_alert=True)
      return
    if unbanned_user is not None:
      await _notify_user_unbanned_for_room(user=unbanned_user)
  if callback.message is not None:
    await _safe_callback_edit_text(callback, Text.admin.POKER_UNBAN_PLAYER_SUCCESS.value)
  await callback.answer(Text.admin.POKER_UNBAN_PLAYER_SUCCESS.value)


@router.message((F.text == Buttons.room.BUYIN.value) | (F.text == Buttons.admin_room_correct.BUYIN_CORRECT.value))
async def buyin_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    user = await user_repository.get_by_telegram_id(message.from_user.id)
    if user is None or not user.is_approved:
      await message.answer(Text.user.STATUS_NEED_REGISTRATION.value)
      return
    is_admin = await is_tg_admin(session=session, telegram_id=message.from_user.id)
    poker_repository = PokerRepository(session)
    active = await poker_repository.get_started()
    if active is None:
      await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
      return
    poker, params = active
    if poker.is_ready_for_chips_entering:
      await message.answer(Text.user.FINISH_CHIPS_NOT_READY.value)
      return
    if poker.cashier_id is None:
      await message.answer(Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value)
      return
    poker_data_repository = PokerDataRepository(session)
    players = await poker_data_repository.list_players(date=poker.date)
    if not players:
      await message.answer(Text.admin.POKER_BUYIN_EMPTY.value)
      return

    is_correct_mode = message.text == Buttons.admin_room_correct.BUYIN_CORRECT.value
    if is_admin:
      prompt_text = Text.admin.POKER_BUYIN_CORRECT_CHOOSE.value if is_correct_mode else Text.admin.POKER_BUYIN_CHOOSE.value
      await message.answer(
        prompt_text,
        reply_markup=poker_buyin_candidates_keyboard(
          players=players,
          show_buyins=is_correct_mode,
          callback_prefix="pokerbuyincorrect" if is_correct_mode else "pokerbuyin",
        ),
      )
      return

    self_player = await poker_data_repository.get_player(date=poker.date, player_id=int(user.row_id))
    if self_player is None:
      await message.answer(Text.user.STATUS_ROOM_NOT_ADDED.value)
      return
    include_king_buyin = bool(self_player.is_prev_winner)
    await message.answer(
      Text.admin.POKER_BUYIN_PROMPT.value,
      reply_markup=poker_buyin_count_keyboard(
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


@router.callback_query(F.data.startswith("pokerbuyin:"))
async def buyin_select_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  player_id = int(callback.data.split(":", 1)[1])
  source_message = callback.message
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
    poker_repository = PokerRepository(session)
    active = await poker_repository.get_started()
    if active is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    poker, params = active
    if poker.is_ready_for_chips_entering:
      await callback.answer(Text.user.FINISH_CHIPS_NOT_READY.value, show_alert=True)
      return
    if poker.cashier_id is None:
      await callback.answer(Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value, show_alert=True)
      return
    player = await PokerDataRepository(session).get_player(date=poker.date, player_id=player_id)
    include_king_buyin = bool(player is not None and player.is_prev_winner)
    current_big_buyin_count = int(player.big_buyin_count) if player is not None else 0
    current_super_buyin_count = int(player.super_buyin_count) if player is not None else 0
  if source_message is not None:
    try:
      await source_message.delete()
    except Exception:
      pass
    await source_message.answer(
      Text.admin.POKER_BUYIN_PROMPT.value,
      reply_markup=poker_buyin_count_keyboard(
        player_id=player_id,
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
      ),
    )
  await callback.answer()


@router.callback_query(F.data.startswith("pokerbuyincorrect:"))
async def buyin_correct_select_callback(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  player_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
    active = await PokerRepository(session).get_started()
    if active is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    poker, _ = active
    player = await PokerDataRepository(session).get_player(date=poker.date, player_id=player_id)
    if player is None:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return
    await state.set_state(AdminPokerState.waiting_for_buyin_correct_amount)
    await state.update_data(
      buyin_correct_player_id=int(player_id),
      buyin_correct_player_name=str(player.player_name),
      buyin_correct_old_buyins=int(player.buyins),
    )
  if callback.message is not None:
    await callback.message.answer(
      f"Введи новое количество закупов для {player.player_name}.\nСейчас: {int(player.buyins)}"
    )
  await callback.answer()


@router.message(AdminPokerState.waiting_for_buyin_correct_amount)
async def buyin_correct_amount_input(message: Message, state: FSMContext) -> None:
  if message.from_user is None or not message.text:
    return
  if not message.text.isdigit():
    await message.answer(Text.admin.POKER_BUYIN_INVALID.value)
    return
  new_buyins = int(message.text)
  data = await state.get_data()
  player_id = int(data.get("buyin_correct_player_id", 0))
  old_buyins = int(data.get("buyin_correct_old_buyins", 0))
  player_name = str(data.get("buyin_correct_player_name", "игрок"))
  if player_id <= 0:
    await state.clear()
    await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
    return
  await message.answer(
    f"Подтверди изменение для {player_name}: {old_buyins} → {new_buyins}",
    reply_markup=poker_buyin_correct_confirm_keyboard(player_id=player_id, new_buyins=new_buyins),
  )


@router.callback_query(F.data.startswith("pokerbuyincorrectconfirm:"))
async def buyin_correct_confirm_callback(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  parts = str(callback.data).split(":")
  if len(parts) != 4:
    await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
    return
  choice, player_id_s, new_buyins_s = parts[1], parts[2], parts[3]
  if not (player_id_s.isdigit() and new_buyins_s.isdigit()):
    await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
    return
  player_id = int(player_id_s)
  new_buyins = int(new_buyins_s)
  await _clear_inline_keyboard(callback)
  if choice != "yes":
    await state.clear()
    await callback.answer(Buttons.betting_inline.CONFIRM_NO.value)
    return
  async with SessionFactory() as session:
    if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      await state.clear()
      return
    active = await PokerRepository(session).get_started()
    if active is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      await state.clear()
      return
    poker, _ = active
    poker_data_repository = PokerDataRepository(session)
    player = await poker_data_repository.get_player(date=poker.date, player_id=player_id)
    if player is None:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      await state.clear()
      return
    old_buyins = int(player.buyins)
    delta = int(new_buyins) - old_buyins
    if delta != 0:
      updated = await poker_data_repository.add_buyins(
        date=poker.date,
        player_id=player_id,
        buyins_count=delta,
        big_buyin_count=0,
        super_buyin_count=0,
      )
      if updated is None:
        await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
        await state.clear()
        return
    else:
      updated = player
  await state.clear()
  if callback.message is not None:
    await callback.message.answer(f"{Text.admin.POKER_BUYIN_SAVED.value}\n\n{updated.player_name}: {updated.buyins}")
  await callback.answer(Text.admin.POKER_BUYIN_SAVED.value)


@router.callback_query(F.data.startswith("pokerbuyincount:"))
async def buyin_count_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  parts = callback.data.split(":")
  if len(parts) != 3:
    await callback.answer(Text.admin.POKER_BUYIN_INVALID.value, show_alert=True)
    return
  player_id = int(parts[1])
  buyins_count = int(parts[2])
  if buyins_count <= 0:
    await callback.answer(Text.admin.POKER_BUYIN_INVALID.value, show_alert=True)
    return
  source_message = callback.message
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    is_admin = await is_tg_admin(session=session, telegram_id=callback.from_user.id)
    requester = await UserRepository(session).get_by_telegram_id(callback.from_user.id)
    requester_row_id = int(requester.row_id) if requester is not None else -1
    if not is_admin and int(player_id) != requester_row_id:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return
    poker_repository = PokerRepository(session)
    active = await poker_repository.get_started()
    if active is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    poker, params = active
    if poker.is_ready_for_chips_entering:
      await callback.answer(Text.user.FINISH_CHIPS_NOT_READY.value, show_alert=True)
      return
    if poker.cashier_id is None:
      await callback.answer(Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value, show_alert=True)
      return
    prev_player = await PokerDataRepository(session).get_player(date=poker.date, player_id=player_id)
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
      if buyins_count > int(params.max_buyins) and buyins_count not in allowed_special_amounts:
        await callback.answer(Text.admin.POKER_BUYIN_INVALID.value, show_alert=True)
        return
    big_count = 0
    super_count = 0
    if is_special_mode:
      if include_king_buyin and current_big_count == 0 and current_super_count == 0 and buyins_count >= king_threshold:
        big_count += 1
        super_count += 1
      elif buyins_count >= super_threshold:
        if current_big_count == 0 and current_super_count == 0:
          super_count += 1
        elif current_super_count == 0 and current_big_count < 2 and buyins_count >= big_threshold:
          big_count += 1
      elif current_super_count == 0 and current_big_count < 2 and buyins_count >= big_threshold:
        big_count += 1
    use_case = ManagePokerPlayersUseCase(
      poker_repository=poker_repository,
      poker_data_repository=PokerDataRepository(session),
      buyin_data_repository=BuyinDataRepository(session),
    )
    updated = await use_case.add_buyin_to_active_player(
      player_id=int(player_id),
      buyins_count=buyins_count,
      big_buyin_count=big_count,
      super_buyin_count=super_count,
      poker_date=poker.date,
    )
    if updated is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    notify_admins = True
    key = (int(callback.from_user.id), int(player_id))
    if key in TG_BUYIN_NOTIFY_CASHIER_ONLY:
      notify_admins = False
      TG_BUYIN_NOTIFY_CASHIER_ONLY.discard(key)
    await _notify_about_buyin(
      session=session,
      poker=poker,
      updated_player=updated,
      buyins_count=buyins_count,
      notify_admins=notify_admins,
    )
  if source_message is not None:
    try:
      await source_message.delete()
    except Exception:
      pass
  await callback.answer(Text.admin.POKER_BUYIN_SAVED.value)


@router.callback_query(F.data.startswith("pokerbuyincancel:"))
async def buyin_cancel_callback(callback: CallbackQuery) -> None:
  source_message = callback.message
  await _clear_inline_keyboard(callback)
  if source_message is not None:
    try:
      await source_message.delete()
    except Exception:
      pass
  await callback.answer(Buttons.betting_inline.CONFIRM_NO.value)


@router.callback_query(F.data.startswith("pokercashout:"))
async def cashout_select_callback(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  player_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
    user_repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    poker_data_repository = PokerDataRepository(session)
    ready = await poker_repository.get_latest_ready_for_chips_with_params()
    if ready is None:
      await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
      return
    poker, params = ready
    player = await poker_data_repository.get_player(date=poker.date, player_id=player_id)
    if player is None:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return
    data = await state.get_data()
    chips_value = data.get("cashout_input_value")
    if chips_value is not None:
      chips = int(chips_value)
      bb_size = max(1, int(params.bb_size_chips or 10))
      step = max(1, bb_size // 2)
      if chips % step != 0:
        await state.update_data(cashout_input_value=None)
        if callback.message is not None:
          await callback.message.answer(Text.user.FINISH_CHIPS_INVALID.value.format(step=step))
        await callback.answer()
        return
      money_kopecks = ((chips - int(player.buyins) * int(params.buyin_size_chips)) * int(params.buyin_size_kopecks)) // int(params.buyin_size_chips)
      updated = await poker_data_repository.set_chips(date=poker.date, player_id=player_id, chips=chips)
      if updated is not None:
        await poker_data_repository.set_cashout(date=poker.date, player_id=player_id, money_kopecks=int(money_kopecks))
        await _upsert_tg_admin_chips_status(session=session, poker_date=poker.date)
      await state.update_data(cashout_input_value=None)
      if updated is not None:
        user = await user_repository.get_by_row_id(int(updated.player_id))
        if user is not None and user.notification_platform == "tg" and user.telegram_id is not None:
          await _upsert_tg_user_chips_result(
            chat_id=int(user.telegram_id),
            text=_build_user_chips_text(
              chips=int(chips),
              money_kopecks=int(money_kopecks),
              reaction=_get_reaction("winner" if int(money_kopecks) >= 0 else "loser"),
            ),
          )
        elif user is not None and user.notification_platform == "vk" and user.vk_id is not None:
          await send_vk_message(
            user_id=user.vk_id,
            message=_build_user_chips_text(
              chips=int(chips),
              money_kopecks=int(money_kopecks),
              reaction=_get_reaction("winner" if int(money_kopecks) >= 0 else "loser"),
            ),
          )
      if callback.message is not None:
        try:
          await callback.message.delete()
        except Exception:
          pass
      await callback.answer(Text.admin.POKER_CASHOUT_SAVED.value)
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
  chips = int(message.text)
  target_user = None
  data = await state.get_data()
  player_id = data.get("cashout_player_id")
  if player_id is None:
    await state.clear()
    await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
    return
  async with SessionFactory() as session:
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      await state.clear()
      return
    user_repository = UserRepository(session)
    ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
    if ready is None:
      await state.clear()
      await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
      return
    poker, params = ready
    bb_size = max(1, int(params.bb_size_chips or 10))
    step = max(1, bb_size // 2)
    if chips % step != 0:
      await message.answer(Text.user.FINISH_CHIPS_INVALID.value.format(step=step))
      return
    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    updated = await use_case.set_chips_for_ready_poker_player(player_id=int(player_id), chips=chips)
    if updated is None:
      await state.clear()
      await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
      return
    money_kopecks = ((chips - int(updated.buyins) * int(params.buyin_size_chips)) * int(params.buyin_size_kopecks)) // int(params.buyin_size_chips)
    await PokerDataRepository(session).set_cashout(
      date=poker.date,
      player_id=int(player_id),
      money_kopecks=int(money_kopecks),
    )
    await _upsert_tg_admin_chips_status(session=session, poker_date=poker.date)
    target_user = await user_repository.get_by_row_id(int(player_id))
  await state.clear()
  if target_user is not None and target_user.notification_platform == "tg" and target_user.telegram_id is not None:
    await _upsert_tg_user_chips_result(
      chat_id=int(target_user.telegram_id),
      text=_build_user_chips_text(
        chips=int(chips),
        money_kopecks=int(money_kopecks),
        reaction=_get_reaction("winner" if int(money_kopecks) >= 0 else "loser"),
      ),
    )
  elif target_user is not None and target_user.notification_platform == "vk" and target_user.vk_id is not None:
    await send_vk_message(
      user_id=target_user.vk_id,
      message=_build_user_chips_text(
        chips=int(chips),
        money_kopecks=int(money_kopecks),
        reaction=_get_reaction("winner" if int(money_kopecks) >= 0 else "loser"),
      ),
    )


@router.message(F.text == Buttons.admin_main.MAKE_ADMIN.value)
async def make_admin_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return

  async with SessionFactory() as session:
    repository = UserRepository(session)
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
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
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return

    use_case = MakeAdminUseCase(repository)
    try:
      user = await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
      return

  if callback.message is not None:
    await _safe_callback_edit_text(
      callback,
      f"{Text.admin.MAKE_ADMIN_SUCCESS.value}\n\n"
      f"Имя: {user.name}",
    )
  await callback.answer(Text.admin.MAKE_ADMIN_SUCCESS.value)


@router.message(F.text == Buttons.admin_room.TO_ROOM.value)
async def back_to_room_admin_panel(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
    return
  async with SessionFactory() as session:
    repository = UserRepository(session)
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      return
  await message.answer("Покер рум.", reply_markup=room_admin_keyboard)


@router.callback_query(F.data.startswith("approve:"))
async def approve_registration_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)

  async with SessionFactory() as session:
    repository = UserRepository(session)
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
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
    await _safe_callback_edit_text(
      callback,
      f"Заявка #{row_id} одобрена.\nИмя: {user.name}\nTelegram ID: {user.telegram_id}",
    )
  await callback.answer(Text.admin.APPROVE_ACTION.value)


@router.callback_query(F.data.startswith("betreceipt:"))
async def bet_receipt_manual_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return
  parts = callback.data.split(":")
  if len(parts) < 3:
    await callback.answer("Некорректные данные.", show_alert=True)
    return
  action = parts[1]
  try:
    receipt_row_id = int(parts[2])
  except Exception:
    await callback.answer("Некорректные данные.", show_alert=True)
    return
  admin_id = int(callback.from_user.id)
  state_key = (admin_id, int(receipt_row_id))

  async with SessionFactory() as session:
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
      return
    receipt_repo = BetPaymentReceiptRepository(session)
    bet_repo = BetRepository(session)
    user_repo = UserRepository(session)
    receipt = await receipt_repo.get_by_row_id(row_id=int(receipt_row_id))
    if receipt is None:
      await callback.answer("Квитанция не найдена.", show_alert=True)
      return
    unpaid = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
    selected = TG_MANUAL_RECEIPT_SELECTIONS.setdefault(state_key, set())

    if action == "toggle":
      if len(parts) < 5:
        await callback.answer("Некорректные данные.", show_alert=True)
        return
      bet_row_id = int(parts[3])
      page = int(parts[4])
      if bet_row_id in selected:
        selected.remove(bet_row_id)
      else:
        selected.add(bet_row_id)
      await _safe_callback_edit_reply_markup(
        callback,
        bet_receipt_manual_keyboard(
          receipt_row_id=int(receipt_row_id),
          bets=unpaid,
          selected_ids=sorted(selected),
          page=page,
        ),
      )
      await callback.answer("Обновлено")
      return

    if action == "page":
      if len(parts) < 4:
        await callback.answer("Некорректные данные.", show_alert=True)
        return
      page = int(parts[3])
      await _safe_callback_edit_reply_markup(
        callback,
        bet_receipt_manual_keyboard(
          receipt_row_id=int(receipt_row_id),
          bets=unpaid,
          selected_ids=sorted(selected),
          page=page,
        ),
      )
      await callback.answer("Страница")
      return

    if action == "cancel":
      TG_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
      await _safe_callback_edit_text(
        callback,
        f"🧾 Квитанция #{receipt_row_id}\nОтменено. Без изменений.",
        reply_markup=None,
      )
      await callback.answer("Отменено")
      return

    if action != "done":
      await callback.answer("Некорректное действие.", show_alert=True)
      return

    chosen = [bet for bet in unpaid if int(bet.row_id) in selected]
    if not chosen:
      await callback.answer("Выбери хотя бы одну ставку.", show_alert=True)
      return
    await bet_repo.mark_paid(bets=chosen)
    receipt.status = "accepted_manual"
    await session.commit()
    if receipt.status.startswith("accepted"):
      try:
        await backup_tables_to_google(session=session)
      except Exception:
        logger.exception("Failed to sync Google backup after manual receipt decision")
    remaining = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
    remaining_kopecks = sum(int(item.amount_kopecks) for item in remaining)
    closed_lines = "\n".join(
      f"{(bet.date.strftime('%d.%m.%Y') if bet.date else '—')} - {int(bet.amount_kopecks) // 100} ₽"
      for bet in chosen
    )
    remaining_lines = "\n".join(
      f"{(bet.date.strftime('%d.%m.%Y') if bet.date else '—')} - {int(bet.amount_kopecks) // 100} ₽"
      for bet in remaining
    )
    owner = await user_repo.get_by_row_id(int(receipt.user_row_id))
    user_message = (
      f"Оплата принята. Закрыто ставок: {len(chosen)}. "
      + (
        "Остаток долга: 0 ₽."
        if remaining_kopecks == 0
        else f"Остаток долга:\n{remaining_lines}"
      )
    )
    from app.bot.telegram.runtime import telegram_bot
    if owner is not None and owner.notification_platform == "tg" and owner.telegram_id is not None and telegram_bot is not None:
      await telegram_bot.send_message(chat_id=int(owner.telegram_id), text=user_message)
    elif owner is not None and owner.notification_platform == "vk" and owner.vk_id is not None:
      await send_vk_message(user_id=int(owner.vk_id), message=user_message, keyboard=vk_betting_keyboard)
    TG_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)

  if callback.message is not None:
    await _safe_callback_edit_text(
      callback,
      (
        f"🧾 Решение по квитанции #{receipt_row_id}\n"
        f"Оплата принята.\n"
        f"Закрытые ставки:\n{closed_lines}\n"
        f"Закрыто ставок: {len(chosen)}\n"
        f"Остаток долга: {_format_rub_from_kopecks(int(remaining_kopecks))} ₽"
      ),
      reply_markup=None,
    )
  await callback.answer("Готово")


@router.callback_query(F.data.startswith("correct:"))
async def correct_registration_callback(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])
  await _clear_inline_keyboard(callback)

  async with SessionFactory() as session:
    repository = UserRepository(session)
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
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
    if not await _ensure_tg_admin_message(session=session, user_id=message.from_user.id, message=message):
      await state.clear()
      return
    repository = UserRepository(session)

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
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
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
    await _safe_callback_edit_text(
      callback,
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
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
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
    if not await _ensure_tg_admin_callback(session=session, user_id=callback.from_user.id, callback=callback):
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
    await _safe_callback_edit_text(
      callback,
      f"{Text.admin.LINK_SUCCESS.value}\n\n"
      f"Pending row_id: {pending_row_id}\n"
      f"Linked to row_id: {user.row_id}\n"
      f"Имя: {user.name}\n"
      f"Telegram ID: {user.telegram_id}\n"
      f"VK ID: {user.vk_id}",
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
  await _safe_callback_edit_reply_markup(
    callback,
    reply_markup=link_candidates_page_keyboard(
      pending_row_id=pending_row_id,
      users=approved_users,
      page=page,
    ),
  )
  await callback.answer()
