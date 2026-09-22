from aiogram.types import CallbackQuery, Message

from app.application.exceptions import (
    UserNotFoundError,
)
from app.application.use_cases.user.make_admin import MakeAdminUseCase
from app.bot.shared.texts.inline.telegram.admin import management as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    make_admin_candidates_keyboard,
    room_admin_keyboard,
)
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    _clear_inline_keyboard,
    _ensure_tg_admin_callback,
    _ensure_tg_admin_message,
    _safe_callback_edit_text,
)


async def make_admin_menu(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return

    async with SessionFactory() as session:
        repository = UserRepository(session)
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return

        approved_users = await repository.list_approved()
        candidates = [user for user in approved_users if not user.is_admin]
        if not candidates:
            await message.answer(Text.admin.MAKE_ADMIN_EMPTY.value)
            return

    await message.answer(
        Text.admin.MAKE_ADMIN_PROMPT.value,
        reply_markup=make_admin_candidates_keyboard(users=candidates),
    )


async def make_admin_select_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return

    row_id = int(callback.data.split(":", 1)[1])
    await _clear_inline_keyboard(callback)

    async with SessionFactory() as session:
        repository = UserRepository(session)
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return

        use_case = MakeAdminUseCase(repository)
        try:
            user = await use_case.execute(row_id=row_id)
        except UserNotFoundError:
            await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
            return

    if callback.message is not None:
        await _safe_callback_edit_text(
            callback,
            f'{Text.admin.MAKE_ADMIN_SUCCESS.value}{InlineText.MAKE_ADMIN_SELECT_CALLBACK_TEXT_01_PART_1}{user.name}',
        )
    await callback.answer(Text.admin.MAKE_ADMIN_SUCCESS.value)


async def back_to_room_admin_panel(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        repository = UserRepository(session)
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
    await message.answer(InlineText.BACK_TO_ROOM_ADMIN_PANEL_TEXT_01, reply_markup=room_admin_keyboard)
