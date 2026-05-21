from datetime import date
import random

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message

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
  admin_room_keyboard,
  main_keyboard,
  main_dynamic_keyboard,
  admin_main_keyboard,
  poll_menu_keyboard,
  new_user_keyboard,
  betting_keyboard,
  betting_current_keyboard,
  betting_info_keyboard,
  poker_keyboard,
  poker_info_keyboard,
  poker_cashout_candidates_keyboard,
  poker_room_admin_status_keyboard,
  poker_room_approve_keyboard,
  room_admin_keyboard,
  room_keyboard,
  betting_confirm_keyboard,
  betting_player_keyboard,
  betting_size_keyboard,
  betting_stat_mode_keyboard,
  betting_stat_indicators_keyboard,
  poker_stat_indicators_keyboard,
  poker_history_year_keyboard,
  poker_history_dates_keyboard,
  poker_calc_keyboard,
  stat_year_keyboard,
  stat_sort_keyboard,
  poll_month_keyboard,
  played_before_keyboard,
  registration_candidates_keyboard,
  registration_candidates_page_keyboard,
  registration_link_review_keyboard,
  registration_optional_details_keyboard,
  registration_platform_keyboard,
  registration_review_keyboard,
)
from app.bot.telegram.notifications import notify_admins_about_registration
from app.bot.telegram.states import PollState, RegistrationState
from app.bot.vk.keyboards import (
  poker_room_approve_keyboard as vk_poker_room_approve_keyboard,
  poker_room_admin_status_keyboard as vk_poker_room_admin_status_keyboard,
  registration_link_review_keyboard as vk_registration_link_review_keyboard,
  registration_review_keyboard as vk_registration_review_keyboard,
)
from app.bot.vk.api import delete_vk_message_by_id, send_vk_message, send_vk_message_with_id
from app.bot.shared.chips_runtime import (
  TG_ADMIN_CHIPS_STATUS_MSG_IDS,
  TG_USER_CHIPS_RESULT_MSG_IDS,
  TG_ADMIN_ROOM_STATUS_MSG_IDS,
  VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.vk.notifications import notify_admins_about_registration as notify_vk_admins_about_registration
from app.db.models.user import User
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.achievement_repository import AchievementRepository
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poll_vote_repository import PollVoteRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.stat_image import render_stat_table_png
from app.services.buyins_chart import render_buyins_session_chart_png

router = Router()


def _money_kopecks_from_chips(*, chips: int, buyins: int, buyin_size_chips: int, buyin_size_kopecks: int) -> int:
  if buyin_size_chips <= 0:
    return 0
  return ((int(chips) - int(buyins) * int(buyin_size_chips)) * int(buyin_size_kopecks)) // int(buyin_size_chips)


def _chips_reaction(money_kopecks: int) -> str:
  winner = ["🍾", "👍", "🔥", "🏆", "👏", "🤩", "🎉"]
  loser = ["👎", "🥴", "😢", "💩", "🤮", "😭", "🤷‍♀"]
  return random.choice(winner if int(money_kopecks) >= 0 else loser)


def _format_rub_from_kopecks(value_kopecks: int) -> str:
  rub = int(value_kopecks) // 100
  kop = abs(int(value_kopecks) % 100)
  if kop == 0:
    return str(rub)
  return f"{rub}.{kop:02d}"


def _format_waiting_players(players: list) -> str:
  waiting = [p.player_name for p in players if p.chips is None]
  if not waiting:
    return Text.admin.POKER_CHIPS_ALL_ENTERED.value
  return Text.admin.POKER_CHIPS_WAITING.value.format(players="\n".join(f"- {name}" for name in waiting))


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


async def _notify_admins_about_chips_entry(*, session, player, chips: int, money_kopecks: int) -> None:
  from app.bot.telegram.runtime import telegram_bot

  user_repository = UserRepository(session)
  poker_repository = PokerRepository(session)
  players = await PokerDataRepository(session).list_players(date=player.date)
  player_row_ids = {int(p.player_id) for p in players}
  admins = [u for u in await user_repository.list_approved() if u.is_admin and int(u.row_id) in player_row_ids]
  chips_entered = sum(int(p.chips or 0) for p in players)
  chips_in_game = 0
  ready = await poker_repository.get_latest_ready_for_chips_with_params()
  if ready is not None:
    poker, params = ready
    if poker.date == player.date:
      chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
      for p in players:
        setattr(p, "_buyin_size_chips", int(params.buyin_size_chips))
        setattr(p, "_buyin_size_kopecks", int(params.buyin_size_kopecks))
  full_text = _build_chips_status_text(players=players, chips_in_game=chips_in_game, chips_entered=chips_entered)
  for admin in admins:
    if admin.notification_platform == "tg" and admin.telegram_id is not None and telegram_bot is not None:
      prev_msg_id = TG_ADMIN_CHIPS_STATUS_MSG_IDS.get(int(admin.telegram_id))
      if prev_msg_id is not None:
        try:
          await telegram_bot.delete_message(chat_id=admin.telegram_id, message_id=prev_msg_id)
        except Exception:
          pass
      sent = await telegram_bot.send_message(
        chat_id=admin.telegram_id,
        text=full_text,
        reply_markup=poker_calc_keyboard(),
      )
      TG_ADMIN_CHIPS_STATUS_MSG_IDS[int(admin.telegram_id)] = int(sent.message_id)
    elif admin.notification_platform == "vk" and admin.vk_id is not None:
      await send_vk_message(user_id=admin.vk_id, message=full_text)


def _month_bounds(month: date) -> tuple[date, date]:
  first = date(month.year, month.month, 1)
  if month.month == 12:
    nxt = date(month.year + 1, 1, 1)
  else:
    nxt = date(month.year, month.month + 1, 1)
  return first, (nxt.fromordinal(nxt.toordinal() - 1))


def _parse_month_key(value: str | None) -> date:
  if not value:
    today = date.today()
    return date(today.year, today.month, 1)
  year_s, mon_s = str(value).split("-")
  return date(int(year_s), int(mon_s), 1)


def _parse_iso_dates(values: list[str] | None) -> list[date]:
  if not values:
    return []
  result: list[date] = []
  for item in values:
    try:
      result.append(date.fromisoformat(str(item)))
    except Exception:
      continue
  return sorted(set(result))


def _month_name_ru_upper(month: date) -> str:
  names = [
    "ЯНВАРЬ",
    "ФЕВРАЛЬ",
    "МАРТ",
    "АПРЕЛЬ",
    "МАЙ",
    "ИЮНЬ",
    "ИЮЛЬ",
    "АВГУСТ",
    "СЕНТЯБРЬ",
    "ОКТЯБРЬ",
    "НОЯБРЬ",
    "ДЕКАБРЬ",
  ]
  return names[month.month - 1]


def _poll_choose_text(month: date) -> str:
  return f"Выбери даты на {_month_name_ru_upper(month)} и нажми '🚀 Готово'."


def _poll_days_for_month(month: date) -> list[date]:
  day = date(month.year, month.month, 1)
  result: list[date] = []
  while day.month == month.month:
    if day.weekday() in {4, 5}:
      result.append(day)
    day = date.fromordinal(day.toordinal() + 1)
  return result


def _parse_custom_day_input(raw: str, *, month: date) -> date | None:
  digits = "".join(ch for ch in raw if ch.isdigit())
  if not digits:
    return None
  day = int(digits)
  try:
    value = date(month.year, month.month, day)
  except Exception:
    return None
  return value


def _format_poll_summary(*, month: date, selected_dates: list[date], month_counts: list[tuple[date, int]]) -> str:
  lines = [f"{Text.user.POLL_SAVED.value} ({month:%m.%Y})"]
  if selected_dates:
    lines.append("Твои даты: " + ", ".join(str(item.day) for item in selected_dates))
  else:
    lines.append("Твои даты: не выбраны")
  if month_counts:
    lines.append("")
    lines.append("Общий итог:")
    for day, count in month_counts:
      lines.append(f"{day.day:02d}.{day.month:02d}: {count}")
  return "\n".join(lines)


def _render_poll_results_chart(
  *,
  month: date,
  month_counts: list[tuple[date, int]],
  month_votes: list[tuple[date, int]] | None = None,
  user_names: dict[int, str] | None = None,
  days: list[date] | None = None,
) -> bytes:
  day_counts = {d: int(c) for d, c in month_counts}
  days = days or _poll_days_for_month(month)
  days = [item for item in days if int(day_counts.get(item, 0)) > 0]
  weekday_short = {
    0: "пн",
    1: "вт",
    2: "ср",
    3: "чт",
    4: "пт",
    5: "сб",
    6: "вс",
  }
  x_labels = [f"{item.strftime('%d.%m')}\n{weekday_short[item.weekday()]}" for item in days]
  if month_votes and user_names:
    day_to_index = {day: idx for idx, day in enumerate(days)}
    day_user_voted: dict[tuple[int, int], int] = {}
    for vote_day, player_row_id in month_votes:
      if vote_day in day_to_index:
        day_user_voted[(int(player_row_id), day_to_index[vote_day])] = 1
    series: dict[str, list[tuple[int, int]]] = {}
    for player_row_id, name in user_names.items():
      points = [(idx, day_user_voted.get((int(player_row_id), idx), 0)) for idx in range(len(days))]
      if any(value for _, value in points):
        series[name] = points
    if not series:
      series = {"Голоса": [(idx, int(day_counts.get(day, 0))) for idx, day in enumerate(days)]}
  else:
    series = {"Голоса": [(idx, int(day_counts.get(day, 0))) for idx, day in enumerate(days)]}
  return render_buyins_session_chart_png(
    title=f"Голоса за даты покера ({month.strftime('%m.%Y')})",
    series=series,
    x_labels=x_labels,
    chart_type="barh",
  )


async def _poll_all_days_for_month(*, session, month: date) -> list[date]:
  month_start, month_end = _month_bounds(month)
  extra_dates = await PollVoteRepository(session).get_month_extra_dates(month_start=month_start, month_end=month_end)
  return sorted(set(_poll_days_for_month(month)) | set(extra_dates))


def _filter_betting_indicators_by_mode(*, indicators, mode: str):
  if mode == "all":
    return [item for item in indicators if item.for_current_tournaments in {"yes", "no"}]
  return [item for item in indicators if item.for_current_tournaments in {"yes", "only"}]


def _default_betting_indicator(*, indicators, mode: str):
  preferred = "Денег выиграно" if mode == "all" else "Баллы"
  item = next((ind for ind in indicators if str(ind.description).strip() == preferred), None)
  if item is None and indicators:
    item = indicators[0]
  return item


async def _notify_admins_about_room_join(
  *,
  session,
  joined_user: User,
  platform_label: str,
) -> None:
  from app.bot.telegram.runtime import telegram_bot

  repository = UserRepository(session)
  poker_repository = PokerRepository(session)
  poker_data_repository = PokerDataRepository(session)
  active = await poker_repository.get_started()
  players = await poker_data_repository.list_players(date=active[0].date) if active is not None else []
  player_row_ids = {int(p.player_id) for p in players}
  admins = [u for u in await repository.list_approved() if u.is_admin and int(u.row_id) in player_row_ids]
  admin_tg_ids = [int(u.telegram_id) for u in admins if u.telegram_id is not None]
  admin_vk_ids = [int(u.vk_id) for u in admins if u.vk_id is not None]
  can_start_betting = bool(
    active is not None
    and active[0].cashier_id is not None
    and not bool(active[0].is_bettable)
    and not bool(active[0].is_ready_for_chips_entering)
  )
  if active is None or active[0].cashier_id is None:
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
  for admin_id in admin_tg_ids:
    if joined_user.telegram_id is not None and int(admin_id) == int(joined_user.telegram_id):
      continue
    if telegram_bot is not None:
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
          players=[] if (active is not None and active[0].cashier_id is not None) else players,
          can_start_betting=can_start_betting,
        ),
      )
      TG_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent.message_id)

  for admin_id in admin_vk_ids:
    if joined_user.vk_id is not None and int(admin_id) == int(joined_user.vk_id):
      continue
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
        players=[] if (active is not None and active[0].cashier_id is not None) else players,
        can_start_betting=can_start_betting,
      ),
    )
    if sent_mid is not None:
      VK_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent_mid)


