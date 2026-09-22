from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

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
from app.bot.shared.texts.inline.telegram.admin import registrations as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    link_candidates_keyboard,
    link_candidates_page_keyboard,
)
from app.bot.telegram.notifications import notify_user_about_approval
from app.bot.telegram.states import RegistrationState
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    _clear_inline_keyboard,
    _ensure_tg_admin_callback,
    _ensure_tg_admin_message,
    _safe_callback_edit_reply_markup,
    _safe_callback_edit_text,
)


async def approve_registration_callback(callback: CallbackQuery) -> None:
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

        use_case = ApproveUserUseCase(repository)
        try:
            user = await use_case.execute(row_id=row_id)
        except UserNotFoundError:
            await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
            return

    if user.telegram_id is not None:
        await notify_user_about_approval(telegram_id=user.telegram_id, approved=True)

    if callback.message is not None:
        await _safe_callback_edit_text(
            callback,
            f'{InlineText.APPROVE_REGISTRATION_CALLBACK_TEXT_01_PART_1}{row_id}{InlineText.APPROVE_REGISTRATION_CALLBACK_TEXT_01_PART_2}{user.name}{InlineText.APPROVE_REGISTRATION_CALLBACK_TEXT_01_PART_3}{user.telegram_id}',
        )
    await callback.answer(Text.admin.APPROVE_ACTION.value)


async def correct_registration_callback(callback: CallbackQuery, state: FSMContext) -> None:
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

        user = await repository.get_by_row_id(row_id)
        if user is None:
            await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
            return
        if user.is_approved:
            await callback.answer(Text.admin.REQUEST_ALREADY_APPROVED.value, show_alert=True)
            return

    review_chat_id = callback.message.chat.id if callback.message is not None else None
    review_message_id = callback.message.message_id if callback.message is not None else None

    await state.set_state(RegistrationState.waiting_for_corrected_name)
    await state.update_data(
        pending_row_id=row_id,
        review_chat_id=review_chat_id,
        review_message_id=review_message_id,
    )
    if callback.message is None:
        await callback.answer(Text.admin.CORRECT_PROMPT.value, show_alert=True)
        return

    await callback.answer(Text.admin.CORRECT_FLOW_STARTED.value)
    await callback.message.answer(f'{Text.admin.CORRECT_PROMPT.value}{InlineText.CORRECT_REGISTRATION_CALLBACK_TEXT_01_PART_1}{user.name}')


