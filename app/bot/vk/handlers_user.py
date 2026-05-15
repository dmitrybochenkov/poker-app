from fastapi.responses import PlainTextResponse
from datetime import date, datetime
import random

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
from app.bot.vk.api import (
  delete_vk_message,
  edit_vk_message_by_id,
  send_vk_message,
  send_vk_message_event_answer,
  send_vk_message_with_id,
  send_vk_photo,
)
from app.bot.shared.chips_runtime import VK_ADMIN_CHIPS_STATUS_MSG_IDS, VK_USER_CHIPS_RESULT_MSG_IDS
from app.bot.vk.keyboards import (
  admin_main_keyboard,
  betting_keyboard,
  betting_current_keyboard,
  betting_info_keyboard,
  poker_keyboard,
  poker_info_keyboard,
  poker_cashout_candidates_keyboard,
  poker_calc_keyboard,
  betting_confirm_keyboard,
  betting_player_keyboard,
  betting_size_keyboard,
  betting_stat_mode_keyboard,
  betting_stat_indicators_keyboard,
  poker_stat_indicators_keyboard,
  stat_year_keyboard,
  stat_sort_keyboard,
  poll_month_keyboard,
  main_keyboard,
  main_admin_entry_keyboard,
  new_user_keyboard,
  room_admin_keyboard,
  room_keyboard,
  admin_room_keyboard,
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
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poll_vote_repository import PollVoteRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.stat_image import render_stat_table_png

STAT_SNACKBAR = "Обновлено"


def _clear_vk_bet_draft_state(user_id: int) -> None:
  vk_user_states.pop(user_id, None)
  ctx = vk_user_contexts.setdefault(user_id, {})
  for key in (
    "bet_tournament_type",
    "bet_players",
    "bet_better_name",
    "bet_amount_kopecks",
    "bet_winner_name",
    "bet_loser_name",
  ):
    ctx.pop(key, None)


def _month_bounds(month: date) -> tuple[date, date]:
  first = date(month.year, month.month, 1)
  if month.month == 12:
    nxt = date(month.year + 1, 1, 1)
  else:
    nxt = date(month.year, month.month + 1, 1)
  return first, (nxt.fromordinal(nxt.toordinal() - 1))


def _shift_month(month: date, delta: int) -> date:
  total = month.year * 12 + (month.month - 1) + delta
  year = total // 12
  mon = total % 12 + 1
  return date(year, mon, 1)


def _parse_month_key(value: str | None) -> date:
  if not value:
    today = date.today()
    return date(today.year, today.month, 1)
  year_s, mon_s = str(value).split("-")
  return date(int(year_s), int(mon_s), 1)


def _parse_iso_dates(values: str | None) -> list[date]:
  if not values:
    return []
  result: list[date] = []
  for item in str(values).split("|"):
    if not item:
      continue
    try:
      result.append(date.fromisoformat(item))
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


def _strip_html_tags(text: str) -> str:
  return text.replace("<b>", "").replace("</b>", "")


def _money_kopecks_from_chips(*, chips: int, buyins: int, buyin_size_chips: int, buyin_size_kopecks: int) -> int:
  if buyin_size_chips <= 0:
    return 0
  return ((int(chips) - int(buyins) * int(buyin_size_chips)) * int(buyin_size_kopecks)) // int(buyin_size_chips)


def _format_rub_from_kopecks(value_kopecks: int) -> str:
  rub = int(value_kopecks) // 100
  kop = abs(int(value_kopecks) % 100)
  if kop == 0:
    return str(rub)
  return f"{rub}.{kop:02d}"


def _chips_reaction(money_kopecks: int) -> str:
  winner = ["🍾", "👍", "🔥", "🏆", "👏", "🤩", "🎉"]
  loser = ["👎", "🥴", "😢", "💩", "🤮", "😭", "🤷‍♀"]
  return random.choice(winner if int(money_kopecks) >= 0 else loser)


def _build_chips_status_text(*, players: list, chips_in_game: int, chips_entered: int) -> str:
  lines = [
    "🎰 Ввод фишек.",
    "",
    f"Всего в игре было {chips_in_game} фишек. Введено: {chips_entered} фишек",
    "",
  ]
  for p in players:
    if p.chips is None:
      lines.append(f"{p.player_name}: еще не ввел фишки")
    else:
      lines.append(f"{p.player_name}: {int(p.chips)}")
  return "\n".join(lines)


def _split_names(value: str | None) -> set[str]:
  if not value:
    return set()
  return {item.strip() for item in str(value).split(",") if item.strip()}


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


async def _notify_admins_about_room_join(
  *,
  session,
  joined_user: User,
  platform_label: str,
) -> None:
  from app.bot.telegram.runtime import telegram_bot

  repository = UserRepository(session)
  admin_tg_ids = await repository.list_telegram_admin_ids()
  admin_vk_ids = await repository.list_vk_admin_ids()
  text = (
    "🟢 Новый игрок в покер руме\n"
    f"Игрок: {joined_user.name}\n"
    f"Платформа: {platform_label}"
  )

  for admin_id in admin_tg_ids:
    if joined_user.telegram_id is not None and int(admin_id) == int(joined_user.telegram_id):
      continue
    if telegram_bot is not None:
      await telegram_bot.send_message(chat_id=admin_id, text=text)

  for admin_id in admin_vk_ids:
    if joined_user.vk_id is not None and int(admin_id) == int(joined_user.vk_id):
      continue
    await send_vk_message(user_id=admin_id, message=text)


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
  return "Турнир"


def _format_stat_info_report(indicators) -> str:
  if not indicators:
    return "Справка пока пустая."
  lines: list[str] = []
  for item in indicators:
    lines.append(f"{item.pic} {item.description}")
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
    lines.append(f"{item.pic} {title}")
    if detail:
      lines.append(detail)
    indicator_name = indicators_by_id.get(int(item.stat_id))
    if indicator_name:
      lines.append(f"Показатель: {indicator_name}")
    lines.append("")
  return "\n".join(lines).strip()


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
  await send_vk_message(user_id=user_id, message=success_message, keyboard=new_user_keyboard)


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

  if action == "poll_noop":
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    return PlainTextResponse("ok")

  if action == "poll_month":
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    return PlainTextResponse("ok")

  if action == "poll_page":
    month_key = callback_payload.get("month")
    page = callback_payload.get("page")
    if not isinstance(month_key, str) or not isinstance(page, int):
      return PlainTextResponse("ok")
    month = _parse_month_key(month_key)
    allowed_days = _poll_days_for_month(month)
    max_page = max(0, (len(allowed_days) - 1) // 6)
    page = max(0, min(int(page), max_page))
    ctx = vk_user_contexts.setdefault(user_id, {})
    selected = _parse_iso_dates(ctx.get("poll_selected"))
    ctx["poll_month"] = month_key
    ctx["poll_page"] = str(page)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=_poll_choose_text(month),
      keyboard=poll_month_keyboard(month=month, page=page, selected_dates=selected),
    )
    return PlainTextResponse("ok")

  if action == "poll_day":
    day_iso = callback_payload.get("date")
    page = callback_payload.get("page")
    if not isinstance(day_iso, str) or not isinstance(page, int):
      return PlainTextResponse("ok")
    try:
      day = date.fromisoformat(day_iso)
    except Exception:
      return PlainTextResponse("ok")
    ctx = vk_user_contexts.setdefault(user_id, {})
    selected = set(item.isoformat() for item in _parse_iso_dates(ctx.get("poll_selected")))
    if day_iso in selected:
      selected.remove(day_iso)
    else:
      selected.add(day_iso)
    selected_dates = _parse_iso_dates("|".join(sorted(selected)))
    month = date(day.year, day.month, 1)
    ctx["poll_month"] = f"{day.year}-{day.month:02d}"
    ctx["poll_page"] = str(page)
    ctx["poll_selected"] = "|".join(item.isoformat() for item in selected_dates)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=_poll_choose_text(month),
      keyboard=poll_month_keyboard(month=month, page=page, selected_dates=selected_dates),
    )
    return PlainTextResponse("ok")

  if action == "poll_done":
    user = await _get_vk_user(user_id)
    if user is None or not user.is_approved:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STATUS_NEED_REGISTRATION.value)
      return PlainTextResponse("ok")
    ctx = vk_user_contexts.setdefault(user_id, {})
    month = _parse_month_key(ctx.get("poll_month"))
    month_start, month_end = _month_bounds(month)
    allowed = set(_poll_days_for_month(month))
    selected = [item for item in _parse_iso_dates(ctx.get("poll_selected")) if item in allowed and month_start <= item <= month_end]
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
    ctx.pop("poll_month", None)
    ctx.pop("poll_page", None)
    ctx.pop("poll_selected", None)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=_format_poll_summary(month=month, selected_dates=selected, month_counts=month_counts))
    return PlainTextResponse("ok")

  if action == "poll_cancel":
    ctx = vk_user_contexts.setdefault(user_id, {})
    ctx.pop("poll_month", None)
    ctx.pop("poll_page", None)
    ctx.pop("poll_selected", None)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.POLL_CANCELED.value)
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
    tournament_type = "single"
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      user = await user_repository.get_by_vk_id(user_id)
      if user is None or not user.is_approved:
        await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_NOT_OPEN.value)
        return PlainTextResponse("ok")
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
    context["bet_better_name"] = user.name
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
    async with SessionFactory() as session:
      marks_map, winners_text, losers_text = await _build_bet_last_five_hints(session=session, players=players)
    context["bet_amount_kopecks"] = str(amount_kopecks)
    context["bet_player_marks"] = marks_map
    context["bet_last_winners_text"] = winners_text
    context["bet_last_losers_text"] = losers_text
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_WINNER_CHOOSE.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=f"💍 Последние победители:\n{winners_text}\n\n{Text.user.BETTING_WINNER_CHOOSE.value}",
      keyboard=betting_player_keyboard(action="winner", players=players, player_marks=marks_map),
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
    better_name = context.get("bet_better_name")
    marks_map = context.get("bet_player_marks", {})
    losers_text = context.get("bet_last_losers_text", "")
    losers = [p for p in players if p != winner_name and p != better_name]
    if not losers:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.BETTING_LOSER_CHOOSE.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    loser_marks = {name: marks_map.get(name, "") for name in losers} if isinstance(marks_map, dict) else None
    await send_vk_message(
      user_id=user_id,
      message=f"❌ Последние проигравшие:\n{losers_text}\n\n{Text.user.BETTING_LOSER_CHOOSE.value}",
      keyboard=betting_player_keyboard(action="loser", players=losers, player_marks=loser_marks),
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
    if not tournament_type or not winner_name or not loser_name or amount_kopecks <= 0:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
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
          better_id=user_id,
          tournament_type=tournament_type,
          amount_kopecks=amount_kopecks,
          winner_name=winner_name,
          loser_name=loser_name,
        )
    except Exception:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_NOT_OPEN.value, keyboard=betting_keyboard)
      return PlainTextResponse("ok")
    vk_user_states.pop(user_id, None)
    vk_user_contexts.pop(user_id, None)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    if status == "already_bet":
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_ALREADY_EXISTS.value, keyboard=betting_keyboard)
    elif status in {"betting_closed", "user_not_approved", "invalid_tournament", "missing_params"}:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_NOT_OPEN.value, keyboard=betting_keyboard)
    elif status == "invalid_amount" or created is None:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_NOT_OPEN.value, keyboard=betting_keyboard)
    else:
      await send_vk_message(
        user_id=user_id,
        message=Text.user.BETTING_CREATED.value.format(
          tournament=_format_tournament_name(tournament_type),
          amount_rub=amount_kopecks // 100,
          winner=winner_name,
          loser=loser_name,
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
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.STAT_CHOOSE_PARAMS.value,
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
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.STAT_CHOOSE_PARAMS.value,
      keyboard=betting_stat_indicators_keyboard(indicators=indicators, page=int(page) if isinstance(page, int) else 0, selected_ids=list(selected)),
    )
    return PlainTextResponse("ok")

  if action == "betstat_mode":
    mode = callback_payload.get("mode")
    if mode not in {"all", "regular", "year"}:
      return PlainTextResponse("ok")
    vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = mode
    vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    if not indicators:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_CURRENT_EMPTY.value)
      return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.user.STAT_CHOOSE_PARAMS.value,
      keyboard=betting_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
    )
    return PlainTextResponse("ok")

  if action in {"betstatyear_toggle", "betstatyear_page", "betstatyear_done", "betstatyear_cancel"}:
    user_ctx = vk_user_contexts.setdefault(user_id, {})
    page = callback_payload.get("page", 0)
    selected_years = [int(x) for x in user_ctx.get("betstat_years", "").split(",") if x]
    async with SessionFactory() as session:
      bets = await BetRepository(session).list_all()
    years = sorted({int(item.date.year) for item in bets if item.date is not None}, reverse=True)
    if action == "betstatyear_toggle":
      year = callback_payload.get("year")
      if not isinstance(year, int):
        return PlainTextResponse("ok")
      selected_set = set(selected_years)
      if year in selected_set:
        selected_set.remove(year)
      else:
        selected_set.add(year)
      selected_years = sorted(selected_set)
      user_ctx["betstat_years"] = ",".join(str(x) for x in selected_years)
      user_ctx["betstat_selected_ids"] = ""
    if action == "betstatyear_done":
      mode = user_ctx.get("betstat_mode", "all")
      if not selected_years:
        current_year = datetime.now().year
        selected_years = [current_year] if current_year in years else ([years[0]] if years else [])
        user_ctx["betstat_years"] = ",".join(str(x) for x in selected_years)
      user_ctx["betstat_selected_ids"] = ""
      async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
      indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
      if not indicators:
        await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
        await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
        await send_vk_message(user_id=user_id, message=Text.user.BETTING_CURRENT_EMPTY.value)
        return PlainTextResponse("ok")
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
      await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
      await send_vk_message(
        user_id=user_id,
        message=Text.user.STAT_CHOOSE_PARAMS.value,
        keyboard=betting_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
      )
      return PlainTextResponse("ok")
    if action == "betstatyear_cancel":
      user_ctx["betstat_years"] = ""
      user_ctx["betstat_selected_ids"] = ""
      user_ctx["betstat_mode"] = "all"
      user_ctx["betstat_sort_id"] = ""
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STAT_EXPORT_CANCELED.value)
      await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
      await send_vk_message(user_id=user_id, message=Text.user.STAT_EXPORT_CANCELED.value)
      return PlainTextResponse("ok")
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.STAT_CHOOSE_YEAR.value,
      keyboard=stat_year_keyboard(action="betstatyear", years=years, selected_years=selected_years, page=int(page) if isinstance(page, int) else 0),
    )
    return PlainTextResponse("ok")

  if action == "pokerstat_page":
    page = callback_payload.get("page")
    if not isinstance(page, int):
      return PlainTextResponse("ok")
    selected_ids = [int(x) for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",") if x]
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.STAT_CHOOSE_PARAMS.value,
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
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.STAT_CHOOSE_PARAMS.value,
      keyboard=poker_stat_indicators_keyboard(indicators=indicators, page=int(page) if isinstance(page, int) else 0, selected_ids=list(selected)),
    )
    return PlainTextResponse("ok")

  if action == "pokerstat_done":
    selected_ids = {int(x) for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",") if x}
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
      if not selected_ids:
        default_indicator = next((item for item in indicators if str(item.description).strip() == "Денег всего"), None)
        if default_indicator is None and indicators:
          default_indicator = indicators[0]
        selected_ids = {int(default_indicator.row_id)} if default_indicator is not None else set()
        vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ",".join(str(x) for x in sorted(selected_ids))
      selected = [item for item in indicators if int(item.row_id) in selected_ids]
      if len(selected) == 1:
        selected_years = [int(x) for x in vk_user_contexts.get(user_id, {}).get("pokerstat_years", "").split(",") if x]
        report = await StatUseCases(
          bet_repository=BetRepository(session),
          poker_data_repository=PokerDataRepository(session),
          achievement_repository=AchievementRepository(session),
          bet_tournament_repository=BetTournamentRepository(session),
          bet_tournament_param_repository=BetTournamentParamRepository(session),
          poker_repository=PokerRepository(session),
        ).get_poker_stat(indicators=selected, years=selected_years, sort_pic=selected[0].pic)
        await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text="Готово")
        await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
        image_bytes = render_stat_table_png(title="Статистика покера", report=report)
        await send_vk_photo(
          user_id=user_id,
          image_bytes=image_bytes,
          filename="poker_stat.png",
          message="Статистика покера",
          keyboard=poker_keyboard,
        )
        vk_user_contexts.setdefault(user_id, {})["pokerstat_years"] = ""
        vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["pokerstat_sort_id"] = ""
        return PlainTextResponse("ok")
    vk_user_contexts.setdefault(user_id, {})["pokerstat_sort_id"] = ""
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
      keyboard=stat_sort_keyboard(action="pokerstat_sort", indicators=selected, selected_ids=list(selected_ids), selected_sort_id=None, page=0),
    )
    return PlainTextResponse("ok")

  if action == "pokerstat_sort_page":
    page = callback_payload.get("page", 0)
    selected_ids = {int(x) for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",") if x}
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
      selected = [item for item in indicators if int(item.row_id) in selected_ids]
    sort_id_raw = vk_user_contexts.get(user_id, {}).get("pokerstat_sort_id")
    sort_id = int(sort_id_raw) if isinstance(sort_id_raw, str) and sort_id_raw.isdigit() else None
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
      keyboard=stat_sort_keyboard(
        action="pokerstat_sort",
        indicators=selected,
        selected_ids=list(selected_ids),
        selected_sort_id=sort_id,
        page=int(page) if isinstance(page, int) else 0,
      ),
    )
    return PlainTextResponse("ok")

  if action == "pokerstat_sort":
    indicator_id = callback_payload.get("indicator_id")
    if not isinstance(indicator_id, int):
      return PlainTextResponse("ok")
    page = callback_payload.get("page", 0)
    user_ctx = vk_user_contexts.setdefault(user_id, {})
    current_sort_id_raw = user_ctx.get("pokerstat_sort_id")
    current_sort_id = int(current_sort_id_raw) if isinstance(current_sort_id_raw, str) and current_sort_id_raw.isdigit() else None
    new_sort_id = None if current_sort_id == indicator_id else indicator_id
    user_ctx["pokerstat_sort_id"] = str(new_sort_id) if new_sort_id is not None else ""
    selected_ids = {int(x) for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",") if x}
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
      selected = [item for item in indicators if int(item.row_id) in selected_ids]
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
      keyboard=stat_sort_keyboard(
        action="pokerstat_sort",
        indicators=selected,
        selected_ids=list(selected_ids),
        selected_sort_id=new_sort_id,
        page=int(page) if isinstance(page, int) else 0,
      ),
    )
    return PlainTextResponse("ok")

  if action == "pokerstat_sort_done":
    selected_ids = {int(x) for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",") if x}
    selected_years = [int(x) for x in vk_user_contexts.get(user_id, {}).get("pokerstat_years", "").split(",") if x]
    sort_id_raw = vk_user_contexts.get(user_id, {}).get("pokerstat_sort_id")
    sort_id = int(sort_id_raw) if isinstance(sort_id_raw, str) and sort_id_raw.isdigit() else None
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
      selected = [item for item in indicators if int(item.row_id) in selected_ids]
      sort_indicator = next((item for item in selected if sort_id is not None and int(item.row_id) == sort_id), None)
      sort_pic = sort_indicator.pic if sort_indicator is not None else None
      report = await StatUseCases(
        bet_repository=BetRepository(session),
        poker_data_repository=PokerDataRepository(session),
        achievement_repository=AchievementRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_repository=PokerRepository(session),
      ).get_poker_stat(indicators=selected, years=selected_years, sort_pic=sort_pic)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text="Готово")
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    image_bytes = render_stat_table_png(title="Статистика покера", report=report)
    await send_vk_photo(
      user_id=user_id,
      image_bytes=image_bytes,
      filename="poker_stat.png",
      message="Статистика покера",
      keyboard=poker_keyboard,
    )
    vk_user_contexts.setdefault(user_id, {})["pokerstat_years"] = ""
    vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ""
    vk_user_contexts.setdefault(user_id, {})["pokerstat_sort_id"] = ""
    return PlainTextResponse("ok")

  if action == "pokerstat_sort_cancel":
    vk_user_contexts.setdefault(user_id, {})["pokerstat_years"] = ""
    vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ""
    vk_user_contexts.setdefault(user_id, {})["pokerstat_sort_id"] = ""
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STAT_EXPORT_CANCELED.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.STAT_EXPORT_CANCELED.value)
    return PlainTextResponse("ok")

  if action in {"pokerstatyear_toggle", "pokerstatyear_page", "pokerstatyear_done", "pokerstatyear_cancel"}:
    user_ctx = vk_user_contexts.setdefault(user_id, {})
    page = callback_payload.get("page", 0)
    selected_years = [int(x) for x in user_ctx.get("pokerstat_years", "").split(",") if x]
    async with SessionFactory() as session:
      rows = await PokerDataRepository(session).list_all()
    years = sorted({int(item.date.year) for item in rows if item.date is not None}, reverse=True)
    if action == "pokerstatyear_toggle":
      year = callback_payload.get("year")
      if not isinstance(year, int):
        return PlainTextResponse("ok")
      selected_set = set(selected_years)
      if year in selected_set:
        selected_set.remove(year)
      else:
        selected_set.add(year)
      selected_years = sorted(selected_set)
      user_ctx["pokerstat_years"] = ",".join(str(x) for x in selected_years)
      user_ctx["pokerstat_selected_ids"] = ""
    if action == "pokerstatyear_done":
      if not selected_years:
        current_year = datetime.now().year
        selected_years = [current_year] if current_year in years else ([years[0]] if years else [])
        user_ctx["pokerstat_years"] = ",".join(str(x) for x in selected_years)
      user_ctx["pokerstat_selected_ids"] = ""
      async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
      await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
      await send_vk_message(
        user_id=user_id,
        message=Text.user.STAT_CHOOSE_PARAMS.value,
        keyboard=poker_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
      )
      return PlainTextResponse("ok")
    if action == "pokerstatyear_cancel":
      user_ctx["pokerstat_years"] = ""
      user_ctx["pokerstat_selected_ids"] = ""
      user_ctx["pokerstat_sort_id"] = ""
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STAT_EXPORT_CANCELED.value)
      await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
      await send_vk_message(user_id=user_id, message=Text.user.STAT_EXPORT_CANCELED.value)
      return PlainTextResponse("ok")
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.STAT_CHOOSE_YEAR.value,
      keyboard=stat_year_keyboard(action="pokerstatyear", years=years, selected_years=selected_years, page=int(page) if isinstance(page, int) else 0),
    )
    return PlainTextResponse("ok")

  if action == "pokerstat_cancel":
    vk_user_contexts.setdefault(user_id, {})["pokerstat_years"] = ""
    vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ""
    vk_user_contexts.setdefault(user_id, {})["pokerstat_sort_id"] = ""
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STAT_EXPORT_CANCELED.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.STAT_EXPORT_CANCELED.value)
    return PlainTextResponse("ok")

  if action == "betstat_done":
    user_ctx = vk_user_contexts.get(user_id, {})
    mode = user_ctx.get("betstat_mode", "all")
    selected_ids = {int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x}
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
      indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
      if not selected_ids:
        default_indicator = _default_betting_indicator(indicators=indicators, mode=mode)
        selected_ids = {int(default_indicator.row_id)} if default_indicator is not None else set()
        vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ",".join(str(x) for x in sorted(selected_ids))
      selected = [item for item in indicators if int(item.row_id) in selected_ids]
      if len(selected) == 1:
        selected_years = [int(x) for x in user_ctx.get("betstat_years", "").split(",") if x]
        report = await StatUseCases(
          bet_repository=BetRepository(session),
          achievement_repository=AchievementRepository(session),
          bet_tournament_repository=BetTournamentRepository(session),
          bet_tournament_param_repository=BetTournamentParamRepository(session),
          poker_repository=PokerRepository(session),
        ).get_betting_stat(indicators=selected, mode=mode, years=selected_years, sort_pic=selected[0].pic)
        await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text="Готово")
        await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
        image_bytes = render_stat_table_png(title="Статистика ставок", report=report)
        await send_vk_photo(
          user_id=user_id,
          image_bytes=image_bytes,
          filename="betting_stat.png",
          message="Статистика ставок",
        )
        vk_user_contexts.setdefault(user_id, {})["betstat_years"] = ""
        vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = "all"
        vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = ""
        return PlainTextResponse("ok")
    vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = ""
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
      keyboard=stat_sort_keyboard(action="betstat_sort", indicators=selected, selected_ids=list(selected_ids), selected_sort_id=None, page=0),
    )
    return PlainTextResponse("ok")

  if action == "betstat_sort_page":
    page = callback_payload.get("page", 0)
    user_ctx = vk_user_contexts.get(user_id, {})
    mode = user_ctx.get("betstat_mode", "all")
    selected_ids = {int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x}
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
      indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
      selected = [item for item in indicators if int(item.row_id) in selected_ids]
    sort_id_raw = user_ctx.get("betstat_sort_id")
    sort_id = int(sort_id_raw) if isinstance(sort_id_raw, str) and sort_id_raw.isdigit() else None
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
      keyboard=stat_sort_keyboard(
        action="betstat_sort",
        indicators=selected,
        selected_ids=list(selected_ids),
        selected_sort_id=sort_id,
        page=int(page) if isinstance(page, int) else 0,
      ),
    )
    return PlainTextResponse("ok")

  if action == "betstat_sort":
    indicator_id = callback_payload.get("indicator_id")
    if not isinstance(indicator_id, int):
      return PlainTextResponse("ok")
    page = callback_payload.get("page", 0)
    user_ctx = vk_user_contexts.get(user_id, {})
    current_sort_id_raw = user_ctx.get("betstat_sort_id")
    current_sort_id = int(current_sort_id_raw) if isinstance(current_sort_id_raw, str) and current_sort_id_raw.isdigit() else None
    new_sort_id = None if current_sort_id == indicator_id else indicator_id
    vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = str(new_sort_id) if new_sort_id is not None else ""
    mode = user_ctx.get("betstat_mode", "all")
    selected_ids = {int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x}
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
      indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
      selected = [item for item in indicators if int(item.row_id) in selected_ids]
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(
      user_id=user_id,
      message=f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
      keyboard=stat_sort_keyboard(
        action="betstat_sort",
        indicators=selected,
        selected_ids=list(selected_ids),
        selected_sort_id=new_sort_id,
        page=int(page) if isinstance(page, int) else 0,
      ),
    )
    return PlainTextResponse("ok")

  if action == "betstat_sort_done":
    user_ctx = vk_user_contexts.get(user_id, {})
    mode = user_ctx.get("betstat_mode", "all")
    selected_ids = {int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x}
    selected_years = [int(x) for x in user_ctx.get("betstat_years", "").split(",") if x]
    sort_id_raw = user_ctx.get("betstat_sort_id")
    sort_id = int(sort_id_raw) if isinstance(sort_id_raw, str) and sort_id_raw.isdigit() else None
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
      indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
      selected = [item for item in indicators if int(item.row_id) in selected_ids]
      sort_indicator = next((item for item in selected if sort_id is not None and int(item.row_id) == sort_id), None)
      sort_pic = sort_indicator.pic if sort_indicator is not None else None
      report = await StatUseCases(
        bet_repository=BetRepository(session),
        achievement_repository=AchievementRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_repository=PokerRepository(session),
      ).get_betting_stat(indicators=selected, mode=mode, years=selected_years, sort_pic=sort_pic)
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text="Готово")
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    image_bytes = render_stat_table_png(title="Статистика ставок", report=report)
    await send_vk_photo(
      user_id=user_id,
      image_bytes=image_bytes,
      filename="betting_stat.png",
      message="Статистика ставок",
    )
    vk_user_contexts.setdefault(user_id, {})["betstat_years"] = ""
    vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
    vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = "all"
    vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = ""
    return PlainTextResponse("ok")

  if action == "betstat_sort_cancel":
    vk_user_contexts.setdefault(user_id, {})["betstat_years"] = ""
    vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
    vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = "all"
    vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = ""
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STAT_EXPORT_CANCELED.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.STAT_EXPORT_CANCELED.value)
    return PlainTextResponse("ok")

  if action == "betstat_cancel":
    vk_user_contexts.setdefault(user_id, {})["betstat_years"] = ""
    vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
    vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = "all"
    vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = ""
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.STAT_EXPORT_CANCELED.value)
    await _delete_event_message_if_possible(peer_id=peer_id, conversation_message_id=conversation_message_id)
    await send_vk_message(user_id=user_id, message=Text.user.STAT_EXPORT_CANCELED.value)
    return PlainTextResponse("ok")

  return None