def _split_names(value: str | None) -> set[str]:
  if not value:
    return set()
  return {item.strip() for item in str(value).split(",") if item.strip()}


def _calculate_transfers_history(money_rows: list[dict[str, int | str]]) -> list[str]:
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
    lines.append(f"{loser['name']} → {winner['name']} {_format_rub_from_kopecks(transfer)} ₽")
  return lines


async def _build_poker_history_report(*, session, target_date: date) -> str:
  poker_rows = await PokerRepository(session).list_all()
  poker = next((item for item in poker_rows if item.date == target_date and not bool(item.is_going)), None)
  if poker is None:
    return "Игра не найдена."
  params = await PokerParamRepository(session).get_by_row_id(row_id=int(poker.params_id))
  buyin_size_chips = int(params.buyin_size_chips) if params is not None else 200
  buyin_size_kopecks = int(params.buyin_size_kopecks) if params is not None else 20000
  players = await PokerDataRepository(session).list_players(date=target_date)
  if not players:
    return "Нет данных по игре."

  player_rows: list[dict[str, int | str]] = []
  money_rows: list[dict[str, int | str]] = []
  for player in players:
    chips = int(player.chips or 0)
    money_kopecks = int(player.money_kopecks or _money_kopecks_from_chips(
      chips=chips,
      buyins=int(player.buyins),
      buyin_size_chips=buyin_size_chips,
      buyin_size_kopecks=buyin_size_kopecks,
    ))
    money_rows.append({"name": player.player_name, "money": money_kopecks})
    player_rows.append({
      "name": player.player_name,
      "buyins": int(player.buyins),
      "chips": chips,
      "money": money_kopecks,
    })

  player_rows.sort(key=lambda item: int(item["money"]), reverse=True)
  player_lines = [
    (
      f"{str(item['name'])}: {int(item['buyins'])} закупов, {int(item['chips'])} фишек, "
      f"{_format_rub_from_kopecks(int(item['money']))} рублей"
    )
    for item in player_rows
  ]
  poker_money_by_name = {str(item["name"]): int(item["money"]) for item in player_rows}

  winners = [name.strip() for name in str(poker.winners or "").split(",") if name.strip()]
  losers = [name.strip() for name in str(poker.loosers or "").split(",") if name.strip()]
  winner_line = ", ".join(f"💍 {name}" for name in winners) if winners else "💍 -"
  loser_line = ", ".join(f"❌ {name}" for name in losers) if losers else "❌ -"
  transfer_lines = _calculate_transfers_history(money_rows)
  bets = await BetRepository(session).list_for_poker(date=target_date)

  lines = [target_date.strftime("%d.%m.%Y"), "♣️ Покер", *player_lines, "", winner_line, loser_line, "", "💲 Переводы:"]
  lines.extend(transfer_lines if transfer_lines else ["Переводы не требуются"])
  if bets:
    lines.extend(["", "🍀 Ставки"])
    for bet in sorted(
      bets,
      key=lambda item: (
        -int(item.score or 0),
        -int(poker_money_by_name.get(str(item.better_name), 0)),
        int(item.row_id),
      ),
    ):
      size_mark = "🐔" if int(bet.amount_kopecks or 0) >= 40000 else "🐤"
      score_value = int(bet.score or 0)
      score_text = f"+{score_value}" if score_value > 0 else str(score_value)
      winner_name = str(bet.winner_name or "-")
      loser_name = str(bet.loser_name or "-")
      lines.append(
        f"{bet.better_name}: {size_mark}, W: {winner_name}, L: {loser_name} → {score_text} баллов"
      )
  return "\n".join(lines)


async def _build_poker_history_buyins_chart(*, session, target_date: date) -> bytes | None:
  buyin_events = await BuyinDataRepository(session).list_for_date(poker_date=target_date)
  if not buyin_events:
    return None

  cumulative: dict[str, int] = {}
  points: dict[str, list[tuple[int, int]]] = {}
  x_labels: list[str] = []

  for idx, event in enumerate(buyin_events):
    label = event.created_at.strftime("%H:%M") if event.created_at is not None else str(idx + 1)
    x_labels.append(label)
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
    title=f"Закупы за игру {target_date.strftime('%d.%m.%Y')}",
    series=points,
    x_labels=x_labels,
  )


async def _build_bet_last_five_hints(*, session, players: list[str]) -> tuple[dict[str, str], str, str]:
  poker_rows = await PokerRepository(session).list_all()
  poker_rows = [
    p for p in poker_rows
    if p.date is not None
    and not bool(p.is_going)
    and bool(str(p.winners or "").strip())
    and bool(str(p.loosers or "").strip())
  ]
  poker_rows.sort(key=lambda p: p.date)
  winners_by_date = {p.date: _split_names(p.winners) for p in poker_rows}
  losers_by_date = {p.date: _split_names(p.loosers) for p in poker_rows}
  completed_dates = {p.date for p in poker_rows}
  poker_data_rows = await PokerDataRepository(session).list_all()
  player_game_dates: dict[str, list] = {}
  for row in poker_data_rows:
    if row.date in completed_dates:
      player_game_dates.setdefault(row.player_name, []).append(row.date)
  for name, dates in list(player_game_dates.items()):
    player_game_dates[name] = sorted(set(dates))

  def player_marks(player_name: str) -> str:
    player_dates = player_game_dates.get(player_name, [])[-5:]
    marks: list[str] = []
    for d in player_dates:
      if player_name in winners_by_date.get(d, set()):
        marks.append(" 🟢")
      elif player_name in losers_by_date.get(d, set()):
        marks.append(" 🔴")
      else:
        marks.append(" ⚪")
    return "".join(marks)

  marks_map = {name: player_marks(name) for name in players}
  last_five_games = poker_rows[-5:]
  winners_text = "\n".join(str(p.winners or "-") for p in last_five_games)
  losers_text = "\n".join(str(p.loosers or "-") for p in last_five_games)
  return marks_map, winners_text, losers_text


async def _get_telegram_user(telegram_id: int) -> User | None:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    return await repository.get_by_telegram_id(telegram_id)


async def _ensure_approved_telegram_user(message: Message) -> bool:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard)
    return False
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return False
  if not user.is_approved:
    await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
    return False
  return True


async def _approved_tg_keyboard(user: User):
  async with SessionFactory() as session:
    active = await PokerRepository(session).get_started()
    poll_month = await PollConfigRepository(session).get_active_month()
  return main_dynamic_keyboard(
    is_admin=bool(user.is_admin),
    has_active_poker=active is not None,
    has_active_poll=poll_month is not None,
  )


async def _post_bet_tg_keyboard_for_user(*, telegram_id: int):
  async with SessionFactory() as session:
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    if user is None:
      return main_keyboard
    active = await PokerRepository(session).get_started()
    if active is None:
      return await _approved_tg_keyboard(user)
    poker, _ = active
    player = await PokerDataRepository(session).get_player(date=poker.date, player_id=int(user.row_id))
    if player is not None:
      return room_admin_keyboard if user.is_admin else room_keyboard
    return await _approved_tg_keyboard(user)


