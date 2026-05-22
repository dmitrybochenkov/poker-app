from fastapi.responses import PlainTextResponse
from datetime import date, timezone
from types import SimpleNamespace
import random
import logging
from zoneinfo import ZoneInfo

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
from app.bot.telegram.keyboards import main_dynamic_keyboard as tg_main_dynamic_keyboard
from app.bot.telegram.notifications import notify_user_about_approval
from app.bot.vk.api import (
  clear_vk_message_keyboard_by_id,
  delete_vk_message_by_id,
  delete_vk_message,
  pin_vk_message_by_id,
  send_vk_message,
  send_vk_message_event_answer,
  send_vk_message_with_id,
  send_vk_photo,
  unpin_vk_message,
)
from app.bot.shared.chips_runtime import (
  TG_ADMIN_ROOM_STATUS_MSG_IDS,
  VK_ADMIN_CHIPS_STATUS_MSG_IDS,
  VK_ADMIN_ROOM_STATUS_MSG_IDS,
  VK_USER_CHIPS_RESULT_MSG_IDS,
)
from app.bot.telegram.keyboards import poker_room_admin_status_keyboard as tg_poker_room_admin_status_keyboard
from app.bot.vk.keyboards import (
  admin_room_correct_keyboard,
  admin_room_keyboard,
  betting_keyboard,
  link_candidates_keyboard,
  link_candidates_page_keyboard,
  main_keyboard,
  main_dynamic_keyboard as vk_main_dynamic_keyboard,
  make_admin_candidates_keyboard,
  poker_add_player_candidates_keyboard,
  poker_buyin_candidates_keyboard,
  poker_buyin_correct_confirm_keyboard,
  poker_buyin_count_keyboard,
  poker_cashout_candidates_keyboard,
  poker_cashier_candidates_keyboard,
  poker_room_manage_player_keyboard,
  poker_remove_player_candidates_keyboard,
  poker_room_approve_keyboard,
  poker_unban_player_candidates_keyboard,
  poker_params_keyboard,
  poker_calc_keyboard,
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
  WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT,
  WAITING_FOR_ADMIN_CORRECTED_NAME,
  WAITING_FOR_ADMIN_NEW_PLAYER_NAME,
  vk_user_contexts,
  vk_user_states,
)
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.session import SessionFactory
from app.services.buyins_chart import render_buyins_session_chart_png
from app.services.google_backup import backup_tables_to_google

VK_BUYIN_NOTIFY_CASHIER_ONLY: set[tuple[int, int]] = set()
logger = logging.getLogger(__name__)


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


