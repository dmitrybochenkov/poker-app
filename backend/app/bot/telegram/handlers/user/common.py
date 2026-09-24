import logging
import random

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
from app.application.use_cases.user.request_registration import RequestRegistrationUseCase
from app.bot.shared.chips_runtime import (
    TG_ADMIN_CHIPS_STATUS_MSG_IDS,
    TG_ADMIN_ROOM_STATUS_MSG_IDS,
    TG_USER_CHIPS_RESULT_MSG_IDS,
    VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.shared.texts.inline.telegram.user import common as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    betting_dynamic_keyboard,
    main_dynamic_keyboard,
    main_keyboard,
    new_user_keyboard,
    poker_calc_keyboard,
    poker_room_admin_status_keyboard,
    registration_link_review_keyboard,
    registration_review_keyboard,
    room_admin_keyboard,
    room_keyboard,
)
from app.bot.telegram.notifications import notify_admins_about_registration
from app.bot.telegram.states import RegistrationState
from app.bot.vk.api import delete_vk_message_by_id, send_vk_message, send_vk_message_with_id
from app.bot.vk.keyboards import (
    poker_room_admin_status_keyboard as vk_poker_room_admin_status_keyboard,
)
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
from .poker_history_helpers import _format_rub_from_kopecks

router = Router()
logger = logging.getLogger(__name__)
PAYMENT_OWNER_ROW_ID = 1




def _chips_reaction(money_kopecks: int) -> str:
    winner = [InlineText._CHIPS_REACTION_MARKER_01, InlineText._CHIPS_REACTION_MARKER_02, InlineText._CHIPS_REACTION_MARKER_03, InlineText._CHIPS_REACTION_MARKER_04, InlineText._CHIPS_REACTION_MARKER_05, InlineText._CHIPS_REACTION_MARKER_06, InlineText._CHIPS_REACTION_MARKER_07]
    loser = [InlineText._CHIPS_REACTION_MARKER_08, InlineText._CHIPS_REACTION_MARKER_09, InlineText._CHIPS_REACTION_MARKER_10, InlineText._CHIPS_REACTION_MARKER_11, InlineText._CHIPS_REACTION_MARKER_12, InlineText._CHIPS_REACTION_MARKER_13, InlineText._CHIPS_REACTION_MARKER_14]
    return random.choice(winner if int(money_kopecks) >= 0 else loser)














def _format_waiting_players(players: list) -> str:
    waiting = [p.player_name for p in players if p.chips is None]
    if not waiting:
        return Text.admin.POKER_CHIPS_ALL_ENTERED.value
    return Text.admin.POKER_CHIPS_WAITING.value.format(
        players="\n".join(f"- {name}" for name in waiting)
    )


def _build_chips_status_text(*, players: list, chips_in_game: int, chips_entered: int) -> str:
    def money_from_chips(
        chips: int, buyins: int, buyin_size_chips: int, buyin_size_kopecks: int
    ) -> int:
        if buyin_size_chips <= 0:
            return 0
        return (
            (int(chips) - int(buyins) * int(buyin_size_chips)) * int(buyin_size_kopecks)
        ) // int(buyin_size_chips)

    def reaction(money_kopecks: int) -> str:
        return InlineText.REACTION_MARKER_16 if int(money_kopecks) >= 0 else InlineText._CHIPS_REACTION_MARKER_12

    buyin_size_chips = 200
    buyin_size_kopecks = 20000
    if players:
        sample = players[0]
        buyin_size_chips = int(getattr(sample, "_buyin_size_chips", buyin_size_chips))
        buyin_size_kopecks = int(getattr(sample, "_buyin_size_kopecks", buyin_size_kopecks))

    remainder = int(chips_in_game) - int(chips_entered)
    lines = [
        InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_01,
        "",
        f'{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_02_PART_1}{chips_in_game}{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_02_PART_2}{chips_entered}{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_02_PART_3}{remainder}',
        "",
    ]
    for p in players:
        if p.chips is None:
            lines.append(f'{p.player_name}{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_03_PART_1}')
        else:
            money_kopecks = money_from_chips(
                chips=int(p.chips),
                buyins=int(p.buyins),
                buyin_size_chips=buyin_size_chips,
                buyin_size_kopecks=buyin_size_kopecks,
            )
            lines.append(
                f'{p.player_name}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_1}{int(p.chips)}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_4}{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_18_PART_6}{reaction(int(money_kopecks))}'
            )
    return "\n".join(lines)


async def _upsert_tg_user_chips_result(*, chat_id: int, text: str) -> None:
    from app.bot.telegram.runtime import telegram_bot

    if telegram_bot is None:
        return
    prev_msg_id = TG_USER_CHIPS_RESULT_MSG_IDS.get(int(chat_id))
    if prev_msg_id is not None:
        try:
            await telegram_bot.delete_message(chat_id=chat_id, message_id=prev_msg_id)
        except Exception:
            pass
    sent = await telegram_bot.send_message(chat_id=chat_id, text=text)
    TG_USER_CHIPS_RESULT_MSG_IDS[int(chat_id)] = int(sent.message_id)


