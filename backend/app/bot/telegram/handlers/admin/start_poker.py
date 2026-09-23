from aiogram.types import CallbackQuery, Message

from app.application.use_cases.poker.start_poker import (
    PokerAlreadyStartedError,
    PokerParamsNotFoundError,
    StartPokerNotAuthorizedError,
    StartPokerUseCase,
)
from app.bot.shared.texts.inline.telegram.admin import poker as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.shared.identity import resolve_telegram_user_id
from app.bot.telegram.keyboards import poker_params_keyboard
from app.db.session import SessionFactory
from app.services.start_poker_flow import execute_start_poker

from .common import (
    _clear_inline_keyboard,
    _ensure_tg_admin_message,
    _safe_callback_edit_text,
)


async def start_poker_menu(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return

    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
        can_start, params = await StartPokerUseCase(session).get_start_data()
        if not can_start:
            await message.answer(Text.admin.POKER_STARTED.value)
            return
        if not params:
            await message.answer(Text.admin.POKER_PARAMS_EMPTY.value)
            return

    await message.answer(
        "\n\n".join(
            [
                Text.admin.POKER_PARAMS_CHOOSE.value,
                *[
                    (
                        f"{InlineText.START_POKER_MENU_TEXT_01_PART_1}{p.row_id}"
                        f"{InlineText.START_POKER_MENU_TEXT_01_PART_2}{p.buyin_size_chips}"
                        f"{InlineText.START_POKER_MENU_TEXT_01_PART_3}"
                        f"{int(p.buyin_size_kopecks) // 100}"
                        f"{InlineText.START_POKER_MENU_TEXT_01_PART_4}{p.bb_size_chips}"
                        f"{InlineText.START_POKER_MENU_TEXT_01_PART_5}{p.max_buyins}"
                        f"{InlineText.START_POKER_MENU_TEXT_01_PART_6}{p.big_buyin}"
                        f"{InlineText.START_POKER_MENU_TEXT_01_PART_7}{p.super_buyin}"
                    )
                    for p in params
                ],
            ]
        ),
        reply_markup=poker_params_keyboard(params=params),
    )


async def start_poker_with_param(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return

    params_id = int(callback.data.split(":", 1)[1])
    await _clear_inline_keyboard(callback)

    async with SessionFactory() as session:
        actor_user_id = await resolve_telegram_user_id(
            session=session,
            telegram_id=callback.from_user.id,
        )
    if actor_user_id is None:
        await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
        return

    try:
        await execute_start_poker(actor_user_id=actor_user_id, params_id=params_id)
    except (PokerAlreadyStartedError, PokerParamsNotFoundError):
        await callback.answer(Text.admin.POKER_STARTED.value, show_alert=True)
        return
    except StartPokerNotAuthorizedError:
        await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
        return

    if callback.message is not None:
        await _safe_callback_edit_text(callback, Text.admin.POKER_START_SUCCESS.value)
    await callback.answer(Text.admin.POKER_START_SUCCESS.value)
