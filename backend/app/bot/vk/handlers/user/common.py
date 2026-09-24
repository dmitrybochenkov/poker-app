import logging
import random
import re

from app.application.exceptions import (
    UserAlreadyRegisteredError,
    UserIdentityRequiredError,
    UserNameRequiredError,
    UserRegistrationPendingError,
)
from app.application.use_cases.user.request_registration import RequestRegistrationUseCase
from app.bot.shared.chips_runtime import (
    TG_ADMIN_ROOM_STATUS_MSG_IDS,
    VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.shared.texts.inline.vk.user import common as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    poker_room_admin_status_keyboard as tg_poker_room_admin_status_keyboard,
)
from app.bot.telegram.keyboards import (
    registration_link_review_keyboard as tg_registration_link_review_keyboard,
)
from app.bot.telegram.keyboards import (
    registration_review_keyboard as tg_registration_review_keyboard,
)
from app.bot.telegram.notifications import (
    notify_admins_about_registration as notify_tg_admins_about_registration,
)
from app.bot.vk.api import (
    delete_vk_message,
    delete_vk_message_by_id,
    send_vk_message,
    send_vk_message_with_id,
)
from app.bot.vk.keyboards import (
    betting_dynamic_keyboard,
    main_dynamic_keyboard,
    main_keyboard,
    new_user_keyboard,
    poker_room_admin_status_keyboard,
    room_admin_keyboard,
    room_keyboard,
)
from app.bot.vk.keyboards import (
    registration_link_review_keyboard as vk_registration_link_review_keyboard,
)
from app.bot.vk.keyboards import (
    registration_review_keyboard as vk_registration_review_keyboard,
)
from app.bot.vk.notifications import notify_admins_about_registration
from app.bot.vk.state import (
    vk_user_contexts,
    vk_user_states,
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
from .poll_helpers import (
    _shift_month as _shift_month,
)
from .receipts_helpers import (
    _download_vk_receipt_bytes as _download_vk_receipt_bytes,
)
from .receipts_helpers import (
    _extract_vk_attachment_url as _extract_vk_attachment_url,
)
from .receipts_helpers import (
    _extract_vk_external_file_id as _extract_vk_external_file_id,
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
from .poker_history_helpers import _format_rub_from_kopecks

STAT_SNACKBAR = InlineText.MODULE_TEXT_01
PAYMENT_OWNER_ROW_ID = 1
logger = logging.getLogger(__name__)


HANDLER_UNMATCHED = object()


def _clear_vk_bet_draft_state(user_id: int) -> None:
    vk_user_states.pop(user_id, None)
    ctx = vk_user_contexts.setdefault(user_id, {})
    for key in (
        "bet_tournament_type",
        "bet_players",
        "bet_better_name",
        "bet_amount_kopecks",
        "bet_winner_name",
        "bet_loser_name",
    ):
        ctx.pop(key, None)












































def _strip_html_tags(text: str) -> str:
    return text.replace("<b>", "").replace("</b>", "")


def _normalize_vk_button_text(text: str) -> str:
    normalized = " ".join((text or "").replace(InlineText._NORMALIZE_VK_BUTTON_TEXT_MARKER_02, "").split()).strip().lower()
    normalized = re.sub(InlineText.NORMALIZE_VK_BUTTON_TEXT_TEXT_01, "", normalized, flags=re.IGNORECASE)
    return normalized


def _vk_button_matches(text: str, button_text: str) -> bool:
    return _normalize_vk_button_text(text) == _normalize_vk_button_text(button_text)






def _chips_reaction(money_kopecks: int) -> str:
    winner = [InlineText._CHIPS_REACTION_MARKER_03, InlineText._CHIPS_REACTION_MARKER_04, InlineText._CHIPS_REACTION_MARKER_05, InlineText._CHIPS_REACTION_MARKER_06, InlineText._CHIPS_REACTION_MARKER_07, InlineText._CHIPS_REACTION_MARKER_08, InlineText._CHIPS_REACTION_MARKER_09]
    loser = [InlineText._CHIPS_REACTION_MARKER_10, InlineText._CHIPS_REACTION_MARKER_11, InlineText._CHIPS_REACTION_MARKER_12, InlineText._CHIPS_REACTION_MARKER_13, InlineText._CHIPS_REACTION_MARKER_14, InlineText._CHIPS_REACTION_MARKER_15, InlineText._CHIPS_REACTION_MARKER_16]
    return random.choice(winner if int(money_kopecks) >= 0 else loser)


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
        return InlineText.REACTION_MARKER_17 if int(money_kopecks) >= 0 else InlineText._CHIPS_REACTION_MARKER_14

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
                f'{p.player_name}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_1}{int(p.chips)}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_4}{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_19_PART_6}{reaction(int(money_kopecks))}'
            )
    return "\n".join(lines)


def _build_user_chips_text(
    *, chips: int | None, money_kopecks: int | None, reaction: str | None
) -> str:
    chips_text = str(chips) if chips is not None else InlineText.BUILD_USER_CHIPS_TEXT_TEXT_01
    if money_kopecks is None or reaction is None:
        result_text = InlineText.BUILD_USER_CHIPS_TEXT_TEXT_02
    else:
        result_text = f'{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_19_PART_6}{reaction}'
    return (
        f'{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_1}{chips_text}{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_2}{result_text}'
    )












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
                reply_markup=tg_poker_room_admin_status_keyboard(
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
            keyboard=poker_room_admin_status_keyboard(
                players=[]
                if (active is not None and active[0].cashier_id is not None)
                else players,
                can_start_betting=can_start_betting,
            ),
        )
        if sent_mid is not None:
            VK_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent_mid)


