import logging
from datetime import date

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
    poker_room_admin_status_keyboard,
)
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .poker_helpers import _build_user_chips_text

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
                    reply_markup=tg_main_dynamic_keyboard(
                        is_admin=False,
                        has_active_poker=False,
                        has_active_poll=False,
                    ),
                )
            elif user.notification_platform == "vk" and user.vk_id is not None:
                await send_vk_message(
                    user_id=user.vk_id,
                    message=text,
                    keyboard=vk_main_dynamic_keyboard(
                        is_admin=False,
                        has_active_poker=False,
                        has_active_poll=False,
                    ),
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
