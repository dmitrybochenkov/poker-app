from types import SimpleNamespace

from aiogram.types import CallbackQuery, Message

from app.application.use_cases.poker.manage_players import (
    CashierCandidateNotParticipantError,
    ManagePokerPlayersUseCase,
)
from app.bot.shared.texts.inline.telegram.admin import poker as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    admin_room_correct_keyboard,
    admin_room_keyboard,
    poker_cashier_candidates_keyboard,
)
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    _clear_inline_keyboard,
    _ensure_tg_admin_callback,
    _ensure_tg_admin_message,
)
from .room_status_helpers import _refresh_admin_room_status


async def set_cashier_menu(message: Message) -> None:
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
        )
        active_players = await use_case.list_active_poker_players()
        if not active_players:
            await message.answer(Text.admin.POKER_PLAYERS_EMPTY.value)
            return
        players: list[SimpleNamespace] = []
        for player in active_players:
            user = await user_repository.get_by_row_id(int(player.player_id))
            if user is None:
                continue
            players.append(
                SimpleNamespace(player_id=int(user.row_id), player_name=player.player_name)
            )
        if not players:
            await message.answer(Text.admin.POKER_PLAYERS_EMPTY.value)
            return
    await message.answer(
        Text.admin.POKER_CASHIER_CHOOSE.value,
        reply_markup=poker_cashier_candidates_keyboard(players=players),
    )


async def open_correct_poker_menu(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
    await message.answer(
        InlineText.OPEN_CORRECT_POKER_MENU_TEXT_01, reply_markup=admin_room_correct_keyboard
    )


async def back_from_correct_poker_menu(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
    await message.answer(Text.admin.ADMIN_PANEL.value, reply_markup=admin_room_keyboard)


async def set_cashier_callback(callback: CallbackQuery) -> None:
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
            buyin_data_repository=BuyinDataRepository(session),
        )
        try:
            updated = await use_case.set_cashier_for_active_poker(cashier_id=user_row_id)
        except CashierCandidateNotParticipantError:
            await callback.answer(
                Text.admin.POKER_CASHIER_NOT_PARTICIPANT.value,
                show_alert=True,
            )
            return
        if updated is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        cashier_user = await user_repository.get_by_row_id(user_row_id)
        cashier_name = cashier_user.name if cashier_user is not None else f"ID {user_row_id}"
        cashier_text = f"{cashier_name}{InlineText.SET_CASHIER_CALLBACK_TEXT_01_PART_1}"
        await _refresh_admin_room_status(session=session)
    await callback.answer(cashier_text)


async def set_cashier_from_room_callback(callback: CallbackQuery) -> None:
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
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        poker, _ = active
        if poker.cashier_id is not None:
            await callback.answer(
                InlineText.SET_CASHIER_FROM_ROOM_CALLBACK_TEXT_01,
                show_alert=True,
            )
            return
        user_repository = UserRepository(session)
        use_case = ManagePokerPlayersUseCase(
            poker_repository=poker_repository,
            poker_data_repository=PokerDataRepository(session),
            buyin_data_repository=BuyinDataRepository(session),
        )
        try:
            updated = await use_case.set_cashier_for_active_poker(cashier_id=user_row_id)
        except CashierCandidateNotParticipantError:
            await callback.answer(
                Text.admin.POKER_CASHIER_NOT_PARTICIPANT.value,
                show_alert=True,
            )
            return
        if updated is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        cashier_user = await user_repository.get_by_row_id(user_row_id)
        cashier_name = cashier_user.name if cashier_user is not None else f"ID {user_row_id}"
        await _refresh_admin_room_status(session=session)
    await callback.answer(
        f"{cashier_name}{InlineText.SET_CASHIER_FROM_ROOM_CALLBACK_TEXT_02_PART_1}"
    )