async def _ensure_approved_telegram_callback_user(callback: CallbackQuery) -> bool:
  if callback.from_user is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return False
  user = await _get_telegram_user(callback.from_user.id)
  if user is None:
    await callback.answer(Text.user.STATUS_NEED_REGISTRATION.value, show_alert=True)
    return False
  if not user.is_approved:
    await callback.answer(Text.user.STATUS_PENDING.value, show_alert=True)
    return False
  return True


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
  return "Турнир"


def _format_stat_info_report(indicators) -> str:
  if not indicators:
    return "Справка пока пустая."
  lines: list[str] = []
  for item in indicators:
    lines.append(f"{item.pic} <b>{item.description}</b>")
    lines.append(f"{item.description_full}")
    lines.append("")
  return "\n".join(lines).strip()


def _format_achievement_description(raw: str) -> tuple[str, str | None]:
  if "_" not in raw:
    return raw, None
  title, detail = raw.split("_", 1)
  return title.strip(), detail.strip() if detail else None


def _format_achievement_info_report(achievements, indicators_by_id: dict[int, str]) -> str:
  if not achievements:
    return "Справка пока пустая."
  lines: list[str] = []
  for item in achievements:
    title, detail = _format_achievement_description(item.description)
    lines.append(f"{item.pic} <b>{title}</b>")
    if detail:
      lines.append(detail)
    indicator_name = indicators_by_id.get(int(item.stat_id))
    if indicator_name:
      lines.append(f"Показатель: {indicator_name}")
    lines.append("")
  return "\n".join(lines).strip()


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard)
    return

  await state.clear()
  reply_markup = new_user_keyboard
  async with SessionFactory() as session:
    repository = UserRepository(session)
    existing_user = await repository.get_by_telegram_id(message.from_user.id)
    if existing_user is not None and existing_user.is_approved:
      reply_markup = await _approved_tg_keyboard(existing_user)

  await message.answer(
    Text.user.BOT_INFO.value,
    reply_markup=reply_markup,
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
      await message.answer(Text.user.REGISTRATION_EXIST.value, reply_markup=await _approved_tg_keyboard(existing_user))
      return
    await message.answer(Text.user.REGISTRATION_PENDING.value, reply_markup=new_user_keyboard)
    return

  await state.set_state(RegistrationState.waiting_for_played_before_answer)
  await message.answer(
    Text.user.REGISTRATION_PLAYED_BEFORE_Q.value,
    reply_markup=played_before_keyboard(),
  )


@router.message(F.text == Buttons.new_user.ABOUT.value)
async def show_bot_info(message: Message, state: FSMContext) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard)
    return

  await state.clear()
  reply_markup = new_user_keyboard
  async with SessionFactory() as session:
    repository = UserRepository(session)
    existing_user = await repository.get_by_telegram_id(message.from_user.id)
    if existing_user is not None and existing_user.is_approved:
      reply_markup = await _approved_tg_keyboard(existing_user)

  await message.answer(
    Text.user.BOT_INFO.value,
    reply_markup=reply_markup,
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
      await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
      return
    if not user.is_approved:
      await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
      return

    use_case = ManagePokerPlayersUseCase(
      poker_repository=PokerRepository(session),
      poker_data_repository=PokerDataRepository(session),
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
    )
    is_denied = await use_case.is_denied_for_active_poker(user_row_id=int(user.row_id))
    if is_denied:
      await message.answer(Text.user.STATUS_ROOM_NOT_ADDED.value)
      return
    players = await use_case.list_active_poker_players()
    if not players:
      await message.answer(Text.user.STATUS_ROOM_CLOSED.value)
      return

    current_player = next((item for item in players if int(item.player_id) == int(user.row_id)), None)
    if current_player is None:
      await message.answer(Text.user.STATUS_ROOM_NOT_ADDED.value)
      return

    lines: list[str] = ["🏦 Закупы"]
    if user.is_admin:
      active = await PokerRepository(session).get_started()
      bet_row_ids: set[int] = set()
      bet_name_by_id: dict[int, str] = {}
      better_row_by_id: dict[int, int] = {}
      if active is not None:
        poker, _ = active
        bets = await BetRepository(session).list_for_poker(date=poker.date)
        for bet in bets:
          better_id = int(bet.better_id)
          better_user = await user_repository.get_by_row_id(better_id)
          if better_user is not None:
            better_row_id = int(better_user.row_id)
            bet_row_ids.add(better_row_id)
            better_row_by_id[better_id] = better_row_id
          else:
            # better_id in bets is expected to be users.row_id
            bet_row_ids.add(better_id)
            better_row_by_id[better_id] = better_id
          bet_name_by_id[better_id] = bet.better_name
      player_ids = {int(p.player_id) for p in players}
      for p in players:
        if int(p.player_id) in bet_row_ids:
          lines.append(f"{p.player_name}: 🍀 {p.buyins}")
        else:
          lines.append(f"{p.player_name}: {p.buyins}")
      outsider_ids = [
        better_id
        for better_id in bet_name_by_id.keys()
        if better_row_by_id.get(better_id) not in player_ids
      ]
      outsider_ids.sort()
      for better_id in outsider_ids:
        better_name = bet_name_by_id.get(better_id, f"ID {better_id}")
        lines.append(f"{better_name}: 🍀")
    else:
      for p in players:
        lines.append(f"{p.player_name}: {p.buyins}")

  await message.answer("\n".join(lines))


@router.message(F.text == Buttons.main.ROOM.value)
async def join_poker_room(message: Message, state: FSMContext) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
    return
  await state.clear()

  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    user = await user_repository.get_by_telegram_id(message.from_user.id)
    if user is None:
      await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
      return
    if not user.is_approved:
      await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
      return

    poker_repository = PokerRepository(session)
    poker_data_repository = PokerDataRepository(session)
    active = await poker_repository.get_started()
    ready = await poker_repository.get_latest_ready_for_chips() if active is None else None
    current_poker_date = active[0].date if active is not None else (ready.date if ready is not None else None)
    if current_poker_date is None:
      await message.answer(Text.user.STATUS_ROOM_CLOSED.value)
      return

    use_case = ManagePokerPlayersUseCase(
      poker_repository=poker_repository,
      poker_data_repository=poker_data_repository,
      poker_room_denied_repository=PokerRoomDeniedRepository(session),
    )
    is_denied = await use_case.is_denied_for_active_poker(user_row_id=int(user.row_id))
    if is_denied:
      await message.answer(Text.user.STATUS_ROOM_NOT_ADDED.value)
      return
    players = await poker_data_repository.list_players(date=current_poker_date)
    if players:
      already_in_room = any(int(item.player_id) == int(user.row_id) for item in players)
      if already_in_room:
        await message.answer(
          Text.user.ROOM_JOINED.value,
          reply_markup=room_admin_keyboard if user.is_admin else room_keyboard,
        )
        return
    if active is None:
      await message.answer(Text.user.STATUS_ROOM_CLOSED.value)
      return
    poker, _ = active
    if poker.cashier_id is None:
      created = await use_case.add_player_to_active_poker(player_id=int(user.row_id), player_name=user.name)
      if created is None:
        await message.answer(Text.user.STATUS_ROOM_CLOSED.value)
        return
      await _notify_admins_about_room_join(
        session=session,
        joined_user=user,
        platform_label="Telegram",
      )
    else:
      players_now = await poker_data_repository.list_players(date=poker.date)
      player_row_ids = {int(item.player_id) for item in players_now}
      approved = await user_repository.list_approved()
      admins = [
        u for u in approved
        if u.is_admin
        and int(u.row_id) in player_row_ids
        and u.notification_platform == "tg"
        and u.telegram_id is not None
      ]
      for admin in admins:
        await message.bot.send_message(
          chat_id=int(admin.telegram_id),
          text=f"Новый вход в рум: {user.name}\nРазрешить?",
          reply_markup=poker_room_approve_keyboard(player_id=int(user.row_id)),
        )
      vk_admins = [
        u for u in approved
        if u.is_admin
        and int(u.row_id) in player_row_ids
        and u.notification_platform == "vk"
        and u.vk_id is not None
      ]
      for admin in vk_admins:
        await send_vk_message(
          user_id=int(admin.vk_id),
          message=f"Новый вход в рум: {user.name}\nРазрешить?",
          keyboard=vk_poker_room_approve_keyboard(player_id=int(user.row_id)),
        )
      await message.answer("Запрос на вход отправлен админам. Ожидай подтверждение.")
      return

  await message.answer(
    Text.user.ROOM_JOINED.value,
    reply_markup=room_admin_keyboard if user.is_admin else room_keyboard,
  )


@router.message(F.text == Buttons.room.POKER_ADMIN.value)
async def open_room_admin_panel(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard)
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  if not user.is_approved:
    await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
    return
  if not user.is_admin:
    await message.answer(Text.admin.NO_RIGHTS.value, reply_markup=room_keyboard)
    return
  await message.answer(Text.admin.ADMIN_PANEL.value, reply_markup=admin_room_keyboard)


@router.message((F.text == Buttons.poker.POLL.value) | (F.text == Buttons.poll_menu.VOTE.value))
async def start_room_poll(message: Message, state: FSMContext) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard)
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  if not user.is_approved:
    await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
    return

  async with SessionFactory() as session:
    month = await PollConfigRepository(session).get_active_month()
  if month is None:
    await message.answer(Text.user.POLL_NOT_ACTIVE.value, reply_markup=await _approved_tg_keyboard(user))
    return
  month_start, month_end = _month_bounds(month)
  async with SessionFactory() as session:
    all_days = await _poll_all_days_for_month(session=session, month=month)
    selected = await PollVoteRepository(session).get_user_month_votes(
      player_row_id=int(user.row_id),
      month_start=month_start,
      month_end=month_end,
    )
  await state.update_data(
    poll_month=f"{month.year}-{month.month:02d}",
    poll_page=0,
    poll_selected=[item.isoformat() for item in selected],
  )
  await message.answer(
    _poll_choose_text(month),
    reply_markup=poll_month_keyboard(month=month, page=0, selected_dates=selected, extra_dates=all_days),
  )


