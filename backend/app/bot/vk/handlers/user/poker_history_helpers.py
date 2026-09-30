from datetime import date, timezone
from zoneinfo import ZoneInfo

from app.bot.shared.texts.inline.vk.user import common as InlineText
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.services.buyins_chart import render_buyins_session_chart_png

def _money_kopecks_from_chips(
    *, chips: int, buyins: int, buyin_size_chips: int, buyin_size_kopecks: int
) -> int:
    if buyin_size_chips <= 0:
        return 0
    return ((int(chips) - int(buyins) * int(buyin_size_chips)) * int(buyin_size_kopecks)) // int(
        buyin_size_chips
    )

def _format_rub_from_kopecks(value_kopecks: int) -> str:
    rub = int(value_kopecks) // 100
    kop = abs(int(value_kopecks) % 100)
    if kop == 0:
        return str(rub)
    return f"{rub}.{kop:02d}"

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
        lines.append(f'{loser['name']}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_4}{winner['name']}{InlineText.FORMAT_ACHIEVEMENT_INFO_REPORT_TEXT_02_PART_2}{_format_rub_from_kopecks(transfer)}{InlineText._FORMAT_UNPAID_BETS_LINES_MARKER_01_PART_4}')
    return lines

async def _build_poker_history_report(*, session, target_date: date) -> str:
    poker_rows = await PokerRepository(session).list_all()
    poker = next(
        (item for item in poker_rows if item.date == target_date and not bool(item.is_going)), None
    )
    if poker is None:
        return InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_01
    params = await PokerParamRepository(session).get_by_row_id(row_id=int(poker.params_id))
    buyin_size_chips = int(params.buyin_size_chips) if params is not None else 200
    buyin_size_kopecks = int(params.buyin_size_kopecks) if params is not None else 20000
    players = await PokerDataRepository(session).list_players_for_date(date=target_date)
    if not players:
        return InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_02

    player_rows: list[dict[str, int | str]] = []
    money_rows: list[dict[str, int | str]] = []
    for player in players:
        chips = int(player.chips or 0)
        money_kopecks = int(
            player.money_kopecks
            or _money_kopecks_from_chips(
                chips=chips,
                buyins=int(player.buyins),
                buyin_size_chips=buyin_size_chips,
                buyin_size_kopecks=buyin_size_kopecks,
            )
        )
        money_rows.append({"name": player.player_name, "money": money_kopecks})
        player_rows.append(
            {
                "name": player.player_name,
                "buyins": int(player.buyins),
                "chips": chips,
                "money": money_kopecks,
            }
        )

    player_rows.sort(key=lambda item: int(item["money"]), reverse=True)
    player_lines = [
        (
            f'{str(item['name'])}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_03_PART_1}{int(item['buyins'])}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_03_PART_2}{int(item['chips'])}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_03_PART_3}{_format_rub_from_kopecks(int(item['money']))}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_03_PART_4}'
        )
        for item in player_rows
    ]
    poker_money_by_name = {str(item["name"]): int(item["money"]) for item in player_rows}

    winners = [name.strip() for name in str(poker.winners or "").split(",") if name.strip()]
    losers = [name.strip() for name in str(poker.loosers or "").split(",") if name.strip()]
    winner_line = ", ".join(f'{InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_22_PART_1}{name}' for name in winners) if winners else InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_23
    loser_line = ", ".join(f'{InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_24_PART_1}{name}' for name in losers) if losers else InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_25
    transfer_lines = _calculate_transfers_history(money_rows)
    bets = await BetRepository(session).list_for_date(date=target_date)

    lines = [
        target_date.strftime("%d.%m.%Y"),
        InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_04,
        *player_lines,
        "",
        winner_line,
        loser_line,
        "",
        InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_05,
    ]
    lines.extend(transfer_lines if transfer_lines else [InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_06])
    if bets:
        lines.extend(["", InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_07])
        for bet in sorted(
            bets,
            key=lambda item: (
                -int(item.score or 0),
                -int(poker_money_by_name.get(str(item.better_name), 0)),
                int(item.row_id),
            ),
        ):
            size_mark = InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_26 if int(bet.amount_kopecks or 0) >= 40000 else InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_27
            score_value = int(bet.score or 0)
            score_text = f"+{score_value}" if score_value > 0 else str(score_value)
            winner_name = str(bet.winner_name or "-")
            loser_name = str(bet.loser_name or "-")
            lines.append(
                f'{bet.better_name}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_1}{size_mark}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_2}{winner_name}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_3}{loser_name}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_4}{score_text}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_5}'
            )
    return "\n".join(lines)

async def _build_poker_history_buyins_chart(*, session, target_date: date) -> bytes | None:
    buyin_events = await BuyinDataRepository(session).list_for_date(poker_date=target_date)
    if not buyin_events:
        return None

    cumulative: dict[str, int] = {}
    points: dict[str, list[tuple[int, int]]] = {}
    x_labels: list[str] = []
    msk_tz = ZoneInfo("Europe/Moscow")

    for idx, event in enumerate(buyin_events):
        if event.created_at is not None:
            event_dt = event.created_at
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
            label = event_dt.astimezone(msk_tz).strftime("%H:%M")
        else:
            label = str(idx + 1)
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
        title=f'{InlineText.BUILD_POKER_HISTORY_BUYINS_CHART_TEXT_01_PART_1}{target_date.strftime('%d.%m.%Y')}',
        series=points,
        x_labels=x_labels,
        legend_value_mode="max",
    )

async def _build_bet_last_five_hints(
    *, session, players: list[str]
) -> tuple[dict[str, str], str, str]:
    poker_rows = await PokerRepository(session).list_all()
    poker_rows = [
        p
        for p in poker_rows
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
                marks.append(InlineText.PLAYER_MARKS_MARKER_28)
            elif player_name in losers_by_date.get(d, set()):
                marks.append(InlineText.PLAYER_MARKS_MARKER_29)
            else:
                marks.append(InlineText.PLAYER_MARKS_MARKER_30)
        return "".join(marks)

    marks_map = {name: player_marks(name) for name in players}
    last_five_games = poker_rows[-5:]
    winners_text = "\n".join(str(p.winners or "-") for p in last_five_games)
    losers_text = "\n".join(str(p.loosers or "-") for p in last_five_games)
    return marks_map, winners_text, losers_text