async def _get_vk_user(user_id: int) -> User | None:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        return await repository.get_by_vk_id(user_id)


async def _is_vk_user_approved(user_id: int) -> bool:
    user = await _get_vk_user(user_id)
    return bool(user and user.is_approved)


async def _approved_vk_keyboard(user: User) -> str:
    async with SessionFactory() as session:
        active = await PokerRepository(session).get_started()
        poll_month = await PollConfigRepository(session).get_active_month()
    return main_dynamic_keyboard(
        is_admin=bool(user.is_admin),
        has_active_poker=active is not None,
        has_active_poll=poll_month is not None,
    )


async def _betting_vk_keyboard() -> str:
    return betting_dynamic_keyboard(include_make_bet=True)


async def _post_bet_vk_keyboard_for_user(*, vk_id: int) -> str:
    async with SessionFactory() as session:
        user = await UserRepository(session).get_by_vk_id(vk_id)
        if user is None:
            return main_keyboard
        active = await PokerRepository(session).get_started()
        if active is None:
            return await _approved_vk_keyboard(user)
        poker, _ = active
        player = await PokerDataRepository(session).get_player(
            date=poker.date, player_id=int(user.row_id)
        )
        if player is not None:
            return room_admin_keyboard if user.is_admin else room_keyboard
        return await _approved_vk_keyboard(user)


async def _delete_event_message_if_possible(
    *, peer_id: int | None, conversation_message_id: int | None
) -> None:
    if peer_id is None or conversation_message_id is None:
        return
    try:
        await delete_vk_message(
            peer_id=peer_id,
            conversation_message_id=conversation_message_id,
        )
    except Exception:
        return










async def _submit_registration_request(
    *,
    user_id: int,
    name: str,
    success_message: str,
    linked_to_user: User | None = None,
    bank_name: str | None = None,
    tel_number: str | None = None,
    notification_platform: str | None = None,
) -> None:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        use_case = RequestRegistrationUseCase(repository)
        try:
            user = await use_case.execute(
                name=name,
                vk_id=user_id,
                bank_name=bank_name,
                tel_number=tel_number,
                notification_platform=notification_platform,
            )
        except UserIdentityRequiredError:
            await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_ID_ERROR.value)
            return
        except UserNameRequiredError:
            await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_EMPTY_NAME.value)
            return
        except UserAlreadyRegisteredError:
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            existing_user = await repository.get_by_vk_id(user_id)
            keyboard = (
                (await _approved_vk_keyboard(existing_user))
                if existing_user and existing_user.is_approved
                else new_user_keyboard
            )
            await send_vk_message(
                user_id=user_id, message=Text.user.REGISTRATION_EXIST.value, keyboard=keyboard
            )
            return
        except UserRegistrationPendingError:
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            await send_vk_message(
                user_id=user_id,
                message=Text.user.REGISTRATION_PENDING.value,
                keyboard=new_user_keyboard,
            )
            return

        admin_ids = await repository.list_admin_vk_ids()
        tg_admin_chat_ids = await repository.list_admin_tg_ids()

    vk_user_states.pop(user_id, None)
    vk_user_contexts.pop(user_id, None)
    await notify_tg_admins_about_registration(
        name=name,
        telegram_id=None,
        vk_id=user_id,
        requester_platform="vk",
        admin_chat_ids=tg_admin_chat_ids,
        linked_to_user=linked_to_user,
        reply_markup=(
            tg_registration_link_review_keyboard(row_id=user.row_id)
            if linked_to_user is not None
            else tg_registration_review_keyboard(row_id=user.row_id)
        ),
    )
    await notify_admins_about_registration(
        name=name,
        vk_id=user_id,
        requester_platform="vk",
        admin_ids=admin_ids,
        linked_to_user=linked_to_user,
        keyboard=(
            vk_registration_link_review_keyboard(row_id=user.row_id)
            if linked_to_user is not None
            else vk_registration_review_keyboard(row_id=user.row_id)
        ),
    )
    await send_vk_message(user_id=user_id, message=success_message, keyboard=new_user_keyboard)


def _normalize_phone(value: str) -> str | None:
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("7") and len(digits) == 11:
        return f"+{digits}"
    return None
