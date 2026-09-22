from types import SimpleNamespace

from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.application.use_cases.poker.calculate_bet_scores import CalculateBetScoresUseCase
from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.application.use_cases.poker.start_poker import StartPokerUseCase
from app.bot.shared.guards import is_tg_admin
from app.bot.shared.texts.inline.telegram.admin import poker as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    admin_room_correct_keyboard,
    admin_room_keyboard,
    main_keyboard,
    poker_cashier_candidates_keyboard,
    poker_params_keyboard,
)
from app.bot.telegram.keyboards import (
    main_dynamic_keyboard as tg_main_dynamic_keyboard,
)
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import main_dynamic_keyboard as vk_main_dynamic_keyboard
from app.bot.vk.keyboards import main_keyboard as vk_main_keyboard
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.google_backup import backup_tables_to_google

from .common import (
    _bet_mark,
    _build_poker_buyins_session_chart,
    _calculate_transfers,
    _clear_inline_keyboard,
    _clear_tg_admin_chips_calc_buttons,
    _ensure_tg_admin_callback,
    _ensure_tg_admin_message,
    _notify_players_about_finish,
    _refresh_admin_room_status,
    _safe_callback_edit_text,
    _split_names_csv,
    _upsert_tg_admin_chips_status,
    _winner_mark,
    logger,
)


