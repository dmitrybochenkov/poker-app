import random

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_tg_admin
from app.bot.shared.texts.inline.telegram.admin import players as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    poker_add_player_candidates_keyboard,
    poker_buyin_count_keyboard,
    poker_remove_player_candidates_keyboard,
    poker_room_manage_player_keyboard,
    poker_unban_player_candidates_keyboard,
)
from app.bot.telegram.states import AdminPokerState
from app.bot.vk.api import send_vk_message
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    TG_BUYIN_NOTIFY_CASHIER_ONLY,
    _clear_inline_keyboard,
    _ensure_tg_admin_callback,
    _ensure_tg_admin_message,
    _safe_callback_edit_reply_markup,
    _safe_callback_edit_text,
)
from .player_notification_helpers import (
    _notify_admins_about_removed_player,
    _notify_user_removed_from_room,
    _notify_user_unbanned_for_room,
)


async def poker_room_manage_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    _, player_id_s = str(callback.data).split(":", maxsplit=1)
    if not player_id_s.isdigit():
        await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
        return
    async with SessionFactory() as session:
        if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
            await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
            return
    if callback.message is not None:
        try:
            await _safe_callback_edit_reply_markup(
                callback,
                reply_markup=poker_room_manage_player_keyboard(player_id=int(player_id_s)),
            )
        except Exception:
            await callback.message.answer(
                InlineText.POKER_ROOM_MANAGE_CALLBACK_TEXT_01,
                reply_markup=poker_room_manage_player_keyboard(player_id=int(player_id_s)),
            )
    await callback.answer()


async def poker_room_approve_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    _, player_id_s = str(callback.data).split(":", maxsplit=1)
    if not player_id_s.isdigit():
        await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
        return
    user_row_id = int(player_id_s)
    async with SessionFactory() as session:
        if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
            await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
            return
        user_repository = UserRepository(session)
        candidate = await user_repository.get_by_row_id(user_row_id)
        if candidate is None:
            await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
            return
        use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
        )
        created = await use_case.add_player_to_active_poker_and_allow(
            player_id=int(candidate.row_id),
            player_name=candidate.name,
        )
        if created is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
    await _clear_inline_keyboard(callback)
    await callback.answer(InlineText.POKER_ROOM_APPROVE_CALLBACK_TEXT_01)
    if callback.message is not None:
        await callback.message.answer(f'{candidate.name}{InlineText.POKER_ROOM_APPROVE_CALLBACK_TEXT_02_PART_1}')
    if candidate.telegram_id is not None and callback.message is not None:
        await callback.message.bot.send_message(
            chat_id=int(candidate.telegram_id), text=InlineText.POKER_ROOM_APPROVE_CALLBACK_TEXT_03
        )
    elif candidate.vk_id is not None:
        await send_vk_message(user_id=int(candidate.vk_id), message=InlineText.POKER_ROOM_APPROVE_CALLBACK_TEXT_04)


async def poker_room_reject_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    _, player_id_s = str(callback.data).split(":", maxsplit=1)
    if not player_id_s.isdigit():
        await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
        return
    user_row_id = int(player_id_s)
    async with SessionFactory() as session:
        if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
            await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
            return
        user_repository = UserRepository(session)
        candidate = await user_repository.get_by_row_id(user_row_id)
        if candidate is None:
            await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
            return
        await PokerRoomDeniedRepository(session).add(user_row_id=int(candidate.row_id))
    await _clear_inline_keyboard(callback)
    await callback.answer(InlineText.POKER_ROOM_REJECT_CALLBACK_TEXT_01)
    if callback.message is not None:
        await callback.message.answer(f'{candidate.name}{InlineText.POKER_ROOM_REJECT_CALLBACK_TEXT_02_PART_1}')
    if candidate.telegram_id is not None and callback.message is not None:
        await callback.message.bot.send_message(
            chat_id=int(candidate.telegram_id), text=InlineText.POKER_ROOM_REJECT_CALLBACK_TEXT_03
        )
    elif candidate.vk_id is not None:
        await send_vk_message(user_id=int(candidate.vk_id), message=InlineText.POKER_ROOM_REJECT_CALLBACK_TEXT_04)


