from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.application.use_cases.poker.enter_player_chips import EnterPlayerChipsUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_tg_admin
from app.bot.shared.texts.inline.telegram.admin import buyins as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    poker_buyin_candidates_keyboard,
    poker_buyin_correct_confirm_keyboard,
    poker_buyin_count_keyboard,
)
from app.bot.telegram.states import AdminPokerState
from app.bot.vk.api import send_vk_message
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    TG_BUYIN_NOTIFY_CASHIER_ONLY,
    _clear_inline_keyboard,
    _ensure_tg_admin_callback,
    _ensure_tg_admin_message,
    _notify_about_buyin,
)
from .poker_helpers import (
    _build_user_chips_text,
    _get_reaction,
    _upsert_tg_admin_chips_status,
    _upsert_tg_user_chips_result,
)


async def buyin_menu(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        user_repository = UserRepository(session)
        user = await user_repository.get_by_telegram_id(message.from_user.id)
        if user is None or not user.is_approved:
            await message.answer(Text.user.STATUS_NEED_REGISTRATION.value)
            return
        is_admin = await is_tg_admin(session=session, telegram_id=message.from_user.id)
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
            await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
            return
        poker, params = active
        if poker.is_ready_for_chips_entering:
            await message.answer(Text.user.FINISH_CHIPS_NOT_READY.value)
            return
        if poker.cashier_id is None:
            await message.answer(Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value)
            return
        poker_data_repository = PokerDataRepository(session)
        players = await poker_data_repository.list_players(date=poker.date)
        if not players:
            await message.answer(Text.admin.POKER_BUYIN_EMPTY.value)
            return

        is_correct_mode = message.text == Buttons.admin_room_correct.BUYIN_CORRECT.value
        if is_admin:
            prompt_text = (
                Text.admin.POKER_BUYIN_CORRECT_CHOOSE.value
                if is_correct_mode
                else Text.admin.POKER_BUYIN_CHOOSE.value
            )
            await message.answer(
                prompt_text,
                reply_markup=poker_buyin_candidates_keyboard(
                    players=players,
                    show_buyins=is_correct_mode,
                    callback_prefix="pokerbuyincorrect" if is_correct_mode else "pokerbuyin",
                ),
            )
            return

        self_player = await poker_data_repository.get_player(
            date=poker.date, player_id=int(user.row_id)
        )
        if self_player is None:
            await message.answer(Text.user.STATUS_ROOM_NOT_ADDED.value)
            return
        include_king_buyin = bool(self_player.is_prev_winner)
        await message.answer(
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
                current_big_buyin_count=int(self_player.big_buyin_count),
                current_super_buyin_count=int(self_player.super_buyin_count),
            ),
        )


