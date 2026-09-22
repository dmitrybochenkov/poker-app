from fastapi.responses import PlainTextResponse

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.chips_runtime import (
    TG_ADMIN_ROOM_STATUS_MSG_IDS,
    VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.shared import formatting as FormattingText
from app.bot.shared.texts.inline.vk.admin import bets as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import betting_keyboard as tg_betting_keyboard
from app.bot.vk.api import (
    delete_vk_message_by_id,
    send_vk_message,
    send_vk_message_event_answer,
    unpin_vk_message,
)
from app.bot.vk.keyboards import (
    bet_receipt_manual_keyboard,
    betting_keyboard,
)
from app.db.repositories.bet_payment_receipt_repository import BetPaymentReceiptRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.google_backup import backup_tables_to_google

from .common import (
    HANDLER_UNMATCHED,
    VK_MANUAL_RECEIPT_SELECTIONS,
    _clear_event_inline_keyboard_if_possible,
    _format_rub_from_kopecks,
    logger,
)


async def _event_0_02(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action in {
        "bet_receipt_toggle",
        "bet_receipt_page",
        "bet_receipt_done",
        "bet_receipt_cancel",
    }:
        receipt_row_id = callback_payload.get("receipt_row_id")
        if not isinstance(receipt_row_id, int):
            return PlainTextResponse("ok")
        state_key = (int(admin_user_id), int(receipt_row_id))
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.NO_RIGHTS.value,
                )
                return PlainTextResponse("ok")
            receipt_repo = BetPaymentReceiptRepository(session)
            bet_repo = BetRepository(session)
            user_repo = UserRepository(session)
            receipt = await receipt_repo.get_by_row_id(row_id=int(receipt_row_id))
            if receipt is None:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=InlineText.EVENT_0_02_TEXT_01,
                )
                return PlainTextResponse("ok")
            unpaid = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
            selected = VK_MANUAL_RECEIPT_SELECTIONS.setdefault(state_key, set())

            if action == "bet_receipt_toggle":
                bet_row_id = callback_payload.get("bet_row_id")
                page = callback_payload.get("page")
                if not isinstance(bet_row_id, int) or not isinstance(page, int):
                    return PlainTextResponse("ok")
                if bet_row_id in selected:
                    selected.remove(bet_row_id)
                else:
                    selected.add(bet_row_id)
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=InlineText.EVENT_0_02_TEXT_02,
                )
                await _clear_event_inline_keyboard_if_possible(
                    peer_id=peer_id, conversation_message_id=conversation_message_id
                )
                await send_vk_message(
                    user_id=admin_user_id,
                    message=f'{InlineText.EVENT_0_02_TEXT_03_PART_1}{int(receipt_row_id)}',
                    keyboard=bet_receipt_manual_keyboard(
                        receipt_row_id=int(receipt_row_id),
                        bets=unpaid,
                        selected_ids=sorted(selected),
                        page=int(page),
                    ),
                )
                return PlainTextResponse("ok")

            if action == "bet_receipt_page":
                page = callback_payload.get("page")
                if not isinstance(page, int):
                    return PlainTextResponse("ok")
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=InlineText.EVENT_0_02_TEXT_04,
                )
                await _clear_event_inline_keyboard_if_possible(
                    peer_id=peer_id, conversation_message_id=conversation_message_id
                )
                await send_vk_message(
                    user_id=admin_user_id,
                    message=f'{InlineText.EVENT_0_02_TEXT_05_PART_1}{int(receipt_row_id)}',
                    keyboard=bet_receipt_manual_keyboard(
                        receipt_row_id=int(receipt_row_id),
                        bets=unpaid,
                        selected_ids=sorted(selected),
                        page=int(page),
                    ),
                )
                return PlainTextResponse("ok")

            if action == "bet_receipt_cancel":
                VK_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=InlineText.EVENT_0_02_TEXT_06,
                )
                await _clear_event_inline_keyboard_if_possible(
                    peer_id=peer_id, conversation_message_id=conversation_message_id
                )
                await send_vk_message(
                    user_id=admin_user_id,
                    message=f'{InlineText.EVENT_0_02_TEXT_07_PART_1}{int(receipt_row_id)}{InlineText.EVENT_0_02_TEXT_07_PART_2}',
                )
                return PlainTextResponse("ok")

            chosen = [bet for bet in unpaid if int(bet.row_id) in selected]
            if not chosen:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=InlineText.EVENT_0_02_TEXT_08,
                )
                return PlainTextResponse("ok")

            await bet_repo.mark_paid(bets=chosen)
            receipt.status = "accepted_manual"
            await session.commit()
            if str(receipt.status).startswith("accepted"):
                try:
                    await backup_tables_to_google(session=session)
                except Exception:
                    logger.exception(
                        "Failed to sync Google backup after manual VK receipt decision"
                    )
            remaining = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
            remaining_kopecks = sum(int(item.amount_kopecks) for item in remaining)
            closed_lines = "\n".join(
                f'{(bet.date.strftime('%d.%m.%Y') if bet.date else FormattingText.NOT_AVAILABLE)}{InlineText._EVENT_0_02_MARKER_01_PART_2}{int(bet.amount_kopecks) // 100}{InlineText.EVENT_0_02_TEXT_13_PART_5}'
                for bet in chosen
            )
            remaining_lines = "\n".join(
                f'{(bet.date.strftime('%d.%m.%Y') if bet.date else FormattingText.NOT_AVAILABLE)}{InlineText._EVENT_0_02_MARKER_01_PART_2}{int(bet.amount_kopecks) // 100}{InlineText.EVENT_0_02_TEXT_13_PART_5}'
                for bet in remaining
            )
            owner = await user_repo.get_by_row_id(int(receipt.user_row_id))
            user_message = f'{InlineText.EVENT_0_02_TEXT_09_PART_1}{len(chosen)}{InlineText.EVENT_0_02_TEXT_09_PART_2}' + (
                InlineText.EVENT_0_02_TEXT_10
                if remaining_kopecks == 0
                else f'{InlineText.EVENT_0_02_TEXT_11_PART_1}{remaining_lines}'
            )
            from app.bot.telegram.runtime import telegram_bot

            if (
                owner is not None
                and owner.notification_platform == "tg"
                and owner.telegram_id is not None
                and telegram_bot is not None
            ):
                await telegram_bot.send_message(
                    chat_id=int(owner.telegram_id),
                    text=user_message,
                    reply_markup=tg_betting_keyboard,
                )
            elif (
                owner is not None
                and owner.notification_platform == "vk"
                and owner.vk_id is not None
            ):
                await send_vk_message(
                    user_id=int(owner.vk_id), message=user_message, keyboard=betting_keyboard
                )
            VK_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=InlineText.EVENT_0_02_TEXT_12,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=admin_user_id,
            message=(
                f'{InlineText.EVENT_0_02_TEXT_13_PART_1}{int(receipt_row_id)}{InlineText.EVENT_0_02_TEXT_13_PART_2}{closed_lines}{InlineText.EVENT_0_02_TEXT_13_PART_3}{len(chosen)}{InlineText.EVENT_0_02_TEXT_13_PART_4}{_format_rub_from_kopecks(int(remaining_kopecks))}{InlineText.EVENT_0_02_TEXT_13_PART_5}'
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_12(*, user_id, text):
    if text == Buttons.admin_room.START_BETTING.value:
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            poker_repository = PokerRepository(session)
            active = await poker_repository.get_started()
            if active is None:
                await send_vk_message(
                    user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value
                )
                return PlainTextResponse("ok")
            poker, _ = active
            if poker.is_ready_for_chips_entering:
                await send_vk_message(
                    user_id=user_id, message=Text.user.FINISH_CHIPS_NOT_READY.value
                )
                return PlainTextResponse("ok")
            if poker.is_bettable:
                await send_vk_message(
                    user_id=user_id, message=Text.admin.BETTING_ALREADY_OPEN.value
                )
                return PlainTextResponse("ok")
            await poker_repository.start_betting(poker)
            tg_user_ids = await user_repository.list_approved_tg_ids()
            vk_user_ids = await user_repository.list_approved_vk_ids()

        from app.bot.telegram.runtime import telegram_bot

        if telegram_bot is not None:
            for chat_id, message_id in list(TG_ADMIN_ROOM_STATUS_MSG_IDS.items()):
                try:
                    await telegram_bot.unpin_chat_message(
                        chat_id=int(chat_id), message_id=int(message_id)
                    )
                except Exception:
                    pass
                try:
                    await telegram_bot.delete_message(
                        chat_id=int(chat_id), message_id=int(message_id)
                    )
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
                try:
                    await telegram_bot.send_message(
                        chat_id=recipient_id,
                        text=Text.user.START_BETTING.value,
                        reply_markup=tg_betting_keyboard,
                    )
                except Exception:
                    logger.exception(
                        "Failed to announce betting start to Telegram user %s", recipient_id
                    )
        for recipient_id in vk_user_ids:
            try:
                await send_vk_message(
                    user_id=recipient_id,
                    message=Text.user.START_BETTING.value,
                    keyboard=betting_keyboard,
                )
            except Exception:
                logger.exception("Failed to announce betting start to VK user %s", recipient_id)

        await send_vk_message(user_id=user_id, message=Text.admin.BETTING_START_SUCCESS.value)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