async def start_poker_menu(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return

    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
        user_repository = UserRepository(session)

        use_case = StartPokerUseCase(
            poker_repository=PokerRepository(session),
            poker_param_repository=PokerParamRepository(session),
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
        )
        can_start, params = await use_case.get_start_data()
        if not can_start:
            await message.answer(Text.admin.POKER_STARTED.value)
            return
        if not params:
            await message.answer(Text.admin.POKER_PARAMS_EMPTY.value)
            return

    await message.answer(
        "\n\n".join(
            [
                Text.admin.POKER_PARAMS_CHOOSE.value,
                *[
                    (
                        f'{InlineText.START_POKER_MENU_TEXT_01_PART_1}{p.row_id}{InlineText.START_POKER_MENU_TEXT_01_PART_2}{p.buyin_size_chips}{InlineText.START_POKER_MENU_TEXT_01_PART_3}{int(p.buyin_size_kopecks) // 100}{InlineText.START_POKER_MENU_TEXT_01_PART_4}{p.bb_size_chips}{InlineText.START_POKER_MENU_TEXT_01_PART_5}{p.max_buyins}{InlineText.START_POKER_MENU_TEXT_01_PART_6}{p.big_buyin}{InlineText.START_POKER_MENU_TEXT_01_PART_7}{p.super_buyin}'
                    )
                    for p in params
                ],
            ]
        ),
        reply_markup=poker_params_keyboard(params=params),
    )


async def start_poker_with_param(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return

    params_id = int(callback.data.split(":", 1)[1])
    await _clear_inline_keyboard(callback)

    async with SessionFactory() as session:
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return
        user_repository = UserRepository(session)

        use_case = StartPokerUseCase(
            poker_repository=PokerRepository(session),
            poker_param_repository=PokerParamRepository(session),
            poker_room_denied_repository=PokerRoomDeniedRepository(session),
        )
        created = await use_case.execute(params_id=params_id)
        if created is None:
            await callback.answer(Text.admin.POKER_STARTED.value, show_alert=True)
            return
        starter = await user_repository.get_by_telegram_id(callback.from_user.id)
        if starter is not None:
            await ManagePokerPlayersUseCase(
                poker_repository=PokerRepository(session),
                poker_data_repository=PokerDataRepository(session),
            ).add_player_to_active_poker(
                player_id=int(starter.row_id),
                player_name=starter.name,
            )

        approved_users = await user_repository.list_approved()

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

    if callback.message is not None:
        await _safe_callback_edit_text(callback, Text.admin.POKER_START_SUCCESS.value)
    await callback.answer(Text.admin.POKER_START_SUCCESS.value)


async def finish_poker(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
        user_repository = UserRepository(session)
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
            await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
            return
        poker, params = active
        poker_data_repository = PokerDataRepository(session)
        players = await poker_data_repository.list_players(date=poker.date)
        await poker_repository.finish(poker)
        await PokerRoomDeniedRepository(session).clear_all()
    await _notify_players_about_finish(players=players)
    await message.answer(Text.admin.POKER_FINISH_SUCCESS.value)
    if players:
        async with SessionFactory() as session:
            await _upsert_tg_admin_chips_status(session=session, poker_date=players[0].date)


async def calculate_poker(message: Message, admin_user_id: int | None = None) -> None:
    initiator_id = (
        int(admin_user_id)
        if admin_user_id is not None
        else (int(message.from_user.id) if message.from_user is not None else None)
    )
    if initiator_id is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=initiator_id, message=message
        ):
            return
        user_repository = UserRepository(session)
        poker_repository = PokerRepository(session)
        ready = await poker_repository.get_latest_ready_for_chips_with_params()
        if ready is None:
            await message.answer(Text.admin.POKER_CASHOUT_EMPTY.value)
            return
        poker, params = ready
        poker_data_repository = PokerDataRepository(session)
        players = await poker_data_repository.list_players(date=poker.date)
        if not players:
            await message.answer(Text.admin.POKER_CASHOUT_EMPTY.value)
            return
        chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
        chips_entered = sum(int(p.chips or 0) for p in players)
        diff = chips_entered - chips_in_game
        if diff != 0:
            await message.answer(
                f'{InlineText.CALCULATE_POKER_TEXT_01_PART_1}{diff}'
            )
            return

        money_rows: list[dict[str, int | str]] = []
        for player in players:
            money_kopecks = (
                (int(player.chips) - int(player.buyins) * int(params.buyin_size_chips))
                * int(params.buyin_size_kopecks)
            ) // int(params.buyin_size_chips)
            await poker_data_repository.set_cashout(
                date=poker.date,
                player_id=int(player.player_id),
                money_kopecks=int(money_kopecks),
            )
            money_rows.append({"name": player.player_name, "money": int(money_kopecks)})

        max_money = max(int(item["money"]) for item in money_rows)
        min_money = min(int(item["money"]) for item in money_rows)
        winners = [str(item["name"]) for item in money_rows if int(item["money"]) == max_money]
        loosers = [str(item["name"]) for item in money_rows if int(item["money"]) == min_money]
        winners_text = ", ".join(winners)
        loosers_text = ", ".join(loosers)
        transfers = _calculate_transfers(money_rows)

        # Bet scores are calculated only after final winners/losers/money are known.
        await CalculateBetScoresUseCase(
            bet_repository=BetRepository(session),
            bet_param_repository=BetParamRepository(session),
            bet_tournament_param_repository=BetTournamentParamRepository(session),
            poker_data_repository=poker_data_repository,
        ).execute(
            poker_id=poker.row_id,
            poker_date=poker.date,
        )
        bets = await BetRepository(session).list_for_poker(date=poker.date)

        await poker_repository.finish_chips_entering(
            poker,
            winners=winners_text,
            loosers=loosers_text,
        )
        try:
            await backup_tables_to_google(session=session)
        except Exception:
            logger.exception("Google backup failed after poker calculation (TG).")

        all_pokers = await poker_repository.list_all()
        prev_completed = None
        for old in sorted(all_pokers, key=lambda x: int(x.row_id), reverse=True):
            if int(old.row_id) == int(poker.row_id):
                continue
            if bool(old.winners):
                prev_completed = old
                break
        prev_winners = _split_names_csv(
            prev_completed.winners if prev_completed is not None else None
        )

        winner_line = ", ".join(
            f"{_winner_mark(is_streak=(name in prev_winners))} {name}" for name in winners
        )
        loser_line = ", ".join(f'{InlineText.CALCULATE_POKER_MARKER_01_PART_1}{name}' for name in loosers)

        transfer_lines: list[str] = []
        for line in transfers:
            # add recipient bank/phone for convenience
            recipient_name = line.split(InlineText.CALCULATE_POKER_MARKER_02)[1].split(" ")[0:2]
            recipient_name_joined = " ".join(recipient_name).strip()
            recipient_user = next(
                (
                    u
                    for u in await user_repository.list_approved()
                    if u.name.startswith(recipient_name_joined)
                ),
                None,
            )
            extra = ""
            if recipient_user is not None and recipient_user.tel_number:
                bank = f" ({recipient_user.bank_name})" if recipient_user.bank_name else ""
                extra = f" [{recipient_user.tel_number}{bank}]"
            transfer_lines.append(f"{line}{extra}")

        bet_lines: list[str] = []
        for bet in sorted(bets, key=lambda x: int(x.row_id)):
            guessed_winner = bool(bet.winner_name) and bet.winner_name in winners
            guessed_loser = bool(bet.loser_name) and bet.loser_name in loosers
            if not guessed_winner and not guessed_loser:
                continue
            mark = _bet_mark(
                amount_kopecks=int(bet.amount_kopecks),
                guessed_winner=guessed_winner,
                guessed_loser=guessed_loser,
            )
            bet_lines.append(f"{bet.better_name}: {mark} +{int(bet.score)}")

        lines = [
            Text.admin.POKER_CALC_SUCCESS.value,
            "",
            f"{winner_line}",
            f"{loser_line}",
            "",
            InlineText.CALCULATE_POKER_TEXT_02,
        ]
        lines.extend(transfer_lines if transfer_lines else [InlineText.CALCULATE_POKER_TEXT_03])
        lines.append("")
        lines.append(InlineText.CALCULATE_POKER_TEXT_04)
        lines.extend(bet_lines if bet_lines else [InlineText.CALCULATE_POKER_TEXT_05])
        result_text = "\n".join(lines)
        chart_png = await _build_poker_buyins_session_chart(session=session, poker_date=poker.date)

        from app.bot.telegram.runtime import telegram_bot

        recipient_row_ids = {int(p.player_id) for p in players} | {int(b.better_id) for b in bets}
        sent_tg_ids: set[int] = set()
        sent_vk_ids: set[int] = set()
        for row_id in sorted(recipient_row_ids):
            user = await user_repository.get_by_row_id(row_id)
            if user is None:
                continue
            if (
                user.notification_platform == "tg"
                and user.telegram_id is not None
                and telegram_bot is not None
            ):
                await telegram_bot.send_message(
                    chat_id=user.telegram_id, text=result_text, reply_markup=main_keyboard
                )
                if chart_png is not None:
                    await telegram_bot.send_photo(
                        chat_id=user.telegram_id,
                        photo=BufferedInputFile(chart_png, filename="poker_buyins_session.png"),
                        caption=InlineText.CALCULATE_POKER_TEXT_06,
                        reply_markup=main_keyboard,
                    )
                sent_tg_ids.add(int(user.telegram_id))
            elif user.notification_platform == "vk" and user.vk_id is not None:
                await send_vk_message(
                    user_id=user.vk_id, message=result_text, keyboard=vk_main_keyboard
                )
                if chart_png is not None:
                    from app.bot.vk.api import send_vk_photo

                    await send_vk_photo(
                        user_id=user.vk_id,
                        image_bytes=chart_png,
                        filename="poker_buyins_session.png",
                    )
                sent_vk_ids.add(int(user.vk_id))
        initiator_user = await user_repository.get_by_telegram_id(int(initiator_id))
        if initiator_user is not None:
            if (
                initiator_user.notification_platform == "tg"
                and initiator_user.telegram_id is not None
                and telegram_bot is not None
                and int(initiator_user.telegram_id) not in sent_tg_ids
            ):
                await telegram_bot.send_message(
                    chat_id=initiator_user.telegram_id, text=result_text, reply_markup=main_keyboard
                )
                if chart_png is not None:
                    await telegram_bot.send_photo(
                        chat_id=initiator_user.telegram_id,
                        photo=BufferedInputFile(chart_png, filename="poker_buyins_session.png"),
                        caption=InlineText.CALCULATE_POKER_TEXT_07,
                        reply_markup=main_keyboard,
                    )
            elif (
                initiator_user.notification_platform == "vk"
                and initiator_user.vk_id is not None
                and int(initiator_user.vk_id) not in sent_vk_ids
            ):
                await send_vk_message(
                    user_id=initiator_user.vk_id, message=result_text, keyboard=vk_main_keyboard
                )
                if chart_png is not None:
                    from app.bot.vk.api import send_vk_photo

                    await send_vk_photo(
                        user_id=initiator_user.vk_id,
                        image_bytes=chart_png,
                        filename="poker_buyins_session.png",
                    )
        await _clear_tg_admin_chips_calc_buttons()


async def calculate_poker_inline(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    if callback.message is not None:
        async with SessionFactory() as session:
            if not await is_tg_admin(session=session, telegram_id=callback.from_user.id):
                await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
                return
            ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
            if ready is None:
                await callback.answer(Text.admin.POKER_CASHOUT_EMPTY.value, show_alert=True)
                return
            poker, params = ready
            players = await PokerDataRepository(session).list_players(date=poker.date)
            chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
            chips_entered = sum(int(p.chips or 0) for p in players)
            diff = chips_entered - chips_in_game
            if diff != 0:
                await callback.answer(
                    f'{InlineText.CALCULATE_POKER_INLINE_TEXT_01_PART_1}{diff}',
                    show_alert=True,
                )
                return
        await calculate_poker(callback.message, admin_user_id=callback.from_user.id)
    await callback.answer()


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
    await message.answer(InlineText.OPEN_CORRECT_POKER_MENU_TEXT_01, reply_markup=admin_room_correct_keyboard)


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
        updated = await use_case.set_cashier_for_active_poker(cashier_id=user_row_id)
        if updated is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        cashier_user = await user_repository.get_by_row_id(user_row_id)
        cashier_name = cashier_user.name if cashier_user is not None else f"ID {user_row_id}"
        cashier_text = f'{cashier_name}{InlineText.SET_CASHIER_CALLBACK_TEXT_01_PART_1}'
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
        updated = await use_case.set_cashier_for_active_poker(cashier_id=user_row_id)
        if updated is None:
            await callback.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value, show_alert=True)
            return
        cashier_user = await user_repository.get_by_row_id(user_row_id)
        cashier_name = cashier_user.name if cashier_user is not None else f"ID {user_row_id}"
        await _refresh_admin_room_status(session=session)
    await callback.answer(f'{cashier_name}{InlineText.SET_CASHIER_FROM_ROOM_CALLBACK_TEXT_02_PART_1}')
