import random
from datetime import date, timezone
from zoneinfo import ZoneInfo

from app.bot.shared.chips_runtime import (
    TG_ADMIN_CHIPS_STATUS_MSG_IDS,
    TG_USER_CHIPS_RESULT_MSG_IDS,
)
from app.bot.shared.texts.inline.telegram.admin import common as InlineText
from app.bot.telegram.keyboards import poker_calc_keyboard
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.services.buyins_chart import render_buyins_session_chart_png

def _format_rub_from_kopecks(value_kopecks: int) -> str:
    rub = int(value_kopecks) // 100
    kop = int(value_kopecks) % 100
    if kop == 0:
        return str(rub)
    return f"{rub}.{kop:02d}"

def _get_reaction(mode: str) -> str:
    winner = [InlineText._GET_REACTION_MARKER_01, InlineText._GET_REACTION_MARKER_02, InlineText._GET_REACTION_MARKER_03, InlineText._GET_REACTION_MARKER_04, InlineText._GET_REACTION_MARKER_05, InlineText._GET_REACTION_MARKER_06, InlineText._GET_REACTION_MARKER_07]
    loser = [InlineText._GET_REACTION_MARKER_08, InlineText._GET_REACTION_MARKER_09, InlineText._GET_REACTION_MARKER_10, InlineText._GET_REACTION_MARKER_11, InlineText._GET_REACTION_MARKER_12, InlineText._GET_REACTION_MARKER_13, InlineText._GET_REACTION_MARKER_14]
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
        lines.append(f'{loser['name']}{InlineText._CALCULATE_TRANSFERS_MARKER_15_PART_2}{winner['name']}{InlineText._CALCULATE_TRANSFERS_MARKER_15_PART_4}{_format_rub_from_kopecks(transfer)}{InlineText._CALCULATE_TRANSFERS_MARKER_15_PART_6}')
    return lines

def _split_names_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in str(value).split(",") if item.strip()}

def _winner_mark(*, is_streak: bool) -> str:
    return InlineText._WINNER_MARK_MARKER_16 if is_streak else InlineText._WINNER_MARK_MARKER_17

def _bet_mark(*, amount_kopecks: int, guessed_winner: bool, guessed_loser: bool) -> str:
    size_mark = InlineText._BET_MARK_MARKER_18 if int(amount_kopecks) >= 40000 else InlineText._BET_MARK_MARKER_19
    if guessed_winner and guessed_loser:
        return f'{size_mark}{InlineText._BET_MARK_MARKER_20_PART_2}'
    if guessed_winner or guessed_loser:
        return f'{size_mark}{InlineText._BET_MARK_MARKER_21_PART_2}'
    return size_mark

def _build_chips_status_text(*, players: list, chips_in_game: int, chips_entered: int) -> str:
    def money_from_chips(
        chips: int, buyins: int, buyin_size_chips: int, buyin_size_kopecks: int
    ) -> int:
        if buyin_size_chips <= 0:
            return 0
        return (
            (int(chips) - int(buyins) * int(buyin_size_chips)) * int(buyin_size_kopecks)
        ) // int(buyin_size_chips)

    def reaction(money_kopecks: int) -> str:
        return InlineText.REACTION_MARKER_22 if int(money_kopecks) >= 0 else InlineText._GET_REACTION_MARKER_12

    # Fallback values are replaced by real params in _upsert_tg_admin_chips_status.
    buyin_size_chips = 200
    buyin_size_kopecks = 20000
    if players:
        sample = players[0]
        buyin_size_chips = int(getattr(sample, "_buyin_size_chips", buyin_size_chips))
        buyin_size_kopecks = int(getattr(sample, "_buyin_size_kopecks", buyin_size_kopecks))

    remainder = int(chips_in_game) - int(chips_entered)
    lines = [
        InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_01,
        "",
        f'{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_02_PART_1}{chips_in_game}{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_02_PART_2}{chips_entered}{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_02_PART_3}{remainder}',
        "",
    ]
    for p in players:
        if p.chips is None:
            lines.append(f'{p.player_name}{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_03_PART_1}')
        else:
            money_kopecks = money_from_chips(
                chips=int(p.chips),
                buyins=int(p.buyins),
                buyin_size_chips=buyin_size_chips,
                buyin_size_kopecks=buyin_size_kopecks,
            )
            lines.append(
                f'{p.player_name}{InlineText.NOTIFY_ADMINS_ABOUT_REMOVED_PLAYER_TEXT_01_PART_2}{int(p.chips)}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_24_PART_4}{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_24_PART_6}{reaction(int(money_kopecks))}'
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
        title=f'{InlineText.BUILD_POKER_BUYINS_SESSION_CHART_TEXT_01_PART_1}{poker_date.strftime('%d.%m.%Y')}',
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
    players = await poker_data_repository.list_players_for_date(date=poker_date)
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
    text = _build_chips_status_text(
        players=players, chips_in_game=chips_in_game, chips_entered=chips_entered
    )
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await user_repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
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

def _build_user_chips_text(
    *, chips: int | None, money_kopecks: int | None, reaction: str | None
) -> str:
    chips_text = str(chips) if chips is not None else InlineText.BUILD_USER_CHIPS_TEXT_TEXT_01
    if money_kopecks is None or reaction is None:
        result_text = InlineText.BUILD_USER_CHIPS_TEXT_TEXT_02
    else:
        result_text = f'{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_24_PART_6}{reaction}'
    return (
        f'{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_1}{chips_text}{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_2}{result_text}'
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
