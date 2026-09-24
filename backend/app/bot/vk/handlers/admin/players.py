import random

from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.vk.admin import players as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
)
from app.bot.vk.keyboards import (
    poker_add_player_candidates_keyboard,
    poker_buyin_count_keyboard,
    poker_remove_player_candidates_keyboard,
    poker_room_manage_player_keyboard,
    poker_unban_player_candidates_keyboard,
)
from app.bot.vk.state import (
    WAITING_FOR_ADMIN_NEW_PLAYER_NAME,
    vk_user_contexts,
    vk_user_states,
)
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    HANDLER_UNMATCHED,
    VK_BUYIN_NOTIFY_CASHIER_ONLY,
    _clear_event_inline_keyboard_if_possible,
)
from .player_notification_helpers import (
    _notify_admins_about_removed_player,
    _notify_user_removed_from_room,
    _notify_user_unbanned_for_room,
)


async def handle_poker_add_player_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_add_player_select":
        row_id = callback_payload.get("row_id")
        if not isinstance(row_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            result_keyboard = None
            result_added_text = None
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                result_text = Text.admin.NO_RIGHTS.value
            else:
                user = await user_repository.get_by_row_id(row_id)
                if user is None or user.vk_id is None:
                    result_text = Text.admin.USER_NOT_FOUND.value
                else:
                    use_case = ManagePokerPlayersUseCase(
                        poker_repository=PokerRepository(session),
                        poker_data_repository=PokerDataRepository(session),
                    )
                    created = await use_case.add_player_to_active_poker(
                        player_id=int(user.row_id),
                        player_name=user.name,
                    )
                    if created is None:
                        result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
                        result_keyboard = None
                    else:
                        poker, params = await PokerRepository(session).get_started()
                        self_player = await PokerDataRepository(session).get_player(
                            date=poker.date, player_id=int(user.row_id)
                        )
                        include_king_buyin = bool(
                            self_player is not None and self_player.is_prev_winner
                        )
                        current_big_buyin_count = (
                            int(self_player.big_buyin_count) if self_player is not None else 0
                        )
                        current_super_buyin_count = (
                            int(self_player.super_buyin_count) if self_player is not None else 0
                        )
                        VK_BUYIN_NOTIFY_CASHIER_ONLY.add((int(admin_user_id), int(user.row_id)))
                        result_text = Text.admin.POKER_BUYIN_PROMPT.value
                        result_added_text = f'{InlineText.EVENT_0_09_TEXT_01_PART_1}{user.name}{InlineText.EVENT_0_09_TEXT_01_PART_2}{(int(self_player.buyins) if self_player is not None else 0)}'
                        result_keyboard = poker_buyin_count_keyboard(
                            player_id=int(user.row_id),
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
                        await use_case.remove_denied_for_active_poker(user_row_id=int(user.row_id))
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=result_text,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        if result_added_text:
            await send_vk_message(user_id=admin_user_id, message=result_added_text)
        await send_vk_message(user_id=admin_user_id, message=result_text, keyboard=result_keyboard)
        return None
    return HANDLER_UNMATCHED


async def handle_poker_add_player_new_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_add_player_new":
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.NO_RIGHTS.value,
                )
                return PlainTextResponse("ok")
        vk_user_states[admin_user_id] = WAITING_FOR_ADMIN_NEW_PLAYER_NAME
        vk_user_contexts.setdefault(admin_user_id, {})["new_player_from"] = "poker_add"
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=InlineText.EVENT_0_10_TEXT_01,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=admin_user_id, message=InlineText.EVENT_0_10_TEXT_02)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_add_player_cancel_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_add_player_cancel":
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
    return HANDLER_UNMATCHED