def _build_user_chips_text(
    *, chips: int | None, money_kopecks: int | None, reaction: str | None
) -> str:
    chips_text = str(chips) if chips is not None else InlineText.BUILD_USER_CHIPS_TEXT_TEXT_01
    if money_kopecks is None or reaction is None:
        result_text = InlineText.BUILD_USER_CHIPS_TEXT_TEXT_02
    else:
        result_text = f'{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_18_PART_6}{reaction}'
    return (
        f'{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_1}{chips_text}{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_2}{result_text}'
    )


async def _notify_admins_about_chips_entry(
    *, session, player, chips: int, money_kopecks: int
) -> None:
    from app.bot.telegram.runtime import telegram_bot

    user_repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    players = await PokerDataRepository(session).list_players(date=player.date)
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await user_repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
    chips_entered = sum(int(p.chips or 0) for p in players)
    chips_in_game = 0
    ready = await poker_repository.get_latest_ready_for_chips_with_params()
    if ready is not None:
        poker, params = ready
        if poker.date == player.date:
            chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
            for p in players:
                setattr(p, "_buyin_size_chips", int(params.buyin_size_chips))
                setattr(p, "_buyin_size_kopecks", int(params.buyin_size_kopecks))
    full_text = _build_chips_status_text(
        players=players, chips_in_game=chips_in_game, chips_entered=chips_entered
    )
    for admin in admins:
        if (
            admin.notification_platform == "tg"
            and admin.telegram_id is not None
            and telegram_bot is not None
        ):
            prev_msg_id = TG_ADMIN_CHIPS_STATUS_MSG_IDS.get(int(admin.telegram_id))
            if prev_msg_id is not None:
                try:
                    await telegram_bot.delete_message(
                        chat_id=admin.telegram_id, message_id=prev_msg_id
                    )
                except Exception:
                    pass
            sent = await telegram_bot.send_message(
                chat_id=admin.telegram_id,
                text=full_text,
                reply_markup=poker_calc_keyboard(),
            )
            TG_ADMIN_CHIPS_STATUS_MSG_IDS[int(admin.telegram_id)] = int(sent.message_id)
        elif admin.notification_platform == "vk" and admin.vk_id is not None:
            await send_vk_message(user_id=admin.vk_id, message=full_text)




























async def _notify_admins_about_room_join(
    *,
    session,
    joined_user: User,
    platform_label: str,
) -> None:
    from app.bot.telegram.runtime import telegram_bot

    repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    poker_data_repository = PokerDataRepository(session)
    active = await poker_repository.get_started()
    players = (
        await poker_data_repository.list_players(date=active[0].date) if active is not None else []
    )
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
    admin_tg_ids = [int(u.telegram_id) for u in admins if u.telegram_id is not None]
    admin_vk_ids = [int(u.vk_id) for u in admins if u.vk_id is not None]
    can_start_betting = bool(
        active is not None
        and active[0].cashier_id is not None
        and not bool(active[0].is_bettable)
        and not bool(active[0].is_ready_for_chips_entering)
    )
    if active is None or active[0].cashier_id is None:
        status_text = (
            InlineText.NOTIFY_ADMINS_ABOUT_ROOM_JOIN_TEXT_01
        )
    else:
        status_text = (
            InlineText.NOTIFY_ADMINS_ABOUT_ROOM_JOIN_TEXT_02
        )
    for admin_id in admin_tg_ids:
        if joined_user.telegram_id is not None and int(admin_id) == int(joined_user.telegram_id):
            continue
        if telegram_bot is not None:
            prev_mid = TG_ADMIN_ROOM_STATUS_MSG_IDS.get(int(admin_id))
            if prev_mid is not None:
                try:
                    await telegram_bot.delete_message(
                        chat_id=int(admin_id), message_id=int(prev_mid)
                    )
                except Exception:
                    pass
            sent = await telegram_bot.send_message(
                chat_id=int(admin_id),
                text=status_text,
                reply_markup=poker_room_admin_status_keyboard(
                    players=[]
                    if (active is not None and active[0].cashier_id is not None)
                    else players,
                    can_start_betting=can_start_betting,
                ),
            )
            TG_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent.message_id)

    for admin_id in admin_vk_ids:
        if joined_user.vk_id is not None and int(admin_id) == int(joined_user.vk_id):
            continue
        prev_mid = VK_ADMIN_ROOM_STATUS_MSG_IDS.get(int(admin_id))
        if prev_mid is not None:
            try:
                await delete_vk_message_by_id(peer_id=int(admin_id), message_id=int(prev_mid))
            except Exception:
                pass
        sent_mid = await send_vk_message_with_id(
            user_id=int(admin_id),
            message=status_text,
            keyboard=vk_poker_room_admin_status_keyboard(
                players=[]
                if (active is not None and active[0].cashier_id is not None)
                else players,
                can_start_betting=can_start_betting,
            ),
        )
        if sent_mid is not None:
            VK_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent_mid)












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
        use_case = RequestRegistrationUseCase(repository)

        try:
            user = await use_case.execute(
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

        tg_admin_chat_ids = await repository.list_admin_tg_ids()
        vk_admin_ids = await repository.list_admin_vk_ids()

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
