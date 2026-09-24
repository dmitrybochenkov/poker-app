from types import SimpleNamespace

from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.application.use_cases.poker.enter_player_chips import EnterPlayerChipsUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.chips_runtime import (
    VK_USER_CHIPS_RESULT_MSG_IDS,
)
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.vk.admin import cashier as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    delete_vk_message_by_id,
    send_vk_message,
    send_vk_message_event_answer,
    send_vk_message_with_id,
)
from app.bot.vk.keyboards import (
    poker_cashier_candidates_keyboard,
)
from app.bot.vk.state import (
    WAITING_FOR_ADMIN_CASHOUT_AMOUNT,
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
    _clear_event_inline_keyboard_if_possible,
)
from .poker_helpers import (
    _build_user_chips_text,
    _get_reaction,
    _upsert_vk_admin_chips_status,
)
from .room_status_helpers import _refresh_admin_room_status


async def handle_poker_set_cashier_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_set_cashier_select":
        user_row_id = callback_payload.get("player_id")
        if not isinstance(user_row_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                result_text = Text.admin.NO_RIGHTS.value
            else:
                use_case = ManagePokerPlayersUseCase(
                    poker_repository=PokerRepository(session),
                    poker_data_repository=PokerDataRepository(session),
                )
                updated = await use_case.set_cashier_for_active_poker(cashier_id=user_row_id)
                if updated is None:
                    result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
                else:
                    cashier_user = await user_repository.get_by_row_id(user_row_id)
                    cashier_name = (
                        cashier_user.name if cashier_user is not None else f"ID {user_row_id}"
                    )
                    result_text = f'{cashier_name}{InlineText.EVENT_0_17_TEXT_01_PART_1}'
                    await _refresh_admin_room_status(session=session)
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


async def handle_poker_room_set_cashier_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_room_set_cashier_select":
        user_row_id = callback_payload.get("player_id")
        if not isinstance(user_row_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                result_text = Text.admin.NO_RIGHTS.value
            else:
                poker_repository = PokerRepository(session)
                active = await poker_repository.get_started()
                if active is None:
                    result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
                else:
                    poker, _ = active
                    if poker.cashier_id is not None:
                        result_text = InlineText.EVENT_0_18_TEXT_01
                    else:
                        user_repository = UserRepository(session)
                        use_case = ManagePokerPlayersUseCase(
                            poker_repository=poker_repository,
                            poker_data_repository=PokerDataRepository(session),
                            buyin_data_repository=BuyinDataRepository(session),
                        )
                        updated = await use_case.set_cashier_for_active_poker(
                            cashier_id=user_row_id
                        )
                        if updated is None:
                            result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
                        else:
                            cashier_user = await user_repository.get_by_row_id(user_row_id)
                            cashier_name = (
                                cashier_user.name
                                if cashier_user is not None
                                else f"ID {user_row_id}"
                            )
                            result_text = f'{cashier_name}{InlineText.EVENT_0_18_TEXT_02_PART_1}'
                            await _refresh_admin_room_status(session=session)
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


async def handle_poker_cashout_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_cashout_select":
        player_id = callback_payload.get("player_id")
        if not isinstance(player_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                result_text = Text.admin.NO_RIGHTS.value
            else:
                ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
                if ready is None:
                    result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
                else:
                    poker, params = ready
                    pdata = PokerDataRepository(session)
                    player = await pdata.get_player(date=poker.date, player_id=int(player_id))
                    chips_raw = vk_user_contexts.get(admin_user_id, {}).get("cashout_input_value")
                    if chips_raw is not None and player is not None:
                        chips = int(chips_raw)
                        bb_size = max(1, int(params.bb_size_chips or 10))
                        step = max(1, bb_size // 2)
                        if chips % step != 0:
                            vk_user_contexts.setdefault(admin_user_id, {}).pop(
                                "cashout_input_value", None
                            )
                            result_text = Text.user.FINISH_CHIPS_INVALID.value.format(step=step)
                        else:
                            actor = await user_repository.get_by_vk_id(admin_user_id)
                            updated = await EnterPlayerChipsUseCase(session).execute(
                                actor_user_id=int(actor.row_id),
                                player_user_id=int(player_id),
                                chips=chips,
                            )
                            money_kopecks = updated.money_kopecks
                            await _upsert_vk_admin_chips_status(
                                session=session, poker_date=updated.poker_date
                            )
                            vk_user_contexts.setdefault(admin_user_id, {}).pop(
                                "cashout_input_value", None
                            )
                            target_user = await user_repository.get_by_row_id(int(player_id))
                            if target_user is not None and target_user.vk_id is not None:
                                user_text = _build_user_chips_text(
                                    chips=int(chips),
                                    money_kopecks=int(money_kopecks),
                                    reaction=_get_reaction(
                                        "winner" if int(money_kopecks) >= 0 else "loser"
                                    ),
                                )
                                prev_user_mid = VK_USER_CHIPS_RESULT_MSG_IDS.get(
                                    int(target_user.vk_id)
                                )
                                if prev_user_mid is not None:
                                    try:
                                        await delete_vk_message_by_id(
                                            peer_id=int(target_user.vk_id),
                                            message_id=int(prev_user_mid),
                                        )
                                    except Exception:
                                        pass
                                sent_user_mid = await send_vk_message_with_id(
                                    user_id=int(target_user.vk_id), message=user_text
                                )
                                if sent_user_mid is not None:
                                    VK_USER_CHIPS_RESULT_MSG_IDS[int(target_user.vk_id)] = int(
                                        sent_user_mid
                                    )
                            result_text = InlineText.EVENT_0_24_TEXT_01
                    else:
                        vk_user_states[admin_user_id] = WAITING_FOR_ADMIN_CASHOUT_AMOUNT
                        vk_user_contexts[admin_user_id] = {"cashout_player_id": str(player_id)}
                        result_text = Text.admin.POKER_CASHOUT_PROMPT.value
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=result_text,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        if result_text == Text.admin.POKER_CASHOUT_PROMPT.value:
            await send_vk_message(user_id=admin_user_id, message=result_text)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_admin_cashout_amount_text(*, user_id, text):
    if vk_user_states.get(user_id) == WAITING_FOR_ADMIN_CASHOUT_AMOUNT:
        if not text.isdigit() or int(text) < 0:
            await send_vk_message(user_id=user_id, message=Text.admin.POKER_CASHOUT_INVALID.value)
            return PlainTextResponse("ok")
        chips = int(text)
        target_user = None
        player_id = vk_user_contexts.get(user_id, {}).get("cashout_player_id")
        if player_id is None:
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            await send_vk_message(user_id=user_id, message=Text.admin.REQUEST_NOT_FOUND.value)
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=user_id):
                vk_user_states.pop(user_id, None)
                vk_user_contexts.pop(user_id, None)
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            user_repository = UserRepository(session)
            ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
            if ready is None:
                vk_user_states.pop(user_id, None)
                vk_user_contexts.pop(user_id, None)
                await send_vk_message(
                    user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value
                )
                return PlainTextResponse("ok")
            poker, params = ready
            bb_size = max(1, int(params.bb_size_chips or 10))
            step = max(1, bb_size // 2)
            if chips % step != 0:
                await send_vk_message(
                    user_id=user_id, message=Text.user.FINISH_CHIPS_INVALID.value.format(step=step)
                )
                return PlainTextResponse("ok")
            actor = await user_repository.get_by_vk_id(user_id)
            updated = await EnterPlayerChipsUseCase(session).execute(
                actor_user_id=int(actor.row_id),
                player_user_id=int(player_id),
                chips=chips,
            )
            money_kopecks = updated.money_kopecks
            await _upsert_vk_admin_chips_status(
                session=session, poker_date=updated.poker_date
            )
            target_user = await user_repository.get_by_row_id(int(player_id))
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        if target_user is not None and target_user.vk_id is not None:
            user_text = _build_user_chips_text(
                chips=int(chips),
                money_kopecks=int(money_kopecks),
                reaction=_get_reaction("winner" if int(money_kopecks) >= 0 else "loser"),
            )
            prev_mid = VK_USER_CHIPS_RESULT_MSG_IDS.get(int(target_user.vk_id))
            if prev_mid is not None:
                try:
                    await delete_vk_message_by_id(
                        peer_id=int(target_user.vk_id), message_id=int(prev_mid)
                    )
                except Exception:
                    pass
            sent_mid = await send_vk_message_with_id(
                user_id=int(target_user.vk_id), message=user_text
            )
            if sent_mid is not None:
                VK_USER_CHIPS_RESULT_MSG_IDS[int(target_user.vk_id)] = int(sent_mid)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_set_cashier_text(*, user_id, text):
    if (
        text == Buttons.admin_room.SET_CASHIER.value
        or text == Buttons.admin_room_correct.SET_CASHIER.value
    ):
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            use_case = ManagePokerPlayersUseCase(
                poker_repository=PokerRepository(session),
                poker_data_repository=PokerDataRepository(session),
            )
            active_players = await use_case.list_active_poker_players()
            if not active_players:
                await send_vk_message(user_id=user_id, message=Text.admin.POKER_PLAYERS_EMPTY.value)
                return PlainTextResponse("ok")
            players: list[SimpleNamespace] = []
            for player in active_players:
                user = await user_repository.get_by_row_id(int(player.player_id))
                if user is None:
                    continue
                players.append(
                    SimpleNamespace(player_id=int(user.row_id), player_name=player.player_name)
                )
            if not players:
                await send_vk_message(user_id=user_id, message=Text.admin.POKER_PLAYERS_EMPTY.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.admin.POKER_CASHIER_CHOOSE.value,
            keyboard=poker_cashier_candidates_keyboard(players=players),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
