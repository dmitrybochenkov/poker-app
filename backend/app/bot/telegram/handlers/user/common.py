import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.application.exceptions import (
    UserAlreadyRegisteredError,
    UserIdentityRequiredError,
    UserNameRequiredError,
    UserRegistrationPendingError,
)
from app.application.use_cases.user.registration import SubmitRegistrationUseCase
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    betting_dynamic_keyboard,
    main_dynamic_keyboard,
    main_keyboard,
    new_user_keyboard,
    registration_link_review_keyboard,
    registration_review_keyboard,
    room_admin_keyboard,
    room_keyboard,
)
from app.bot.telegram.notifications import notify_admins_about_registration
from app.bot.telegram.states import RegistrationState
from app.bot.vk.keyboards import (
    registration_link_review_keyboard as vk_registration_link_review_keyboard,
)
from app.bot.vk.keyboards import (
    registration_review_keyboard as vk_registration_review_keyboard,
)
from app.bot.vk.notifications import (
    notify_admins_about_registration as notify_vk_admins_about_registration,
)
from app.db.models.user import User
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .poll_helpers import (
    _format_poll_summary as _format_poll_summary,
)
from .poll_helpers import (
    _month_bounds as _month_bounds,
)
from .poll_helpers import (
    _month_name_ru_upper as _month_name_ru_upper,
)
from .poll_helpers import (
    _parse_custom_day_input as _parse_custom_day_input,
)
from .poll_helpers import (
    _parse_iso_dates as _parse_iso_dates,
)
from .poll_helpers import (
    _parse_month_key as _parse_month_key,
)
from .poll_helpers import (
    _poll_all_days_for_month as _poll_all_days_for_month,
)
from .poll_helpers import (
    _poll_choose_text as _poll_choose_text,
)
from .poll_helpers import (
    _poll_days_for_month as _poll_days_for_month,
)
from .poll_helpers import (
    _render_poll_results_chart as _render_poll_results_chart,
)
from .receipts_helpers import (
    _download_telegram_receipt_bytes as _download_telegram_receipt_bytes,
)
from .receipts_helpers import (
    _format_payment_requisites as _format_payment_requisites,
)
from .receipts_helpers import (
    _format_unpaid_bets_lines as _format_unpaid_bets_lines,
)
from .receipts_helpers import (
    _pick_fifo_bets_to_close as _pick_fifo_bets_to_close,
)
from .receipts_helpers import (
    _telegram_external_file_id as _telegram_external_file_id,
)

router = Router()
logger = logging.getLogger(__name__)
PAYMENT_OWNER_ROW_ID = 1


































































async def _get_telegram_user(telegram_id: int) -> User | None:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        return await repository.get_by_telegram_id(telegram_id)


async def _ensure_approved_telegram_user(message: Message) -> bool:
    if message.from_user is None:
        await message.answer(
            Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard
        )
        return False
    user = await _get_telegram_user(message.from_user.id)
    if user is None:
        await message.answer(
            Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
        )
        return False
    if not user.is_approved:
        await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
        return False
    return True


async def _approved_tg_keyboard(user: User):
    async with SessionFactory() as session:
        active = await PokerRepository(session).get_started()
        poll_month = await PollConfigRepository(session).get_active_month()
    return main_dynamic_keyboard(
        is_admin=bool(user.is_admin),
        has_active_poker=active is not None,
        has_active_poll=poll_month is not None,
    )


async def _betting_tg_keyboard():
    return betting_dynamic_keyboard(include_make_bet=True)


async def _post_bet_tg_keyboard_for_user(*, telegram_id: int):
    async with SessionFactory() as session:
        user = await UserRepository(session).get_by_telegram_id(telegram_id)
        if user is None:
            return main_keyboard
        active = await PokerRepository(session).get_started()
        if active is None:
            return await _approved_tg_keyboard(user)
        poker, _ = active
        player = await PokerDataRepository(session).get_player(
            date=poker.date, player_id=int(user.row_id)
        )
        if player is not None:
            return room_admin_keyboard if user.is_admin else room_keyboard
        return await _approved_tg_keyboard(user)