async def buyin_select_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    player_id = int(callback.data.split(":", 1)[1])
    source_message = callback.message
    await _clear_inline_keyboard(callback)
    async with SessionFactory() as session:
        if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
            await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
            return
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        poker, params = active
        if poker.is_ready_for_chips_entering:
            await callback.answer(Text.user.FINISH_CHIPS_NOT_READY.value, show_alert=True)
            return
        if poker.cashier_id is None:
            await callback.answer(Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value, show_alert=True)
            return
        player = await PokerDataRepository(session).get_player(date=poker.date, player_id=player_id)
        include_king_buyin = bool(player is not None and player.is_prev_winner)
        current_big_buyin_count = int(player.big_buyin_count) if player is not None else 0
        current_super_buyin_count = int(player.super_buyin_count) if player is not None else 0
    if source_message is not None:
        try:
            await source_message.delete()
        except Exception:
            pass
        await source_message.answer(
            Text.admin.POKER_BUYIN_PROMPT.value,
            reply_markup=poker_buyin_count_keyboard(
                player_id=player_id,
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
    await callback.answer()


async def buyin_correct_select_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    player_id = int(callback.data.split(":", 1)[1])
    await _clear_inline_keyboard(callback)
    async with SessionFactory() as session:
        if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
            await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
            return
        active = await PokerRepository(session).get_started()
        if active is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        poker, _ = active
        player = await PokerDataRepository(session).get_player(date=poker.date, player_id=player_id)
        if player is None:
            await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
            return
        await state.set_state(AdminPokerState.waiting_for_buyin_correct_amount)
        await state.update_data(
            buyin_correct_player_id=int(player_id),
            buyin_correct_player_name=str(player.player_name),
            buyin_correct_old_buyins=int(player.buyins),
        )
    if callback.message is not None:
        await callback.message.answer(
            f'{InlineText.BUYIN_CORRECT_SELECT_CALLBACK_TEXT_01_PART_1}{player.player_name}{InlineText.BUYIN_CORRECT_SELECT_CALLBACK_TEXT_01_PART_2}{int(player.buyins)}'
        )
    await callback.answer()


async def buyin_correct_amount_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    if not message.text.isdigit():
        await message.answer(Text.admin.POKER_BUYIN_INVALID.value)
        return
    new_buyins = int(message.text)
    data = await state.get_data()
    player_id = int(data.get("buyin_correct_player_id", 0))
    old_buyins = int(data.get("buyin_correct_old_buyins", 0))
    player_name = str(data.get("buyin_correct_player_name", InlineText.BUYIN_CORRECT_AMOUNT_INPUT_TEXT_01))
    if player_id <= 0:
        await state.clear()
        await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
        return
    await message.answer(
        f'{InlineText.BUYIN_CORRECT_AMOUNT_INPUT_TEXT_02_PART_1}{player_name}{InlineText.BUYIN_CORRECT_AMOUNT_INPUT_TEXT_02_PART_2}{old_buyins}{InlineText.BUYIN_CORRECT_AMOUNT_INPUT_TEXT_02_PART_3}{new_buyins}',
        reply_markup=poker_buyin_correct_confirm_keyboard(
            player_id=player_id, new_buyins=new_buyins
        ),
    )


async def buyin_correct_confirm_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    parts = str(callback.data).split(":")
    if len(parts) != 4:
        await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
        return
    choice, player_id_s, new_buyins_s = parts[1], parts[2], parts[3]
    if not (player_id_s.isdigit() and new_buyins_s.isdigit()):
        await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
        return
    player_id = int(player_id_s)
    new_buyins = int(new_buyins_s)
    await _clear_inline_keyboard(callback)
    if choice != "yes":
        await state.clear()
        await callback.answer(Buttons.betting_inline.CONFIRM_NO.value)
        return
    async with SessionFactory() as session:
        if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
            await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
            await state.clear()
            return
        active = await PokerRepository(session).get_started()
        if active is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            await state.clear()
            return
        poker, _ = active
        poker_data_repository = PokerDataRepository(session)
        player = await poker_data_repository.get_player(date=poker.date, player_id=player_id)
        if player is None:
            await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
            await state.clear()
            return
        old_buyins = int(player.buyins)
        delta = int(new_buyins) - old_buyins
        if delta != 0:
            updated = await poker_data_repository.add_buyins(
                date=poker.date,
                player_id=player_id,
                buyins_count=delta,
                big_buyin_count=0,
                super_buyin_count=0,
            )
            if updated is None:
                await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
                await state.clear()
                return
        else:
            updated = player
    await state.clear()
    if callback.message is not None:
        await callback.message.answer(
            f"{Text.admin.POKER_BUYIN_SAVED.value}\n\n{updated.player_name}: {updated.buyins}"
        )
    await callback.answer(Text.admin.POKER_BUYIN_SAVED.value)


async def buyin_count_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer(Text.admin.POKER_BUYIN_INVALID.value, show_alert=True)
        return
    player_id = int(parts[1])
    buyins_count = int(parts[2])
    if buyins_count <= 0:
        await callback.answer(Text.admin.POKER_BUYIN_INVALID.value, show_alert=True)
        return
    source_message = callback.message
    await _clear_inline_keyboard(callback)
    async with SessionFactory() as session:
        is_admin = await is_tg_admin(session=session, telegram_id=callback.from_user.id)
        requester = await UserRepository(session).get_by_telegram_id(callback.from_user.id)
        requester_row_id = int(requester.row_id) if requester is not None else -1
        if not is_admin and int(player_id) != requester_row_id:
            await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
            return
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        poker, params = active
        if poker.is_ready_for_chips_entering:
            await callback.answer(Text.user.FINISH_CHIPS_NOT_READY.value, show_alert=True)
            return
        if poker.cashier_id is None:
            await callback.answer(Text.admin.POKER_BUYIN_CASHIER_REQUIRED.value, show_alert=True)
            return
        prev_player = await PokerDataRepository(session).get_player(
            date=poker.date, player_id=player_id
        )
        is_special_mode = int(params.max_buyins) == 2
        include_king_buyin = bool(prev_player is not None and prev_player.is_prev_winner)
        big_threshold = int(params.big_buyin or 5)
        super_threshold = int(params.super_buyin or 10)
        king_threshold = int(params.king_buyin or 15)
        current_big_count = int(prev_player.big_buyin_count) if prev_player is not None else 0
        current_super_count = int(prev_player.super_buyin_count) if prev_player is not None else 0
        if is_special_mode:
            allowed_special_amounts: set[int] = set()
            if current_super_count == 0 and current_big_count < 2:
                allowed_special_amounts.add(big_threshold)
            if current_super_count == 0 and current_big_count == 0:
                allowed_special_amounts.add(super_threshold)
                if include_king_buyin:
                    allowed_special_amounts.add(king_threshold)
            if (
                buyins_count > int(params.max_buyins)
                and buyins_count not in allowed_special_amounts
            ):
                await callback.answer(Text.admin.POKER_BUYIN_INVALID.value, show_alert=True)
                return
        big_count = 0
        super_count = 0
        if is_special_mode:
            if (
                include_king_buyin
                and current_big_count == 0
                and current_super_count == 0
                and buyins_count >= king_threshold
            ):
                big_count += 1
                super_count += 1
            elif buyins_count >= super_threshold:
                if current_big_count == 0 and current_super_count == 0:
                    super_count += 1
                elif (
                    current_super_count == 0
                    and current_big_count < 2
                    and buyins_count >= big_threshold
                ):
                    big_count += 1
            elif (
                current_super_count == 0 and current_big_count < 2 and buyins_count >= big_threshold
            ):
                big_count += 1
        use_case = ManagePokerPlayersUseCase(
            poker_repository=poker_repository,
            poker_data_repository=PokerDataRepository(session),
            buyin_data_repository=BuyinDataRepository(session),
        )
        updated = await use_case.add_buyin_to_active_player(
            player_id=int(player_id),
            buyins_count=buyins_count,
            big_buyin_count=big_count,
            super_buyin_count=super_count,
            poker_date=poker.date,
        )
        if updated is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        notify_admins = True
        key = (int(callback.from_user.id), int(player_id))
        if key in TG_BUYIN_NOTIFY_CASHIER_ONLY:
            notify_admins = False
            TG_BUYIN_NOTIFY_CASHIER_ONLY.discard(key)
        await _notify_about_buyin(
            session=session,
            poker=poker,
            updated_player=updated,
            buyins_count=buyins_count,
            notify_admins=notify_admins,
        )
    if source_message is not None:
        try:
            await source_message.delete()
        except Exception:
            pass
    await callback.answer(Text.admin.POKER_BUYIN_SAVED.value)


async def buyin_cancel_callback(callback: CallbackQuery) -> None:
    source_message = callback.message
    await _clear_inline_keyboard(callback)
    if source_message is not None:
        try:
            await source_message.delete()
        except Exception:
            pass
    await callback.answer(Buttons.betting_inline.CONFIRM_NO.value)


async def cashout_select_callback(callback: CallbackQuery, state: FSMContext) -> None:
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
        poker_repository = PokerRepository(session)
        poker_data_repository = PokerDataRepository(session)
        ready = await poker_repository.get_latest_ready_for_chips_with_params()
        if ready is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        poker, params = ready
        player = await poker_data_repository.get_player(date=poker.date, player_id=player_id)
        if player is None:
            await callback.answer(Text.admin.USER_NOT_FOUND.value, show_alert=True)
            return
        data = await state.get_data()
        chips_value = data.get("cashout_input_value")
        if chips_value is not None:
            chips = int(chips_value)
            bb_size = max(1, int(params.bb_size_chips or 10))
            step = max(1, bb_size // 2)
            if chips % step != 0:
                await state.update_data(cashout_input_value=None)
                if callback.message is not None:
                    await callback.message.answer(
                        Text.user.FINISH_CHIPS_INVALID.value.format(step=step)
                    )
                await callback.answer()
                return
            actor = await user_repository.get_by_telegram_id(callback.from_user.id)
            updated = await EnterPlayerChipsUseCase(session).execute(
                actor_user_id=int(actor.row_id),
                player_user_id=player_id,
                chips=chips,
            )
            money_kopecks = updated.money_kopecks
            await _upsert_tg_admin_chips_status(
                session=session, poker_date=updated.poker_date
            )
            await state.update_data(cashout_input_value=None)
            if updated is not None:
                user = await user_repository.get_by_row_id(int(updated.player_id))
                if (
                    user is not None
                    and user.notification_platform == "tg"
                    and user.telegram_id is not None
                ):
                    await _upsert_tg_user_chips_result(
                        chat_id=int(user.telegram_id),
                        text=_build_user_chips_text(
                            chips=int(chips),
                            money_kopecks=int(money_kopecks),
                            reaction=_get_reaction(
                                "winner" if int(money_kopecks) >= 0 else "loser"
                            ),
                        ),
                    )
                elif (
                    user is not None
                    and user.notification_platform == "vk"
                    and user.vk_id is not None
                ):
                    await send_vk_message(
                        user_id=user.vk_id,
                        message=_build_user_chips_text(
                            chips=int(chips),
                            money_kopecks=int(money_kopecks),
                            reaction=_get_reaction(
                                "winner" if int(money_kopecks) >= 0 else "loser"
                            ),
                        ),
                    )
            if callback.message is not None:
                try:
                    await callback.message.delete()
                except Exception:
                    pass
            await callback.answer(Text.admin.POKER_CASHOUT_SAVED.value)
            return
    await state.set_state(AdminPokerState.waiting_for_cashout_amount)
    await state.update_data(cashout_player_id=player_id)
    if callback.message is not None:
        await callback.message.answer(Text.admin.POKER_CASHOUT_PROMPT.value)
    await callback.answer()


async def cashout_amount_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        await message.answer(Text.admin.POKER_CASHOUT_INVALID.value)
        return
    if not message.text.isdigit() or int(message.text) < 0:
        await message.answer(Text.admin.POKER_CASHOUT_INVALID.value)
        return
    chips = int(message.text)
    target_user = None
    data = await state.get_data()
    player_id = data.get("cashout_player_id")
    if player_id is None:
        await state.clear()
        await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            await state.clear()
            return
        user_repository = UserRepository(session)
        ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
        if ready is None:
            await state.clear()
            await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
            return
        poker, params = ready
        bb_size = max(1, int(params.bb_size_chips or 10))
        step = max(1, bb_size // 2)
        if chips % step != 0:
            await message.answer(Text.user.FINISH_CHIPS_INVALID.value.format(step=step))
            return
        actor = await user_repository.get_by_telegram_id(message.from_user.id)
        updated = await EnterPlayerChipsUseCase(session).execute(
            actor_user_id=int(actor.row_id),
            player_user_id=int(player_id),
            chips=chips,
        )
        money_kopecks = updated.money_kopecks
        await _upsert_tg_admin_chips_status(
            session=session, poker_date=updated.poker_date
        )
        target_user = await user_repository.get_by_row_id(int(player_id))
    await state.clear()
    if (
        target_user is not None
        and target_user.notification_platform == "tg"
        and target_user.telegram_id is not None
    ):
        await _upsert_tg_user_chips_result(
            chat_id=int(target_user.telegram_id),
            text=_build_user_chips_text(
                chips=int(chips),
                money_kopecks=int(money_kopecks),
                reaction=_get_reaction("winner" if int(money_kopecks) >= 0 else "loser"),
            ),
        )
    elif (
        target_user is not None
        and target_user.notification_platform == "vk"
        and target_user.vk_id is not None
    ):
        await send_vk_message(
            user_id=target_user.vk_id,
            message=_build_user_chips_text(
                chips=int(chips),
                money_kopecks=int(money_kopecks),
                reaction=_get_reaction("winner" if int(money_kopecks) >= 0 else "loser"),
            ),
        )
