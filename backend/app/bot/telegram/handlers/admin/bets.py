from aiogram.types import CallbackQuery

from app.bot.shared.texts.inline.telegram.admin import bets as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    bet_receipt_manual_keyboard,
    bet_receipt_review_keyboard,
)
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import betting_keyboard as vk_betting_keyboard
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
    TG_MANUAL_RECEIPT_SELECTIONS,
    _ensure_tg_admin_callback,
    _safe_callback_edit_reply_markup,
    _safe_callback_edit_text,
    logger,
)
from .poker_helpers import _format_rub_from_kopecks


async def bet_receipt_manual_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_01, show_alert=True)
        return
    action = parts[1]
    try:
        receipt_row_id = int(parts[2])
    except Exception:
        await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_02, show_alert=True)
        return
    admin_id = int(callback.from_user.id)
    state_key = (admin_id, int(receipt_row_id))

    async with SessionFactory() as session:
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return
        receipt_repo = BetPaymentReceiptRepository(session)
        bet_repo = BetRepository(session)
        receipt = await receipt_repo.get_by_row_id(row_id=int(receipt_row_id))
        if receipt is None:
            await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_03, show_alert=True)
            return
        if str(receipt.status).startswith(("accepted", "rejected")):
            TG_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
            await callback.answer(
                InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_ALREADY_PROCESSED,
                show_alert=True,
            )
            return
        unpaid = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
        selected = TG_MANUAL_RECEIPT_SELECTIONS.setdefault(state_key, set())

        if action == "confirm":
            result = await confirm_receipt_payment(session=session, receipt_row_id=receipt_row_id)
            owner = await UserRepository(session).get_by_row_id(int(receipt.user_row_id))
            await session.commit()
            TG_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
            if result.ok:
                try:
                    await backup_tables_to_google(session=session)
                except Exception:
                    logger.exception("Failed to sync Google backup after manual TG receipt decision")
                user_message = Text.user.BETTING_PAY_MATCHED.value.format(
                    count=result.closed_count,
                    debt_rub=_format_rub_from_kopecks(result.debt_kopecks or 0),
                )
                from app.bot.telegram.runtime import telegram_bot
                if owner is not None and owner.notification_platform == "tg" and owner.telegram_id and telegram_bot:
                    await telegram_bot.send_message(chat_id=int(owner.telegram_id), text=user_message)
                elif owner is not None and owner.notification_platform == "vk" and owner.vk_id:
                    await send_vk_message(user_id=int(owner.vk_id), message=user_message, keyboard=vk_betting_keyboard)
            await callback.answer(result.message, show_alert=not result.ok)
            return

        if action == "reject":
            result = await reject_receipt_payment(session=session, receipt_row_id=receipt_row_id)
            await session.commit()
            TG_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
            await _safe_callback_edit_text(callback, result.message, reply_markup=None)
            await callback.answer()
            return

        if action == "change":
            intended = await receipt_repo.list_intended_bet_ids(receipt_row_id=receipt_row_id)
            TG_MANUAL_RECEIPT_SELECTIONS[state_key] = set(intended)
            await _safe_callback_edit_reply_markup(callback, bet_receipt_manual_keyboard(
                receipt_row_id=receipt_row_id, bets=unpaid, selected_ids=intended, page=0))
            await callback.answer()
            return

        if action == "toggle":
            if len(parts) < 5:
                await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_04, show_alert=True)
                return
            bet_row_id = int(parts[3])
            page = int(parts[4])
            if bet_row_id in selected:
                selected.remove(bet_row_id)
            else:
                selected.add(bet_row_id)
            await _safe_callback_edit_reply_markup(
                callback,
                bet_receipt_manual_keyboard(
                    receipt_row_id=int(receipt_row_id),
                    bets=unpaid,
                    selected_ids=sorted(selected),
                    page=page,
                ),
            )
            await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_05)
            return

        if action == "page":
            if len(parts) < 4:
                await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_06, show_alert=True)
                return
            page = int(parts[3])
            await _safe_callback_edit_reply_markup(
                callback,
                bet_receipt_manual_keyboard(
                    receipt_row_id=int(receipt_row_id),
                    bets=unpaid,
                    selected_ids=sorted(selected),
                    page=page,
                ),
            )
            await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_07)
            return

        if action == "cancel":
            TG_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
            await _safe_callback_edit_text(
                callback,
                f'{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_08_PART_1}{receipt_row_id}{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_08_PART_2}',
                reply_markup=None,
            )
            await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_09)
            return

        if action != "done":
            await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_10, show_alert=True)
            return

        chosen = [bet for bet in unpaid if int(bet.row_id) in selected]
        if not chosen:
            await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_11, show_alert=True)
            return
        changed = await change_receipt_intent(
            session=session,
            receipt_row_id=receipt_row_id,
            intended_bet_ids=[int(bet.row_id) for bet in chosen],
        )
        await session.commit()
        TG_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
        await _safe_callback_edit_text(
            callback,
            "Выбор сохранён. Проверь и подтверди оплату.",
            reply_markup=bet_receipt_review_keyboard(receipt_row_id=receipt_row_id),
        )
        await callback.answer(changed.message, show_alert=not changed.ok)
