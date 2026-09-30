from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.buyins import (
    ActivePokerNotFoundError,
    AddBuyinUseCase,
    BuyinNotAuthorizedError,
    BuyinPlayerNotFoundError,
    CorrectBuyinUseCase,
    InvalidBuyinCountError,
    PokerCashierRequiredError,
    PokerReadyForChipsError,
)
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.identity import resolve_vk_user_id
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
    clear_durable_vk_state,
    load_durable_vk_state,
    replace_durable_vk_state,
)
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
                        poker_id=int(poker.row_id), player_id=int(player_id)
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
                poker_id=int(poker.row_id), player_id=int(player_id)
            )
            if player is None:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.USER_NOT_FOUND.value,
                )
                return PlainTextResponse("ok")
            await replace_durable_vk_state(
                admin_user_id,
                state_type=WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT,
                payload={
                    "buyin_correct_player_id": int(player_id),
                    "buyin_correct_old_buyins": int(player.buyins),
                    "buyin_correct_player_name": str(player.player_name),
                },
            )
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
        if action == "poker_buyin_correct_confirm_no":
            await clear_durable_vk_state(admin_user_id)
            result_text = Buttons.betting_inline.CONFIRM_NO.value
        else:
            async with SessionFactory() as session:
                actor_user_id = await resolve_vk_user_id(
                    session=session, vk_id=admin_user_id
                )
            async with SessionFactory() as session:
                try:
                    updated = await CorrectBuyinUseCase(session).execute(
                        actor_user_id=actor_user_id,
                        target_user_id=player_id,
                        total_buyins=new_buyins,
                    )
                except BuyinNotAuthorizedError:
                    result_text = Text.admin.NO_RIGHTS.value
                except ActivePokerNotFoundError:
                    result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
                except BuyinPlayerNotFoundError:
                    result_text = Text.admin.USER_NOT_FOUND.value
                except InvalidBuyinCountError:
                    result_text = Text.admin.POKER_BUYIN_INVALID.value
                else:
                    result_text = Text.admin.POKER_BUYIN_SAVED.value
                    await send_vk_message(
                        user_id=admin_user_id,
                        message=f"{Text.admin.POKER_BUYIN_SAVED.value}\n\n{updated.player_name}: {updated.total_buyins}",
                    )
            await clear_durable_vk_state(admin_user_id)
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=result_text,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
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
            actor_user_id = await resolve_vk_user_id(session=session, vk_id=admin_user_id)
        result = None
        async with SessionFactory() as session:
            try:
                result = await AddBuyinUseCase(session).execute(
                    actor_user_id=actor_user_id,
                    target_user_id=player_id,
                    buyins_count=buyins_count,
                    operation_id=f"vk:{event_id}",
                )
            except BuyinNotAuthorizedError:
                result_text = Text.admin.NO_RIGHTS.value
            except ActivePokerNotFoundError:
                result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
            except PokerReadyForChipsError:
                result_text = Text.user.FINISH_CHIPS_NOT_READY.value
            except PokerCashierRequiredError:
                result_text = Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value
            except (InvalidBuyinCountError, BuyinPlayerNotFoundError):
                result_text = Text.admin.POKER_BUYIN_INVALID.value
        if result is not None:
            if not result.applied:
                result_text = Text.admin.POKER_BUYIN_ALREADY_SAVED.value
            else:
                result_text = f"{Text.admin.POKER_BUYIN_SAVED.value}\n\n{result.player_name}: {result.total_buyins}"
                notify_admins = True
                key = (int(admin_user_id), int(player_id))
                if key in VK_BUYIN_NOTIFY_CASHIER_ONLY:
                    notify_admins = False
                    VK_BUYIN_NOTIFY_CASHIER_ONLY.discard(key)
                async with SessionFactory() as session:
                    await _notify_about_buyin(
                        session=session,
                        poker=type("PokerNotice", (), {
                            "row_id": result.poker_id,
                            "date": result.poker_date,
                            "cashier_id": result.cashier_user_id,
                        })(),
                        updated_player=type("PlayerNotice", (), {
                            "player_id": result.player_user_id,
                            "player_name": result.player_name,
                            "buyins": result.total_buyins,
                        })(),
                        buyins_count=result.added_buyins,
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
    durable_state = await load_durable_vk_state(user_id)
    if durable_state is not None and durable_state.state_type == WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT:
        if not text.isdigit():
            await send_vk_message(user_id=user_id, message=Text.admin.POKER_BUYIN_INVALID.value)
            return PlainTextResponse("ok")
        new_buyins = int(text)
        ctx = durable_state.payload
        player_id = int(ctx.get("buyin_correct_player_id", "0") or "0")
        old_buyins = int(ctx.get("buyin_correct_old_buyins", "0") or "0")
        player_name = str(ctx.get("buyin_correct_player_name", InlineText.TEXT_1_02_TEXT_01))
        if player_id <= 0:
            await clear_durable_vk_state(user_id)
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
            players = await poker_data_repository.list_players(poker_id=int(poker.row_id))
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
                poker_id=int(poker.row_id), player_id=int(user.row_id)
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