async def add_player_menu(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
        user_repository = UserRepository(session)
        use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            user_repository=user_repository,
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
        )
        players = await use_case.list_active_poker_players()
        active_user_row_ids = {int(player.player_id) for player in players}
        approved_users = await user_repository.list_approved()
        candidates = [
            user
            for user in approved_users
            if user.telegram_id is not None and int(user.row_id) not in active_user_row_ids
        ]
        text = Text.admin.POKER_ADD_PLAYER_CHOOSE.value
        if not candidates:
            text = f'{Text.admin.POKER_ADD_PLAYER_EMPTY.value}{InlineText.ADD_PLAYER_MENU_TEXT_01_PART_1}'
    await message.answer(
        text,
        reply_markup=poker_add_player_candidates_keyboard(users=candidates),
    )


async def add_player_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    row_id = int(callback.data.split(":", 1)[1])
    await _clear_inline_keyboard(callback)
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return
        user_repository = UserRepository(session)
        user = await user_repository.get_by_row_id(row_id)
        if user is None or user.telegram_id is None:
            await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
            return
        use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
        )
        created = await use_case.add_player_to_active_poker_and_allow(
            player_id=int(user.row_id),
            player_name=user.name,
        )
        if created is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        poker, params = await PokerRepository(session).get_started()
        self_player = await PokerDataRepository(session).get_player(
            poker_id=int(poker.row_id), player_id=int(user.row_id)
        )
        include_king_buyin = bool(self_player is not None and self_player.is_prev_winner)
        current_big_buyin_count = int(self_player.big_buyin_count) if self_player is not None else 0
        current_super_buyin_count = (
            int(self_player.super_buyin_count) if self_player is not None else 0
        )
    if callback.message is not None:
        await callback.message.answer(
            f'{InlineText.ADD_PLAYER_CALLBACK_TEXT_01_PART_1}{user.name}{InlineText.ADD_PLAYER_CALLBACK_TEXT_01_PART_2}{(int(self_player.buyins) if self_player is not None else 0)}'
        )
        TG_BUYIN_NOTIFY_CASHIER_ONLY.add((int(callback.from_user.id), int(user.row_id)))
        await callback.message.answer(
            Text.admin.POKER_BUYIN_PROMPT.value,
            reply_markup=poker_buyin_count_keyboard(
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
            ),
        )
    await callback.answer(InlineText.ADD_PLAYER_CALLBACK_TEXT_02)


async def add_player_new_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return
    await _clear_inline_keyboard(callback)
    await state.set_state(AdminPokerState.waiting_for_new_player_name)
    if callback.message is not None:
        await callback.message.answer(InlineText.ADD_PLAYER_NEW_CALLBACK_TEXT_01)
    await callback.answer()


async def add_player_cancel_callback(callback: CallbackQuery) -> None:
    await _clear_inline_keyboard(callback)
    await callback.answer(Buttons.betting_inline.CONFIRM_NO.value)