async def finish_correct_user(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        await message.answer(Text.admin.EMPTY_CORRECTED_NAME.value)
        return

    corrected_name = " ".join(message.text.split())
    if not corrected_name:
        await message.answer(Text.admin.EMPTY_CORRECTED_NAME.value)
        return

    data = await state.get_data()
    pending_row_id = data.get("pending_row_id")
    review_chat_id = data.get("review_chat_id")
    review_message_id = data.get("review_message_id")

    if pending_row_id is None:
        await state.clear()
        await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
        return

    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            await state.clear()
            return
        repository = UserRepository(session)

        use_case = CorrectUserUseCase(repository)
        try:
            user = await use_case.execute(
                row_id=pending_row_id,
                corrected_name=corrected_name,
            )
        except UserNotFoundError:
            await state.clear()
            await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
            return
        except UserNameRequiredError:
            await message.answer(Text.admin.EMPTY_CORRECTED_NAME.value)
            return
        except UserAlreadyApprovedError:
            await state.clear()
            await message.answer(Text.admin.REQUEST_ALREADY_APPROVED.value)
            return

    if user.telegram_id is not None:
        await notify_user_about_approval(telegram_id=user.telegram_id, approved=True)

    if review_chat_id is not None and review_message_id is not None:
        from app.bot.telegram.runtime import telegram_bot

        if telegram_bot is not None:
            await telegram_bot.edit_message_text(
                chat_id=review_chat_id,
                message_id=review_message_id,
                text=(
                    f'{Text.admin.CORRECT_ACTION.value}{InlineText.FINISH_CORRECT_USER_TEXT_01_PART_1}{user.row_id}{InlineText.FINISH_CORRECT_USER_TEXT_01_PART_2}{user.name}{InlineText.FINISH_CORRECT_USER_TEXT_01_PART_3}{user.telegram_id}{InlineText.FINISH_CORRECT_USER_TEXT_01_PART_4}{user.vk_id}'
                ),
            )

    await state.clear()
    await message.answer(
        f'{Text.admin.CORRECT_ACTION.value}{InlineText.FINISH_CORRECT_USER_TEXT_02_PART_1}{user.row_id}{InlineText.FINISH_CORRECT_USER_TEXT_02_PART_2}{user.name}{InlineText.FINISH_CORRECT_USER_TEXT_02_PART_3}{user.telegram_id}{InlineText.FINISH_CORRECT_USER_TEXT_02_PART_4}{user.vk_id}',
    )


async def reject_registration_callback(callback: CallbackQuery) -> None:
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

        user = await repository.get_by_row_id(row_id)
        if user is None:
            await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
            return

        user_telegram_id = user.telegram_id
        user_name = user.name

        use_case = RejectUserUseCase(repository)
        try:
            await use_case.execute(row_id=row_id)
        except UserNotFoundError:
            await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
            return
        except UserAlreadyApprovedError:
            await callback.answer(Text.admin.REQUEST_ALREADY_APPROVED.value, show_alert=True)
            return

    if user_telegram_id is not None:
        await notify_user_about_approval(telegram_id=user_telegram_id, approved=False)

    if callback.message is not None:
        await _safe_callback_edit_text(
            callback,
            f'{InlineText.REJECT_REGISTRATION_CALLBACK_TEXT_01_PART_1}{row_id}{InlineText.REJECT_REGISTRATION_CALLBACK_TEXT_01_PART_2}{user_name}{InlineText.REJECT_REGISTRATION_CALLBACK_TEXT_01_PART_3}{user_telegram_id}',
        )
    await callback.answer(Text.admin.REJECT_ACTION.value)


async def link_registration_callback(callback: CallbackQuery) -> None:
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

        approved_users = await repository.list_approved()

    await callback.answer(Text.admin.LINK_ACTION.value)
    if callback.message is not None:
        await callback.message.answer(Text.admin.LINK_PROMPT.value)
        await callback.message.answer(
            Text.admin.LINK_CHOICES_TITLE.value,
            reply_markup=link_candidates_keyboard(
                pending_row_id=row_id,
                users=approved_users,
            ),
        )


async def choose_link_target_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return

    _, pending_row_id_text, existing_row_id_text = callback.data.split(":", 2)
    await _clear_inline_keyboard(callback)
    pending_row_id = int(pending_row_id_text)
    existing_row_id = int(existing_row_id_text)

    async with SessionFactory() as session:
        repository = UserRepository(session)
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return

        use_case = LinkPendingUserUseCase(repository)
        try:
            user = await use_case.execute(
                pending_row_id=pending_row_id,
                existing_row_id=existing_row_id,
            )
        except UserNotFoundError:
            await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
            return
        except UserLinkConflictError:
            await callback.answer(Text.admin.LINK_CONFLICT.value, show_alert=True)
            return

    if callback.message is not None:
        await _safe_callback_edit_text(
            callback,
            f'{Text.admin.LINK_SUCCESS.value}{InlineText.CHOOSE_LINK_TARGET_CALLBACK_TEXT_01_PART_1}{pending_row_id}{InlineText.CHOOSE_LINK_TARGET_CALLBACK_TEXT_01_PART_2}{user.row_id}{InlineText.CHOOSE_LINK_TARGET_CALLBACK_TEXT_01_PART_3}{user.name}{InlineText.CHOOSE_LINK_TARGET_CALLBACK_TEXT_01_PART_4}{user.telegram_id}{InlineText.CHOOSE_LINK_TARGET_CALLBACK_TEXT_01_PART_5}{user.vk_id}',
        )
    await callback.answer(Text.admin.LINK_SUCCESS.value)


async def choose_link_target_page_callback(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
        return
    _, pending_row_id_text, page_text = callback.data.split(":", 2)
    pending_row_id = int(pending_row_id_text)
    page = int(page_text)
    async with SessionFactory() as session:
        repository = UserRepository(session)
        approved_users = await repository.list_approved()
    await _safe_callback_edit_reply_markup(
        callback,
        reply_markup=link_candidates_page_keyboard(
            pending_row_id=pending_row_id,
            users=approved_users,
            page=page,
        ),
    )
    await callback.answer()
