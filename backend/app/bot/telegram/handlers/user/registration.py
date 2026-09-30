from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.bot.shared.texts.inline.telegram.user import registration as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    new_user_keyboard,
    played_before_keyboard,
    registration_candidates_keyboard,
    registration_candidates_page_keyboard,
    registration_optional_details_keyboard,
    registration_platform_keyboard,
)
from app.bot.telegram.states import RegistrationState
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    REGISTRATION_USER_STATES,
    _approved_tg_keyboard,
    _delete_message_if_possible,
    _normalize_phone,
    _submit_registration_request,
)


async def start_command(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer(
            Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard
        )
        return

    await state.clear()
    reply_markup = new_user_keyboard
    async with SessionFactory() as session:
        repository = UserRepository(session)
        existing_user = await repository.get_by_telegram_id(message.from_user.id)
        if existing_user is not None and existing_user.is_approved:
            reply_markup = await _approved_tg_keyboard(existing_user)

    await message.answer(
        Text.user.BOT_INFO.value,
        reply_markup=reply_markup,
    )


async def start_registration(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
        return

    current_state = await state.get_state()
    if current_state in REGISTRATION_USER_STATES:
        await message.answer(Text.user.REGISTRATION_IN_PROGRESS.value)
        return

    async with SessionFactory() as session:
        repository = UserRepository(session)
        existing_user = await repository.get_by_telegram_id(message.from_user.id)

    if existing_user is not None:
        await state.clear()
        if existing_user.is_approved:
            await message.answer(
                Text.user.REGISTRATION_EXIST.value,
                reply_markup=await _approved_tg_keyboard(existing_user),
            )
            return
        await message.answer(Text.user.REGISTRATION_PENDING.value, reply_markup=new_user_keyboard)
        return

    await state.set_state(RegistrationState.waiting_for_played_before_answer)
    await message.answer(
        Text.user.REGISTRATION_PLAYED_BEFORE_Q.value,
        reply_markup=played_before_keyboard(),
    )


async def show_bot_info(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer(
            Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard
        )
        return

    await state.clear()
    reply_markup = new_user_keyboard
    async with SessionFactory() as session:
        repository = UserRepository(session)
        existing_user = await repository.get_by_telegram_id(message.from_user.id)
        if existing_user is not None and existing_user.is_approved:
            reply_markup = await _approved_tg_keyboard(existing_user)

    await message.answer(
        Text.user.BOT_INFO.value,
        reply_markup=reply_markup,
    )


async def show_user_status(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
        return

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

        use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
        )
        is_denied = await use_case.is_denied_for_active_poker(user_row_id=int(user.row_id))
        if is_denied:
            await message.answer(Text.user.STATUS_ROOM_NOT_ADDED.value)
            return
        players = await use_case.list_active_poker_players()
        if not players:
            await message.answer(Text.user.STATUS_ROOM_CLOSED.value)
            return

        current_player = next(
            (item for item in players if int(item.player_id) == int(user.row_id)), None
        )
        if current_player is None:
            await message.answer(Text.user.STATUS_ROOM_NOT_ADDED.value)
            return

        lines: list[str] = [InlineText.SHOW_USER_STATUS_TEXT_01]
        if user.is_admin:
            active = await PokerRepository(session).get_started()
            bet_row_ids: set[int] = set()
            bet_name_by_id: dict[int, str] = {}
            better_row_by_id: dict[int, int] = {}
            if active is not None:
                poker, _ = active
                bets = await BetRepository(session).list_for_poker(poker_id=int(poker.row_id))
                for bet in bets:
                    better_id = int(bet.better_id)
                    better_user = await user_repository.get_by_row_id(better_id)
                    if better_user is not None:
                        better_row_id = int(better_user.row_id)
                        bet_row_ids.add(better_row_id)
                        better_row_by_id[better_id] = better_row_id
                    else:
                        # better_id in bets is expected to be users.row_id
                        bet_row_ids.add(better_id)
                        better_row_by_id[better_id] = better_id
                    bet_name_by_id[better_id] = bet.better_name
            player_ids = {int(p.player_id) for p in players}
            for p in players:
                if int(p.player_id) in bet_row_ids:
                    lines.append(f'{p.player_name}{InlineText.SHOW_USER_STATUS_MARKER_01_PART_2}{p.buyins}')
                else:
                    lines.append(f"{p.player_name}: {p.buyins}")
            outsider_ids = [
                better_id
                for better_id in bet_name_by_id.keys()
                if better_row_by_id.get(better_id) not in player_ids
            ]
            outsider_ids.sort()
            for better_id in outsider_ids:
                better_name = bet_name_by_id.get(better_id, f"ID {better_id}")
                lines.append(f'{better_name}{InlineText.SHOW_USER_STATUS_MARKER_02_PART_2}')
        else:
            for p in players:
                lines.append(f"{p.player_name}: {p.buyins}")

    await message.answer("\n".join(lines))


async def choose_registration_branch(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return

    choice = callback.data.split(":", 1)[1]
    if choice == "yes":
        await _delete_message_if_possible(callback)
        async with SessionFactory() as session:
            repository = UserRepository(session)
            candidates = await repository.list_approved_without_telegram_id()

        if not candidates:
            await state.set_state(RegistrationState.waiting_for_new_name)
            await callback.message.answer(Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value)
        else:
            await state.clear()
            await callback.message.answer(
                Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
                reply_markup=registration_candidates_keyboard(users=candidates),
            )
    else:
        await _delete_message_if_possible(callback)
        await state.set_state(RegistrationState.waiting_for_new_name)
        await callback.message.answer(Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
    await callback.answer()


async def repeat_registration_branch_prompt(message: Message) -> None:
    await message.answer(
        Text.user.REGISTRATION_PLAYED_BEFORE_Q.value,
        reply_markup=played_before_keyboard(),
    )


async def finish_existing_row_id_registration(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.from_user is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return

    selected_value = callback.data.split(":", 1)[1]
    await _delete_message_if_possible(callback)
    if selected_value == "new":
        await state.set_state(RegistrationState.waiting_for_new_name)
        if callback.message is not None:
            await callback.message.answer(Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
        await callback.answer()
        return

    selected_row_id = int(selected_value)
    async with SessionFactory() as session:
        repository = UserRepository(session)
        selected_user = await repository.get_by_row_id(selected_row_id)
        if (
            selected_user is None
            or not selected_user.is_approved
            or selected_user.telegram_id is not None
        ):
            await callback.answer(Text.user.REGISTRATION_CHOOSE_FROM_LIST.value, show_alert=True)
            return

    await state.set_state(RegistrationState.waiting_for_registration_platform_choice)
    await state.update_data(
        linked_user_row_id=selected_user.row_id,
        linked_user_name=selected_user.name,
    )
    if callback.message is not None:
        await callback.message.answer(
            Text.user.REGISTRATION_PLATFORM_PROMPT.value,
            reply_markup=registration_platform_keyboard(),
        )
    await callback.answer()


async def registration_existing_page(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    page = int(callback.data.split(":", 1)[1])
    async with SessionFactory() as session:
        repository = UserRepository(session)
        candidates = await repository.list_approved_without_telegram_id()
    await _delete_message_if_possible(callback)
    if not candidates:
        await callback.message.answer(Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value)
        await callback.answer()
        return
    await callback.message.answer(
        Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
        reply_markup=registration_candidates_page_keyboard(users=candidates, page=page),
    )
    await callback.answer()


async def choose_registration_platform(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.from_user is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    await _delete_message_if_possible(callback)
    platform = callback.data.split(":", 1)[1]
    if platform not in {"tg", "vk"}:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return

    data = await state.get_data()
    selected_name = data.get("linked_user_name")
    selected_row_id = data.get("linked_user_row_id")
    if not selected_name or not selected_row_id:
        await state.clear()
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return

    async with SessionFactory() as session:
        repository = UserRepository(session)
        linked_user = await repository.get_by_row_id(int(selected_row_id))
        if linked_user is None:
            await state.clear()
            await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
            return

    await _submit_registration_request(
        message=callback.message,
        state=state,
        name=selected_name,
        success_text=Text.user.REGISTRATION_WAIT.value,
        linked_to_user=linked_user,
        requester_telegram_id=callback.from_user.id,
        notification_platform=platform,
    )
    await callback.answer()


async def finish_registration(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
        return

    name = " ".join(message.text.split())
    await state.set_state(RegistrationState.waiting_for_optional_details_action)
    await state.update_data(
        registration_name=name,
        bank_name=None,
        tel_number=None,
    )
    await message.answer(
        Text.user.REGISTRATION_OPTIONAL_DETAILS_PROMPT.value,
        reply_markup=registration_optional_details_keyboard(),
    )


async def choose_optional_registration_data(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.from_user is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return

    action = callback.data.split(":", 1)[1]
    await _delete_message_if_possible(callback)
    if action == "bank":
        await state.set_state(RegistrationState.waiting_for_bank_name)
        await callback.message.answer(Text.user.REGISTRATION_BANK_PROMPT.value)
        await callback.answer()
        return
    if action == "phone":
        await state.set_state(RegistrationState.waiting_for_phone)
        await callback.message.answer(Text.user.REGISTRATION_PHONE_PROMPT.value)
        await callback.answer()
        return

    data = await state.get_data()
    registration_name = data.get("registration_name")
    if not registration_name:
        await state.clear()
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    await _submit_registration_request(
        message=callback.message,
        state=state,
        name=registration_name,
        success_text=Text.user.REGISTRATION_WAIT.value,
        requester_telegram_id=callback.from_user.id,
        bank_name=data.get("bank_name"),
        tel_number=data.get("tel_number"),
    )
    await callback.answer()


async def save_optional_bank_name(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer(Text.user.REGISTRATION_BANK_PROMPT.value)
        return
    bank_name = " ".join(message.text.split()).title()
    if not bank_name:
        await message.answer(Text.user.REGISTRATION_BANK_PROMPT.value)
        return
    data = await state.get_data()
    await state.update_data(bank_name=bank_name)
    existing_phone = data.get("tel_number")
    if existing_phone:
        registration_name = data.get("registration_name")
        if not registration_name:
            await state.clear()
            await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
            return
        await _submit_registration_request(
            message=message,
            state=state,
            name=registration_name,
            success_text=Text.user.REGISTRATION_WAIT.value,
            bank_name=bank_name,
            tel_number=existing_phone,
        )
        return

    await state.set_state(RegistrationState.waiting_for_phone)
    await message.answer(Text.user.REGISTRATION_PHONE_PROMPT.value)


async def save_optional_phone(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer(Text.user.REGISTRATION_PHONE_PROMPT.value)
        return
    normalized_phone = _normalize_phone(message.text)
    if normalized_phone is None:
        await message.answer(Text.user.REGISTRATION_PHONE_INVALID.value)
        return
    data = await state.get_data()
    await state.update_data(tel_number=normalized_phone)
    existing_bank = data.get("bank_name")
    if existing_bank:
        registration_name = data.get("registration_name")
        if not registration_name:
            await state.clear()
            await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
            return
        await _submit_registration_request(
            message=message,
            state=state,
            name=registration_name,
            success_text=Text.user.REGISTRATION_WAIT.value,
            bank_name=existing_bank,
            tel_number=normalized_phone,
        )
        return

    await state.set_state(RegistrationState.waiting_for_bank_name)
    await message.answer(Text.user.REGISTRATION_BANK_PROMPT.value)


async def repeat_optional_registration_prompt(message: Message) -> None:
    await message.answer(
        Text.user.REGISTRATION_OPTIONAL_DETAILS_PROMPT.value,
        reply_markup=registration_optional_details_keyboard(),
    )
