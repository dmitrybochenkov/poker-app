from aiogram.types import CallbackQuery, Message
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
        await callback.answer("Некорректные данные.", show_alert=True)
        return
    action = parts[1]
    try:
        receipt_row_id = int(parts[2])
    except Exception:
        await callback.answer("Некорректные данные.", show_alert=True)
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
            await callback.answer("Квитанция не найдена.", show_alert=True)
            return
        unpaid = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
        selected = TG_MANUAL_RECEIPT_SELECTIONS.setdefault(state_key, set())

        if action == "toggle":
            if len(parts) < 5:
                await callback.answer("Некорректные данные.", show_alert=True)
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
            await callback.answer("Обновлено")
            return

        if action == "page":
            if len(parts) < 4:
                await callback.answer("Некорректные данные.", show_alert=True)
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
            await callback.answer("Страница")
            return

        if action == "cancel":
            TG_MANUAL_RECEIPT_SELECTIONS.pop(state_key, None)
            await _safe_callback_edit_text(
                callback,
                f"🧾 Квитанция #{receipt_row_id}\nОтменено. Без изменений.",
                reply_markup=None,
            )
            await callback.answer("Отменено")
            return

        if action != "done":
            await callback.answer("Некорректное действие.", show_alert=True)
            return

        chosen = [bet for bet in unpaid if int(bet.row_id) in selected]
        if not chosen:
            await callback.answer("Выбери хотя бы одну ставку.", show_alert=True)
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
            f"{(bet.date.strftime('%d.%m.%Y') if bet.date else '—')} - {int(bet.amount_kopecks) // 100} ₽"
            for bet in chosen
        )
        remaining_lines = "\n".join(
            f"{(bet.date.strftime('%d.%m.%Y') if bet.date else '—')} - {int(bet.amount_kopecks) // 100} ₽"
            for bet in remaining
        )
        owner = await user_repo.get_by_row_id(int(receipt.user_row_id))
        user_message = f"Оплата принята. Закрыто ставок: {len(chosen)}. " + (
            "Остаток долга: 0 ₽."
            if remaining_kopecks == 0
            else f"Остаток долга:\n{remaining_lines}"
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
                f"🧾 Решение по квитанции #{receipt_row_id}\n"
                f"Оплата принята.\n"
                f"Закрытые ставки:\n{closed_lines}\n"
                f"Закрыто ставок: {len(chosen)}\n"
                f"Остаток долга: {_format_rub_from_kopecks(int(remaining_kopecks))} ₽"
            ),
            reply_markup=None,
        )
    await callback.answer("Готово")
