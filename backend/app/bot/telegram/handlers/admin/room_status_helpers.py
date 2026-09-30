from app.bot.shared.chips_runtime import TG_ADMIN_ROOM_STATUS_MSG_IDS, VK_ADMIN_ROOM_STATUS_MSG_IDS
from app.bot.shared.texts.inline.telegram.admin import common as InlineText
from app.bot.telegram.keyboards import poker_room_admin_status_keyboard
from app.bot.vk.api import delete_vk_message_by_id, pin_vk_message_by_id, send_vk_message_with_id
from app.bot.vk.keyboards import (
    poker_room_admin_status_keyboard as vk_poker_room_admin_status_keyboard,
)
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository

async def _refresh_admin_room_status(*, session) -> None:
    from app.bot.telegram.runtime import telegram_bot

    user_repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    poker_data_repository = PokerDataRepository(session)
    active = await poker_repository.get_started()
    if active is None:
        return
    poker, _ = active
    players = await poker_data_repository.list_players(poker_id=int(poker.row_id))
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
                reply_markup=poker_room_admin_status_keyboard(
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