async def _ensure_approved_telegram_callback_user(callback: CallbackQuery) -> bool:
    if callback.from_user is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return False
    user = await _get_telegram_user(callback.from_user.id)
    if user is None:
        await callback.answer(Text.user.STATUS_NEED_REGISTRATION.value, show_alert=True)
        return False
    if not user.is_approved:
        await callback.answer(Text.user.STATUS_PENDING.value, show_alert=True)
        return False
    return True


async def _clear_inline_keyboard(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        return


async def _delete_message_if_possible(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.delete()
    except Exception:
        return










async def _safe_edit_reply_markup(
    message: Message | None, reply_markup: InlineKeyboardMarkup | None
) -> None:
    if message is None:
        return
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def _safe_callback_edit_reply_markup(
    callback: CallbackQuery,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    await _safe_edit_reply_markup(callback.message, reply_markup)


async def _safe_callback_edit_text(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise




async def _submit_registration_request(
    *,
    message: Message,
    state: FSMContext,
    name: str,
    success_text: str,
    linked_to_user: User | None = None,
    requester_telegram_id: int | None = None,
    bank_name: str | None = None,
    tel_number: str | None = None,
    notification_platform: str | None = None,
) -> None:
    telegram_id = (
        requester_telegram_id
        if requester_telegram_id is not None
        else (message.from_user.id if message.from_user is not None else None)
    )
    if telegram_id is None:
        await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
        return

    async with SessionFactory() as session:
        repository = UserRepository(session)
        use_case = SubmitRegistrationUseCase(session)

        try:
            result = await use_case.execute(
                name=name,
                telegram_id=telegram_id,
                bank_name=bank_name,
                tel_number=tel_number,
                notification_platform=notification_platform,
            )
        except UserIdentityRequiredError:
            await message.answer(Text.user.REGISTRATION_ID_ERROR.value)
            return
        except UserNameRequiredError:
            await message.answer(Text.user.REGISTRATION_EMPTY_NAME.value)
            return
        except UserAlreadyRegisteredError:
            existing_user = await repository.get_by_telegram_id(telegram_id)
            reply_markup = (
                (await _approved_tg_keyboard(existing_user))
                if existing_user and existing_user.is_approved
                else new_user_keyboard
            )
            await message.answer(Text.user.REGISTRATION_EXIST.value, reply_markup=reply_markup)
            await state.clear()
            return
        except UserRegistrationPendingError:
            await message.answer(
                Text.user.REGISTRATION_PENDING.value,
                reply_markup=new_user_keyboard,
            )
            await state.clear()
            return

        user = result.user
        tg_admin_chat_ids = result.telegram_admin_ids
        vk_admin_ids = result.vk_admin_ids

    await notify_admins_about_registration(
        name=name,
        telegram_id=telegram_id,
        vk_id=None,
        requester_platform="tg",
        admin_chat_ids=tg_admin_chat_ids,
        linked_to_user=linked_to_user,
        reply_markup=(
            registration_link_review_keyboard(row_id=user.row_id)
            if linked_to_user is not None
            else registration_review_keyboard(row_id=user.row_id)
        ),
    )
    await notify_vk_admins_about_registration(
        name=name,
        vk_id=None,
        telegram_id=telegram_id,
        requester_platform="tg",
        admin_ids=vk_admin_ids,
        linked_to_user=linked_to_user,
        keyboard=(
            vk_registration_link_review_keyboard(row_id=user.row_id)
            if linked_to_user is not None
            else vk_registration_review_keyboard(row_id=user.row_id)
        ),
    )
    await state.clear()
    await message.answer(
        success_text,
        reply_markup=new_user_keyboard,
    )


def _normalize_phone(value: str) -> str | None:
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("7") and len(digits) == 11:
        return f"+{digits}"
    return None


REGISTRATION_USER_STATES = {
    RegistrationState.waiting_for_played_before_answer.state,
    RegistrationState.waiting_for_new_name.state,
    RegistrationState.waiting_for_registration_platform_choice.state,
    RegistrationState.waiting_for_optional_details_action.state,
    RegistrationState.waiting_for_bank_name.state,
    RegistrationState.waiting_for_phone.state,
}
