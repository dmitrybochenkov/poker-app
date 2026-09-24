from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.vk.admin import buyins as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
)
from app.bot.vk.keyboards import (
    poker_buyin_candidates_keyboard,
    poker_buyin_correct_confirm_keyboard,
    poker_buyin_count_keyboard,
)
from app.bot.vk.state import (
    WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT,
    vk_user_contexts,
    vk_user_states,
)
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    HANDLER_UNMATCHED,
    VK_BUYIN_NOTIFY_CASHIER_ONLY,
    _clear_event_inline_keyboard_if_possible,
)
from .player_notification_helpers import _notify_about_buyin


async def handle_poker_buyin_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_buyin_select":
        player_id = callback_payload.get("player_id")
        if not isinstance(player_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                result_text = Text.admin.NO_RIGHTS.value
                result_keyboard = None
            else:
                poker_repository = PokerRepository(session)
                active = await poker_repository.get_started()
                if active is None:
                    result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
                    result_keyboard = None
                else:
                    poker, params = active
                    if poker.is_ready_for_chips_entering:
                        result_text = Text.user.FINISH_CHIPS_NOT_READY.value
                        result_keyboard = None
                        await send_vk_message_event_answer(
                            event_id=event_id,
                            user_id=admin_user_id,
                            peer_id=peer_id,
                            text=result_text,
                        )
                        await _clear_event_inline_keyboard_if_possible(
                            peer_id=peer_id, conversation_message_id=conversation_message_id
                        )
                        await send_vk_message(user_id=admin_user_id, message=result_text)
                        return PlainTextResponse("ok")
                    if poker.cashier_id is None:
                        result_text = Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value
                        result_keyboard = None
                        await send_vk_message_event_answer(
                            event_id=event_id,
                            user_id=admin_user_id,
                            peer_id=peer_id,
                            text=result_text,
                        )
                        await _clear_event_inline_keyboard_if_possible(
                            peer_id=peer_id, conversation_message_id=conversation_message_id
                        )
                        await send_vk_message(user_id=admin_user_id, message=result_text)
                        return PlainTextResponse("ok")
                    player = await PokerDataRepository(session).get_player(
                        date=poker.date, player_id=int(player_id)
                    )
                    include_king_buyin = bool(player is not None and player.is_prev_winner)
                    current_big_buyin_count = (
                        int(player.big_buyin_count) if player is not None else 0
                    )
                    current_super_buyin_count = (
                        int(player.super_buyin_count) if player is not None else 0
                    )
                    result_text = Text.admin.POKER_BUYIN_PROMPT.value
                    result_keyboard = poker_buyin_count_keyboard(
                        player_id=int(player_id),
                        max_buyins=int(params.max_buyins),
                        big_buyin=params.big_buyin,
                        king_buyin=params.king_buyin,
                        super_buyin=params.super_buyin,
                        big_buyin_pic=params.big_buyin_pic,
                        king_buyin_pic=params.king_buyin_pic,
                        super_buyin_pic=params.super_buyin_pic,
                        include_king_buyin=include_king_buyin,
                        current_big_buyin_count=current_big_buyin_count,
                        current_super_buyin_count=current_super_buyin_count,
                    )
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=result_text,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=admin_user_id, message=result_text, keyboard=result_keyboard)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_buyin_correct_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_buyin_correct_select":
        player_id = callback_payload.get("player_id")
        if not isinstance(player_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.NO_RIGHTS.value,
                )
                return PlainTextResponse("ok")
            active = await PokerRepository(session).get_started()
            if active is None:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.POKER_ACTIVE_NOT_FOUND.value,
                )
                return PlainTextResponse("ok")
            poker, _ = active
            player = await PokerDataRepository(session).get_player(
                date=poker.date, player_id=int(player_id)
            )
            if player is None:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.USER_NOT_FOUND.value,
                )
                return PlainTextResponse("ok")
            vk_user_states[admin_user_id] = WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT
            vk_user_contexts.setdefault(admin_user_id, {})
            vk_user_contexts[admin_user_id]["buyin_correct_player_id"] = str(int(player_id))
            vk_user_contexts[admin_user_id]["buyin_correct_old_buyins"] = str(int(player.buyins))
            vk_user_contexts[admin_user_id]["buyin_correct_player_name"] = str(player.player_name)
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=InlineText.EVENT_0_20_TEXT_01,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=admin_user_id,
            message=f'{InlineText.EVENT_0_20_TEXT_02_PART_1}{player.player_name}{InlineText.EVENT_0_20_TEXT_02_PART_2}{int(player.buyins)}',
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_buyin_correction_confirmation_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action in {"poker_buyin_correct_confirm_yes", "poker_buyin_correct_confirm_no"}:
        player_id = callback_payload.get("player_id")
        new_buyins = callback_payload.get("new_buyins")
        if not isinstance(player_id, int) or not isinstance(new_buyins, int):
            return PlainTextResponse("ok")
        if action.endswith("_no"):
            vk_user_states.pop(admin_user_id, None)
            vk_user_contexts.pop(admin_user_id, None)
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=admin_user_id,
                peer_id=peer_id,
                text=Buttons.betting_inline.CONFIRM_NO.value,
            )
            await _clear_event_inline_keyboard_if_possible(
                peer_id=peer_id, conversation_message_id=conversation_message_id
            )
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.NO_RIGHTS.value,
                )
                return PlainTextResponse("ok")
            active = await PokerRepository(session).get_started()
            if active is None:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.POKER_ACTIVE_NOT_FOUND.value,
                )
                return PlainTextResponse("ok")
            poker, _ = active
            poker_data_repository = PokerDataRepository(session)
            player = await poker_data_repository.get_player(
                date=poker.date, player_id=int(player_id)
            )
            if player is None:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.USER_NOT_FOUND.value,
                )
                return PlainTextResponse("ok")
            old_buyins = int(player.buyins)
            delta = int(new_buyins) - old_buyins
            if delta != 0:
                updated = await poker_data_repository.add_buyins(
                    date=poker.date,
                    player_id=int(player_id),
                    buyins_count=int(delta),
                    big_buyin_count=0,
                    super_buyin_count=0,
                )
            else:
                updated = player
        vk_user_states.pop(admin_user_id, None)
        vk_user_contexts.pop(admin_user_id, None)
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=Text.admin.POKER_BUYIN_SAVED.value,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=admin_user_id,
            message=f"{Text.admin.POKER_BUYIN_SAVED.value}\n\n{updated.player_name}: {updated.buyins}",
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_buyin_count_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_buyin_count_select":
        player_id = callback_payload.get("player_id")
        buyins_count = callback_payload.get("count")
        if not isinstance(player_id, int) or not isinstance(buyins_count, int) or buyins_count <= 0:
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            is_admin = await is_vk_admin(session=session, vk_id=admin_user_id)
            requester = await UserRepository(session).get_by_vk_id(admin_user_id)
            requester_row_id = int(requester.row_id) if requester is not None else -1
            if not is_admin and int(player_id) != requester_row_id:
                result_text = Text.admin.NO_RIGHTS.value
            else:
                poker_repository = PokerRepository(session)
                active = await poker_repository.get_started()
                if active is None:
                    result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
                else:
                    poker, params = active
                    if poker.is_ready_for_chips_entering:
                        result_text = Text.user.FINISH_CHIPS_NOT_READY.value
                        await send_vk_message_event_answer(
                            event_id=event_id,
                            user_id=admin_user_id,
                            peer_id=peer_id,
                            text=result_text,
                        )
                        await _clear_event_inline_keyboard_if_possible(
                            peer_id=peer_id, conversation_message_id=conversation_message_id
                        )
                        await send_vk_message(user_id=admin_user_id, message=result_text)
                        return PlainTextResponse("ok")
                    if poker.cashier_id is None:
                        result_text = Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value
                        await send_vk_message_event_answer(
                            event_id=event_id,
                            user_id=admin_user_id,
                            peer_id=peer_id,
                            text=result_text,
                        )
                        await _clear_event_inline_keyboard_if_possible(
                            peer_id=peer_id, conversation_message_id=conversation_message_id
                        )
                        await send_vk_message(user_id=admin_user_id, message=result_text)
                        return PlainTextResponse("ok")
                    poker_data_repository = PokerDataRepository(session)
                    prev_player = await poker_data_repository.get_player(
                        date=poker.date, player_id=int(player_id)
                    )
                    is_special_mode = int(params.max_buyins) == 2
                    include_king_buyin = bool(
                        prev_player is not None and prev_player.is_prev_winner
                    )
                    big_threshold = int(params.big_buyin or 5)
                    super_threshold = int(params.super_buyin or 10)
                    king_threshold = int(params.king_buyin or 15)
                    current_big_count = (
                        int(prev_player.big_buyin_count) if prev_player is not None else 0
                    )
                    current_super_count = (
                        int(prev_player.super_buyin_count) if prev_player is not None else 0
                    )
                    if is_special_mode:
                        allowed_special_amounts: set[int] = set()
                        if current_super_count == 0 and current_big_count < 2:
                            allowed_special_amounts.add(big_threshold)
                        if current_super_count == 0 and current_big_count == 0:
                            allowed_special_amounts.add(super_threshold)
                            if include_king_buyin:
                                allowed_special_amounts.add(king_threshold)
                        if (
                            int(buyins_count) > int(params.max_buyins)
                            and int(buyins_count) not in allowed_special_amounts
                        ):
                            result_text = Text.admin.POKER_BUYIN_INVALID.value
                            await send_vk_message_event_answer(
                                event_id=event_id,
                                user_id=admin_user_id,
                                peer_id=peer_id,
                                text=result_text,
                            )
                            await _clear_event_inline_keyboard_if_possible(
                                peer_id=peer_id, conversation_message_id=conversation_message_id
                            )
                            await send_vk_message(user_id=admin_user_id, message=result_text)
                            return PlainTextResponse("ok")
                    big_count = 0
                    super_count = 0
                    if is_special_mode:
                        if (
                            include_king_buyin
                            and current_big_count == 0
                            and current_super_count == 0
                            and int(buyins_count) >= king_threshold
                        ):
                            big_count += 1
                            super_count += 1
                        elif int(buyins_count) >= super_threshold:
                            if current_big_count == 0 and current_super_count == 0:
                                super_count += 1
                            elif (
                                current_super_count == 0
                                and current_big_count < 2
                                and int(buyins_count) >= big_threshold
                            ):
                                big_count += 1
                        elif (
                            current_super_count == 0
                            and current_big_count < 2
                            and int(buyins_count) >= big_threshold
                        ):
                            big_count += 1
                    use_case = ManagePokerPlayersUseCase(
                        poker_repository=poker_repository,
                        poker_data_repository=poker_data_repository,
                        buyin_data_repository=BuyinDataRepository(session),
                    )
                    updated = await use_case.add_buyin_to_active_player(
                        player_id=int(player_id),
                        buyins_count=int(buyins_count),
                        big_buyin_count=big_count,
                        super_buyin_count=super_count,
                        poker_date=poker.date,
                    )
                    if updated is None:
                        result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
                    else:
                        result_text = f"{Text.admin.POKER_BUYIN_SAVED.value}\n\n{updated.player_name}: {updated.buyins}"
                        notify_admins = True
                        key = (int(admin_user_id), int(player_id))
                        if key in VK_BUYIN_NOTIFY_CASHIER_ONLY:
                            notify_admins = False
                            VK_BUYIN_NOTIFY_CASHIER_ONLY.discard(key)
                        await _notify_about_buyin(
                            session=session,
                            poker=poker,
                            updated_player=updated,
                            buyins_count=int(buyins_count),
                            notify_admins=notify_admins,
                        )
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=result_text,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=admin_user_id, message=result_text)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_buyin_cancel_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_buyin_cancel":
        result_text = Buttons.betting_inline.CONFIRM_NO.value
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=result_text,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=admin_user_id, message=result_text)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_admin_buyin_correct_amount_text(*, user_id, text):
    if vk_user_states.get(user_id) == WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT:
        if not text.isdigit():
            await send_vk_message(user_id=user_id, message=Text.admin.POKER_BUYIN_INVALID.value)
            return PlainTextResponse("ok")
        new_buyins = int(text)
        ctx = vk_user_contexts.get(user_id, {})
        player_id = int(ctx.get("buyin_correct_player_id", "0") or "0")
        old_buyins = int(ctx.get("buyin_correct_old_buyins", "0") or "0")
        player_name = str(ctx.get("buyin_correct_player_name", InlineText.TEXT_1_02_TEXT_01))
        if player_id <= 0:
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            await send_vk_message(user_id=user_id, message=Text.admin.REQUEST_NOT_FOUND.value)
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=f'{InlineText.TEXT_1_02_TEXT_02_PART_1}{player_name}{InlineText.TEXT_1_02_TEXT_02_PART_2}{old_buyins}{InlineText.TEXT_1_02_TEXT_02_PART_3}{new_buyins}',
            keyboard=poker_buyin_correct_confirm_keyboard(
                player_id=player_id, new_buyins=new_buyins
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_buyin_menu_text(*, user_id, text):
    if text == Buttons.room.BUYIN.value or text == Buttons.admin_room_correct.BUYIN_CORRECT.value:
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            user = await user_repository.get_by_vk_id(user_id)
            if user is None or not user.is_approved:
                await send_vk_message(
                    user_id=user_id, message=Text.user.STATUS_NEED_REGISTRATION.value
                )
                return PlainTextResponse("ok")
            poker_repository = PokerRepository(session)
            active = await poker_repository.get_started()
            if active is None:
                await send_vk_message(
                    user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value
                )
                return PlainTextResponse("ok")
            poker, _ = active
            if poker.is_ready_for_chips_entering:
                await send_vk_message(
                    user_id=user_id, message=Text.user.FINISH_CHIPS_NOT_READY.value
                )
                return PlainTextResponse("ok")
            if poker.cashier_id is None:
                await send_vk_message(
                    user_id=user_id, message=Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value
                )
                return PlainTextResponse("ok")
            is_admin = await is_vk_admin(session=session, vk_id=user_id)
            poker_data_repository = PokerDataRepository(session)
            players = await poker_data_repository.list_players(date=poker.date)
            if not players:
                await send_vk_message(user_id=user_id, message=Text.admin.POKER_BUYIN_EMPTY.value)
                return PlainTextResponse("ok")

            is_correct_mode = text == Buttons.admin_room_correct.BUYIN_CORRECT.value
            if is_admin:
                prompt_text = (
                    Text.admin.POKER_BUYIN_CORRECT_CHOOSE.value
                    if is_correct_mode
                    else Text.admin.POKER_BUYIN_CHOOSE.value
                )
                await send_vk_message(
                    user_id=user_id,
                    message=prompt_text,
                    keyboard=poker_buyin_candidates_keyboard(
                        players=players,
                        show_buyins=is_correct_mode,
                        action="poker_buyin_correct_select"
                        if is_correct_mode
                        else "poker_buyin_select",
                    ),
                )
                return PlainTextResponse("ok")

            poker, params = active
            self_player = await poker_data_repository.get_player(
                date=poker.date, player_id=int(user.row_id)
            )
            if self_player is None:
                await send_vk_message(
                    user_id=user_id, message=Text.user.STATUS_ROOM_NOT_ADDED.value
                )
                return PlainTextResponse("ok")
            include_king_buyin = bool(self_player.is_prev_winner)
            await send_vk_message(
                user_id=user_id,
                message=Text.admin.POKER_BUYIN_PROMPT.value,
                keyboard=poker_buyin_count_keyboard(
                    player_id=int(user.row_id),
                    max_buyins=int(params.max_buyins),
                    big_buyin=params.big_buyin,
                    king_buyin=params.king_buyin,
                    super_buyin=params.super_buyin,
                    big_buyin_pic=params.big_buyin_pic,
                    king_buyin_pic=params.king_buyin_pic,
                    super_buyin_pic=params.super_buyin_pic,
                    include_king_buyin=include_king_buyin,
                    current_big_buyin_count=int(self_player.big_buyin_count),
                    current_super_buyin_count=int(self_player.super_buyin_count),
                ),
            )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
