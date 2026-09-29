from aiogram.types import CallbackQuery, Message

from app.bot.shared.identity import resolve_telegram_user_id
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    admin_betting_keyboard,
    admin_main_keyboard,
    tournament_close_keyboard,
    tournament_confirm_keyboard,
)
from app.db.session import SessionFactory
from app.services.close_betting_tournament_flow import (
    TODAY,
    build_close_tournament_use_case,
    format_preview,
)

from .common import _ensure_tg_admin_message


async def _authorized(message: Message) -> bool:
    if message.from_user is None:
        return False
    async with SessionFactory() as session:
        return await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        )


async def tournament_menu(message: Message):
    if not await _authorized(message):
        return
    await message.answer(Text.admin.TOURNAMENT_MENU.value, reply_markup=admin_betting_keyboard)


async def tournament_open(message: Message):
    if not await _authorized(message):
        return
    await message.answer(
        Text.admin.TOURNAMENT_OPEN_PLACEHOLDER.value, reply_markup=admin_betting_keyboard
    )


async def tournament_back(message: Message):
    if not await _authorized(message):
        return
    await message.answer(Text.admin.ADMIN_PANEL.value, reply_markup=admin_main_keyboard)


async def tournament_close(message: Message):
    async with SessionFactory() as session:
        actor = await resolve_telegram_user_id(session=session, telegram_id=message.from_user.id)
        try:
            items = await build_close_tournament_use_case(session).list_eligible(
                actor_user_id=actor or 0, today=TODAY()
            )
        except PermissionError:
            await message.answer(Text.admin.NO_RIGHTS.value)
            return
    await message.answer(
        Text.admin.TOURNAMENT_CLOSE_CHOOSE.value
        if items
        else Text.admin.TOURNAMENT_CLOSE_EMPTY.value,
        reply_markup=tournament_close_keyboard(tournaments=items)
        if items
        else admin_betting_keyboard,
    )


async def tournament_close_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if parts[1] == "cancel":
        await callback.message.edit_text(Text.admin.TOURNAMENT_CANCELED.value)
        await callback.answer()
        return
    tournament_id = int(parts[2])
    async with SessionFactory() as session:
        actor = await resolve_telegram_user_id(session=session, telegram_id=callback.from_user.id)
        use_case = build_close_tournament_use_case(session)
        try:
            if parts[1] == "preview":
                tournament, result = await use_case.preview(
                    actor_user_id=actor or 0, tournament_id=tournament_id, today=TODAY()
                )
            else:
                tournament, result = await use_case.confirm(
                    actor_user_id=actor or 0, tournament_id=tournament_id, today=TODAY()
                )
        except (PermissionError, ValueError):
            await callback.answer(Text.admin.TOURNAMENT_ALREADY_FINALIZED.value, show_alert=True)
            return
    await callback.message.edit_text(
        format_preview(tournament, result),
        reply_markup=tournament_confirm_keyboard(tournament_id=tournament_id)
        if parts[1] == "preview"
        else None,
    )
    await callback.answer(Text.admin.TOURNAMENT_FINALIZED.value if parts[1] == "confirm" else "")
