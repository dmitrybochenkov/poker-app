from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.bet import BetUseCases
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.identity import resolve_vk_user_id
from app.bot.shared.texts.inline.shared import receipt_ocr as ReceiptText
from app.bot.shared.texts.inline.vk.user import bets as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    bet_receipt_manual_keyboard as tg_bet_receipt_manual_keyboard,
)
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
)
from app.bot.vk.keyboards import (
    bet_receipt_manual_keyboard,
    betting_confirm_keyboard,
    betting_player_keyboard,
    betting_size_keyboard,
    new_user_keyboard,
)
from app.bot.vk.state import (
    WAITING_FOR_BET_AMOUNT,
    WAITING_FOR_BET_PAYMENT_RECEIPT,
    vk_user_contexts,
    vk_user_states,
)
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_payment_receipt_repository import BetPaymentReceiptRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.google_backup import backup_tables_to_google
from app.services.receipt_ocr import (
    extract_amount_rub,
    extract_operation_id,
    extract_phone_tail4,
    ocr_text_from_image_bytes,
    phone_tail_matches,
)

from .common import (
    HANDLER_UNMATCHED,
    PAYMENT_OWNER_ROW_ID,
    _approved_vk_keyboard,
    _betting_vk_keyboard,
    _clear_vk_bet_draft_state,
    _delete_event_message_if_possible,
    _download_vk_receipt_bytes,
    _extract_vk_external_file_id,
    _format_payment_requisites,
    _format_unpaid_bets_lines,
    _get_vk_user,
    _is_vk_user_approved,
    _pick_fifo_bets_to_close,
    _post_bet_vk_keyboard_for_user,
    _vk_button_matches,
    logger,
)
from .poker_history_helpers import _build_bet_last_five_hints, _format_rub_from_kopecks
from .stat_helpers import _format_tournament_name