async def add_new_player_name_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    name = " ".join((message.text or "").split())
    if not name:
        await message.answer(InlineText.ADD_NEW_PLAYER_NAME_INPUT_TEXT_01)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            await state.clear()
            return
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
        created = await use_case.add_player_to_active_poker_and_allow(
            player_id=int(created_user.row_id),
            player_name=created_user.name,
        )
        if created is None:
            await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
            await state.clear()
            return
        poker, params = await PokerRepository(session).get_started()
        self_player = await PokerDataRepository(session).get_player(
            poker_id=int(poker.row_id), player_id=int(created_user.row_id)
        )
        include_king_buyin = bool(self_player is not None and self_player.is_prev_winner)
        current_big_buyin_count = int(self_player.big_buyin_count) if self_player is not None else 0
        current_super_buyin_count = (
            int(self_player.super_buyin_count) if self_player is not None else 0
        )
    await state.clear()
    await message.answer(
        f'{InlineText.ADD_NEW_PLAYER_NAME_INPUT_TEXT_02_PART_1}{created_user.name}{InlineText.ADD_NEW_PLAYER_NAME_INPUT_TEXT_02_PART_2}{(int(self_player.buyins) if self_player is not None else 0)}'
    )
    TG_BUYIN_NOTIFY_CASHIER_ONLY.add((int(message.from_user.id), int(created_user.row_id)))
    await message.answer(
        Text.admin.POKER_BUYIN_PROMPT.value,
        reply_markup=poker_buyin_count_keyboard(
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


async def remove_player_menu(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
        user_repository = UserRepository(session)
        use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            buyin_data_repository=BuyinDataRepository(session),
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
            user_repository=user_repository,
        )
        players = await use_case.list_active_poker_players()
        if not players:
            await message.answer(Text.admin.POKER_PLAYERS_EMPTY.value)
            return
    await message.answer(
        Text.admin.POKER_REMOVE_PLAYER_CHOOSE.value,
        reply_markup=poker_remove_player_candidates_keyboard(players=players),
    )


async def remove_player_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    player_id = int(callback.data.split(":", 1)[1])
    await _clear_inline_keyboard(callback)
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return
        user_repository = UserRepository(session)
        use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
            user_repository=user_repository,
        )
        removed_user = await user_repository.get_by_row_id(player_id)
        active = await PokerRepository(session).get_started()
        removed_player_name = removed_user.name if removed_user is not None else f"ID {player_id}"
        removed_player_buyins = 0
        poker_date = None
        if active is not None:
            poker_date = active[0].date
            player_before_remove = await PokerDataRepository(session).get_player(
                poker_id=int(active[0].row_id), player_id=player_id
            )
            if player_before_remove is not None:
                removed_player_name = str(player_before_remove.player_name)
                removed_player_buyins = int(player_before_remove.buyins)
        removed = await use_case.remove_player_from_active_poker(player_id=player_id)
        if removed is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        if removed is False:
            await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
            return
        if removed_user is not None:
            await _notify_user_removed_from_room(user=removed_user)
        if poker_date is not None:
            await _notify_admins_about_removed_player(
                session=session,
                poker_date=poker_date,
                player_name=removed_player_name,
                buyins=removed_player_buyins,
            )
    if callback.message is not None:
        try:
            await callback.message.delete()
        except Exception:
            pass
    await callback.answer(Text.admin.POKER_REMOVE_PLAYER_SUCCESS.value)


async def unban_player_menu(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
        user_repository = UserRepository(session)
        use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
            user_repository=user_repository,
        )
        denied = await use_case.list_denied_for_active_poker()
        if not denied:
            await message.answer(Text.admin.POKER_UNBAN_PLAYER_EMPTY.value)
            return
        candidates: list[dict[str, int | str]] = []
        for item in denied:
            user = await user_repository.get_by_row_id(int(item.user_row_id))
            name = user.name if user is not None else f"ID {int(item.user_row_id)}"
            candidates.append({"player_id": int(item.user_row_id), "name": name})
    await message.answer(
        Text.admin.POKER_UNBAN_PLAYER_CHOOSE.value,
        reply_markup=poker_unban_player_candidates_keyboard(players=candidates),
    )


async def unban_player_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    user_row_id = int(callback.data.split(":", 1)[1])
    await _clear_inline_keyboard(callback)
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return
        user_repository = UserRepository(session)
        use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
            user_repository=user_repository,
        )
        unbanned_user = await user_repository.get_by_row_id(user_row_id)
        removed = await use_case.remove_denied_for_active_poker(user_row_id=user_row_id)
        if not removed:
            await callback.answer(Text.admin.POKER_UNBAN_PLAYER_EMPTY.value, show_alert=True)
            return
        if unbanned_user is not None:
            await _notify_user_unbanned_for_room(user=unbanned_user)
    if callback.message is not None:
        await _safe_callback_edit_text(callback, Text.admin.POKER_UNBAN_PLAYER_SUCCESS.value)
    await callback.answer(Text.admin.POKER_UNBAN_PLAYER_SUCCESS.value)
