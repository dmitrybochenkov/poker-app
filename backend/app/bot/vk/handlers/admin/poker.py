from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.application.use_cases.poker.start_poker import StartPokerUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import main_dynamic_keyboard as tg_main_dynamic_keyboard
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
)
from app.bot.vk.keyboards import (
    admin_room_correct_keyboard,
    admin_room_keyboard,
    poker_params_keyboard,
    room_admin_keyboard,
)
from app.bot.vk.keyboards import (
    main_dynamic_keyboard as vk_main_dynamic_keyboard,
)
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from fastapi.responses import PlainTextResponse

from .common import (
    HANDLER_UNMATCHED,
    _clear_event_inline_keyboard_if_possible,
    _notify_players_about_finish,
    _upsert_vk_admin_chips_status,
)


async def _event_0_08(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_start_param":
        params_id = callback_payload.get("params_id")
        if not isinstance(params_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                result_text = Text.admin.NO_RIGHTS.value
            else:
                use_case = StartPokerUseCase(
                    poker_repository=PokerRepository(session),
                    poker_param_repository=PokerParamRepository(session),
                    poker_room_denied_repository=PokerRoomDeniedRepository(session),
                )
                created = await use_case.execute(params_id=params_id)
                if created is None:
                    result_text = Text.admin.POKER_STARTED.value
                else:
                    starter = await user_repository.get_by_vk_id(admin_user_id)
                    if starter is not None:
                        await ManagePokerPlayersUseCase(
                            poker_repository=PokerRepository(session),
                            poker_data_repository=PokerDataRepository(session),
                        ).add_player_to_active_poker(
                            player_id=int(starter.row_id),
                            player_name=starter.name,
                        )
                    result_text = Text.admin.POKER_START_SUCCESS.value
                    approved_users = await user_repository.list_approved()
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
        if result_text == Text.admin.POKER_START_SUCCESS.value:
            from app.bot.telegram.runtime import telegram_bot

            if telegram_bot is not None:
                for user in approved_users:
                    if user.telegram_id is None:
                        continue
                    await telegram_bot.send_message(
                        chat_id=int(user.telegram_id),
                        text=Text.user.START_POKER.value,
                        reply_markup=tg_main_dynamic_keyboard(
                            is_admin=bool(user.is_admin),
                            has_active_poker=True,
                            has_active_poll=False,
                        ),
                    )
            for user in approved_users:
                if user.vk_id is None:
                    continue
                await send_vk_message(
                    user_id=int(user.vk_id),
                    message=Text.user.START_POKER.value,
                    keyboard=vk_main_dynamic_keyboard(
                        is_admin=bool(user.is_admin),
                        has_active_poker=True,
                        has_active_poll=False,
                    ),
                )
        return None
    return HANDLER_UNMATCHED


async def _event_0_29(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_start_betting_inline":
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text="Запускаю...",
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        return await handle_admin_text_commands(
            user_id=admin_user_id, text=Buttons.admin_room.START_BETTING.value
        )
    return HANDLER_UNMATCHED


async def _text_1_09(*, user_id, text):
    if text == Buttons.admin_main.START_POKER.value:
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            use_case = StartPokerUseCase(
                poker_repository=PokerRepository(session),
                poker_param_repository=PokerParamRepository(session),
                poker_room_denied_repository=PokerRoomDeniedRepository(session),
            )
            can_start, params = await use_case.get_start_data()
            if not can_start:
                await send_vk_message(user_id=user_id, message=Text.admin.POKER_STARTED.value)
                return PlainTextResponse("ok")
            if not params:
                await send_vk_message(user_id=user_id, message=Text.admin.POKER_PARAMS_EMPTY.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message="\n\n".join(
                [
                    Text.admin.POKER_PARAMS_CHOOSE.value,
                    *[
                        (
                            f"🎲 ID: {p.row_id}\n"
                            f"Закуп: ⭕ {p.buyin_size_chips} / 💲 {int(p.buyin_size_kopecks) // 100}\n"
                            f"ББ: {p.bb_size_chips} | 🔝 Макс закуп: {p.max_buyins}\n"
                            f"Большой / Супер закуп: 💸 {p.big_buyin} / 🤑 {p.super_buyin}"
                        )
                        for p in params
                    ],
                ]
            ),
            keyboard=poker_params_keyboard(params=params),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_10(*, user_id, text):
    if text == Buttons.admin_room.FINISH_POKER.value:
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            poker_repository = PokerRepository(session)
            active = await poker_repository.get_started()
            if active is None:
                await send_vk_message(
                    user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value
                )
                return PlainTextResponse("ok")
            poker, params = active
            poker_data_repository = PokerDataRepository(session)
            players = await poker_data_repository.list_players(date=poker.date)
            await poker_repository.finish(poker)
            await PokerRoomDeniedRepository(session).clear_all()
        await _notify_players_about_finish(players=players)
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_FINISH_SUCCESS.value)
        if players:
            async with SessionFactory() as session:
                await _upsert_vk_admin_chips_status(session=session, poker_date=players[0].date)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_14(*, user_id, text):
    if text == Buttons.admin_room.CORRECT_POKER.value:
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id, message="Корректировки покера:", keyboard=admin_room_correct_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_15(*, user_id, text):
    if text == Buttons.admin_room_correct.TO_ADMIN_ROOM.value:
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id, message=Text.admin.ADMIN_PANEL.value, keyboard=admin_room_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_21(*, user_id, text):
    if text == Buttons.admin_room.TO_ROOM.value:
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message="Покер рум.",
            keyboard=room_admin_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
