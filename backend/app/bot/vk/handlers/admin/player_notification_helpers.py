import logging

from app.bot.shared.texts.inline.vk.admin import common as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import main_dynamic_keyboard as tg_main_dynamic_keyboard
from app.bot.telegram.keyboards import main_keyboard as tg_main_keyboard
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import main_dynamic_keyboard as vk_main_dynamic_keyboard
from app.bot.vk.keyboards import main_keyboard
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .poker_helpers import _build_user_chips_text

logger = logging.getLogger(__name__)


async def _send_preferred_notification(*, user, text: str, flow: str) -> None:
    from app.bot.telegram.runtime import telegram_bot

    if user.notification_platform == "tg" and user.telegram_id is not None:
        if telegram_bot is None:
            return
        try:
            await telegram_bot.send_message(chat_id=user.telegram_id, text=text)
        except Exception:
            logger.exception(
                "%s delivery failed: platform=tg recipient_id=%s",
                flow,
                user.telegram_id,
            )
    elif user.notification_platform == "vk" and user.vk_id is not None:
        try:
            await send_vk_message(user_id=user.vk_id, message=text)
        except Exception:
            logger.exception(
                "%s delivery failed: platform=vk recipient_id=%s",
                flow,
                user.vk_id,
            )

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
    user_repository = UserRepository(session)
    cashier = None
    if poker.cashier_id is not None:
        cashier = await user_repository.get_by_row_id(int(poker.cashier_id))

    text = (
        f'{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_1}{updated_player.player_name}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_2}{buyins_count}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_3}{updated_player.buyins}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_4}'
    )
    if cashier is not None:
        await _send_preferred_notification(user=cashier, text=text, flow="Buyin cashier")
    if notify_admins:
        poker_players = await PokerDataRepository(session).list_players(poker_id=int(poker.row_id))
        player_row_ids = {int(p.player_id) for p in poker_players}
        admins = [
            u
            for u in await user_repository.list_approved()
            if u.is_admin
            and int(u.row_id) in player_row_ids
            and (cashier is None or int(u.row_id) != int(cashier.row_id))
        ]
        for admin in admins:
            await _send_preferred_notification(user=admin, text=text, flow="Buyin admin")

    player_user = await user_repository.get_by_row_id(int(updated_player.player_id))
    if player_user is not None and player_user.notification_platform is not None:
        player_text = f'{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_02_PART_1}{buyins_count}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_02_PART_2}{updated_player.buyins}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_02_PART_3}'
        await _send_preferred_notification(
            user=player_user, text=player_text, flow="Buyin player"
        )

async def _notify_admins_about_removed_player(
    *, session, poker_date, player_name: str, buyins: int
) -> None:
    user_repository = UserRepository(session)
    players = await PokerDataRepository(session).list_players_for_date(date=poker_date)
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await user_repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
    text = f'{InlineText.NOTIFY_ADMINS_ABOUT_REMOVED_PLAYER_TEXT_01_PART_1}{player_name}{InlineText.NOTIFY_ADMINS_ABOUT_REMOVED_PLAYER_TEXT_01_PART_2}{int(buyins)}'
    for user in admins:
        await _send_preferred_notification(user=user, text=text, flow="Removed player admin")

async def _notify_user_removed_from_room(*, user) -> None:
    from app.bot.telegram.runtime import telegram_bot

    if user.telegram_id is not None and telegram_bot is not None:
        try:
            await telegram_bot.send_message(
                chat_id=user.telegram_id,
                text=Text.user.ROOM_REMOVED_BY_ADMIN.value,
                reply_markup=tg_main_keyboard,
            )
        except Exception:
            logger.exception(
                "Removed player delivery failed: platform=tg recipient_id=%s",
                user.telegram_id,
            )
    if user.vk_id is not None:
        try:
            await send_vk_message(
                user_id=user.vk_id,
                message=Text.user.ROOM_REMOVED_BY_ADMIN.value,
                keyboard=main_keyboard,
            )
        except Exception:
            logger.exception(
                "Removed player delivery failed: platform=vk recipient_id=%s",
                user.vk_id,
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