@router.message(F.text == Buttons.poll_menu.RESULTS.value)
async def show_poll_results(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard)
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  if not user.is_approved:
    await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
    return

  async with SessionFactory() as session:
    month = await PollConfigRepository(session).get_active_month()
    if month is None:
      await message.answer(Text.user.POLL_NOT_ACTIVE.value, reply_markup=await _approved_tg_keyboard(user))
      return
    month_start, month_end = _month_bounds(month)
    poll_repo = PollVoteRepository(session)
    month_counts = await poll_repo.get_month_counts(month_start=month_start, month_end=month_end)
    month_votes = await poll_repo.get_month_votes(month_start=month_start, month_end=month_end)
    user_ids = sorted({int(player_row_id) for _, player_row_id in month_votes})
    user_repository = UserRepository(session)
    user_names: dict[int, str] = {}
    for row_id in user_ids:
      poll_user = await user_repository.get_by_row_id(row_id)
      user_names[row_id] = poll_user.name if poll_user is not None else f"ID {row_id}"
    all_days = await _poll_all_days_for_month(session=session, month=month)
  image_bytes = _render_poll_results_chart(
    month=month,
    month_counts=month_counts,
    month_votes=month_votes,
    user_names=user_names,
    days=all_days,
  )
  try:
    await message.answer_photo(
      photo=BufferedInputFile(image_bytes, filename="poll_results.png"),
      caption=f"📊 Результаты опроса за {month.strftime('%m.%Y')}",
      reply_markup=poll_menu_keyboard,
    )
  except Exception:
    await message.answer_document(
      document=BufferedInputFile(image_bytes, filename="poll_results.png"),
      caption=f"📊 Результаты опроса за {month.strftime('%m.%Y')}",
      reply_markup=poll_menu_keyboard,
    )


@router.callback_query(F.data == "poll_noop")
async def poll_noop(callback: CallbackQuery) -> None:
  await callback.answer()


async def _safe_edit_reply_markup(message: Message | None, reply_markup: InlineKeyboardMarkup | None) -> None:
  if message is None:
    return
  try:
    await message.edit_reply_markup(reply_markup=reply_markup)
  except TelegramBadRequest as exc:
    if "message is not modified" not in str(exc).lower():
      raise


async def _safe_callback_edit_reply_markup(
  callback: CallbackQuery,
  reply_markup: InlineKeyboardMarkup | None,
) -> None:
  await _safe_edit_reply_markup(callback.message, reply_markup)


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


@router.callback_query(F.data.startswith("poll_page:"))
async def poll_page_nav(callback: CallbackQuery, state: FSMContext) -> None:
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  _, month_key, page_s = str(callback.data).split(":")
  month = _parse_month_key(month_key)
  async with SessionFactory() as session:
    allowed_days = await _poll_all_days_for_month(session=session, month=month)
  max_page = max(0, (len(allowed_days) - 1) // 4)
  page = max(0, min(int(page_s), max_page))
  data = await state.get_data()
  selected = _parse_iso_dates(data.get("poll_selected", []))
  await state.update_data(poll_month=f"{month.year}-{month.month:02d}", poll_page=page)
  await _safe_edit_reply_markup(
    callback.message,
    poll_month_keyboard(month=month, page=page, selected_dates=selected, extra_dates=allowed_days),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("poll_day:"))
async def poll_day_toggle(callback: CallbackQuery, state: FSMContext) -> None:
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  _, day_iso, page_s = str(callback.data).split(":")
  day = date.fromisoformat(day_iso)
  data = await state.get_data()
  selected_set = set(data.get("poll_selected", []))
  if day_iso in selected_set:
    selected_set.remove(day_iso)
  else:
    selected_set.add(day_iso)
  selected = _parse_iso_dates(list(selected_set))
  async with SessionFactory() as session:
    allowed_days = await _poll_all_days_for_month(session=session, month=date(day.year, day.month, 1))
  await state.update_data(
    poll_month=f"{day.year}-{day.month:02d}",
    poll_page=int(page_s),
    poll_selected=[item.isoformat() for item in selected],
  )
  await _safe_edit_reply_markup(
    callback.message,
    poll_month_keyboard(
      month=date(day.year, day.month, 1),
      page=int(page_s),
      selected_dates=selected,
      extra_dates=allowed_days,
    ),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("poll_suggest:"))
async def poll_suggest_day(callback: CallbackQuery, state: FSMContext) -> None:
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  month_key = str(callback.data).split(":", 1)[1]
  month = _parse_month_key(month_key)
  await state.set_state(PollState.waiting_for_custom_day)
  await state.update_data(poll_suggest_month=f"{month.year}-{month.month:02d}")
  await callback.answer()
  if callback.message is not None:
    await callback.message.answer(f"Введи число дня для {_month_name_ru_upper(month)}:")


@router.message(PollState.waiting_for_custom_day)
async def poll_suggest_day_input(message: Message, state: FSMContext) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard)
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None or not user.is_approved:
    await state.clear()
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  data = await state.get_data()
  month = _parse_month_key(data.get("poll_suggest_month"))
  chosen = _parse_custom_day_input(message.text or "", month=month)
  if chosen is None:
    await message.answer(f"Некорректный день. Введи число от 1 до 31 для {_month_name_ru_upper(month)}.")
    return

  month_start, month_end = _month_bounds(month)
  async with SessionFactory() as session:
    repo = PollVoteRepository(session)
    existing_days = await _poll_all_days_for_month(session=session, month=month)
    if chosen in existing_days:
      await message.answer("Этот день уже есть в голосовании.")
      return
    await repo.add_month_extra_date(poll_date=chosen)
    selected = await repo.get_user_month_votes(
      player_row_id=int(user.row_id),
      month_start=month_start,
      month_end=month_end,
    )
    all_days = await _poll_all_days_for_month(session=session, month=month)
    await session.commit()

  await state.update_data(
    poll_month=f"{month.year}-{month.month:02d}",
    poll_page=0,
    poll_selected=[item.isoformat() for item in selected],
  )
  await state.set_state(None)
  await message.answer(
    _poll_choose_text(month),
    reply_markup=poll_month_keyboard(month=month, page=0, selected_dates=selected, extra_dates=all_days),
  )