async def handle_user_message_new(*, user_id: int, text: str) -> PlainTextResponse | None:
  if text.isdigit():
    chips = int(text)
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      user = await user_repository.get_by_vk_id(user_id)
      if user is None or not user.is_approved:
        return None
      ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
      if ready is None:
        return None
      poker, params = ready
      bb_size = max(1, int(params.bb_size_chips or 10))
      step = max(1, bb_size // 2)
      if chips % step != 0:
        await send_vk_message(user_id=user_id, message=Text.user.FINISH_CHIPS_INVALID.value.format(step=step))
        return PlainTextResponse("ok")
      poker_data_repository = PokerDataRepository(session)
      players = await poker_data_repository.list_players(date=poker.date)
      if not players:
        await send_vk_message(user_id=user_id, message=Text.user.FINISH_CHIPS_NOT_READY.value)
        return PlainTextResponse("ok")
      if user.is_admin:
        vk_user_contexts.setdefault(user_id, {})["cashout_input_value"] = str(chips)
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.POKER_CHIPS_FOR_WHO.value.format(chips=chips),
          keyboard=poker_cashout_candidates_keyboard(players=players),
        )
        return PlainTextResponse("ok")
      player = await poker_data_repository.get_player(date=poker.date, player_id=int(user.row_id))
      if player is None:
        await send_vk_message(user_id=user_id, message=Text.user.FINISH_CHIPS_NOT_IN_GAME.value)
        return PlainTextResponse("ok")
      money_kopecks = _money_kopecks_from_chips(
        chips=chips,
        buyins=int(player.buyins),
        buyin_size_chips=int(params.buyin_size_chips),
        buyin_size_kopecks=int(params.buyin_size_kopecks),
      )
      updated = await poker_data_repository.set_chips(date=poker.date, player_id=int(user.row_id), chips=chips)
      if updated is None:
        await send_vk_message(user_id=user_id, message=Text.user.FINISH_CHIPS_NOT_IN_GAME.value)
        return PlainTextResponse("ok")
      await poker_data_repository.set_cashout(
        date=poker.date,
        player_id=int(user.row_id),
        money_kopecks=int(money_kopecks),
      )
      admins = [u for u in await user_repository.list_approved() if u.is_admin]
      all_players = await poker_data_repository.list_players(date=poker.date)
      chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in all_players)
      chips_entered = sum(int(p.chips or 0) for p in all_players)
      admin_text = _build_chips_status_text(
        players=all_players,
        chips_in_game=chips_in_game,
        chips_entered=chips_entered,
      )
      from app.bot.telegram.runtime import telegram_bot
      for admin in admins:
        if admin.notification_platform == "tg" and admin.telegram_id is not None and telegram_bot is not None:
          await telegram_bot.send_message(chat_id=admin.telegram_id, text=admin_text)
        elif admin.notification_platform == "vk" and admin.vk_id is not None:
          prev_mid = VK_ADMIN_CHIPS_STATUS_MSG_IDS.get(int(admin.vk_id))
          if prev_mid is not None:
            try:
              await edit_vk_message_by_id(
                peer_id=int(admin.vk_id),
                message_id=int(prev_mid),
                message=admin_text,
                keyboard=poker_calc_keyboard(),
              )
              continue
            except Exception:
              pass
          sent_mid = await send_vk_message_with_id(
            user_id=int(admin.vk_id),
            message=admin_text,
            keyboard=poker_calc_keyboard(),
          )
          if sent_mid is not None:
            VK_ADMIN_CHIPS_STATUS_MSG_IDS[int(admin.vk_id)] = int(sent_mid)
      user_text = Text.user.FINISH_CHIPS_SAVED.value.format(
        chips=chips,
        money_rub=_format_rub_from_kopecks(int(money_kopecks)),
        reaction=_chips_reaction(int(money_kopecks)),
      )
      prev_user_mid = VK_USER_CHIPS_RESULT_MSG_IDS.get(int(user_id))
      if prev_user_mid is not None:
        try:
          await edit_vk_message_by_id(
            peer_id=int(user_id),
            message_id=int(prev_user_mid),
            message=user_text,
          )
        except Exception:
          sent_mid = await send_vk_message_with_id(user_id=user_id, message=user_text)
          if sent_mid is not None:
            VK_USER_CHIPS_RESULT_MSG_IDS[int(user_id)] = int(sent_mid)
      else:
        sent_mid = await send_vk_message_with_id(user_id=user_id, message=user_text)
        if sent_mid is not None:
          VK_USER_CHIPS_RESULT_MSG_IDS[int(user_id)] = int(sent_mid)
      return PlainTextResponse("ok")

  if text in {
    Buttons.main.BETTING.value,
    Buttons.betting.TO_MAIN.value,
    Buttons.betting.CURRENT_TOURS.value,
    Buttons.betting_current.REG_TOURNAMENT.value,
    Buttons.betting_current.YEAR_TOURNAMENT.value,
    Buttons.betting_current.TO_MAIN.value,
    Buttons.betting.BETTING_STAT.value,
    Buttons.betting.BETTING_INFO.value,
    Buttons.bettingInfo.BETTING_RULES.value,
    Buttons.bettingInfo.BETTING_ACH_INFO.value,
    Buttons.bettingInfo.BETTING_STAT_INFO.value,
    Buttons.betting.MAKE_BET.value,
    Buttons.main.ROOM.value,
    Buttons.room.STATUS.value,
    Buttons.main.ADMIN.value,
    Buttons.admin_main.TO_MAIN.value,
    Buttons.main.POKER.value,
    Buttons.poker.TO_MAIN.value,
    Buttons.poker.POKER_INFO.value,
    Buttons.pokerInfo.POKER_ACH_INFO.value,
    Buttons.pokerInfo.POKER_STAT_INFO.value,
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
    await send_vk_message(user_id=user_id, message=Text.admin.ADMIN_PANEL.value, keyboard=admin_main_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.admin_main.TO_MAIN.value:
    user = await _get_vk_user(user_id)
    if user is None:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    if not user.is_approved:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=Text.user.MAIN_MENU.value, keyboard=_approved_vk_keyboard(user))
    return PlainTextResponse("ok")

  if text == Buttons.main.BETTING.value:
    await send_vk_message(user_id=user_id, message=Text.user.BETTING_MENU.value, keyboard=betting_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.main.POKER.value:
    await send_vk_message(user_id=user_id, message=Text.user.POKER_MENU.value, keyboard=poker_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.betting.TO_MAIN.value:
    await send_vk_message(user_id=user_id, message=Text.user.MAIN_MENU.value, keyboard=main_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.poker.TO_MAIN.value:
    user = await _get_vk_user(user_id)
    if user is None:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=Text.user.MAIN_MENU.value, keyboard=_approved_vk_keyboard(user))
    return PlainTextResponse("ok")

  if text == Buttons.room.TO_MAIN.value:
    user = await _get_vk_user(user_id)
    if user is None:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    if not user.is_approved:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=Text.user.MAIN_MENU.value, keyboard=_approved_vk_keyboard(user))
    return PlainTextResponse("ok")

  if text == Buttons.poker.POKER_INFO.value:
    await send_vk_message(user_id=user_id, message=Text.user.POKER_STAT_BTN.value, keyboard=poker_info_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.betting.BETTING_INFO.value:
    await send_vk_message(user_id=user_id, message=Text.user.BETTING_MENU.value, keyboard=betting_info_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.bettingInfo.BETTING_RULES.value:
    await send_vk_message(
      user_id=user_id,
      message=_strip_html_tags(Text.user.BET_RULES.value),
      keyboard=betting_info_keyboard,
    )
    return PlainTextResponse("ok")

  if text == Buttons.bettingInfo.BETTING_STAT_INFO.value:
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    await send_vk_message(
      user_id=user_id,
      message=_format_stat_info_report(indicators),
      keyboard=betting_info_keyboard,
    )
    return PlainTextResponse("ok")

  if text == Buttons.bettingInfo.BETTING_ACH_INFO.value:
    async with SessionFactory() as session:
      achievements = await AchievementRepository(session).list_by_type(achievement_type="betting")
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators_by_id = {int(item.row_id): item.description for item in indicators}
    await send_vk_message(
      user_id=user_id,
      message=_format_achievement_info_report(achievements, indicators_by_id),
      keyboard=betting_info_keyboard,
    )
    return PlainTextResponse("ok")

  if text == Buttons.pokerInfo.POKER_STAT_INFO.value:
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    await send_vk_message(
      user_id=user_id,
      message=_format_stat_info_report(indicators),
      keyboard=poker_info_keyboard,
    )
    return PlainTextResponse("ok")

  if text == Buttons.pokerInfo.POKER_ACH_INFO.value:
    async with SessionFactory() as session:
      achievements = await AchievementRepository(session).list_by_type(achievement_type="poker")
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    indicators_by_id = {int(item.row_id): item.description for item in indicators}
    await send_vk_message(
      user_id=user_id,
      message=_format_achievement_info_report(achievements, indicators_by_id),
      keyboard=poker_info_keyboard,
    )
    return PlainTextResponse("ok")

  if text == Buttons.poker.POKER_STAT.value:
    user_ctx = vk_user_contexts.setdefault(user_id, {})
    user_ctx["pokerstat_years"] = ""
    user_ctx["pokerstat_selected_ids"] = ""
    user_ctx["pokerstat_sort_id"] = ""
    async with SessionFactory() as session:
      rows = await PokerDataRepository(session).list_all()
    years = sorted({int(item.date.year) for item in rows if item.date is not None}, reverse=True)
    if not years:
      await send_vk_message(user_id=user_id, message=Text.user.POKER_STAT_REPORT.value.format(report="Нет данных по покеру."))
      return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.user.STAT_CHOOSE_YEAR.value,
      keyboard=stat_year_keyboard(action="pokerstatyear", years=years, selected_years=[], page=0),
    )
    return PlainTextResponse("ok")

  if text == Buttons.betting.CURRENT_TOURS.value:
    await send_vk_message(user_id=user_id, message=Text.user.BETTING_MENU.value, keyboard=betting_current_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.betting.BETTING_STAT.value:
    user_ctx = vk_user_contexts.setdefault(user_id, {})
    user_ctx["betstat_years"] = ""
    user_ctx["betstat_selected_ids"] = ""
    user_ctx["betstat_mode"] = "all"
    user_ctx["betstat_sort_id"] = ""
    async with SessionFactory() as session:
      bets = await BetRepository(session).list_all()
    years = sorted({int(item.date.year) for item in bets if item.date is not None}, reverse=True)
    if not years:
      await send_vk_message(user_id=user_id, message="Нет данных по ставкам.")
      return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.user.STAT_CHOOSE_YEAR.value,
      keyboard=stat_year_keyboard(action="betstatyear", years=years, selected_years=[], page=0),
    )
    return PlainTextResponse("ok")

  if text in {Buttons.betting_current.REG_TOURNAMENT.value, Buttons.betting_current.YEAR_TOURNAMENT.value}:
    user_ctx = vk_user_contexts.setdefault(user_id, {})
    user_ctx["betstat_years"] = ""
    user_ctx["betstat_selected_ids"] = ""
    user_ctx["betstat_mode"] = "regular" if text == Buttons.betting_current.REG_TOURNAMENT.value else "year"
    user_ctx["betstat_sort_id"] = ""
    async with SessionFactory() as session:
      indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=user_ctx["betstat_mode"])
    if not indicators:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_CURRENT_EMPTY.value)
      return PlainTextResponse("ok")
    await send_vk_message(
      user_id=user_id,
      message=Text.user.STAT_CHOOSE_PARAMS.value,
      keyboard=betting_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
    )
    return PlainTextResponse("ok")

  if text == Buttons.betting_current.TO_MAIN.value:
    await send_vk_message(user_id=user_id, message=Text.user.BETTING_MENU.value, keyboard=betting_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.betting.MAKE_BET.value:
    async with SessionFactory() as session:
      user_repository = UserRepository(session)
      user = await user_repository.get_by_vk_id(user_id)
      if user is None or not user.is_approved:
        await send_vk_message(user_id=user_id, message=Text.user.BETTING_NOT_OPEN.value)
        return PlainTextResponse("ok")
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
        better_id=user_id,
        tournament_type="single",
      )
    if status != "ok" or bet_params is None:
      await send_vk_message(user_id=user_id, message=Text.user.BETTING_NOT_OPEN.value)
      return PlainTextResponse("ok")
    context = vk_user_contexts.setdefault(user_id, {})
    context["bet_tournament_type"] = "single"
    context["bet_players"] = "|".join([p.player_name for p in players])
    context["bet_better_name"] = user.name
    vk_user_states[user_id] = WAITING_FOR_BET_AMOUNT
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BETTING_SIZE_CHOOSE.value,
      keyboard=betting_size_keyboard(
        small_size_kopecks=bet_params.small_size_kopecks,
        big_size_kopecks=bet_params.big_size_kopecks,
      ),
    )
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_BET_AMOUNT:
    menu_buttons = {
      Buttons.main.ROOM.value,
      Buttons.main.POKER.value,
      Buttons.main.BETTING.value,
      Buttons.main.ADMIN.value,
      Buttons.room.TO_MAIN.value,
      Buttons.poker.TO_MAIN.value,
      Buttons.betting.TO_MAIN.value,
    }
    if text in menu_buttons:
      _clear_vk_bet_draft_state(user_id=user_id)
    else:
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

      poker_repository = PokerRepository(session)
      poker_data_repository = PokerDataRepository(session)
      active = await poker_repository.get_started()
      ready = await poker_repository.get_latest_ready_for_chips() if active is None else None
      current_poker_date = active[0].date if active is not None else (ready.date if ready is not None else None)
      if current_poker_date is None:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_CLOSED.value)
        return PlainTextResponse("ok")

      use_case = ManagePokerPlayersUseCase(
        poker_repository=poker_repository,
        poker_data_repository=poker_data_repository,
        poker_room_denied_repository=PokerRoomDeniedRepository(session),
      )
      is_denied = await use_case.is_denied_for_active_poker(user_row_id=int(user.row_id))
      if is_denied:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_NOT_ADDED.value)
        return PlainTextResponse("ok")
      players = await poker_data_repository.list_players(date=current_poker_date)
      if players:
        already_in_room = any(int(item.player_id) == int(user.row_id) for item in players)
        if already_in_room:
          await send_vk_message(
            user_id=user_id,
            message=Text.user.ROOM_JOINED.value,
            keyboard=room_admin_keyboard if user.is_admin else room_keyboard,
          )
          return PlainTextResponse("ok")

      if active is None:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_CLOSED.value)
        return PlainTextResponse("ok")
      created = await use_case.add_player_to_active_poker(player_id=int(user.row_id), player_name=user.name)
      if created is None:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_CLOSED.value)
        return PlainTextResponse("ok")
      await _notify_admins_about_room_join(
        session=session,
        joined_user=user,
        platform_label="VK",
      )

    await send_vk_message(
      user_id=user_id,
      message=Text.user.ROOM_JOINED.value,
      keyboard=room_admin_keyboard if user.is_admin else room_keyboard,
    )
    return PlainTextResponse("ok")

  if text == Buttons.room.POKER_ADMIN.value:
    user = await _get_vk_user(user_id)
    if user is None:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    if not user.is_approved:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    if not user.is_admin:
      await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value, keyboard=room_keyboard)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=Text.admin.ADMIN_PANEL.value, keyboard=admin_room_keyboard)
    return PlainTextResponse("ok")

  if text == Buttons.poker.POLL.value:
    user = await _get_vk_user(user_id)
    if user is None:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    if not user.is_approved:
      await send_vk_message(user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard)
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      month = await PollConfigRepository(session).get_active_month()
    if month is None:
      await send_vk_message(user_id=user_id, message=Text.user.POLL_NOT_ACTIVE.value)
      return PlainTextResponse("ok")
    month_start, month_end = _month_bounds(month)
    async with SessionFactory() as session:
      selected = await PollVoteRepository(session).get_user_month_votes(
        player_row_id=int(user.row_id),
        month_start=month_start,
        month_end=month_end,
      )
    ctx = vk_user_contexts.setdefault(user_id, {})
    ctx["poll_month"] = f"{month.year}-{month.month:02d}"
    ctx["poll_page"] = "0"
    ctx["poll_selected"] = "|".join(item.isoformat() for item in selected)
    await send_vk_message(
      user_id=user_id,
      message=_poll_choose_text(month),
      keyboard=poll_month_keyboard(month=month, page=0, selected_dates=selected),
    )
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

      current_player = next((item for item in players if int(item.player_id) == int(user.row_id)), None)
      if current_player is None:
        await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_NOT_ADDED.value)
        return PlainTextResponse("ok")

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

    await send_vk_message(user_id=user_id, message="\n".join(lines))
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

  if text == Buttons.new_user.ABOUT.value:
    async with SessionFactory() as session:
      repository = UserRepository(session)
      existing_user = await repository.get_by_vk_id(user_id)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BOT_INFO.value,
      keyboard=_approved_vk_keyboard(existing_user) if existing_user and existing_user.is_approved else new_user_keyboard,
    )
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
