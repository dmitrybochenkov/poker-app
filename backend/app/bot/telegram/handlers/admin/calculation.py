from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.application.use_cases.poker.calculate_poker_result import (
    CalculatePokerNotAuthorizedError,
    CalculatePokerResultUseCase,
    MissingPlayerChipsError,
    PokerCalculationAlreadyCompletedError,
    PokerChipTotalMismatchError,
    PokerNotReadyForCalculationError,
)
from app.bot.shared.guards import is_tg_admin
from app.bot.shared.identity import resolve_telegram_user_id
from app.bot.shared.texts.inline.telegram.admin import poker as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import main_keyboard
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import main_keyboard as vk_main_keyboard
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.google_backup import backup_tables_to_google

from .common import logger
from .poker_helpers import (
    _bet_mark,
    _build_poker_buyins_session_chart,
    _calculate_transfers,
    _clear_tg_admin_chips_calc_buttons,
    _winner_mark,
)


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
        actor_user_id = await resolve_telegram_user_id(session=session, telegram_id=initiator_id)
        try:
            result = await CalculatePokerResultUseCase(session).execute(
                actor_user_id=actor_user_id or -1
            )
        except CalculatePokerNotAuthorizedError:
            await message.answer(Text.admin.NO_RIGHTS.value)
            return
        except (PokerNotReadyForCalculationError, PokerCalculationAlreadyCompletedError):
            await message.answer(Text.admin.POKER_CASHOUT_EMPTY.value)
            return
        except MissingPlayerChipsError as error:
            await message.answer(
                Text.admin.POKER_CHIPS_WAITING.value.format(players=", ".join(error.player_names))
            )
            return
        except PokerChipTotalMismatchError as error:
            await message.answer(f"{InlineText.CALCULATE_POKER_TEXT_01_PART_1}{error.diff}")
            return

    players = result.players
    bets = result.bets
    winners = list(result.winners)
    loosers = list(result.losers)
    money_rows = [{"name": player.player_name, "money": player.money_kopecks} for player in players]
    transfers = _calculate_transfers(money_rows)
    prev_winners = set(result.previous_winners)
    async with SessionFactory() as session:
        user_repository = UserRepository(session)
        try:
            await backup_tables_to_google(session=session)
        except Exception:
            logger.exception("Google backup failed after poker calculation (TG).")

        winner_line = ", ".join(
            f"{_winner_mark(is_streak=(name in prev_winners))} {name}" for name in winners
        )
        loser_line = ", ".join(
            f"{InlineText.CALCULATE_POKER_MARKER_01_PART_1}{name}" for name in loosers
        )

        transfer_lines: list[str] = []
        for line, transfer in zip(transfers, result.transfers, strict=True):
            recipient_user = await user_repository.get_by_row_id(transfer.to_user_id)
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
        try:
            chart_png = await _build_poker_buyins_session_chart(
                session=session, poker_date=result.poker_date
            )
        except Exception:
            logger.exception("Poker result chart generation failed after commit (TG).")
            chart_png = None

        from app.bot.telegram.runtime import telegram_bot

        recipient_row_ids = set(result.recipient_user_ids)
        sent_tg_ids: set[int] = set()
        sent_vk_ids: set[int] = set()
        for row_id in sorted(recipient_row_ids):
            user = None
            try:
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
            except Exception:
                logger.exception(
                    "Poker result delivery failed: platform=%s user_id=%s context=TG calculation",
                    getattr(user, "notification_platform", "unknown"),
                    row_id,
                )
        try:
            initiator_user = await user_repository.get_by_telegram_id(int(initiator_id))
        except Exception:
            logger.exception(
                "Poker result initiator lookup failed: platform=tg context=TG calculation"
            )
            initiator_user = None
        if initiator_user is not None:
            try:
                if (
                    initiator_user.notification_platform == "tg"
                    and initiator_user.telegram_id is not None
                    and telegram_bot is not None
                    and int(initiator_user.telegram_id) not in sent_tg_ids
                ):
                    await telegram_bot.send_message(
                        chat_id=initiator_user.telegram_id,
                        text=result_text,
                        reply_markup=main_keyboard,
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
            except Exception:
                logger.exception(
                    "Poker result initiator delivery failed: platform=%s user_id=%s context=TG calculation",
                    initiator_user.notification_platform,
                    int(initiator_user.row_id),
                )
        try:
            await _clear_tg_admin_chips_calc_buttons()
        except Exception:
            logger.exception("Poker result cleanup failed after commit (TG).")


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
            missing_players = [player.player_name for player in players if player.chips is None]
            if missing_players:
                await callback.answer(
                    Text.admin.POKER_CHIPS_WAITING.value.format(players=", ".join(missing_players)),
                    show_alert=True,
                )
                return
            chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
            chips_entered = sum(int(p.chips or 0) for p in players)
            diff = chips_entered - chips_in_game
            if diff != 0:
                await callback.answer(
                    f"{InlineText.CALCULATE_POKER_INLINE_TEXT_01_PART_1}{diff}",
                    show_alert=True,
                )
                return
        await calculate_poker(callback.message, admin_user_id=callback.from_user.id)
    await callback.answer()