@router.callback_query(F.data == "poll_done")
async def poll_done(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.from_user is None:
    await callback.answer()
    return
  user = await _get_telegram_user(callback.from_user.id)
  if user is None or not user.is_approved:
    await callback.answer(Text.user.STATUS_NEED_REGISTRATION.value, show_alert=True)
    return
  data = await state.get_data()
  month = _parse_month_key(data.get("poll_month"))
  month_start, month_end = _month_bounds(month)
  async with SessionFactory() as session:
    allowed = set(await _poll_all_days_for_month(session=session, month=month))
  selected = [item for item in _parse_iso_dates(data.get("poll_selected", [])) if item in allowed and month_start <= item <= month_end]
  async with SessionFactory() as session:
    repository = PollVoteRepository(session)
    await repository.replace_user_month_votes(
      player_row_id=int(user.row_id),
      month_start=month_start,
      month_end=month_end,
      selected_dates=selected,
    )
    month_counts = await repository.get_month_counts(month_start=month_start, month_end=month_end)
    await session.commit()
  await state.clear()
  await _delete_message_if_possible(callback)
  if callback.message is not None:
    await callback.message.answer(_format_poll_summary(month=month, selected_dates=selected, month_counts=month_counts))
  await callback.answer()


@router.callback_query(F.data == "poll_cancel")
async def poll_cancel(callback: CallbackQuery, state: FSMContext) -> None:
  await state.clear()
  await _delete_message_if_possible(callback)
  if callback.message is not None:
    await callback.message.answer(Text.user.POLL_CANCELED.value)
  await callback.answer()


@router.message(F.text == Buttons.main.BETTING.value)
async def open_betting_menu(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await message.answer(Text.user.BETTING_MENU.value, reply_markup=betting_keyboard)


@router.message(F.text == Buttons.main.POKER.value)
async def open_poker_menu(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await message.answer(Text.user.POKER_MENU.value, reply_markup=poker_keyboard)


@router.message(F.text == Buttons.main.NEXT_POKER_DATE.value)
async def open_next_poker_date_menu(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard)
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  if not user.is_approved:
    await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
    return
  async with SessionFactory() as session:
    month = await PollConfigRepository(session).get_active_month()
  if month is None:
    await message.answer(Text.user.POLL_NOT_ACTIVE.value, reply_markup=await _approved_tg_keyboard(user))
    return
  await message.answer("Выбери действие:", reply_markup=poll_menu_keyboard)


@router.message(F.text == Buttons.main.ADMIN.value)
async def open_admin_panel(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard)
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  if not user.is_approved:
    await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
    return
  if not user.is_admin:
    await message.answer(Text.admin.NO_RIGHTS.value, reply_markup=await _approved_tg_keyboard(user))
    return
  await message.answer(Text.admin.ADMIN_PANEL.value, reply_markup=admin_main_keyboard)


@router.message(F.text == Buttons.admin_main.TO_MAIN.value)
async def back_from_admin_to_main(message: Message) -> None:
  if message.from_user is None:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard)
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  if not user.is_approved:
    await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
    return
  await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


@router.message(F.text == Buttons.betting.TO_MAIN.value)
async def back_to_main_from_betting(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


@router.message(F.text == Buttons.poker.TO_MAIN.value)
async def back_to_main_from_poker(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


@router.message(F.text == Buttons.room.TO_MAIN.value)
async def back_to_main_from_room(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


@router.message(F.text == Buttons.poll_menu.TO_MAIN.value)
async def back_to_main_from_poll_menu(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  user = await _get_telegram_user(message.from_user.id)
  if user is None:
    await message.answer(Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard)
    return
  await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


@router.message(F.text == Buttons.poker.POKER_INFO.value)
async def show_poker_info(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await message.answer(Text.user.POKER_STAT_BTN.value, reply_markup=poker_info_keyboard)


@router.message(F.text == Buttons.betting.BETTING_INFO.value)
async def show_betting_info(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await message.answer(Text.user.BETTING_MENU.value, reply_markup=betting_info_keyboard)


@router.message(F.text == Buttons.bettingInfo.BETTING_RULES.value)
async def show_betting_rules(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await message.answer(Text.user.BET_RULES.value, reply_markup=betting_info_keyboard, parse_mode="HTML")


@router.message(F.text == Buttons.bettingInfo.BETTING_STAT_INFO.value)
async def show_betting_stat_info(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
  await message.answer(_format_stat_info_report(indicators), reply_markup=betting_info_keyboard, parse_mode="HTML")


@router.message(F.text == Buttons.bettingInfo.BETTING_ACH_INFO.value)
async def show_betting_achievement_info(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  async with SessionFactory() as session:
    achievement_repository = AchievementRepository(session)
    indicator_repository = StatIndicatorRepository(session)
    achievements = await achievement_repository.list_by_type(achievement_type="betting")
    indicators = await indicator_repository.list_by_type(indicator_type="betting")
  indicators_by_id = {int(item.row_id): item.description for item in indicators}
  await message.answer(
    _format_achievement_info_report(achievements, indicators_by_id),
    reply_markup=betting_info_keyboard,
    parse_mode="HTML",
  )


@router.message(F.text == Buttons.pokerInfo.POKER_STAT_INFO.value)
async def show_poker_stat_info(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
  await message.answer(_format_stat_info_report(indicators), reply_markup=poker_info_keyboard, parse_mode="HTML")


@router.message(F.text == Buttons.pokerInfo.POKER_ACH_INFO.value)
async def show_poker_achievement_info(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  async with SessionFactory() as session:
    achievement_repository = AchievementRepository(session)
    indicator_repository = StatIndicatorRepository(session)
    achievements = await achievement_repository.list_by_type(achievement_type="poker")
    indicators = await indicator_repository.list_by_type(indicator_type="poker")
  indicators_by_id = {int(item.row_id): item.description for item in indicators}
  await message.answer(
    _format_achievement_info_report(achievements, indicators_by_id),
    reply_markup=poker_info_keyboard,
    parse_mode="HTML",
  )


@router.message((F.text == Buttons.poker.HISTORY.value) | (F.text == Buttons.pokerInfo.HISTORY.value))
async def show_poker_history_years(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  async with SessionFactory() as session:
    pokers = await PokerRepository(session).list_all()
  years = sorted({int(item.date.year) for item in pokers if item.date is not None and not bool(item.is_going)}, reverse=True)
  if not years:
    await message.answer("Нет завершенных игр.", reply_markup=poker_info_keyboard)
    return
  await message.answer(
    "Выбери год:",
    reply_markup=poker_history_year_keyboard(years=years),
  )


@router.callback_query(F.data == "pokerhist_cancel")
async def poker_history_cancel(callback: CallbackQuery) -> None:
  await _clear_inline_keyboard(callback)
  await callback.answer("Отменено")


@router.callback_query(F.data.startswith("pokerhistyear:"))
async def poker_history_year_pick(callback: CallbackQuery) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  year = int(str(callback.data).split(":", 1)[1])
  async with SessionFactory() as session:
    pokers = await PokerRepository(session).list_all()
  dates = sorted(
    {item.date for item in pokers if item.date is not None and not bool(item.is_going) and int(item.date.year) == int(year)},
  )
  if not dates:
    await callback.answer("Нет игр за выбранный год", show_alert=True)
    return
  await callback.message.edit_text(
    f"Выбери дату игры ({year}):",
    reply_markup=poker_history_dates_keyboard(year=year, dates=list(dates), page=0),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("pokerhistpage:"))
async def poker_history_page(callback: CallbackQuery) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  _, year_s, page_s = str(callback.data).split(":")
  year = int(year_s)
  page = int(page_s)
  async with SessionFactory() as session:
    pokers = await PokerRepository(session).list_all()
  dates = sorted(
    {item.date for item in pokers if item.date is not None and not bool(item.is_going) and int(item.date.year) == int(year)},
  )
  await callback.message.edit_text(
    f"Выбери дату игры ({year}):",
    reply_markup=poker_history_dates_keyboard(year=year, dates=list(dates), page=page),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("pokerhistdate:"))
async def poker_history_date_pick(callback: CallbackQuery) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  parts = str(callback.data).split(":")
  if len(parts) != 4:
    await callback.answer("Некорректная дата", show_alert=True)
    return
  try:
    await callback.message.delete()
  except Exception:
    await _clear_inline_keyboard(callback)
  target_date = date.fromisoformat(parts[3])
  async with SessionFactory() as session:
    report = await _build_poker_history_report(session=session, target_date=target_date)
    chart_png = await _build_poker_history_buyins_chart(session=session, target_date=target_date)
  await callback.message.answer(report, reply_markup=poker_keyboard)
  if chart_png is not None:
    await callback.message.answer_photo(
      photo=BufferedInputFile(chart_png, filename="poker_buyins_history.png"),
      caption="📈 История закупов",
      reply_markup=poker_keyboard,
    )
  await callback.answer()


@router.message(F.text == Buttons.poker.POKER_STAT.value)
async def show_poker_stat_indicators(message: Message, state: FSMContext) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await state.update_data(
    pokerstat_years=[],
    pokerstat_selected_ids=[],
    pokerstat_sort_id=None,
  )
  async with SessionFactory() as session:
    rows = await PokerDataRepository(session).list_all()
  years = sorted({int(item.date.year) for item in rows if item.date is not None}, reverse=True)
  if not years:
    await message.answer(Text.user.POKER_STAT_REPORT.value.format(report="Нет данных по покеру."))
    return
  await message.answer(
    Text.user.STAT_CHOOSE_YEAR.value,
    reply_markup=stat_year_keyboard(prefix="pokerstatyear", years=years, selected_years=[], page=0),
  )


@router.callback_query(F.data.startswith("pokerstatyear_page:"))
async def poker_stat_year_page(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  page = int(callback.data.split(":", 1)[1])
  data = await state.get_data()
  selected_years: list[int] = data.get("pokerstat_years", [])
  async with SessionFactory() as session:
    rows = await PokerDataRepository(session).list_all()
  years = sorted({int(item.date.year) for item in rows if item.date is not None}, reverse=True)
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_YEAR.value,
    reply_markup=stat_year_keyboard(prefix="pokerstatyear", years=years, selected_years=selected_years, page=page),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("pokerstatyear_toggle:"))
async def poker_stat_year_toggle(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  _, year_raw, page_raw = callback.data.split(":")
  year = int(year_raw)
  page = int(page_raw)
  data = await state.get_data()
  selected_years = set(data.get("pokerstat_years", []))
  if year in selected_years:
    selected_years.remove(year)
  else:
    selected_years.add(year)
  await state.update_data(pokerstat_years=sorted(selected_years), pokerstat_selected_ids=[])
  async with SessionFactory() as session:
    rows = await PokerDataRepository(session).list_all()
  years = sorted({int(item.date.year) for item in rows if item.date is not None}, reverse=True)
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_YEAR.value,
    reply_markup=stat_year_keyboard(prefix="pokerstatyear", years=years, selected_years=sorted(selected_years), page=page),
  )
  await callback.answer()


@router.callback_query(F.data == "pokerstatyear_cancel")
async def poker_stat_year_cancel(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  await state.update_data(pokerstat_years=[], pokerstat_selected_ids=[], pokerstat_sort_id=None)
  await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
  await callback.answer()


@router.callback_query(F.data == "pokerstatyear_done")
async def poker_stat_year_done(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  data = await state.get_data()
  selected_years: list[int] = data.get("pokerstat_years", [])
  if not selected_years:
    async with SessionFactory() as session:
      rows = await PokerDataRepository(session).list_all()
    years = sorted({int(item.date.year) for item in rows if item.date is not None}, reverse=True)
    if not years:
      await callback.message.edit_text(Text.user.POKER_STAT_REPORT.value.format(report="Нет данных по покеру."))
      await callback.answer()
      return
    current_year = datetime.now().year
    selected_years = [current_year] if current_year in years else [years[0]]
    await state.update_data(pokerstat_years=selected_years)
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
  if not indicators:
    await callback.message.edit_text(Text.user.POKER_STAT_REPORT.value.format(report="Нет данных по покеру."))
    await callback.answer()
    return
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_PARAMS.value,
    reply_markup=poker_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("pokerstat_page:"))
async def poker_stat_page(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  page = int(callback.data.split(":", 1)[1])
  data = await state.get_data()
  selected_ids: list[int] = data.get("pokerstat_selected_ids", [])
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_PARAMS.value,
    reply_markup=poker_stat_indicators_keyboard(indicators=indicators, page=page, selected_ids=selected_ids),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("pokerstat_toggle:"))
async def poker_stat_indicator_selected(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  _, indicator_id_raw, page_raw = callback.data.split(":")
  indicator_id = int(indicator_id_raw)
  page = int(page_raw)
  data = await state.get_data()
  selected = set(data.get("pokerstat_selected_ids", []))
  if indicator_id in selected:
    selected.remove(indicator_id)
  else:
    selected.add(indicator_id)
  await state.update_data(pokerstat_selected_ids=list(selected))
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_PARAMS.value,
    reply_markup=poker_stat_indicators_keyboard(indicators=indicators, page=page, selected_ids=list(selected)),
  )
  await callback.answer()


@router.callback_query(F.data == "pokerstat_done")
async def poker_stat_done(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  data = await state.get_data()
  selected_ids: list[int] = data.get("pokerstat_selected_ids", [])
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    if not selected_ids:
      default_indicator = next((item for item in indicators if str(item.description).strip() == "Денег всего"), None)
      if default_indicator is None and indicators:
        default_indicator = indicators[0]
      selected_ids = [int(default_indicator.row_id)] if default_indicator is not None else []
      await state.update_data(pokerstat_selected_ids=selected_ids)
    selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
    if len(selected) == 1:
      selected_years: list[int] = data.get("pokerstat_years", [])
      report = await StatUseCases(
        bet_repository=BetRepository(session),
        poker_data_repository=PokerDataRepository(session),
        achievement_repository=AchievementRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_repository=PokerRepository(session),
      ).get_poker_stat(
        indicators=selected,
        years=selected_years,
        sort_pic=selected[0].pic,
      )
      image_bytes = render_stat_table_png(title="Статистика покера", report=report)
      await callback.message.answer_photo(
        photo=BufferedInputFile(image_bytes, filename="poker_stat.png"),
        caption="Статистика покера",
        reply_markup=poker_keyboard,
      )
      await state.update_data(pokerstat_years=[], pokerstat_selected_ids=[], pokerstat_sort_id=None)
      await callback.answer()
      return
  await callback.message.edit_text(
    f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
    reply_markup=stat_sort_keyboard(
      prefix="pokerstatsort",
      indicators=selected,
      selected_ids=selected_ids,
      selected_sort_id=None,
      page=0,
    ),
  )
  await state.update_data(pokerstat_sort_id=None)
  await callback.answer()


@router.callback_query(F.data == "pokerstat_cancel")
async def poker_stat_cancel(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  await state.update_data(pokerstat_years=[], pokerstat_selected_ids=[], pokerstat_sort_id=None)
  await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
  await callback.answer()


@router.callback_query(F.data.startswith("pokerstatsort_page:"))
async def poker_stat_sort_page(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  page = int(callback.data.split(":", 1)[1])
  data = await state.get_data()
  selected_ids: list[int] = data.get("pokerstat_selected_ids", [])
  selected_sort_id = data.get("pokerstat_sort_id")
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
  await callback.message.edit_text(
    f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
    reply_markup=stat_sort_keyboard(
      prefix="pokerstatsort",
      indicators=selected,
      selected_ids=selected_ids,
      selected_sort_id=int(selected_sort_id) if selected_sort_id is not None else None,
      page=page,
    ),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("pokerstatsort_toggle:"))
async def poker_stat_sort_toggle(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  _, indicator_id_raw, page_raw = callback.data.split(":")
  indicator_id = int(indicator_id_raw)
  page = int(page_raw)
  data = await state.get_data()
  current_sort_id = data.get("pokerstat_sort_id")
  new_sort_id = None if current_sort_id is not None and int(current_sort_id) == indicator_id else indicator_id
  await state.update_data(pokerstat_sort_id=new_sort_id)
  selected_ids: list[int] = data.get("pokerstat_selected_ids", [])
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
  await callback.message.edit_text(
    f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
    reply_markup=stat_sort_keyboard(
      prefix="pokerstatsort",
      indicators=selected,
      selected_ids=selected_ids,
      selected_sort_id=new_sort_id,
      page=page,
    ),
  )
  await callback.answer()


@router.callback_query(F.data == "pokerstatsort_cancel")
async def poker_stat_sort_cancel(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  await state.update_data(pokerstat_years=[], pokerstat_selected_ids=[], pokerstat_sort_id=None)
  await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
  await callback.answer()


@router.callback_query(F.data == "pokerstatsort_done")
async def poker_stat_sort_done(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  data = await state.get_data()
  selected_ids: list[int] = data.get("pokerstat_selected_ids", [])
  selected_years: list[int] = data.get("pokerstat_years", [])
  sort_id = data.get("pokerstat_sort_id")
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
    sort_indicator = next((item for item in selected if sort_id is not None and int(item.row_id) == int(sort_id)), None)
    sort_pic = sort_indicator.pic if sort_indicator is not None else None
    report = await StatUseCases(
      bet_repository=BetRepository(session),
      poker_data_repository=PokerDataRepository(session),
      achievement_repository=AchievementRepository(session),
      bet_tournament_repository=BetTournamentRepository(session),
      bet_tournament_param_repository=BetTournamentParamRepository(session),
      poker_repository=PokerRepository(session),
    ).get_poker_stat(
      indicators=selected,
      years=selected_years,
      sort_pic=sort_pic,
    )
  image_bytes = render_stat_table_png(title="Статистика покера", report=report)
  await callback.message.answer_photo(
    photo=BufferedInputFile(image_bytes, filename="poker_stat.png"),
    caption="Статистика покера",
    reply_markup=poker_keyboard,
  )
  await state.update_data(pokerstat_years=[], pokerstat_selected_ids=[], pokerstat_sort_id=None)
  await callback.answer()


@router.message(F.text == Buttons.betting.CURRENT_TOURS.value)
async def show_current_betting_tournaments(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await message.answer(Text.user.BETTING_MENU.value, reply_markup=betting_current_keyboard)


async def _start_betting_stat_flow(*, message: Message, state: FSMContext, mode: str) -> None:
  await state.update_data(
    betstat_years=[],
    betstat_selected_ids=[],
    betstat_mode=mode,
    betstat_sort_id=None,
  )
  if mode in {"regular", "year"}:
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    if not indicators:
      await message.answer(Text.user.BETTING_CURRENT_EMPTY.value)
      return
    await message.answer(
      Text.user.STAT_CHOOSE_PARAMS.value,
      reply_markup=betting_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
    )
    return
  async with SessionFactory() as session:
    bets = await BetRepository(session).list_all()
  years = sorted({int(item.date.year) for item in bets if item.date is not None}, reverse=True)
  if not years:
    await message.answer("Нет данных по ставкам.")
    return
  await message.answer(
    Text.user.STAT_CHOOSE_YEAR.value,
    reply_markup=stat_year_keyboard(prefix="betstatyear", years=years, selected_years=[], page=0),
  )


@router.message(F.text == Buttons.betting_current.REG_TOURNAMENT.value)
async def show_regular_betting_tournament_stat(message: Message, state: FSMContext) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await _start_betting_stat_flow(message=message, state=state, mode="regular")


@router.message(F.text == Buttons.betting_current.YEAR_TOURNAMENT.value)
async def show_year_betting_tournament_stat(message: Message, state: FSMContext) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await _start_betting_stat_flow(message=message, state=state, mode="year")


@router.message(F.text == Buttons.betting_current.TO_MAIN.value)
async def back_to_betting_from_current_tournaments(message: Message) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await message.answer(Text.user.BETTING_MENU.value, reply_markup=betting_keyboard)


@router.message(F.text == Buttons.betting.BETTING_STAT.value)
async def show_betting_stat_indicators(message: Message, state: FSMContext) -> None:
  if not await _ensure_approved_telegram_user(message):
    return
  await _start_betting_stat_flow(message=message, state=state, mode="all")


@router.callback_query(F.data.startswith("betstatyear_page:"))
async def betting_stat_year_page(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  page = int(callback.data.split(":", 1)[1])
  data = await state.get_data()
  selected_years: list[int] = data.get("betstat_years", [])
  async with SessionFactory() as session:
    bets = await BetRepository(session).list_all()
  years = sorted({int(item.date.year) for item in bets if item.date is not None}, reverse=True)
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_YEAR.value,
    reply_markup=stat_year_keyboard(prefix="betstatyear", years=years, selected_years=selected_years, page=page),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("betstatyear_toggle:"))
async def betting_stat_year_toggle(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  _, year_raw, page_raw = callback.data.split(":")
  year = int(year_raw)
  page = int(page_raw)
  data = await state.get_data()
  selected_years = set(data.get("betstat_years", []))
  if year in selected_years:
    selected_years.remove(year)
  else:
    selected_years.add(year)
  await state.update_data(betstat_years=sorted(selected_years), betstat_selected_ids=[])
  async with SessionFactory() as session:
    bets = await BetRepository(session).list_all()
  years = sorted({int(item.date.year) for item in bets if item.date is not None}, reverse=True)
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_YEAR.value,
    reply_markup=stat_year_keyboard(prefix="betstatyear", years=years, selected_years=sorted(selected_years), page=page),
  )
  await callback.answer()


@router.callback_query(F.data == "betstatyear_cancel")
async def betting_stat_year_cancel(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  await state.update_data(betstat_years=[], betstat_selected_ids=[], betstat_mode="all", betstat_sort_id=None)
  await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
  await callback.answer()


@router.callback_query(F.data == "betstatyear_done")
async def betting_stat_year_done(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  data = await state.get_data()
  selected_years: list[int] = data.get("betstat_years", [])
  mode = data.get("betstat_mode", "all")
  if not selected_years:
    async with SessionFactory() as session:
      bets = await BetRepository(session).list_all()
    years = sorted({int(item.date.year) for item in bets if item.date is not None}, reverse=True)
    if not years:
      await callback.message.edit_text("Нет данных по ставкам.")
      await callback.answer()
      return
    current_year = datetime.now().year
    selected_years = [current_year] if current_year in years else [years[0]]
    await state.update_data(betstat_years=selected_years)
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
  indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
  if not indicators:
    await callback.message.edit_text(Text.user.BETTING_CURRENT_EMPTY.value)
    await callback.answer()
    return
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_PARAMS.value,
    reply_markup=betting_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("betstatmode:"))
async def betting_stat_mode_selected(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  mode = callback.data.split(":", 1)[1]
  if mode not in {"all", "regular", "year"}:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  await state.update_data(betstat_mode=mode, betstat_selected_ids=[])
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
  indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
  if not indicators:
    await callback.message.edit_text(Text.user.BETTING_CURRENT_EMPTY.value)
    await callback.answer()
    return
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_PARAMS.value,
    reply_markup=betting_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
  )
  await callback.answer()
@router.callback_query(F.data.startswith("betstat_page:"))
async def betting_stat_page(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  page = int(callback.data.split(":", 1)[1])
  data = await state.get_data()
  selected_ids: list[int] = data.get("betstat_selected_ids", [])
  mode = data.get("betstat_mode", "all")
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
  indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_PARAMS.value,
    reply_markup=betting_stat_indicators_keyboard(indicators=indicators, page=page, selected_ids=selected_ids),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("betstat_toggle:"))
async def betting_stat_indicator_selected(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  _, indicator_id_raw, page_raw = callback.data.split(":")
  indicator_id = int(indicator_id_raw)
  page = int(page_raw)
  data = await state.get_data()
  selected = set(data.get("betstat_selected_ids", []))
  mode = data.get("betstat_mode", "all")
  if indicator_id in selected:
    selected.remove(indicator_id)
  else:
    selected.add(indicator_id)
  await state.update_data(betstat_selected_ids=list(selected))
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
  indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
  await callback.message.edit_text(
    Text.user.STAT_CHOOSE_PARAMS.value,
    reply_markup=betting_stat_indicators_keyboard(indicators=indicators, page=page, selected_ids=list(selected)),
  )
  await callback.answer()


@router.callback_query(F.data == "betstat_done")
async def betting_stat_done(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  data = await state.get_data()
  selected_ids: list[int] = data.get("betstat_selected_ids", [])
  mode = data.get("betstat_mode", "all")
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    if not selected_ids:
      default_indicator = _default_betting_indicator(indicators=indicators, mode=mode)
      selected_ids = [int(default_indicator.row_id)] if default_indicator is not None else []
      await state.update_data(betstat_selected_ids=selected_ids)
    selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
    if len(selected) == 1:
      selected_years: list[int] = data.get("betstat_years", [])
      report = await StatUseCases(
        bet_repository=BetRepository(session),
        achievement_repository=AchievementRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_repository=PokerRepository(session),
      ).get_betting_stat(
        indicators=selected,
        mode=mode,
        years=selected_years,
        sort_pic=selected[0].pic,
      )
      image_bytes = render_stat_table_png(title="Статистика ставок", report=report)
      await callback.message.answer_photo(
        photo=BufferedInputFile(image_bytes, filename="betting_stat.png"),
        caption="Статистика ставок",
      )
      await state.update_data(betstat_years=[], betstat_selected_ids=[], betstat_mode="all", betstat_sort_id=None)
      await callback.answer()
      return
  await callback.message.edit_text(
    f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
    reply_markup=stat_sort_keyboard(
      prefix="betstatsort",
      indicators=selected,
      selected_ids=selected_ids,
      selected_sort_id=None,
      page=0,
    ),
  )
  await state.update_data(betstat_sort_id=None)
  await callback.answer()


@router.callback_query(F.data == "betstat_cancel")
async def betting_stat_cancel(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  await state.update_data(betstat_years=[], betstat_selected_ids=[], betstat_mode="all", betstat_sort_id=None)
  await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
  await callback.answer()


@router.callback_query(F.data.startswith("betstatsort_page:"))
async def betting_stat_sort_page(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  page = int(callback.data.split(":", 1)[1])
  data = await state.get_data()
  selected_ids: list[int] = data.get("betstat_selected_ids", [])
  mode = data.get("betstat_mode", "all")
  selected_sort_id = data.get("betstat_sort_id")
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
  await callback.message.edit_text(
    f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
    reply_markup=stat_sort_keyboard(
      prefix="betstatsort",
      indicators=selected,
      selected_ids=selected_ids,
      selected_sort_id=int(selected_sort_id) if selected_sort_id is not None else None,
      page=page,
    ),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("betstatsort_toggle:"))
async def betting_stat_sort_toggle(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  _, indicator_id_raw, page_raw = callback.data.split(":")
  indicator_id = int(indicator_id_raw)
  page = int(page_raw)
  data = await state.get_data()
  current_sort_id = data.get("betstat_sort_id")
  new_sort_id = None if current_sort_id is not None and int(current_sort_id) == indicator_id else indicator_id
  await state.update_data(betstat_sort_id=new_sort_id)
  selected_ids: list[int] = data.get("betstat_selected_ids", [])
  mode = data.get("betstat_mode", "all")
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
  await callback.message.edit_text(
    f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
    reply_markup=stat_sort_keyboard(
      prefix="betstatsort",
      indicators=selected,
      selected_ids=selected_ids,
      selected_sort_id=new_sort_id,
      page=page,
    ),
  )
  await callback.answer()


@router.callback_query(F.data == "betstatsort_cancel")
async def betting_stat_sort_cancel(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  await state.update_data(betstat_years=[], betstat_selected_ids=[], betstat_mode="all", betstat_sort_id=None)
  await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
  await callback.answer()


@router.callback_query(F.data == "betstatsort_done")
async def betting_stat_sort_done(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  data = await state.get_data()
  selected_ids: list[int] = data.get("betstat_selected_ids", [])
  mode = data.get("betstat_mode", "all")
  selected_years: list[int] = data.get("betstat_years", [])
  sort_id = data.get("betstat_sort_id")
  async with SessionFactory() as session:
    indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
    sort_indicator = next((item for item in selected if sort_id is not None and int(item.row_id) == int(sort_id)), None)
    sort_pic = sort_indicator.pic if sort_indicator is not None else None
    report = await StatUseCases(
      bet_repository=BetRepository(session),
      achievement_repository=AchievementRepository(session),
      bet_tournament_repository=BetTournamentRepository(session),
      bet_tournament_param_repository=BetTournamentParamRepository(session),
      poker_repository=PokerRepository(session),
    ).get_betting_stat(
      indicators=selected,
      mode=mode,
      years=selected_years,
      sort_pic=sort_pic,
    )
  image_bytes = render_stat_table_png(title="Статистика ставок", report=report)
  await callback.message.answer_photo(
    photo=BufferedInputFile(image_bytes, filename="betting_stat.png"),
    caption="Статистика ставок",
  )
  await state.update_data(betstat_years=[], betstat_selected_ids=[], betstat_mode="all", betstat_sort_id=None)
  await callback.answer()


@router.message(F.text == Buttons.betting.MAKE_BET.value)
async def start_make_bet(message: Message, state: FSMContext) -> None:
  if not await _ensure_approved_telegram_user(message):
    return

  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    user = await user_repository.get_by_telegram_id(message.from_user.id)
    if user is None or not user.is_approved:
      await message.answer(Text.user.BETTING_NOT_OPEN.value)
      return
    use_case = BetUseCases(
      user_repository=user_repository,
      poker_repository=PokerRepository(session),
      bet_repository=BetRepository(session),
      bet_param_repository=BetParamRepository(session),
      bet_tournament_repository=BetTournamentRepository(session),
      bet_tournament_param_repository=BetTournamentParamRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    bet_params, players, status = await use_case.get_bet_draft_data(
      better_id=message.from_user.id,
      tournament_type="single",
    )

  if status != "ok" or bet_params is None:
    await message.answer(Text.user.BETTING_NOT_OPEN.value)
    return

  await state.set_state(RegistrationState.waiting_for_bet_amount)
  await state.update_data(
    bet_tournament_type="single",
    bet_players=[p.player_name for p in players],
    bet_better_name=user.name,
  )
  await message.answer(
    Text.user.BETTING_SIZE_CHOOSE.value,
    reply_markup=betting_size_keyboard(
      small_size_kopecks=bet_params.small_size_kopecks,
      big_size_kopecks=bet_params.big_size_kopecks,
    ),
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
      existing_user = await repository.get_by_telegram_id(telegram_id)
      reply_markup = (await _approved_tg_keyboard(existing_user)) if existing_user and existing_user.is_approved else new_user_keyboard
      await message.answer(Text.user.REGISTRATION_EXIST.value, reply_markup=reply_markup)
      await state.clear()
      return
    except UserRegistrationPendingError:
      await message.answer(
        Text.user.REGISTRATION_PENDING.value,
        reply_markup=new_user_keyboard,
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
    reply_markup=new_user_keyboard,
  )


@router.callback_query(F.data.startswith("registration_played_before:"))
async def choose_registration_branch(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  choice = callback.data.split(":", 1)[1]
  if choice == "yes":
    await _delete_message_if_possible(callback)
    async with SessionFactory() as session:
      repository = UserRepository(session)
      candidates = await repository.list_approved_without_telegram_id()

    if not candidates:
      await state.set_state(RegistrationState.waiting_for_new_name)
      await callback.message.answer(Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value)
    else:
      await state.clear()
      await callback.message.answer(
        Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
        reply_markup=registration_candidates_keyboard(users=candidates),
      )
  else:
    await _delete_message_if_possible(callback)
    await state.set_state(RegistrationState.waiting_for_new_name)
    await callback.message.answer(Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
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
  await _delete_message_if_possible(callback)
  if not candidates:
    await callback.message.answer(Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value)
    await callback.answer()
    return
  await callback.message.answer(
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
  await _delete_message_if_possible(callback)
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
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  tournament_type = "single"
  await _delete_message_if_possible(callback)
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    user = await user_repository.get_by_telegram_id(callback.from_user.id)
    if user is None or not user.is_approved:
      await state.clear()
      await callback.message.answer(Text.user.BETTING_NOT_OPEN.value, reply_markup=betting_keyboard)
      await callback.answer()
      return
    use_case = BetUseCases(
      user_repository=user_repository,
      poker_repository=PokerRepository(session),
      bet_repository=BetRepository(session),
      bet_param_repository=BetParamRepository(session),
      bet_tournament_repository=BetTournamentRepository(session),
      bet_tournament_param_repository=BetTournamentParamRepository(session),
      poker_data_repository=PokerDataRepository(session),
    )
    bet_params, players, status = await use_case.get_bet_draft_data(
      better_id=callback.from_user.id,
      tournament_type=tournament_type,
    )
  if status != "ok" or bet_params is None:
    await state.clear()
    await callback.message.answer(Text.user.BETTING_NOT_OPEN.value, reply_markup=betting_keyboard)
    await callback.answer()
    return
  await state.set_state(RegistrationState.waiting_for_bet_amount)
  await state.update_data(
    bet_tournament_type=tournament_type,
    bet_players=[p.player_name for p in players],
    bet_better_name=user.name,
  )
  await callback.message.answer(
    Text.user.BETTING_SIZE_CHOOSE.value,
    reply_markup=betting_size_keyboard(
      small_size_kopecks=bet_params.small_size_kopecks,
      big_size_kopecks=bet_params.big_size_kopecks,
    ),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("bet_size:"))
async def choose_bet_size(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  data = await state.get_data()
  players = data.get("bet_players")
  if not isinstance(players, list) or not players:
    await state.clear()
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  amount_kopecks = int(callback.data.split(":", 1)[1])
  async with SessionFactory() as session:
    marks_map, winners_text, losers_text = await _build_bet_last_five_hints(session=session, players=players)
  await _delete_message_if_possible(callback)
  await state.update_data(
    bet_amount_kopecks=amount_kopecks,
    bet_player_marks=marks_map,
    bet_last_winners_text=winners_text,
    bet_last_losers_text=losers_text,
  )
  await callback.message.answer(
    f"💍 Последние победители:\n{winners_text}\n\n{Text.user.BETTING_WINNER_CHOOSE.value}",
    reply_markup=betting_player_keyboard(action="winner", players=players, player_marks=marks_map),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("bet_winner:"))
async def choose_bet_winner(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  data = await state.get_data()
  players = data.get("bet_players")
  better_name = data.get("bet_better_name")
  marks_map = data.get("bet_player_marks", {})
  losers_text = data.get("bet_last_losers_text", "")
  winner_name = callback.data.split(":", 1)[1]
  if not isinstance(players, list) or winner_name not in players:
    await state.clear()
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  loser_candidates = [player for player in players if player != winner_name and player != better_name]
  if not loser_candidates:
    await state.clear()
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  await _delete_message_if_possible(callback)
  await state.update_data(bet_winner_name=winner_name)
  loser_marks = {name: marks_map.get(name, "") for name in loser_candidates} if isinstance(marks_map, dict) else None
  await callback.message.answer(
    f"❌ Последние проигравшие:\n{losers_text}\n\n{Text.user.BETTING_LOSER_CHOOSE.value}",
    reply_markup=betting_player_keyboard(action="loser", players=loser_candidates, player_marks=loser_marks),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("bet_loser:"))
async def choose_bet_loser(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  loser_name = callback.data.split(":", 1)[1]
  data = await state.get_data()
  winner_name = data.get("bet_winner_name")
  tournament_type = data.get("bet_tournament_type")
  amount_kopecks = data.get("bet_amount_kopecks")
  if (
    not winner_name
    or not tournament_type
    or not isinstance(amount_kopecks, int)
    or loser_name == winner_name
  ):
    await state.clear()
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  await _delete_message_if_possible(callback)
  await state.update_data(bet_loser_name=loser_name)
  await callback.message.answer(
    Text.user.BETTING_CONFIRM.value.format(
      tournament=_format_tournament_name(tournament_type),
      amount_rub=amount_kopecks // 100,
      winner=winner_name,
      loser=loser_name,
    ),
    reply_markup=betting_confirm_keyboard(),
  )
  await callback.answer()


@router.callback_query(F.data.startswith("bet_confirm:"))
async def confirm_bet(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.message is None or callback.from_user is None:
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return
  if not await _ensure_approved_telegram_callback_user(callback):
    return
  choice = callback.data.split(":", 1)[1]
  await _delete_message_if_possible(callback)
  if choice != "yes":
    await state.clear()
    await callback.message.answer(Text.user.BETTING_MENU.value, reply_markup=betting_keyboard)
    await callback.answer()
    return
  data = await state.get_data()
  tournament_type = data.get("bet_tournament_type")
  amount_kopecks = data.get("bet_amount_kopecks")
  winner_name = data.get("bet_winner_name")
  loser_name = data.get("bet_loser_name")
  if (not tournament_type or not isinstance(amount_kopecks, int) or not winner_name or not loser_name):
    await state.clear()
    await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
    return

  try:
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
        better_id=callback.from_user.id,
        tournament_type=tournament_type,
        amount_kopecks=amount_kopecks,
        winner_name=winner_name,
        loser_name=loser_name,
      )
  except Exception:
    await callback.message.answer(Text.user.BETTING_NOT_OPEN.value, reply_markup=betting_keyboard)
    await state.clear()
    await callback.answer()
    return

  if status == "already_bet":
    await callback.message.answer(Text.user.BETTING_ALREADY_EXISTS.value, reply_markup=betting_keyboard)
  elif status in {"betting_closed", "user_not_approved", "invalid_tournament", "missing_params"}:
    await callback.message.answer(Text.user.BETTING_NOT_OPEN.value, reply_markup=betting_keyboard)
  elif status == "invalid_amount" or created is None:
    await callback.message.answer(Text.user.BETTING_NOT_OPEN.value, reply_markup=betting_keyboard)
  else:
    post_bet_keyboard = await _post_bet_tg_keyboard_for_user(telegram_id=callback.from_user.id)
    await callback.message.answer(
      Text.user.BETTING_CREATED.value.format(
        tournament=_format_tournament_name(tournament_type),
        amount_rub=amount_kopecks // 100,
        winner=winner_name,
        loser=loser_name,
      ),
      reply_markup=post_bet_keyboard,
    )
  await state.clear()
  await callback.answer()


@router.message(RegistrationState.waiting_for_bet_amount)
async def repeat_bet_inline_flow(message: Message) -> None:
  await message.answer(Text.user.BETTING_SIZE_CHOOSE.value)


@router.message(F.text.regexp(r"^\d{1,9}$"))
async def process_chips_input(message: Message, state: FSMContext) -> None:
  if message.from_user is None or not message.text:
    return
  if await state.get_state() is not None:
    return
  chips = int(message.text)
  async with SessionFactory() as session:
    user_repository = UserRepository(session)
    user = await user_repository.get_by_telegram_id(message.from_user.id)
    if user is None or not user.is_approved:
      return
    ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
    if ready is None:
      return
    poker, params = ready
    bb_size = max(1, int(params.bb_size_chips or 10))
    step = max(1, bb_size // 2)
    if chips % step != 0:
      await message.answer(Text.user.FINISH_CHIPS_INVALID.value.format(step=step))
      return
    poker_data_repository = PokerDataRepository(session)
    players = await poker_data_repository.list_players(date=poker.date)
    if not players:
      await message.answer(Text.user.FINISH_CHIPS_NOT_READY.value)
      return
    if user.is_admin:
      await state.update_data(cashout_input_value=chips)
      await message.answer(
        Text.admin.POKER_CHIPS_FOR_WHO.value.format(chips=chips),
        reply_markup=poker_cashout_candidates_keyboard(players=players),
      )
      return
    player = await poker_data_repository.get_player(date=poker.date, player_id=int(user.row_id))
    if player is None:
      await message.answer(Text.user.FINISH_CHIPS_NOT_IN_GAME.value)
      return
    money_kopecks = _money_kopecks_from_chips(
      chips=chips,
      buyins=int(player.buyins),
      buyin_size_chips=int(params.buyin_size_chips),
      buyin_size_kopecks=int(params.buyin_size_kopecks),
    )
    updated = await poker_data_repository.set_chips(date=poker.date, player_id=int(user.row_id), chips=chips)
    if updated is None:
      await message.answer(Text.user.FINISH_CHIPS_NOT_IN_GAME.value)
      return
    await poker_data_repository.set_cashout(
      date=poker.date,
      player_id=int(user.row_id),
      money_kopecks=int(money_kopecks),
    )
    await _notify_admins_about_chips_entry(
      session=session,
      player=updated,
      chips=chips,
      money_kopecks=int(money_kopecks),
    )
    await _upsert_tg_user_chips_result(
      chat_id=message.from_user.id,
      text=_build_user_chips_text(
        chips=int(chips),
        money_kopecks=int(money_kopecks),
        reaction=_chips_reaction(int(money_kopecks)),
      ),
    )


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
from datetime import datetime
