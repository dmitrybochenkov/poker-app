import logging
import random
from datetime import date, timezone
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
from app.application.use_cases.user.reject_user import RejectUserUseCase
from app.bot.shared.chips_runtime import (
    TG_ADMIN_ROOM_STATUS_MSG_IDS,
    VK_ADMIN_CHIPS_STATUS_MSG_IDS,
    VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.vk.admin import common as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import main_dynamic_keyboard as tg_main_dynamic_keyboard
from app.bot.telegram.keyboards import main_keyboard as tg_main_keyboard
from app.bot.telegram.keyboards import (
    poker_room_admin_status_keyboard as tg_poker_room_admin_status_keyboard,
)
from app.bot.telegram.notifications import notify_user_about_approval
from app.bot.vk.api import (
    clear_vk_message_keyboard_by_id,
    delete_vk_message,
    delete_vk_message_by_id,
    pin_vk_message_by_id,
    send_vk_message,
    send_vk_message_with_id,
)
from app.bot.vk.keyboards import (
    main_dynamic_keyboard as vk_main_dynamic_keyboard,
)
from app.bot.vk.keyboards import (
    main_keyboard,
    poker_calc_keyboard,
    poker_room_admin_status_keyboard,
)
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.buyins_chart import render_buyins_session_chart_png

VK_BUYIN_NOTIFY_CASHIER_ONLY: set[tuple[int, int]] = set()
VK_MANUAL_RECEIPT_SELECTIONS: dict[tuple[int, int], set[int]] = {}
logger = logging.getLogger(__name__)


HANDLER_UNMATCHED = object()


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
            InlineText.REFRESH_ADMIN_ROOM_STATUS_TEXT_01
        )
    else:
        status_text = (
            InlineText.REFRESH_ADMIN_ROOM_STATUS_TEXT_02
        )
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await user_repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
    tg_admins = [int(u.telegram_id) for u in admins if u.telegram_id is not None]
    vk_admins = [int(u.vk_id) for u in admins if u.vk_id is not None]
    if telegram_bot is not None:
        for admin_id in tg_admins:
            prev_mid = TG_ADMIN_ROOM_STATUS_MSG_IDS.get(int(admin_id))
            if prev_mid is not None:
                try:
                    await telegram_bot.delete_message(
                        chat_id=int(admin_id), message_id=int(prev_mid)
                    )
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
                await telegram_bot.pin_chat_message(
                    chat_id=int(admin_id),
                    message_id=int(sent.message_id),
                    disable_notification=True,
                )
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
            if (
                user.notification_platform == "tg"
                and user.telegram_id is not None
                and telegram_bot is not None
            ):
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
        f'{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_1}{updated_player.player_name}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_2}{buyins_count}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_3}{updated_player.buyins}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_4}'
    )
    if cashier is not None:
        if (
            cashier.notification_platform == "tg"
            and cashier.telegram_id is not None
            and telegram_bot is not None
        ):
            await telegram_bot.send_message(chat_id=cashier.telegram_id, text=text)
        elif cashier.notification_platform == "vk" and cashier.vk_id is not None:
            await send_vk_message(user_id=cashier.vk_id, message=text)
    if notify_admins:
        poker_players = await PokerDataRepository(session).list_players(date=poker.date)
        player_row_ids = {int(p.player_id) for p in poker_players}
        admins = [
            u
            for u in await user_repository.list_approved()
            if u.is_admin
            and int(u.row_id) in player_row_ids
            and (cashier is None or int(u.row_id) != int(cashier.row_id))
        ]
        for admin in admins:
            if (
                admin.notification_platform == "tg"
                and admin.telegram_id is not None
                and telegram_bot is not None
            ):
                await telegram_bot.send_message(chat_id=admin.telegram_id, text=text)
            elif admin.notification_platform == "vk" and admin.vk_id is not None:
                await send_vk_message(user_id=admin.vk_id, message=text)

    player_user = await user_repository.get_by_row_id(int(updated_player.player_id))
    if player_user is not None and player_user.notification_platform is not None:
        player_text = f'{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_02_PART_1}{buyins_count}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_02_PART_2}{updated_player.buyins}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_02_PART_3}'
        if (
            player_user.notification_platform == "tg"
            and player_user.telegram_id is not None
            and telegram_bot is not None
        ):
            await telegram_bot.send_message(chat_id=player_user.telegram_id, text=player_text)
        elif player_user.notification_platform == "vk" and player_user.vk_id is not None:
            await send_vk_message(user_id=player_user.vk_id, message=player_text)


async def _notify_admins_about_removed_player(
    *, session, poker_date, player_name: str, buyins: int
) -> None:
    from app.bot.telegram.runtime import telegram_bot

    user_repository = UserRepository(session)
    players = await PokerDataRepository(session).list_players(date=poker_date)
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await user_repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
    text = f'{InlineText.NOTIFY_ADMINS_ABOUT_REMOVED_PLAYER_TEXT_01_PART_1}{player_name}{InlineText.NOTIFY_ADMINS_ABOUT_REMOVED_PLAYER_TEXT_01_PART_2}{int(buyins)}'
    for user in admins:
        if (
            user.notification_platform == "tg"
            and user.telegram_id is not None
            and telegram_bot is not None
        ):
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
        await send_vk_message(
            user_id=user.vk_id,
            message=Text.user.ROOM_REMOVED_BY_ADMIN.value,
            keyboard=main_keyboard,
        )


async def _notify_user_unbanned_for_room(*, user) -> None:
    from app.bot.telegram.runtime import telegram_bot

    if (
        user.notification_platform == "tg"
        and user.telegram_id is not None
        and telegram_bot is not None
    ):
        await telegram_bot.send_message(
            chat_id=user.telegram_id, text=Text.user.ROOM_UNBANNED_BY_ADMIN.value
        )
    elif user.notification_platform == "vk" and user.vk_id is not None:
        await send_vk_message(user_id=user.vk_id, message=Text.user.ROOM_UNBANNED_BY_ADMIN.value)


async def _clear_event_inline_keyboard_if_possible(
    *, peer_id: int | None, conversation_message_id: int | None
) -> None:
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
        f'{Text.admin.APPROVE_ACTION.value}{InlineText.PROCESS_VK_APPROVE_TEXT_01_PART_1}{approved_user.row_id}{InlineText.PROCESS_VK_APPROVE_TEXT_01_PART_2}{approved_user.name}{InlineText.PROCESS_VK_APPROVE_TEXT_01_PART_3}{approved_user.telegram_id}{InlineText.PROCESS_VK_APPROVE_TEXT_01_PART_4}{approved_user.vk_id}'
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
        f'{Text.admin.CORRECT_ACTION.value}{InlineText.PROCESS_VK_CORRECT_TEXT_01_PART_1}{corrected_user.row_id}{InlineText.PROCESS_VK_CORRECT_TEXT_01_PART_2}{corrected_user.name}{InlineText.PROCESS_VK_CORRECT_TEXT_01_PART_3}{corrected_user.telegram_id}{InlineText.PROCESS_VK_CORRECT_TEXT_01_PART_4}{corrected_user.vk_id}'
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
        f'{Text.admin.LINK_SUCCESS.value}{InlineText.PROCESS_VK_LINK_TEXT_01_PART_1}{linked_user.row_id}{InlineText.PROCESS_VK_LINK_TEXT_01_PART_2}{linked_user.name}{InlineText.PROCESS_VK_LINK_TEXT_01_PART_3}{linked_user.telegram_id}{InlineText.PROCESS_VK_LINK_TEXT_01_PART_4}{linked_user.vk_id}'
    )