def _build_chips_status_text(*, players: list, chips_in_game: int, chips_entered: int) -> str:
  def money_from_chips(chips: int, buyins: int, buyin_size_chips: int, buyin_size_kopecks: int) -> int:
    if buyin_size_chips <= 0:
      return 0
    return ((int(chips) - int(buyins) * int(buyin_size_chips)) * int(buyin_size_kopecks)) // int(buyin_size_chips)

  def reaction(money_kopecks: int) -> str:
    return "😎" if int(money_kopecks) >= 0 else "🤮"

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
  )


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
        reply_markup=tg_poker_room_admin_status_keyboard(
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
      keyboard=poker_room_admin_status_keyboard(
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


async def _clear_vk_admin_chips_calc_buttons() -> None:
  for peer_id, message_id in list(VK_ADMIN_CHIPS_STATUS_MSG_IDS.items()):
    try:
      await clear_vk_message_keyboard_by_id(
        peer_id=int(peer_id),
        message_id=int(message_id),
      )
    except Exception:
      pass
  VK_ADMIN_CHIPS_STATUS_MSG_IDS.clear()


async def _upsert_vk_admin_chips_status(*, session, poker_date) -> None:
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
    if admin.vk_id is None:
      continue
    prev_mid = VK_ADMIN_CHIPS_STATUS_MSG_IDS.get(int(admin.vk_id))
    if prev_mid is not None:
      try:
        await delete_vk_message_by_id(peer_id=int(admin.vk_id), message_id=int(prev_mid))
      except Exception:
        pass
    sent_mid = await send_vk_message_with_id(
      user_id=int(admin.vk_id),
      message=text,
      keyboard=poker_calc_keyboard(),
    )
    if sent_mid is not None:
      VK_ADMIN_CHIPS_STATUS_MSG_IDS[int(admin.vk_id)] = int(sent_mid)


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
    poker_players = await PokerDataRepository(session).list_players(date=poker.date)
    player_row_ids = {int(p.player_id) for p in poker_players}
    admins = [
      u for u in await user_repository.list_approved()
      if u.is_admin and int(u.row_id) in player_row_ids and (cashier is None or int(u.row_id) != int(cashier.row_id))
    ]
    for admin in admins:
      if admin.notification_platform == "tg" and admin.telegram_id is not None and telegram_bot is not None:
        await telegram_bot.send_message(chat_id=admin.telegram_id, text=text)
      elif admin.notification_platform == "vk" and admin.vk_id is not None:
        await send_vk_message(user_id=admin.vk_id, message=text)

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
      reply_markup=tg_main_keyboard,
    )
  if user.vk_id is not None:
    await send_vk_message(user_id=user.vk_id, message=Text.user.ROOM_REMOVED_BY_ADMIN.value, keyboard=main_keyboard)


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
          starter = await user_repository.get_by_vk_id(admin_user_id)
          if starter is not None:
            await ManagePokerPlayersUseCase(
              poker_repository=PokerRepository(session),
              poker_data_repository=PokerDataRepository(session),
            ).add_player_to_active_poker(
              player_id=int(starter.row_id),
              player_name=starter.name,
            )
          result_text = Text.admin.POKER_START_SUCCESS.value
          approved_users = await user_repository.list_approved()
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
    return None

  if action == "poker_add_player_select":
    row_id = callback_payload.get("row_id")
    if not isinstance(row_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      result_keyboard = None
      result_added_text = None
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
            result_keyboard = None
          else:
            poker, params = await PokerRepository(session).get_started()
            self_player = await PokerDataRepository(session).get_player(date=poker.date, player_id=int(user.row_id))
            include_king_buyin = bool(self_player is not None and self_player.is_prev_winner)
            current_big_buyin_count = int(self_player.big_buyin_count) if self_player is not None else 0
            current_super_buyin_count = int(self_player.super_buyin_count) if self_player is not None else 0
            VK_BUYIN_NOTIFY_CASHIER_ONLY.add((int(admin_user_id), int(user.row_id)))
            result_text = Text.admin.POKER_BUYIN_PROMPT.value
            result_added_text = f"🎲 В покер добавлен новый игрок\nИмя: {user.name}: {int(self_player.buyins) if self_player is not None else 0}"
            result_keyboard = poker_buyin_count_keyboard(
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
            )
            await use_case.remove_denied_for_active_poker(user_row_id=int(user.row_id))
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    if result_added_text:
      await send_vk_message(user_id=admin_user_id, message=result_added_text)
    await send_vk_message(user_id=admin_user_id, message=result_text, keyboard=result_keyboard)
    return None

  if action == "poker_add_player_new":
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.admin.NO_RIGHTS.value,
        )
        return PlainTextResponse("ok")
    vk_user_states[admin_user_id] = WAITING_FOR_ADMIN_NEW_PLAYER_NAME
    vk_user_contexts.setdefault(admin_user_id, {})["new_player_from"] = "poker_add"
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text="Введи имя нового игрока",
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message="Введи имя нового игрока:")
    return PlainTextResponse("ok")

  if action == "poker_add_player_cancel":
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=Buttons.betting_inline.CONFIRM_NO.value,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    return PlainTextResponse("ok")

  if action == "poker_room_manage_select":
    player_id = callback_payload.get("player_id")
    if not isinstance(player_id, int):
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
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text="Выбери действие",
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=admin_user_id,
      message="Управление игроком:",
      keyboard=poker_room_manage_player_keyboard(player_id=int(player_id)),
    )
    return PlainTextResponse("ok")

  if action == "poker_room_approve_select":
    player_id = callback_payload.get("player_id")
    if not isinstance(player_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        result_text = Text.admin.NO_RIGHTS.value
      else:
        user = await user_repository.get_by_row_id(int(player_id))
        if user is None:
          result_text = Text.admin.USER_NOT_FOUND.value
        else:
          use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
          )
          created = await use_case.add_player_to_active_poker(
            player_id=int(user.row_id),
            player_name=user.name,
          )
          await use_case.remove_denied_for_active_poker(user_row_id=int(user.row_id))
          result_text = "Вход разрешен" if created is not None else Text.admin.POKER_ACTIVE_NOT_FOUND.value
          if created is not None:
            if user.telegram_id is not None:
              from app.bot.telegram.runtime import telegram_bot
              if telegram_bot is not None:
                await telegram_bot.send_message(chat_id=int(user.telegram_id), text="Вход в покер рум разрешен.")
            elif user.vk_id is not None:
              await send_vk_message(user_id=int(user.vk_id), message="Вход в покер рум разрешен.")
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    return PlainTextResponse("ok")

  if action == "poker_room_reject_select":
    player_id = callback_payload.get("player_id")
    if not isinstance(player_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        result_text = Text.admin.NO_RIGHTS.value
      else:
        user = await user_repository.get_by_row_id(int(player_id))
        if user is None:
          result_text = Text.admin.USER_NOT_FOUND.value
        else:
          await PokerRoomDeniedRepository(session).add(user_row_id=int(user.row_id))
          result_text = "Вход запрещен"
          if user.telegram_id is not None:
            from app.bot.telegram.runtime import telegram_bot
            if telegram_bot is not None:
              await telegram_bot.send_message(chat_id=int(user.telegram_id), text="Вход в покер рум запрещен.")
          elif user.vk_id is not None:
            await send_vk_message(user_id=int(user.vk_id), message="Вход в покер рум запрещен.")
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return PlainTextResponse("ok")

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
          buyin_data_repository=BuyinDataRepository(session),
          user_repository=user_repository,
          poker_room_denied_repository=PokerRoomDeniedRepository(session),
        )
        removed_user = await user_repository.get_by_row_id(int(player_id))
        active = await PokerRepository(session).get_started()
        removed_player_name = removed_user.name if removed_user is not None else f"ID {int(player_id)}"
        removed_player_buyins = 0
        poker_date = None
        if active is not None:
          poker_date = active[0].date
          player_before_remove = await PokerDataRepository(session).get_player(
            date=poker_date,
            player_id=int(player_id),
          )
          if player_before_remove is not None:
            removed_player_name = str(player_before_remove.player_name)
            removed_player_buyins = int(player_before_remove.buyins)
        removed = await use_case.remove_player_from_active_poker(player_id=int(player_id))
        if removed is None:
          result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
        elif removed is False:
          result_text = Text.admin.USER_NOT_FOUND.value
        else:
          result_text = Text.admin.POKER_REMOVE_PLAYER_SUCCESS.value
          if removed_user is not None:
            await _notify_user_removed_from_room(user=removed_user)
          if poker_date is not None:
            await _notify_admins_about_removed_player(
              session=session,
              poker_date=poker_date,
              player_name=removed_player_name,
              buyins=removed_player_buyins,
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
          await _refresh_admin_room_status(session=session)
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    return PlainTextResponse("ok")

  if action == "poker_room_set_cashier_select":
    user_row_id = callback_payload.get("player_id")
    if not isinstance(user_row_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        result_text = Text.admin.NO_RIGHTS.value
      else:
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
          result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
        else:
          poker, _ = active
          if poker.cashier_id is not None:
            result_text = "Кассир уже назначен. Для переназначения используй 'Корректировать покер'."
          else:
            user_repository = UserRepository(session)
            use_case = ManagePokerPlayersUseCase(
              poker_repository=poker_repository,
              poker_data_repository=PokerDataRepository(session),
              buyin_data_repository=BuyinDataRepository(session),
            )
            updated = await use_case.set_cashier_for_active_poker(cashier_id=user_row_id)
            if updated is None:
              result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
            else:
              cashier_user = await user_repository.get_by_row_id(user_row_id)
              cashier_name = cashier_user.name if cashier_user is not None else f"ID {user_row_id}"
              result_text = f"{cashier_name} выбран кассиром."
              await _refresh_admin_room_status(session=session)
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
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

  if action == "poker_buyin_correct_select":
    player_id = callback_payload.get("player_id")
    if not isinstance(player_id, int):
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
      active = await PokerRepository(session).get_started()
      if active is None:
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.admin.POKER_ACTIVE_NOT_FOUND.value,
        )
        return PlainTextResponse("ok")
      poker, _ = active
      player = await PokerDataRepository(session).get_player(date=poker.date, player_id=int(player_id))
      if player is None:
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.admin.USER_NOT_FOUND.value,
        )
        return PlainTextResponse("ok")
      vk_user_states[admin_user_id] = WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT
      vk_user_contexts.setdefault(admin_user_id, {})
      vk_user_contexts[admin_user_id]["buyin_correct_player_id"] = str(int(player_id))
      vk_user_contexts[admin_user_id]["buyin_correct_old_buyins"] = str(int(player.buyins))
      vk_user_contexts[admin_user_id]["buyin_correct_player_name"] = str(player.player_name)
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text="Введи новое значение",
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=admin_user_id,
      message=f"Введи новое количество закупов для {player.player_name}.\nСейчас: {int(player.buyins)}",
    )
    return PlainTextResponse("ok")

  if action in {"poker_buyin_correct_confirm_yes", "poker_buyin_correct_confirm_no"}:
    player_id = callback_payload.get("player_id")
    new_buyins = callback_payload.get("new_buyins")
    if not isinstance(player_id, int) or not isinstance(new_buyins, int):
      return PlainTextResponse("ok")
    if action.endswith("_no"):
      vk_user_states.pop(admin_user_id, None)
      vk_user_contexts.pop(admin_user_id, None)
      await send_vk_message_event_answer(
        event_id=event_id,
        user_id=admin_user_id,
        peer_id=peer_id,
        text=Buttons.betting_inline.CONFIRM_NO.value,
      )
      await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
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
      active = await PokerRepository(session).get_started()
      if active is None:
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.admin.POKER_ACTIVE_NOT_FOUND.value,
        )
        return PlainTextResponse("ok")
      poker, _ = active
      poker_data_repository = PokerDataRepository(session)
      player = await poker_data_repository.get_player(date=poker.date, player_id=int(player_id))
      if player is None:
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.admin.USER_NOT_FOUND.value,
        )
        return PlainTextResponse("ok")
      old_buyins = int(player.buyins)
      delta = int(new_buyins) - old_buyins
      if delta != 0:
        updated = await poker_data_repository.add_buyins(
          date=poker.date,
          player_id=int(player_id),
          buyins_count=int(delta),
          big_buyin_count=0,
          super_buyin_count=0,
        )
      else:
        updated = player
    vk_user_states.pop(admin_user_id, None)
    vk_user_contexts.pop(admin_user_id, None)
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text=Text.admin.POKER_BUYIN_SAVED.value,
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=admin_user_id,
      message=f"{Text.admin.POKER_BUYIN_SAVED.value}\n\n{updated.player_name}: {updated.buyins}",
    )
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
            notify_admins = True
            key = (int(admin_user_id), int(player_id))
            if key in VK_BUYIN_NOTIFY_CASHIER_ONLY:
              notify_admins = False
              VK_BUYIN_NOTIFY_CASHIER_ONLY.discard(key)
            await _notify_about_buyin(
              session=session,
              poker=poker,
              updated_player=updated,
              buyins_count=int(buyins_count),
              notify_admins=notify_admins,
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
                await _upsert_vk_admin_chips_status(session=session, poker_date=poker.date)
              vk_user_contexts.setdefault(admin_user_id, {}).pop("cashout_input_value", None)
              target_user = await user_repository.get_by_row_id(int(player_id))
              if target_user is not None and target_user.vk_id is not None:
                user_text = _build_user_chips_text(
                  chips=int(chips),
                  money_kopecks=int(money_kopecks),
                  reaction=_get_reaction("winner" if int(money_kopecks) >= 0 else "loser"),
                )
                prev_user_mid = VK_USER_CHIPS_RESULT_MSG_IDS.get(int(target_user.vk_id))
                if prev_user_mid is not None:
                  try:
                    await delete_vk_message_by_id(peer_id=int(target_user.vk_id), message_id=int(prev_user_mid))
                  except Exception:
                    pass
                sent_user_mid = await send_vk_message_with_id(user_id=int(target_user.vk_id), message=user_text)
                if sent_user_mid is not None:
                  VK_USER_CHIPS_RESULT_MSG_IDS[int(target_user.vk_id)] = int(sent_user_mid)
              result_text = "Сохранено"
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
    if result_text == Text.admin.POKER_CASHOUT_PROMPT.value:
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
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message=f"Опрос на {month:%m.%Y} создан.")
    return PlainTextResponse("ok")

  if action == "polladmin_cancel":
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text="Отменено",
    )
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=admin_user_id, message="Создание опроса отменено.")
    return PlainTextResponse("ok")

  if action == "poker_calc_run":
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=admin_user_id):
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.admin.NO_RIGHTS.value,
        )
        return PlainTextResponse("ok")
      ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
      if ready is None:
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.admin.POKER_CASHOUT_EMPTY.value,
        )
        return PlainTextResponse("ok")
      poker, params = ready
      players = await PokerDataRepository(session).list_players(date=poker.date)
      chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
      chips_entered = sum(int(p.chips or 0) for p in players)
      diff = chips_entered - chips_in_game
      if diff != 0:
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=f"Фишки не сходятся. Разница: {diff}",
        )
        return PlainTextResponse("ok")
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text="Запускаю расчет...",
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    return await handle_admin_text_commands(user_id=admin_user_id, text=Buttons.admin_room.CALCULATE_POKER.value)

  if action == "poker_start_betting_inline":
    await send_vk_message_event_answer(
      event_id=event_id,
      user_id=admin_user_id,
      peer_id=peer_id,
      text="Запускаю...",
    )
    await _clear_event_inline_keyboard_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    return await handle_admin_text_commands(user_id=admin_user_id, text=Buttons.admin_room.START_BETTING.value)

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

  if vk_user_states.get(user_id) == WAITING_FOR_ADMIN_NEW_PLAYER_NAME:
    name = " ".join((text or "").split())
    if not name:
      await send_vk_message(user_id=user_id, message="Имя не может быть пустым. Введи имя нового игрока:")
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=user_id):
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
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
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value)
        return PlainTextResponse("ok")
      poker, params = await PokerRepository(session).get_started()
      self_player = await PokerDataRepository(session).get_player(date=poker.date, player_id=int(created_user.row_id))
      include_king_buyin = bool(self_player is not None and self_player.is_prev_winner)
      current_big_buyin_count = int(self_player.big_buyin_count) if self_player is not None else 0
      current_super_buyin_count = int(self_player.super_buyin_count) if self_player is not None else 0
      VK_BUYIN_NOTIFY_CASHIER_ONLY.add((int(user_id), int(created_user.row_id)))
    vk_user_states.pop(user_id, None)
    vk_user_contexts.pop(user_id, None)
    await send_vk_message(
      user_id=user_id,
      message=f"🎲 В покер добавлен новый игрок\nИмя: {created_user.name}: {int(self_player.buyins) if self_player is not None else 0}",
    )
    await send_vk_message(
      user_id=user_id,
      message=Text.admin.POKER_BUYIN_PROMPT.value,
      keyboard=poker_buyin_count_keyboard(
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
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT:
    if not text.isdigit():
      await send_vk_message(user_id=user_id, message=Text.admin.POKER_BUYIN_INVALID.value)
      return PlainTextResponse("ok")
    new_buyins = int(text)
    ctx = vk_user_contexts.get(user_id, {})
    player_id = int(ctx.get("buyin_correct_player_id", "0") or "0")
    old_buyins = int(ctx.get("buyin_correct_old_buyins", "0") or "0")
    player_name = str(ctx.get("buyin_correct_player_name", "игрок"))
    if player_id <= 0:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message(user_id=user_id, message=Text.admin.REQUEST_NOT_FOUND.value)
      return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=f"Подтверди изменение для {player_name}: {old_buyins} → {new_buyins}",
      keyboard=poker_buyin_correct_confirm_keyboard(player_id=player_id, new_buyins=new_buyins),
    )
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_ADMIN_CASHOUT_AMOUNT:
    if not text.isdigit() or int(text) < 0:
      await send_vk_message(user_id=user_id, message=Text.admin.POKER_CASHOUT_INVALID.value)
      return PlainTextResponse("ok")
    chips = int(text)
    target_user = None
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
      await _upsert_vk_admin_chips_status(session=session, poker_date=poker.date)
      target_user = await user_repository.get_by_row_id(int(player_id))
    vk_user_states.pop(user_id, None)
    vk_user_contexts.pop(user_id, None)
    if target_user is not None and target_user.vk_id is not None:
      user_text = _build_user_chips_text(
        chips=int(chips),
        money_kopecks=int(money_kopecks),
        reaction=_get_reaction("winner" if int(money_kopecks) >= 0 else "loser"),
      )
      prev_mid = VK_USER_CHIPS_RESULT_MSG_IDS.get(int(target_user.vk_id))
      if prev_mid is not None:
        try:
          await delete_vk_message_by_id(peer_id=int(target_user.vk_id), message_id=int(prev_mid))
        except Exception:
          pass
      sent_mid = await send_vk_message_with_id(user_id=int(target_user.vk_id), message=user_text)
      if sent_mid is not None:
        VK_USER_CHIPS_RESULT_MSG_IDS[int(target_user.vk_id)] = int(sent_mid)
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
      message="\n\n".join(
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
      await PokerRoomDeniedRepository(session).clear_all()
    await _notify_players_about_finish(players=players)
    await send_vk_message(user_id=user_id, message=Text.admin.POKER_FINISH_SUCCESS.value)
    if players:
      async with SessionFactory() as session:
        await _upsert_vk_admin_chips_status(session=session, poker_date=players[0].date)
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
      chips_entered = sum(int(p.chips or 0) for p in players)
      diff = chips_entered - chips_in_game
      if diff != 0:
        mismatch_text = (
          "Количество введенных фишек не совпадает с количеством закупленных\n"
          f"Разница: {diff}"
        )
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
      winner_line = ", ".join(f"{_winner_mark(is_streak=(name in prev_winners))} {name}" for name in winners)
      loser_line = ", ".join(f"❌ {name}" for name in loosers)

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
        if not guessed_winner and not guessed_loser:
          continue
        mark = _bet_mark(
          amount_kopecks=int(bet.amount_kopecks),
          guessed_winner=guessed_winner,
          guessed_loser=guessed_loser,
        )
        bet_lines.append(f"{bet.better_name}: {mark} +{int(bet.score)}")
      await poker_repository.finish_chips_entering(
        poker,
        winners=winners_text,
        loosers=loosers_text,
      )
      try:
        await backup_tables_to_google(session=session)
      except Exception:
        logger.exception("Google backup failed after poker calculation (VK).")

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
      result_lines.extend(bet_lines if bet_lines else ["Успешных ставок не было"])
      result_text = "\n".join(result_lines)
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
          await telegram_bot.send_message(chat_id=user.telegram_id, text=result_text, reply_markup=tg_main_keyboard)
          if chart_png is not None:
            from aiogram.types import BufferedInputFile
            await telegram_bot.send_photo(
              chat_id=user.telegram_id,
              photo=BufferedInputFile(chart_png, filename="poker_buyins_session.png"),
              caption="📈 Закупы за игру",
              reply_markup=tg_main_keyboard,
            )
          sent_tg_ids.add(int(user.telegram_id))
        elif user.notification_platform == "vk" and user.vk_id is not None:
          await send_vk_message(user_id=user.vk_id, message=result_text, keyboard=main_keyboard)
          if chart_png is not None:
            await send_vk_photo(user_id=user.vk_id, image_bytes=chart_png, filename="poker_buyins_session.png")
          sent_vk_ids.add(int(user.vk_id))
      initiator = await user_repository.get_by_vk_id(int(user_id))
      if initiator is not None:
        if (
          initiator.notification_platform == "tg"
          and initiator.telegram_id is not None
          and telegram_bot is not None
          and int(initiator.telegram_id) not in sent_tg_ids
        ):
          await telegram_bot.send_message(chat_id=initiator.telegram_id, text=result_text, reply_markup=tg_main_keyboard)
          if chart_png is not None:
            from aiogram.types import BufferedInputFile
            await telegram_bot.send_photo(
              chat_id=initiator.telegram_id,
              photo=BufferedInputFile(chart_png, filename="poker_buyins_session.png"),
              caption="📈 Закупы за игру",
              reply_markup=tg_main_keyboard,
            )
        elif (
          initiator.notification_platform == "vk"
          and initiator.vk_id is not None
          and int(initiator.vk_id) not in sent_vk_ids
        ):
          await send_vk_message(user_id=initiator.vk_id, message=result_text, keyboard=main_keyboard)
          if chart_png is not None:
            await send_vk_photo(user_id=initiator.vk_id, image_bytes=chart_png, filename="poker_buyins_session.png")
      await _clear_vk_admin_chips_calc_buttons()
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
    current_month = date.today().replace(day=1)
    next_month = _shift_month(current_month, 1)
    await send_vk_message(
      user_id=user_id,
      message="Выбери месяц для опроса:",
      keyboard=poll_admin_choose_keyboard(current_month=current_month, next_month=next_month),
    )
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.CORRECT_POKER.value:
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message="Корректировки покера:", keyboard=admin_room_correct_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.admin_room_correct.TO_ADMIN_ROOM.value:
    async with SessionFactory() as session:
      if not await is_vk_admin(session=session, vk_id=user_id):
        await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
        return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=Text.admin.ADMIN_PANEL.value, keyboard=admin_room_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.ADD_PLAYER.value or text == Buttons.admin_room_correct.ADD_PLAYER.value:
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
      text_out = Text.admin.POKER_ADD_PLAYER_CHOOSE.value
      if not candidates:
        text_out = f"{Text.admin.POKER_ADD_PLAYER_EMPTY.value}\n\nМожно добавить нового игрока вручную."
    await send_vk_message(
      user_id=user_id,
      message=text_out,
      keyboard=poker_add_player_candidates_keyboard(users=candidates),
    )
    return PlainTextResponse("ok")

  if text == Buttons.admin_room.REMOVE_PLAYER.value or text == Buttons.admin_room_correct.REMOVE_PLAYER.value:
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

  if text == Buttons.admin_room.SET_CASHIER.value or text == Buttons.admin_room_correct.SET_CASHIER.value:
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

  if text == Buttons.room.BUYIN.value or text == Buttons.admin_room_correct.BUYIN_CORRECT.value:
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

      is_correct_mode = text == Buttons.admin_room_correct.BUYIN_CORRECT.value
      if is_admin:
        prompt_text = Text.admin.POKER_BUYIN_CORRECT_CHOOSE.value if is_correct_mode else Text.admin.POKER_BUYIN_CHOOSE.value
        await send_vk_message(
          user_id=user_id,
          message=prompt_text,
          keyboard=poker_buyin_candidates_keyboard(
            players=players,
            show_buyins=is_correct_mode,
            action="poker_buyin_correct_select" if is_correct_mode else "poker_buyin_select",
          ),
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
