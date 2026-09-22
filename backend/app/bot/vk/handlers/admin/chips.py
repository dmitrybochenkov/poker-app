from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.calculate_bet_scores import CalculateBetScoresUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.vk.admin import chips as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import main_keyboard as tg_main_keyboard
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
    send_vk_photo,
)
from app.bot.vk.keyboards import (
    main_keyboard,
)
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.google_backup import backup_tables_to_google

from .common import (
    HANDLER_UNMATCHED,
    _bet_mark,
    _build_poker_buyins_session_chart,
    _calculate_transfers,
    _clear_event_inline_keyboard_if_possible,
    _clear_vk_admin_chips_calc_buttons,
    _split_names_csv,
    _winner_mark,
    logger,
)


async def _event_0_28(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_calc_run":
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.NO_RIGHTS.value,
                )
                return PlainTextResponse("ok")
            ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
            if ready is None:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.POKER_CASHOUT_EMPTY.value,
                )
                return PlainTextResponse("ok")
            poker, params = ready
            players = await PokerDataRepository(session).list_players(date=poker.date)
            chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
            chips_entered = sum(int(p.chips or 0) for p in players)
            diff = chips_entered - chips_in_game
            if diff != 0:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=f'{InlineText.EVENT_0_28_TEXT_01_PART_1}{diff}',
                )
                return PlainTextResponse("ok")
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=InlineText.EVENT_0_28_TEXT_02,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        return await handle_admin_text_commands(
            user_id=admin_user_id, text=Buttons.admin_room.CALCULATE_POKER.value
        )
    return HANDLER_UNMATCHED


async def _text_1_11(*, user_id, text):
    if text == Buttons.admin_room.CALCULATE_POKER.value:
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            user_repository = UserRepository(session)
            poker_repository = PokerRepository(session)
            ready = await poker_repository.get_latest_ready_for_chips_with_params()
            if ready is None:
                await send_vk_message(user_id=user_id, message=Text.admin.POKER_CASHOUT_EMPTY.value)
                return PlainTextResponse("ok")
            poker, params = ready
            poker_data_repository = PokerDataRepository(session)
            players = await poker_data_repository.list_players(date=poker.date)
            if not players:
                await send_vk_message(user_id=user_id, message=Text.admin.POKER_CASHOUT_EMPTY.value)
                return PlainTextResponse("ok")

            chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
            chips_entered = sum(int(p.chips or 0) for p in players)
            diff = chips_entered - chips_in_game
            if diff != 0:
                mismatch_text = (
                    f'{InlineText.TEXT_1_11_TEXT_01_PART_1}{diff}'
                )
                await send_vk_message(user_id=user_id, message=mismatch_text)
                return PlainTextResponse("ok")

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
            loser_line = ", ".join(f'{InlineText._TEXT_1_11_MARKER_01_PART_1}{name}' for name in loosers)

            approved_users = await user_repository.list_approved()
            transfer_lines: list[str] = []
            for line in transfers:
                recipient_name = line.split(InlineText._TEXT_1_11_MARKER_02)[1].split(" ")[0:2]
                recipient_name_joined = " ".join(recipient_name).strip()
                recipient_user = next(
                    (u for u in approved_users if u.name.startswith(recipient_name_joined)), None
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
            await poker_repository.finish_chips_entering(
                poker,
                winners=winners_text,
                loosers=loosers_text,
            )
            try:
                await backup_tables_to_google(session=session)
            except Exception:
                logger.exception("Google backup failed after poker calculation (VK).")

            result_lines = [
                Text.admin.POKER_CALC_SUCCESS.value,
                "",
                f"{winner_line}",
                f"{loser_line}",
                "",
                InlineText.TEXT_1_11_TEXT_02,
            ]
            result_lines.extend(transfer_lines if transfer_lines else [InlineText.TEXT_1_11_TEXT_03])
            result_lines.append("")
            result_lines.append(InlineText.TEXT_1_11_TEXT_04)
            result_lines.extend(bet_lines if bet_lines else [InlineText.TEXT_1_11_TEXT_05])
            result_text = "\n".join(result_lines)
            chart_png = await _build_poker_buyins_session_chart(
                session=session, poker_date=poker.date
            )

            from app.bot.telegram.runtime import telegram_bot

            recipient_row_ids = {int(p.player_id) for p in players} | {
                int(b.better_id) for b in bets
            }
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
                        chat_id=user.telegram_id, text=result_text, reply_markup=tg_main_keyboard
                    )
                    if chart_png is not None:
                        from aiogram.types import BufferedInputFile

                        await telegram_bot.send_photo(
                            chat_id=user.telegram_id,
                            photo=BufferedInputFile(chart_png, filename="poker_buyins_session.png"),
                            caption=InlineText.TEXT_1_11_TEXT_06,
                            reply_markup=tg_main_keyboard,
                        )
                    sent_tg_ids.add(int(user.telegram_id))
                elif user.notification_platform == "vk" and user.vk_id is not None:
                    await send_vk_message(
                        user_id=user.vk_id, message=result_text, keyboard=main_keyboard
                    )
                    if chart_png is not None:
                        await send_vk_photo(
                            user_id=user.vk_id,
                            image_bytes=chart_png,
                            filename="poker_buyins_session.png",
                        )
                    sent_vk_ids.add(int(user.vk_id))
            initiator = await user_repository.get_by_vk_id(int(user_id))
            if initiator is not None:
                if (
                    initiator.notification_platform == "tg"
                    and initiator.telegram_id is not None
                    and telegram_bot is not None
                    and int(initiator.telegram_id) not in sent_tg_ids
                ):
                    await telegram_bot.send_message(
                        chat_id=initiator.telegram_id,
                        text=result_text,
                        reply_markup=tg_main_keyboard,
                    )
                    if chart_png is not None:
                        from aiogram.types import BufferedInputFile

                        await telegram_bot.send_photo(
                            chat_id=initiator.telegram_id,
                            photo=BufferedInputFile(chart_png, filename="poker_buyins_session.png"),
                            caption=InlineText.TEXT_1_11_TEXT_07,
                            reply_markup=tg_main_keyboard,
                        )
                elif (
                    initiator.notification_platform == "vk"
                    and initiator.vk_id is not None
                    and int(initiator.vk_id) not in sent_vk_ids
                ):
                    await send_vk_message(
                        user_id=initiator.vk_id, message=result_text, keyboard=main_keyboard
                    )
                    if chart_png is not None:
                        await send_vk_photo(
                            user_id=initiator.vk_id,
                            image_bytes=chart_png,
                            filename="poker_buyins_session.png",
                        )
            await _clear_vk_admin_chips_calc_buttons()
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
