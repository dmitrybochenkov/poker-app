from aiogram.types import CallbackQuery, Message

from app.bot.shared.texts.inline.shared import formatting as FormattingText
from app.bot.shared.texts.inline.telegram.admin import bets as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    bet_receipt_manual_keyboard,
)
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import betting_keyboard as vk_betting_keyboard
from app.db.repositories.bet_payment_receipt_repository import BetPaymentReceiptRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.google_backup import backup_tables_to_google

from .common import (
    TG_MANUAL_RECEIPT_SELECTIONS,
    _clear_inline_keyboard,
    _ensure_tg_admin_callback,
    _ensure_tg_admin_message,
    _format_rub_from_kopecks,
    _safe_callback_edit_reply_markup,
    _safe_callback_edit_text,
    _start_betting_flow,
    logger,
)


async def start_betting(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
    await message.answer(await _start_betting_flow(admin_tg_id=message.from_user.id))


async def start_betting_inline(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return
    result_text = await _start_betting_flow(admin_tg_id=callback.from_user.id)
    await callback.answer(result_text, show_alert=True)
    await _clear_inline_keyboard(callback)
    if callback.message is not None:
        try:
            await callback.message.delete()
        except Exception:
            pass


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
        user_repo = UserRepository(session)
        receipt = await receipt_repo.get_by_row_id(row_id=int(receipt_row_id))
        if receipt is None:
            await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_03, show_alert=True)
            return
        unpaid = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
        selected = TG_MANUAL_RECEIPT_SELECTIONS.setdefault(state_key, set())

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
        await bet_repo.mark_paid(bets=chosen)
        receipt.status = "accepted_manual"
        await session.commit()
        if receipt.status.startswith("accepted"):
            try:
                await backup_tables_to_google(session=session)
            except Exception:
                logger.exception("Failed to sync Google backup after manual receipt decision")
        remaining = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
        remaining_kopecks = sum(int(item.amount_kopecks) for item in remaining)
        closed_lines = "\n".join(
            f'{(bet.date.strftime('%d.%m.%Y') if bet.date else FormattingText.NOT_AVAILABLE)}{InlineText.BET_RECEIPT_MANUAL_CALLBACK_MARKER_01_PART_2}{int(bet.amount_kopecks) // 100}{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_15_PART_5}'
            for bet in chosen
        )
        remaining_lines = "\n".join(
            f'{(bet.date.strftime('%d.%m.%Y') if bet.date else FormattingText.NOT_AVAILABLE)}{InlineText.BET_RECEIPT_MANUAL_CALLBACK_MARKER_01_PART_2}{int(bet.amount_kopecks) // 100}{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_15_PART_5}'
            for bet in remaining
        )
        owner = await user_repo.get_by_row_id(int(receipt.user_row_id))
        user_message = f'{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_12_PART_1}{len(chosen)}{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_12_PART_2}' + (
            InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_13
            if remaining_kopecks == 0
            else f'{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_14_PART_1}{remaining_lines}'
        )
        from app.bot.telegram.runtime import telegram_bot

        if (
            owner is not None
            and owner.notification_platform == "tg"
            and owner.telegram_id is not None
            and telegram_bot is not None
        ):
            await telegram_bot.send_message(chat_id=int(owner.telegram_id), text=user_message)
        elif owner is not None and owner.notification_platform == "vk" and owner.vk_id is not None:
            await send_vk_message(
                user_id=int(owner.vk_id), message=user_message, keyboard=vk_betting_keyboard
            )
        TG_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)

    if callback.message is not None:
        await _safe_callback_edit_text(
            callback,
            (
                f'{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_15_PART_1}{receipt_row_id}{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_15_PART_2}{closed_lines}{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_15_PART_3}{len(chosen)}{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_15_PART_4}{_format_rub_from_kopecks(int(remaining_kopecks))}{InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_15_PART_5}'
            ),
            reply_markup=None,
        )
    await callback.answer(InlineText.BET_RECEIPT_MANUAL_CALLBACK_TEXT_16)
