from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.bot.shared.texts.inline.telegram.user import poker as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    admin_room_keyboard,
    new_user_keyboard,
    poker_cashout_candidates_keyboard,
    poker_room_approve_keyboard,
    room_admin_keyboard,
    room_keyboard,
)
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import (
    poker_room_approve_keyboard as vk_poker_room_approve_keyboard,
)
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    _build_user_chips_text,
    _chips_reaction,
    _get_telegram_user,
    _money_kopecks_from_chips,
    _notify_admins_about_chips_entry,
    _notify_admins_about_room_join,
    _upsert_tg_user_chips_result,
)


async def join_poker_room(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
        return
    await state.clear()

    async with SessionFactory() as session:
        user_repository = UserRepository(session)
        user = await user_repository.get_by_telegram_id(message.from_user.id)
        if user is None:
            await message.answer(
                Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
            )
            return
        if not user.is_approved:
            await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
            return

        poker_repository = PokerRepository(session)
        poker_data_repository = PokerDataRepository(session)
        active = await poker_repository.get_started()
        ready = await poker_repository.get_latest_ready_for_chips() if active is None else None
        current_poker_date = (
            active[0].date if active is not None else (ready.date if ready is not None else None)
        )
        if current_poker_date is None:
            await message.answer(Text.user.STATUS_ROOM_CLOSED.value)
            return

        use_case = ManagePokerPlayersUseCase(
            poker_repository=poker_repository,
            poker_data_repository=poker_data_repository,
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
        )
        is_denied = await use_case.is_denied_for_active_poker(user_row_id=int(user.row_id))
        if is_denied:
            await message.answer(Text.user.STATUS_ROOM_NOT_ADDED.value)
            return
        players = await poker_data_repository.list_players(date=current_poker_date)
        if players:
            already_in_room = any(int(item.player_id) == int(user.row_id) for item in players)
            if already_in_room:
                await message.answer(
                    Text.user.ROOM_JOINED.value,
                    reply_markup=room_admin_keyboard if user.is_admin else room_keyboard,
                )
                return
        if active is None:
            await message.answer(Text.user.STATUS_ROOM_CLOSED.value)
            return
        poker, _ = active
        if poker.cashier_id is None:
            created = await use_case.add_player_to_active_poker(
                player_id=int(user.row_id), player_name=user.name
            )
            if created is None:
                await message.answer(Text.user.STATUS_ROOM_CLOSED.value)
                return
            await _notify_admins_about_room_join(
                session=session,
                joined_user=user,
                platform_label="Telegram",
            )
        else:
            players_now = await poker_data_repository.list_players(date=poker.date)
            player_row_ids = {int(item.player_id) for item in players_now}
            approved = await user_repository.list_approved()
            admins = [
                u
                for u in approved
                if u.is_admin
                and int(u.row_id) in player_row_ids
                and u.notification_platform == "tg"
                and u.telegram_id is not None
            ]
            for admin in admins:
                await message.bot.send_message(
                    chat_id=int(admin.telegram_id),
                    text=f'{InlineText.JOIN_POKER_ROOM_TEXT_01_PART_1}{user.name}{InlineText.JOIN_POKER_ROOM_TEXT_01_PART_2}',
                    reply_markup=poker_room_approve_keyboard(player_id=int(user.row_id)),
                )
            vk_admins = [
                u
                for u in approved
                if u.is_admin
                and int(u.row_id) in player_row_ids
                and u.notification_platform == "vk"
                and u.vk_id is not None
            ]
            for admin in vk_admins:
                await send_vk_message(
                    user_id=int(admin.vk_id),
                    message=f'{InlineText.JOIN_POKER_ROOM_TEXT_02_PART_1}{user.name}{InlineText.JOIN_POKER_ROOM_TEXT_02_PART_2}',
                    keyboard=vk_poker_room_approve_keyboard(player_id=int(user.row_id)),
                )
            await message.answer(InlineText.JOIN_POKER_ROOM_TEXT_03)
            return

    await message.answer(
        Text.user.ROOM_JOINED.value,
        reply_markup=room_admin_keyboard if user.is_admin else room_keyboard,
    )


async def open_room_admin_panel(message: Message) -> None:
    if message.from_user is None:
        await message.answer(
            Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard
        )
        return
    user = await _get_telegram_user(message.from_user.id)
    if user is None:
        await message.answer(
            Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
        )
        return
    if not user.is_approved:
        await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
        return
    if not user.is_admin:
        await message.answer(Text.admin.NO_RIGHTS.value, reply_markup=room_keyboard)
        return
    await message.answer(Text.admin.ADMIN_PANEL.value, reply_markup=admin_room_keyboard)


async def process_chips_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    if await state.get_state() is not None:
        return
    chips = int(message.text)
    async with SessionFactory() as session:
        user_repository = UserRepository(session)
        user = await user_repository.get_by_telegram_id(message.from_user.id)
        if user is None or not user.is_approved:
            return
        ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
        if ready is None:
            return
        poker, params = ready
        bb_size = max(1, int(params.bb_size_chips or 10))
        step = max(1, bb_size // 2)
        if chips % step != 0:
            await message.answer(Text.user.FINISH_CHIPS_INVALID.value.format(step=step))
            return
        poker_data_repository = PokerDataRepository(session)
        players = await poker_data_repository.list_players(date=poker.date)
        if not players:
            await message.answer(Text.user.FINISH_CHIPS_NOT_READY.value)
            return
        if user.is_admin:
            await state.update_data(cashout_input_value=chips)
            await message.answer(
                Text.admin.POKER_CHIPS_FOR_WHO.value.format(chips=chips),
                reply_markup=poker_cashout_candidates_keyboard(players=players),
            )
            return
        player = await poker_data_repository.get_player(date=poker.date, player_id=int(user.row_id))
        if player is None:
            await message.answer(Text.user.FINISH_CHIPS_NOT_IN_GAME.value)
            return
        money_kopecks = _money_kopecks_from_chips(
            chips=chips,
            buyins=int(player.buyins),
            buyin_size_chips=int(params.buyin_size_chips),
            buyin_size_kopecks=int(params.buyin_size_kopecks),
        )
        updated = await poker_data_repository.set_chips(
            date=poker.date, player_id=int(user.row_id), chips=chips
        )
        if updated is None:
            await message.answer(Text.user.FINISH_CHIPS_NOT_IN_GAME.value)
            return
        await poker_data_repository.set_cashout(
            date=poker.date,
            player_id=int(user.row_id),
            money_kopecks=int(money_kopecks),
        )
        await _notify_admins_about_chips_entry(
            session=session,
            player=updated,
            chips=chips,
            money_kopecks=int(money_kopecks),
        )
        await _upsert_tg_user_chips_result(
            chat_id=message.from_user.id,
            text=_build_user_chips_text(
                chips=int(chips),
                money_kopecks=int(money_kopecks),
                reaction=_chips_reaction(int(money_kopecks)),
            ),
        )
