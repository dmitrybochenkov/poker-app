from fastapi.responses import PlainTextResponse

from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.vk.admin import bets as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import betting_keyboard as tg_betting_keyboard
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
)
from app.bot.vk.keyboards import (
    bet_receipt_manual_keyboard,
    bet_receipt_review_keyboard,
    betting_keyboard,
)
from app.db.repositories.bet_payment_receipt_repository import BetPaymentReceiptRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.bet_payment import (
    change_receipt_intent,
    confirm_receipt_payment,
    reject_receipt_payment,
)
from app.services.google_backup import backup_tables_to_google

from .common import (
    HANDLER_UNMATCHED,
    VK_MANUAL_RECEIPT_SELECTIONS,
    _clear_event_inline_keyboard_if_possible,
    logger,
)
from .poker_helpers import _format_rub_from_kopecks


async def handle_bet_receipt_actions_event(
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
        "bet_receipt_confirm",
        "bet_receipt_change",
        "bet_receipt_reject",
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
            receipt = await receipt_repo.get_by_row_id(row_id=int(receipt_row_id))
            if receipt is None:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=InlineText.EVENT_0_02_TEXT_01,
                )
                return PlainTextResponse("ok")
            if str(receipt.status).startswith(("accepted", "rejected")):
                VK_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=InlineText.EVENT_0_02_TEXT_ALREADY_PROCESSED,
                )
                return PlainTextResponse("ok")
            unpaid = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
            selected = VK_MANUAL_RECEIPT_SELECTIONS.setdefault(state_key, set())

            if action == "bet_receipt_confirm":
                result = await confirm_receipt_payment(session=session, receipt_row_id=receipt_row_id)
                owner = await UserRepository(session).get_by_row_id(int(receipt.user_row_id))
                await session.commit()
                VK_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
                if result.ok:
                    try:
                        await backup_tables_to_google(session=session)
                    except Exception:
                        logger.exception("Failed to sync Google backup after manual VK receipt decision")
                    user_message = Text.user.BETTING_PAY_MATCHED.value.format(
                        count=result.closed_count,
                        debt_rub=_format_rub_from_kopecks(result.debt_kopecks or 0),
                    )
                    from app.bot.telegram.runtime import telegram_bot
                    if owner is not None and owner.notification_platform == "tg" and owner.telegram_id and telegram_bot:
                        await telegram_bot.send_message(chat_id=int(owner.telegram_id), text=user_message, reply_markup=tg_betting_keyboard)
                    elif owner is not None and owner.notification_platform == "vk" and owner.vk_id:
                        await send_vk_message(user_id=int(owner.vk_id), message=user_message, keyboard=betting_keyboard)
                await send_vk_message_event_answer(event_id=event_id, user_id=admin_user_id, peer_id=peer_id, text=result.message)
                return PlainTextResponse("ok")

            if action == "bet_receipt_reject":
                result = await reject_receipt_payment(session=session, receipt_row_id=receipt_row_id)
                await session.commit()
                VK_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
                await send_vk_message_event_answer(event_id=event_id, user_id=admin_user_id, peer_id=peer_id, text=result.message)
                return PlainTextResponse("ok")

            if action == "bet_receipt_change":
                intended = await receipt_repo.list_intended_bet_ids(receipt_row_id=receipt_row_id)
                VK_MANUAL_RECEIPT_SELECTIONS[state_key] = set(intended)
                await send_vk_message(user_id=admin_user_id, message="Измени выбранные ставки:", keyboard=bet_receipt_manual_keyboard(
                    receipt_row_id=receipt_row_id, bets=unpaid, selected_ids=intended, page=0))
                return PlainTextResponse("ok")

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

            changed = await change_receipt_intent(
                session=session,
                receipt_row_id=receipt_row_id,
                intended_bet_ids=[int(bet.row_id) for bet in chosen],
            )
            await session.commit()
            VK_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
        await send_vk_message_event_answer(event_id=event_id, user_id=admin_user_id, peer_id=peer_id, text=changed.message)
        await send_vk_message(user_id=admin_user_id, message="Выбор сохранён. Проверь и подтверди оплату.", keyboard=bet_receipt_review_keyboard(receipt_row_id=receipt_row_id))
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