async def handle_poker_room_manage_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_room_manage_select":
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
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=InlineText.EVENT_0_12_TEXT_01,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=admin_user_id,
            message=InlineText.EVENT_0_12_TEXT_02,
            keyboard=poker_room_manage_player_keyboard(player_id=int(player_id)),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_room_approve_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_room_approve_select":
        player_id = callback_payload.get("player_id")
        if not isinstance(player_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                result_text = Text.admin.NO_RIGHTS.value
            else:
                user = await user_repository.get_by_row_id(int(player_id))
                if user is None:
                    result_text = Text.admin.USER_NOT_FOUND.value
                else:
                    use_case = ManagePokerPlayersUseCase(
                        poker_repository=PokerRepository(session),
                        poker_data_repository=PokerDataRepository(session),
                        poker_room_denied_repository=PokerRoomDeniedRepository(session),
                    )
                    created = await use_case.add_player_to_active_poker(
                        player_id=int(user.row_id),
                        player_name=user.name,
                    )
                    await use_case.remove_denied_for_active_poker(user_row_id=int(user.row_id))
                    result_text = (
                        InlineText.EVENT_0_13_TEXT_01
                        if created is not None
                        else Text.admin.POKER_ACTIVE_NOT_FOUND.value
                    )
                    if created is not None:
                        if user.telegram_id is not None:
                            from app.bot.telegram.runtime import telegram_bot

                            if telegram_bot is not None:
                                await telegram_bot.send_message(
                                    chat_id=int(user.telegram_id), text=InlineText.EVENT_0_13_TEXT_02
                                )
                        elif user.vk_id is not None:
                            await send_vk_message(
                                user_id=int(user.vk_id), message=InlineText.EVENT_0_13_TEXT_03
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
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_room_reject_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_room_reject_select":
        player_id = callback_payload.get("player_id")
        if not isinstance(player_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                result_text = Text.admin.NO_RIGHTS.value
            else:
                user = await user_repository.get_by_row_id(int(player_id))
                if user is None:
                    result_text = Text.admin.USER_NOT_FOUND.value
                else:
                    await PokerRoomDeniedRepository(session).add(user_row_id=int(user.row_id))
                    result_text = InlineText.EVENT_0_14_TEXT_01
                    if user.telegram_id is not None:
                        from app.bot.telegram.runtime import telegram_bot

                        if telegram_bot is not None:
                            await telegram_bot.send_message(
                                chat_id=int(user.telegram_id), text=InlineText.EVENT_0_14_TEXT_02
                            )
                    elif user.vk_id is not None:
                        await send_vk_message(
                            user_id=int(user.vk_id), message=InlineText.EVENT_0_14_TEXT_03
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


async def handle_poker_remove_player_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_remove_player_select":
        player_id = callback_payload.get("player_id")
        if not isinstance(player_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                result_text = Text.admin.NO_RIGHTS.value
            else:
                use_case = ManagePokerPlayersUseCase(
                    poker_repository=PokerRepository(session),
                    poker_data_repository=PokerDataRepository(session),
                    buyin_data_repository=BuyinDataRepository(session),
                    user_repository=user_repository,
                    poker_room_denied_repository=PokerRoomDeniedRepository(session),
                )
                removed_user = await user_repository.get_by_row_id(int(player_id))
                active = await PokerRepository(session).get_started()
                removed_player_name = (
                    removed_user.name if removed_user is not None else f"ID {int(player_id)}"
                )
                removed_player_buyins = 0
                poker_date = None
                if active is not None:
                    poker_date = active[0].date
                    player_before_remove = await PokerDataRepository(session).get_player(
                        date=poker_date,
                        player_id=int(player_id),
                    )
                    if player_before_remove is not None:
                        removed_player_name = str(player_before_remove.player_name)
                        removed_player_buyins = int(player_before_remove.buyins)
                removed = await use_case.remove_player_from_active_poker(player_id=int(player_id))
                if removed is None:
                    result_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
                elif removed is False:
                    result_text = Text.admin.USER_NOT_FOUND.value
                else:
                    result_text = Text.admin.POKER_REMOVE_PLAYER_SUCCESS.value
                    if removed_user is not None:
                        await _notify_user_removed_from_room(user=removed_user)
                    if poker_date is not None:
                        await _notify_admins_about_removed_player(
                            session=session,
                            poker_date=poker_date,
                            player_name=removed_player_name,
                            buyins=removed_player_buyins,
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


async def handle_poker_unban_player_select_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_unban_player_select":
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
                    poker_room_denied_repository=PokerRoomDeniedRepository(session),
                    user_repository=user_repository,
                )
                unbanned_user = await user_repository.get_by_row_id(int(user_row_id))
                removed = await use_case.remove_denied_for_active_poker(
                    user_row_id=int(user_row_id)
                )
                result_text = (
                    Text.admin.POKER_UNBAN_PLAYER_SUCCESS.value
                    if removed
                    else Text.admin.POKER_UNBAN_PLAYER_EMPTY.value
                )
                if removed and unbanned_user is not None:
                    await _notify_user_unbanned_for_room(user=unbanned_user)
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


async def handle_admin_new_player_name_text(*, user_id, text):
    if vk_user_states.get(user_id) == WAITING_FOR_ADMIN_NEW_PLAYER_NAME:
        name = " ".join((text or "").split())
        if not name:
            await send_vk_message(
                user_id=user_id, message=InlineText.TEXT_1_01_TEXT_01
            )
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=user_id):
                vk_user_states.pop(user_id, None)
                vk_user_contexts.pop(user_id, None)
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            user_repository = UserRepository(session)
            use_case = ManagePokerPlayersUseCase(
                poker_repository=PokerRepository(session),
                poker_data_repository=PokerDataRepository(session),
                user_repository=user_repository,
                poker_room_denied_repository=PokerRoomDeniedRepository(session),
            )
            tmp_telegram_id = 0
            while True:
                candidate = -random.randint(10_000_000_000, 9_999_999_999_999)
                if await user_repository.get_by_telegram_id(candidate) is None:
                    tmp_telegram_id = candidate
                    break
            created_user = await user_repository.create(
                name=name,
                telegram_id=tmp_telegram_id,
                vk_id=None,
                is_approved=True,
                notification_platform=None,
            )
            created_user.telegram_id = -int(created_user.row_id)
            created_user.notification_platform = None
            await session.commit()
            created = await use_case.add_player_to_active_poker(
                player_id=int(created_user.row_id),
                player_name=created_user.name,
            )
            await use_case.remove_denied_for_active_poker(user_row_id=int(created_user.row_id))
            if created is None:
                vk_user_states.pop(user_id, None)
                vk_user_contexts.pop(user_id, None)
                await send_vk_message(
                    user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value
                )
                return PlainTextResponse("ok")
            poker, params = await PokerRepository(session).get_started()
            self_player = await PokerDataRepository(session).get_player(
                date=poker.date, player_id=int(created_user.row_id)
            )
            include_king_buyin = bool(self_player is not None and self_player.is_prev_winner)
            current_big_buyin_count = (
                int(self_player.big_buyin_count) if self_player is not None else 0
            )
            current_super_buyin_count = (
                int(self_player.super_buyin_count) if self_player is not None else 0
            )
            VK_BUYIN_NOTIFY_CASHIER_ONLY.add((int(user_id), int(created_user.row_id)))
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(
            user_id=user_id,
            message=f'{InlineText.TEXT_1_01_TEXT_02_PART_1}{created_user.name}{InlineText.TEXT_1_01_TEXT_02_PART_2}{(int(self_player.buyins) if self_player is not None else 0)}',
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.admin.POKER_BUYIN_PROMPT.value,
            keyboard=poker_buyin_count_keyboard(
                player_id=int(created_user.row_id),
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
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_add_player_text(*, user_id, text):
    if (
        text == Buttons.admin_room.ADD_PLAYER.value
        or text == Buttons.admin_room_correct.ADD_PLAYER.value
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
            players = await use_case.list_active_poker_players()
            active_vk_ids = {int(player.player_id) for player in players}
            approved_users = await user_repository.list_approved()
            candidates = [
                user
                for user in approved_users
                if user.vk_id is not None and int(user.vk_id) not in active_vk_ids
            ]
            text_out = Text.admin.POKER_ADD_PLAYER_CHOOSE.value
            if not candidates:
                text_out = f'{Text.admin.POKER_ADD_PLAYER_EMPTY.value}{InlineText.TEXT_1_16_TEXT_01_PART_1}'
        await send_vk_message(
            user_id=user_id,
            message=text_out,
            keyboard=poker_add_player_candidates_keyboard(users=candidates),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_remove_player_text(*, user_id, text):
    if (
        text == Buttons.admin_room.REMOVE_PLAYER.value
        or text == Buttons.admin_room_correct.REMOVE_PLAYER.value
    ):
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            use_case = ManagePokerPlayersUseCase(
                poker_repository=PokerRepository(session),
                poker_data_repository=PokerDataRepository(session),
            )
            players = await use_case.list_active_poker_players()
            if not players:
                await send_vk_message(user_id=user_id, message=Text.admin.POKER_PLAYERS_EMPTY.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.admin.POKER_REMOVE_PLAYER_CHOOSE.value,
            keyboard=poker_remove_player_candidates_keyboard(players=players),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_admin_room_unban_player_text(*, user_id, text):
    if text == Buttons.admin_room.UNBAN_PLAYER.value:
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            use_case = ManagePokerPlayersUseCase(
                poker_repository=PokerRepository(session),
                poker_data_repository=PokerDataRepository(session),
                poker_room_denied_repository=PokerRoomDeniedRepository(session),
                user_repository=user_repository,
            )
            denied = await use_case.list_denied_for_active_poker()
            if not denied:
                await send_vk_message(
                    user_id=user_id, message=Text.admin.POKER_UNBAN_PLAYER_EMPTY.value
                )
                return PlainTextResponse("ok")
            candidates: list[dict[str, int | str]] = []
            for item in denied:
                user = await user_repository.get_by_row_id(int(item.user_row_id))
                name = user.name if user is not None else f"ID {int(item.user_row_id)}"
                candidates.append({"player_id": int(item.user_row_id), "name": name})
        await send_vk_message(
            user_id=user_id,
            message=Text.admin.POKER_UNBAN_PLAYER_CHOOSE.value,
            keyboard=poker_unban_player_candidates_keyboard(players=candidates),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