async def handle_bet_tournament_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action in {"bet_tournament_regular", "bet_tournament_year"}:
        if not await _is_vk_user_approved(user_id):
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.STATUS_PENDING.value,
            )
            return PlainTextResponse("ok")
        tournament_type = "single"
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            user = await user_repository.get_by_vk_id(user_id)
            if user is None or not user.is_approved:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=user_id,
                    peer_id=peer_id,
                    text=Text.user.BETTING_NOT_OPEN.value,
                )
                return PlainTextResponse("ok")
            use_case = BetUseCases(
                user_repository=user_repository,
                poker_repository=PokerRepository(session),
                bet_repository=BetRepository(session),
                bet_param_repository=BetParamRepository(session),
                bet_tournament_repository=BetTournamentRepository(session),
                bet_tournament_param_repository=BetTournamentParamRepository(session),
                poker_data_repository=PokerDataRepository(session),
            )
            bet_params, players, status = await use_case.get_bet_draft_data(
                better_id=user_id,
                tournament_type=tournament_type,
            )
        if status != "ok" or bet_params is None:
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.BETTING_NOT_OPEN.value,
            )
            await _delete_event_message_if_possible(
                peer_id=peer_id, conversation_message_id=conversation_message_id
            )
            await send_vk_message(
                user_id=user_id,
                message=Text.user.BETTING_NOT_OPEN.value,
                keyboard=await _betting_vk_keyboard(),
            )
            return PlainTextResponse("ok")
        context = vk_user_contexts.setdefault(user_id, {})
        context["bet_tournament_type"] = tournament_type
        context["bet_players"] = "|".join([p.player_name for p in players])
        context["bet_better_name"] = user.name
        vk_user_states[user_id] = WAITING_FOR_BET_AMOUNT
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.BETTING_SIZE_CHOOSE.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.user.BETTING_SIZE_CHOOSE.value,
            keyboard=betting_size_keyboard(
                small_size_kopecks=bet_params.small_size_kopecks,
                big_size_kopecks=bet_params.big_size_kopecks,
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_bet_size_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "bet_size":
        if not await _is_vk_user_approved(user_id):
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.STATUS_PENDING.value,
            )
            return PlainTextResponse("ok")
        amount_kopecks = callback_payload.get("amount_kopecks")
        if not isinstance(amount_kopecks, int):
            return PlainTextResponse("ok")
        context = vk_user_contexts.setdefault(user_id, {})
        players_str = context.get("bet_players", "")
        players = [p for p in players_str.split("|") if p]
        if not players:
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_READ_ERROR.value,
            )
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            marks_map, winners_text, losers_text = await _build_bet_last_five_hints(
                session=session, players=players
            )
        context["bet_amount_kopecks"] = str(amount_kopecks)
        context["bet_player_marks"] = marks_map
        context["bet_last_winners_text"] = winners_text
        context["bet_last_losers_text"] = losers_text
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.BETTING_WINNER_CHOOSE.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=f'{InlineText.EVENT_0_20_TEXT_01_PART_1}{winners_text}{InlineText.EVENT_0_20_TEXT_01_PART_2}{Text.user.BETTING_WINNER_CHOOSE.value}',
            keyboard=betting_player_keyboard(
                action="winner", players=players, player_marks=marks_map
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_bet_winner_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "bet_winner":
        if not await _is_vk_user_approved(user_id):
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.STATUS_PENDING.value,
            )
            return PlainTextResponse("ok")
        winner_name = callback_payload.get("player_name")
        if not isinstance(winner_name, str):
            return PlainTextResponse("ok")
        context = vk_user_contexts.setdefault(user_id, {})
        players = [p for p in context.get("bet_players", "").split("|") if p]
        if winner_name not in players:
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_READ_ERROR.value,
            )
            return PlainTextResponse("ok")
        context["bet_winner_name"] = winner_name
        better_name = context.get("bet_better_name")
        marks_map = context.get("bet_player_marks", {})
        losers_text = context.get("bet_last_losers_text", "")
        losers = [p for p in players if p != winner_name and p != better_name]
        if not losers:
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_READ_ERROR.value,
            )
            return PlainTextResponse("ok")
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.BETTING_LOSER_CHOOSE.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        loser_marks = (
            {name: marks_map.get(name, "") for name in losers}
            if isinstance(marks_map, dict)
            else None
        )
        await send_vk_message(
            user_id=user_id,
            message=f'{InlineText.EVENT_0_21_TEXT_01_PART_1}{losers_text}{InlineText.EVENT_0_21_TEXT_01_PART_2}{Text.user.BETTING_LOSER_CHOOSE.value}',
            keyboard=betting_player_keyboard(
                action="loser", players=losers, player_marks=loser_marks
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_bet_loser_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "bet_loser":
        if not await _is_vk_user_approved(user_id):
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.STATUS_PENDING.value,
            )
            return PlainTextResponse("ok")
        loser_name = callback_payload.get("player_name")
        if not isinstance(loser_name, str):
            return PlainTextResponse("ok")
        context = vk_user_contexts.setdefault(user_id, {})
        winner_name = context.get("bet_winner_name")
        if not winner_name or winner_name == loser_name:
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_READ_ERROR.value,
            )
            return PlainTextResponse("ok")
        context["bet_loser_name"] = loser_name
        tournament_type = context.get("bet_tournament_type", "regular")
        amount_kopecks = int(context.get("bet_amount_kopecks", "0"))
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.BETTING_CONFIRM.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.user.BETTING_CONFIRM.value.format(
                tournament=_format_tournament_name(tournament_type),
                amount_rub=amount_kopecks // 100,
                winner=winner_name,
                loser=loser_name,
            ),
            keyboard=betting_confirm_keyboard(),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_bet_confirmation_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action in {"bet_confirm_yes", "bet_confirm_no"}:
        if not await _is_vk_user_approved(user_id):
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.STATUS_PENDING.value,
            )
            return PlainTextResponse("ok")
        if action.endswith("_no"):
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.BETTING_MENU.value,
            )
            await _delete_event_message_if_possible(
                peer_id=peer_id, conversation_message_id=conversation_message_id
            )
            await send_vk_message(
                user_id=user_id,
                message=Text.user.BETTING_MENU.value,
                keyboard=await _betting_vk_keyboard(),
            )
            return PlainTextResponse("ok")
        context = vk_user_contexts.get(user_id, {})
        tournament_type = context.get("bet_tournament_type")
        winner_name = context.get("bet_winner_name")
        loser_name = context.get("bet_loser_name")
        amount_kopecks = int(context.get("bet_amount_kopecks", "0"))
        if not tournament_type or not winner_name or not loser_name or amount_kopecks <= 0:
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_READ_ERROR.value,
            )
            return PlainTextResponse("ok")
        try:
            async with SessionFactory() as session:
                actor_user_id = await resolve_vk_user_id(
                    session=session,
                    vk_id=user_id,
                )
                use_case = BetUseCases(
                    user_repository=UserRepository(session),
                    poker_repository=PokerRepository(session),
                    bet_repository=BetRepository(session),
                    bet_param_repository=BetParamRepository(session),
                    bet_tournament_repository=BetTournamentRepository(session),
                    bet_tournament_param_repository=BetTournamentParamRepository(session),
                    poker_data_repository=PokerDataRepository(session),
                )
                created, status = await use_case.create_bet(
                    actor_user_id=actor_user_id or -1,
                    tournament_type=tournament_type,
                    amount_kopecks=amount_kopecks,
                    winner_name=winner_name,
                    loser_name=loser_name,
                )
        except Exception:
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            await _delete_event_message_if_possible(
                peer_id=peer_id, conversation_message_id=conversation_message_id
            )
            await send_vk_message(
                user_id=user_id,
                message=Text.user.BETTING_NOT_OPEN.value,
                keyboard=await _betting_vk_keyboard(),
            )
            return PlainTextResponse("ok")
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        if status == "already_bet":
            await send_vk_message(
                user_id=user_id,
                message=Text.user.BETTING_ALREADY_EXISTS.value,
                keyboard=await _betting_vk_keyboard(),
            )
        elif status in {
            "betting_closed",
            "user_not_approved",
            "invalid_tournament",
            "missing_params",
        }:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.BETTING_NOT_OPEN.value,
                keyboard=await _betting_vk_keyboard(),
            )
        elif status == "invalid_amount" or created is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.BETTING_NOT_OPEN.value,
                keyboard=await _betting_vk_keyboard(),
            )
        else:
            post_bet_keyboard = await _post_bet_vk_keyboard_for_user(vk_id=user_id)
            await send_vk_message(
                user_id=user_id,
                message=Text.user.BETTING_CREATED.value.format(
                    tournament=_format_tournament_name(tournament_type),
                    amount_rub=amount_kopecks // 100,
                    winner=winner_name,
                    loser=loser_name,
                ),
                keyboard=post_bet_keyboard,
            )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_make_bet_text(*, user_id, text, raw_message):
    if _vk_button_matches(text, Buttons.betting.MAKE_BET.value):
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            user = await user_repository.get_by_vk_id(user_id)
            if user is None or not user.is_approved:
                await send_vk_message(user_id=user_id, message=Text.user.BETTING_NOT_OPEN.value)
                return PlainTextResponse("ok")
            use_case = BetUseCases(
                user_repository=user_repository,
                poker_repository=PokerRepository(session),
                bet_repository=BetRepository(session),
                bet_param_repository=BetParamRepository(session),
                bet_tournament_repository=BetTournamentRepository(session),
                bet_tournament_param_repository=BetTournamentParamRepository(session),
                poker_data_repository=PokerDataRepository(session),
            )
            bet_params, players, status = await use_case.get_bet_draft_data(
                better_id=user_id,
                tournament_type="single",
            )
        if status != "ok" or bet_params is None:
            await send_vk_message(user_id=user_id, message=Text.user.BETTING_NOT_OPEN.value)
            return PlainTextResponse("ok")
        context = vk_user_contexts.setdefault(user_id, {})
        context["bet_tournament_type"] = "single"
        context["bet_players"] = "|".join([p.player_name for p in players])
        context["bet_better_name"] = user.name
        vk_user_states[user_id] = WAITING_FOR_BET_AMOUNT
        await send_vk_message(
            user_id=user_id,
            message=Text.user.BETTING_SIZE_CHOOSE.value,
            keyboard=betting_size_keyboard(
                small_size_kopecks=bet_params.small_size_kopecks,
                big_size_kopecks=bet_params.big_size_kopecks,
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betting_pay_bet_text(*, user_id, text, raw_message):
    if text == Buttons.betting.PAY_BET.value:
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            user = await user_repository.get_by_vk_id(user_id)
            if user is None or not user.is_approved:
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.STATUS_NEED_REGISTRATION.value,
                    keyboard=new_user_keyboard,
                )
                return PlainTextResponse("ok")
            bet_repository = BetRepository(session)
            unpaid = await bet_repository.list_unpaid_for_user(better_id=int(user.row_id))
            if not unpaid:
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.BETTING_PAY_EMPTY.value,
                    keyboard=await _betting_vk_keyboard(),
                )
                vk_user_states.pop(user_id, None)
                return PlainTextResponse("ok")
            total_kopecks = sum(int(item.amount_kopecks) for item in unpaid)
            owner = await user_repository.get_by_row_id(PAYMENT_OWNER_ROW_ID)
            vk_user_states[user_id] = WAITING_FOR_BET_PAYMENT_RECEIPT
            await send_vk_message(
                user_id=user_id,
                message=Text.user.BETTING_PAY_LIST.value.format(
                    lines=_format_unpaid_bets_lines(unpaid),
                    total_rub=_format_rub_from_kopecks(total_kopecks),
                    payment_requisites=_format_payment_requisites(owner),
                ),
                keyboard=await _betting_vk_keyboard(),
            )
            return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_bet_amount_text(*, user_id, text, raw_message):
    if vk_user_states.get(user_id) == WAITING_FOR_BET_AMOUNT:
        menu_buttons = {
            Buttons.main.ROOM.value,
            Buttons.main.POKER.value,
            Buttons.main.BETTING.value,
            Buttons.main.ADMIN.value,
            Buttons.room.TO_MAIN.value,
            Buttons.poker.TO_MAIN.value,
            Buttons.betting.TO_MAIN.value,
        }
        if text in menu_buttons:
            _clear_vk_bet_draft_state(user_id=user_id)
        else:
            await send_vk_message(user_id=user_id, message=Text.user.BETTING_SIZE_CHOOSE.value)
            return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_bet_payment_receipt_text(*, user_id, text, raw_message):
    if vk_user_states.get(user_id) == WAITING_FOR_BET_PAYMENT_RECEIPT:
        text_value = (text or "").strip()
        if text_value == Buttons.betting.TO_MAIN.value:
            vk_user_states.pop(user_id, None)
            user = await _get_vk_user(user_id)
            await send_vk_message(user_id=user_id, message=Text.user.BETTING_PAY_CANCELED.value)
            await send_vk_message(
                user_id=user_id,
                message=Text.user.MAIN_MENU.value,
                keyboard=await _approved_vk_keyboard(user)
                if user is not None
                else new_user_keyboard,
            )
            return PlainTextResponse("ok")

        has_receipt = bool((raw_message or {}).get("attachments"))
        if not has_receipt:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.BETTING_PAY_AMOUNT_INVALID.value,
                keyboard=await _betting_vk_keyboard(),
            )
            return PlainTextResponse("ok")
        receipt_bytes = await _download_vk_receipt_bytes(raw_message)
        ocr_text = ocr_text_from_image_bytes(receipt_bytes or b"")
        entered_rub = extract_amount_rub(ocr_text)

        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            user = await user_repository.get_by_vk_id(user_id)
            if user is None or not user.is_approved:
                vk_user_states.pop(user_id, None)
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.STATUS_NEED_REGISTRATION.value,
                    keyboard=new_user_keyboard,
                )
                return PlainTextResponse("ok")
            bet_repository = BetRepository(session)
            receipt_repository = BetPaymentReceiptRepository(session)
            unpaid = await bet_repository.list_unpaid_for_user(better_id=int(user.row_id))
            if not unpaid:
                vk_user_states.pop(user_id, None)
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.BETTING_PAY_EMPTY.value,
                    keyboard=await _betting_vk_keyboard(),
                )
                return PlainTextResponse("ok")
            owner = await user_repository.get_by_row_id(PAYMENT_OWNER_ROW_ID)

            external_file_id = _extract_vk_external_file_id(raw_message)
            if external_file_id:
                existing_by_file = await receipt_repository.get_by_platform_and_external_file_id(
                    platform="vk",
                    external_file_id=external_file_id,
                )
                if existing_by_file is not None:
                    admin_text = (
                        f'{InlineText.TEXT_1_29_TEXT_01_PART_1}{user.name}{InlineText.TEXT_1_29_TEXT_01_PART_2}{external_file_id}'
                    )
                    from app.bot.telegram.runtime import telegram_bot

                    if (
                        owner is not None
                        and owner.notification_platform == "tg"
                        and owner.telegram_id is not None
                        and telegram_bot is not None
                    ):
                        await telegram_bot.send_message(
                            chat_id=int(owner.telegram_id), text=admin_text
                        )
                    elif owner is not None and owner.vk_id is not None:
                        await send_vk_message(user_id=int(owner.vk_id), message=admin_text)
                    vk_user_states.pop(user_id, None)
                    await send_vk_message(
                        user_id=user_id,
                        message=InlineText.TEXT_1_29_TEXT_02,
                        keyboard=await _betting_vk_keyboard(),
                    )
                    return PlainTextResponse("ok")

            operation_id = extract_operation_id(ocr_text)
            if operation_id:
                existing_by_op = await receipt_repository.get_by_operation_id(
                    operation_id=operation_id
                )
                if existing_by_op is not None:
                    admin_text = (
                        f'{InlineText.TEXT_1_29_TEXT_03_PART_1}{user.name}{InlineText.TEXT_1_29_TEXT_03_PART_2}{operation_id}'
                    )
                    from app.bot.telegram.runtime import telegram_bot

                    if (
                        owner is not None
                        and owner.notification_platform == "tg"
                        and owner.telegram_id is not None
                        and telegram_bot is not None
                    ):
                        await telegram_bot.send_message(
                            chat_id=int(owner.telegram_id), text=admin_text
                        )
                    elif owner is not None and owner.vk_id is not None:
                        await send_vk_message(user_id=int(owner.vk_id), message=admin_text)
                    vk_user_states.pop(user_id, None)
                    await send_vk_message(
                        user_id=user_id,
                        message=InlineText.TEXT_1_29_TEXT_04,
                        keyboard=await _betting_vk_keyboard(),
                    )
                    return PlainTextResponse("ok")
            ocr_phone_match = phone_tail_matches(
                ocr_text, owner.tel_number if owner is not None else None
            )
            recipient_tail4 = extract_phone_tail4(
                ocr_text, owner.tel_number if owner is not None else None
            )
            if entered_rub is not None and ocr_phone_match is True:
                paid_kopecks = int(entered_rub) * 100
                to_close = _pick_fifo_bets_to_close(bets=unpaid, paid_kopecks=paid_kopecks)
                if to_close:
                    await bet_repository.mark_paid(bets=to_close)
                    await receipt_repository.create(
                        user_row_id=int(user.row_id),
                        platform="vk",
                        external_file_id=external_file_id,
                        operation_id=operation_id,
                        amount_kopecks_ocr=paid_kopecks,
                        recipient_tail4_ocr=recipient_tail4,
                        status="accepted",
                    )
                    await session.commit()
                    try:
                        await backup_tables_to_google(session=session)
                    except Exception:
                        logger.exception("Failed to sync Google backup after VK is_paid update")
                    remain = await bet_repository.list_unpaid_for_user(better_id=int(user.row_id))
                    remain_kopecks = sum(int(item.amount_kopecks) for item in remain)
                    vk_user_states.pop(user_id, None)
                    await send_vk_message(
                        user_id=user_id,
                        message=Text.user.BETTING_PAY_MATCHED.value.format(
                            count=len(to_close),
                            debt_rub=_format_rub_from_kopecks(remain_kopecks),
                        ),
                        keyboard=await _betting_vk_keyboard(),
                    )
                    return PlainTextResponse("ok")

            total_unpaid = sum(int(item.amount_kopecks) for item in unpaid)
            missing_fields: list[str] = []
            if entered_rub is None:
                missing_fields.append("sum")
            if ocr_phone_match is not True:
                missing_fields.append("recipient")
            if operation_id is None:
                missing_fields.append("operation_id")
            ocr_preview = " ".join((ocr_text or "").split())[:500]
            admin_text = (
                f'{InlineText.TEXT_1_29_TEXT_05_PART_1}{user.name}{InlineText.TEXT_1_29_TEXT_05_PART_2}{(entered_rub if entered_rub is not None else ReceiptText.AMOUNT_UNDETERMINED)}{InlineText.TEXT_1_29_TEXT_05_PART_3}{_format_rub_from_kopecks(total_unpaid)}{InlineText.TEXT_1_29_TEXT_05_PART_4}{(ReceiptText.PHONE_MATCHES if ocr_phone_match else ReceiptText.PHONE_DOES_NOT_MATCH if ocr_phone_match is False else ReceiptText.VALUE_UNDETERMINED)}{InlineText.TEXT_1_29_TEXT_05_PART_5}{(recipient_tail4 if recipient_tail4 is not None else ReceiptText.VALUE_UNDETERMINED)}{InlineText.TEXT_1_29_TEXT_05_PART_6}{(operation_id if operation_id is not None else ReceiptText.VALUE_UNDETERMINED)}{InlineText.TEXT_1_29_TEXT_05_PART_7}{(', '.join(missing_fields) if missing_fields else ReceiptText.NO_MISSING_FIELDS)}{InlineText.TEXT_1_29_TEXT_05_PART_8}{(ocr_preview if ocr_preview else ReceiptText.EMPTY_PREVIEW)}'
            )
            manual_receipt = await receipt_repository.create(
                user_row_id=int(user.row_id),
                platform="vk",
                external_file_id=external_file_id,
                operation_id=operation_id,
                amount_kopecks_ocr=(int(entered_rub) * 100) if entered_rub is not None else None,
                recipient_tail4_ocr=recipient_tail4,
                status="manual",
            )
            reviewer = await user_repository.get_by_row_id(PAYMENT_OWNER_ROW_ID)
            from app.bot.telegram.runtime import telegram_bot

            if (
                reviewer is not None
                and reviewer.notification_platform == "tg"
                and reviewer.telegram_id is not None
                and telegram_bot is not None
            ):
                await telegram_bot.send_message(
                    chat_id=int(reviewer.telegram_id),
                    text=admin_text,
                    reply_markup=tg_bet_receipt_manual_keyboard(
                        receipt_row_id=int(manual_receipt.row_id),
                        bets=unpaid,
                        selected_ids=[],
                        page=0,
                    ),
                )
            elif reviewer is not None and reviewer.vk_id is not None:
                await send_vk_message(
                    user_id=int(reviewer.vk_id),
                    message=admin_text,
                    keyboard=bet_receipt_manual_keyboard(
                        receipt_row_id=int(manual_receipt.row_id),
                        bets=unpaid,
                        selected_ids=[],
                        page=0,
                    ),
                )
            elif (
                telegram_bot is not None
                and reviewer is not None
                and reviewer.telegram_id is not None
            ):
                # Fallback for legacy reviewer rows without notification_platform.
                await telegram_bot.send_message(
                    chat_id=int(reviewer.telegram_id),
                    text=admin_text,
                    reply_markup=tg_bet_receipt_manual_keyboard(
                        receipt_row_id=int(manual_receipt.row_id),
                        bets=unpaid,
                        selected_ids=[],
                        page=0,
                    ),
                )
            await session.commit()
            vk_user_states.pop(user_id, None)
            await send_vk_message(
                user_id=user_id,
                message=Text.user.BETTING_PAY_NEED_MANUAL.value,
                keyboard=await _betting_vk_keyboard(),
            )
            return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
