from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.use_cases.poker.bet import BetUseCases
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.inline.shared import receipt_ocr as ReceiptText
from app.bot.shared.texts.inline.telegram.user import bets as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    bet_receipt_manual_keyboard,
    betting_confirm_keyboard,
    betting_player_keyboard,
    betting_size_keyboard,
    new_user_keyboard,
)
from app.bot.telegram.states import RegistrationState
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import bet_receipt_manual_keyboard as vk_bet_receipt_manual_keyboard
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_payment_receipt_repository import BetPaymentReceiptRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.google_backup import backup_tables_to_google
from app.services.receipt_ocr import (
    extract_amount_rub,
    extract_operation_id,
    extract_phone_tail4,
    ocr_text_from_image_bytes,
    phone_tail_matches,
)

from .common import (
    PAYMENT_OWNER_ROW_ID,
    _approved_tg_keyboard,
    _betting_tg_keyboard,
    _delete_message_if_possible,
    _download_telegram_receipt_bytes,
    _ensure_approved_telegram_callback_user,
    _ensure_approved_telegram_user,
    _format_payment_requisites,
    _format_unpaid_bets_lines,
    _get_telegram_user,
    _pick_fifo_bets_to_close,
    _post_bet_tg_keyboard_for_user,
    _telegram_external_file_id,
    logger,
)
from .poker_history_helpers import _build_bet_last_five_hints, _format_rub_from_kopecks
from .stat_helpers import _format_tournament_name


async def start_pay_bet(message: Message, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    if message.from_user is None:
        await message.answer(
            Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard
        )
        return
    async with SessionFactory() as session:
        user_repository = UserRepository(session)
        user = await user_repository.get_by_telegram_id(message.from_user.id)
        if user is None or not user.is_approved:
            await message.answer(
                Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
            )
            return
        bet_repository = BetRepository(session)
        unpaid = await bet_repository.list_unpaid_for_user(better_id=int(user.row_id))
        if not unpaid:
            await message.answer(
                Text.user.BETTING_PAY_EMPTY.value, reply_markup=await _betting_tg_keyboard()
            )
            await state.clear()
            return
        total_kopecks = sum(int(item.amount_kopecks) for item in unpaid)
        owner = await user_repository.get_by_row_id(PAYMENT_OWNER_ROW_ID)
        await state.set_state(RegistrationState.waiting_for_bet_payment_receipt)
        await message.answer(
            Text.user.BETTING_PAY_LIST.value.format(
                lines=_format_unpaid_bets_lines(unpaid),
                total_rub=_format_rub_from_kopecks(total_kopecks),
                payment_requisites=_format_payment_requisites(owner),
            ),
            reply_markup=await _betting_tg_keyboard(),
        )


async def start_make_bet(message: Message, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_user(message):
        return

    async with SessionFactory() as session:
        user_repository = UserRepository(session)
        user = await user_repository.get_by_telegram_id(message.from_user.id)
        if user is None or not user.is_approved:
            await message.answer(Text.user.BETTING_NOT_OPEN.value)
            return
        use_case = BetUseCases(
            user_repository=user_repository,
            poker_repository=PokerRepository(session),
            bet_repository=BetRepository(session),
            bet_param_repository=BetParamRepository(session),
            bet_tournament_repository=BetTournamentRepository(session),
            bet_tournament_param_repository=BetTournamentParamRepository(session),
            poker_data_repository=PokerDataRepository(session),
        )
        bet_params, players, status = await use_case.get_bet_draft_data(
            better_id=message.from_user.id,
            tournament_type="single",
        )

    if status != "ok" or bet_params is None:
        await message.answer(Text.user.BETTING_NOT_OPEN.value)
        return

    await state.set_state(RegistrationState.waiting_for_bet_amount)
    await state.update_data(
        bet_tournament_type="single",
        bet_players=[p.player_name for p in players],
        bet_better_name=user.name,
    )
    await message.answer(
        Text.user.BETTING_SIZE_CHOOSE.value,
        reply_markup=betting_size_keyboard(
            small_size_kopecks=bet_params.small_size_kopecks,
            big_size_kopecks=bet_params.big_size_kopecks,
        ),
    )


async def choose_bet_tournament(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    tournament_type = "single"
    await _delete_message_if_possible(callback)
    async with SessionFactory() as session:
        user_repository = UserRepository(session)
        user = await user_repository.get_by_telegram_id(callback.from_user.id)
        if user is None or not user.is_approved:
            await state.clear()
            await callback.message.answer(
                Text.user.BETTING_NOT_OPEN.value, reply_markup=await _betting_tg_keyboard()
            )
            await callback.answer()
            return
        use_case = BetUseCases(
            user_repository=user_repository,
            poker_repository=PokerRepository(session),
            bet_repository=BetRepository(session),
            bet_param_repository=BetParamRepository(session),
            bet_tournament_repository=BetTournamentRepository(session),
            bet_tournament_param_repository=BetTournamentParamRepository(session),
            poker_data_repository=PokerDataRepository(session),
        )
        bet_params, players, status = await use_case.get_bet_draft_data(
            better_id=callback.from_user.id,
            tournament_type=tournament_type,
        )
    if status != "ok" or bet_params is None:
        await state.clear()
        await callback.message.answer(
            Text.user.BETTING_NOT_OPEN.value, reply_markup=await _betting_tg_keyboard()
        )
        await callback.answer()
        return
    await state.set_state(RegistrationState.waiting_for_bet_amount)
    await state.update_data(
        bet_tournament_type=tournament_type,
        bet_players=[p.player_name for p in players],
        bet_better_name=user.name,
    )
    await callback.message.answer(
        Text.user.BETTING_SIZE_CHOOSE.value,
        reply_markup=betting_size_keyboard(
            small_size_kopecks=bet_params.small_size_kopecks,
            big_size_kopecks=bet_params.big_size_kopecks,
        ),
    )
    await callback.answer()


async def choose_bet_size(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    data = await state.get_data()
    players = data.get("bet_players")
    if not isinstance(players, list) or not players:
        await state.clear()
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    amount_kopecks = int(callback.data.split(":", 1)[1])
    async with SessionFactory() as session:
        marks_map, winners_text, losers_text = await _build_bet_last_five_hints(
            session=session, players=players
        )
    await _delete_message_if_possible(callback)
    await state.update_data(
        bet_amount_kopecks=amount_kopecks,
        bet_player_marks=marks_map,
        bet_last_winners_text=winners_text,
        bet_last_losers_text=losers_text,
    )
    await callback.message.answer(
        f'{InlineText.CHOOSE_BET_SIZE_TEXT_01_PART_1}{winners_text}{InlineText.CHOOSE_BET_SIZE_TEXT_01_PART_2}{Text.user.BETTING_WINNER_CHOOSE.value}',
        reply_markup=betting_player_keyboard(
            action="winner", players=players, player_marks=marks_map
        ),
    )
    await callback.answer()


async def choose_bet_winner(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    data = await state.get_data()
    players = data.get("bet_players")
    better_name = data.get("bet_better_name")
    marks_map = data.get("bet_player_marks", {})
    losers_text = data.get("bet_last_losers_text", "")
    winner_name = callback.data.split(":", 1)[1]
    if not isinstance(players, list) or winner_name not in players:
        await state.clear()
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    loser_candidates = [
        player for player in players if player != winner_name and player != better_name
    ]
    if not loser_candidates:
        await state.clear()
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    await _delete_message_if_possible(callback)
    await state.update_data(bet_winner_name=winner_name)
    loser_marks = (
        {name: marks_map.get(name, "") for name in loser_candidates}
        if isinstance(marks_map, dict)
        else None
    )
    await callback.message.answer(
        f'{InlineText.CHOOSE_BET_WINNER_TEXT_01_PART_1}{losers_text}{InlineText.CHOOSE_BET_WINNER_TEXT_01_PART_2}{Text.user.BETTING_LOSER_CHOOSE.value}',
        reply_markup=betting_player_keyboard(
            action="loser", players=loser_candidates, player_marks=loser_marks
        ),
    )
    await callback.answer()


async def choose_bet_loser(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    loser_name = callback.data.split(":", 1)[1]
    data = await state.get_data()
    winner_name = data.get("bet_winner_name")
    tournament_type = data.get("bet_tournament_type")
    amount_kopecks = data.get("bet_amount_kopecks")
    if (
        not winner_name
        or not tournament_type
        or not isinstance(amount_kopecks, int)
        or loser_name == winner_name
    ):
        await state.clear()
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    await _delete_message_if_possible(callback)
    await state.update_data(bet_loser_name=loser_name)
    await callback.message.answer(
        Text.user.BETTING_CONFIRM.value.format(
            tournament=_format_tournament_name(tournament_type),
            amount_rub=amount_kopecks // 100,
            winner=winner_name,
            loser=loser_name,
        ),
        reply_markup=betting_confirm_keyboard(),
    )
    await callback.answer()


async def confirm_bet(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.from_user is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    choice = callback.data.split(":", 1)[1]
    await _delete_message_if_possible(callback)
    if choice != "yes":
        await state.clear()
        await callback.message.answer(
            Text.user.BETTING_MENU.value, reply_markup=await _betting_tg_keyboard()
        )
        await callback.answer()
        return
    data = await state.get_data()
    tournament_type = data.get("bet_tournament_type")
    amount_kopecks = data.get("bet_amount_kopecks")
    winner_name = data.get("bet_winner_name")
    loser_name = data.get("bet_loser_name")
    if (
        not tournament_type
        or not isinstance(amount_kopecks, int)
        or not winner_name
        or not loser_name
    ):
        await state.clear()
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return

    try:
        async with SessionFactory() as session:
            use_case = BetUseCases(
                user_repository=UserRepository(session),
                poker_repository=PokerRepository(session),
                bet_repository=BetRepository(session),
                bet_param_repository=BetParamRepository(session),
                bet_tournament_repository=BetTournamentRepository(session),
                bet_tournament_param_repository=BetTournamentParamRepository(session),
                poker_data_repository=PokerDataRepository(session),
            )
            created, status = await use_case.create_bet(
                better_id=callback.from_user.id,
                tournament_type=tournament_type,
                amount_kopecks=amount_kopecks,
                winner_name=winner_name,
                loser_name=loser_name,
            )
    except Exception:
        await callback.message.answer(
            Text.user.BETTING_NOT_OPEN.value, reply_markup=await _betting_tg_keyboard()
        )
        await state.clear()
        await callback.answer()
        return

    if status == "already_bet":
        await callback.message.answer(
            Text.user.BETTING_ALREADY_EXISTS.value, reply_markup=await _betting_tg_keyboard()
        )
    elif status in {"betting_closed", "user_not_approved", "invalid_tournament", "missing_params"}:
        await callback.message.answer(
            Text.user.BETTING_NOT_OPEN.value, reply_markup=await _betting_tg_keyboard()
        )
    elif status == "invalid_amount" or created is None:
        await callback.message.answer(
            Text.user.BETTING_NOT_OPEN.value, reply_markup=await _betting_tg_keyboard()
        )
    else:
        post_bet_keyboard = await _post_bet_tg_keyboard_for_user(telegram_id=callback.from_user.id)
        await callback.message.answer(
            Text.user.BETTING_CREATED.value.format(
                tournament=_format_tournament_name(tournament_type),
                amount_rub=amount_kopecks // 100,
                winner=winner_name,
                loser=loser_name,
            ),
            reply_markup=post_bet_keyboard,
        )
    await state.clear()
    await callback.answer()


async def repeat_bet_inline_flow(message: Message) -> None:
    await message.answer(Text.user.BETTING_SIZE_CHOOSE.value)


async def process_bet_payment_receipt(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer(
            Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard
        )
        return
    user = await _get_telegram_user(message.from_user.id)
    if user is None or not user.is_approved:
        await state.clear()
        await message.answer(
            Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
        )
        return

    has_receipt = bool(message.photo) or (message.document is not None)
    text_value = (message.text or "").strip()
    if text_value == Buttons.betting.TO_MAIN.value:
        await state.clear()
        await message.answer(Text.user.BETTING_PAY_CANCELED.value)
        await message.answer(
            Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user)
        )
        return
    if not has_receipt:
        await message.answer(
            Text.user.BETTING_PAY_AMOUNT_INVALID.value, reply_markup=await _betting_tg_keyboard()
        )
        return
    receipt_bytes = await _download_telegram_receipt_bytes(message)
    ocr_text = ocr_text_from_image_bytes(receipt_bytes or b"")
    entered_rub = extract_amount_rub(ocr_text)

    async with SessionFactory() as session:
        user_repository = UserRepository(session)
        bet_repository = BetRepository(session)
        receipt_repository = BetPaymentReceiptRepository(session)
        unpaid = await bet_repository.list_unpaid_for_user(better_id=int(user.row_id))
        if not unpaid:
            await state.clear()
            await message.answer(
                Text.user.BETTING_PAY_EMPTY.value, reply_markup=await _betting_tg_keyboard()
            )
            return
        owner = await user_repository.get_by_row_id(PAYMENT_OWNER_ROW_ID)

        external_file_id = _telegram_external_file_id(message)
        if external_file_id:
            existing_by_file = await receipt_repository.get_by_platform_and_external_file_id(
                platform="tg",
                external_file_id=external_file_id,
            )
            if existing_by_file is not None:
                admin_text = (
                    f'{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_01_PART_1}{user.name}{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_01_PART_2}{external_file_id}'
                )
                from app.bot.telegram.runtime import telegram_bot

                if (
                    owner is not None
                    and owner.notification_platform == "tg"
                    and owner.telegram_id is not None
                    and telegram_bot is not None
                ):
                    await telegram_bot.send_message(chat_id=int(owner.telegram_id), text=admin_text)
                elif owner is not None and owner.vk_id is not None:
                    await send_vk_message(user_id=int(owner.vk_id), message=admin_text)
                await state.clear()
                await message.answer(
                    InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_02, reply_markup=await _betting_tg_keyboard()
                )
                return

        operation_id = extract_operation_id(ocr_text)
        if operation_id:
            existing_by_op = await receipt_repository.get_by_operation_id(operation_id=operation_id)
            if existing_by_op is not None:
                admin_text = (
                    f'{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_03_PART_1}{user.name}{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_03_PART_2}{operation_id}'
                )
                from app.bot.telegram.runtime import telegram_bot

                if (
                    owner is not None
                    and owner.notification_platform == "tg"
                    and owner.telegram_id is not None
                    and telegram_bot is not None
                ):
                    await telegram_bot.send_message(chat_id=int(owner.telegram_id), text=admin_text)
                elif owner is not None and owner.vk_id is not None:
                    await send_vk_message(user_id=int(owner.vk_id), message=admin_text)
                await state.clear()
                await message.answer(
                    InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_04, reply_markup=await _betting_tg_keyboard()
                )
                return

        ocr_phone_match = phone_tail_matches(
            ocr_text, owner.tel_number if owner is not None else None
        )
        recipient_tail4 = extract_phone_tail4(
            ocr_text, owner.tel_number if owner is not None else None
        )
        if entered_rub is not None and ocr_phone_match is True:
            paid_kopecks = int(entered_rub) * 100
            to_close = _pick_fifo_bets_to_close(bets=unpaid, paid_kopecks=paid_kopecks)
            if to_close:
                await bet_repository.mark_paid(bets=to_close)
                await receipt_repository.create(
                    user_row_id=int(user.row_id),
                    platform="tg",
                    external_file_id=external_file_id,
                    operation_id=operation_id,
                    amount_kopecks_ocr=paid_kopecks,
                    recipient_tail4_ocr=recipient_tail4,
                    status="accepted",
                )
                await session.commit()
                try:
                    await backup_tables_to_google(session=session)
                except Exception:
                    logger.exception("Failed to sync Google backup after TG is_paid update")
                remaining = await bet_repository.list_unpaid_for_user(better_id=int(user.row_id))
                remaining_kopecks = sum(int(item.amount_kopecks) for item in remaining)
                await state.clear()
                await message.answer(
                    Text.user.BETTING_PAY_MATCHED.value.format(
                        count=len(to_close),
                        debt_rub=_format_rub_from_kopecks(remaining_kopecks),
                    ),
                    reply_markup=await _betting_tg_keyboard(),
                )
                return

        total_unpaid = sum(int(item.amount_kopecks) for item in unpaid)
        missing_fields: list[str] = []
        if entered_rub is None:
            missing_fields.append("sum")
        if ocr_phone_match is not True:
            missing_fields.append("recipient")
        if operation_id is None:
            missing_fields.append("operation_id")
        ocr_preview = " ".join((ocr_text or "").split())[:500]
        admin_text = (
            f'{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_05_PART_1}{user.name}{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_05_PART_2}{(entered_rub if entered_rub is not None else ReceiptText.AMOUNT_UNDETERMINED)}{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_05_PART_3}{_format_rub_from_kopecks(total_unpaid)}{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_05_PART_4}{(ReceiptText.PHONE_MATCHES if ocr_phone_match else ReceiptText.PHONE_DOES_NOT_MATCH if ocr_phone_match is False else ReceiptText.VALUE_UNDETERMINED)}{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_05_PART_5}{(recipient_tail4 if recipient_tail4 is not None else ReceiptText.VALUE_UNDETERMINED)}{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_05_PART_6}{(operation_id if operation_id is not None else ReceiptText.VALUE_UNDETERMINED)}{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_05_PART_7}{(', '.join(missing_fields) if missing_fields else ReceiptText.NO_MISSING_FIELDS)}{InlineText.PROCESS_BET_PAYMENT_RECEIPT_TEXT_05_PART_8}{(ocr_preview if ocr_preview else ReceiptText.EMPTY_PREVIEW)}'
        )
        manual_receipt = await receipt_repository.create(
            user_row_id=int(user.row_id),
            platform="tg",
            external_file_id=external_file_id,
            operation_id=operation_id,
            amount_kopecks_ocr=(int(entered_rub) * 100) if entered_rub is not None else None,
            recipient_tail4_ocr=recipient_tail4,
            status="manual",
        )
        reviewer = await user_repository.get_by_row_id(PAYMENT_OWNER_ROW_ID)
        from app.bot.telegram.runtime import telegram_bot

        if (
            reviewer is not None
            and reviewer.notification_platform == "tg"
            and reviewer.telegram_id is not None
            and telegram_bot is not None
        ):
            if has_receipt:
                try:
                    await message.copy_to(
                        chat_id=int(reviewer.telegram_id),
                        caption=admin_text,
                        reply_markup=bet_receipt_manual_keyboard(
                            receipt_row_id=int(manual_receipt.row_id),
                            bets=unpaid,
                            selected_ids=[],
                            page=0,
                        ),
                    )
                except Exception:
                    await telegram_bot.send_message(
                        chat_id=int(reviewer.telegram_id),
                        text=admin_text,
                        reply_markup=bet_receipt_manual_keyboard(
                            receipt_row_id=int(manual_receipt.row_id),
                            bets=unpaid,
                            selected_ids=[],
                            page=0,
                        ),
                    )
            else:
                await telegram_bot.send_message(
                    chat_id=int(reviewer.telegram_id),
                    text=admin_text,
                    reply_markup=bet_receipt_manual_keyboard(
                        receipt_row_id=int(manual_receipt.row_id),
                        bets=unpaid,
                        selected_ids=[],
                        page=0,
                    ),
                )
        elif reviewer is not None and reviewer.vk_id is not None:
            await send_vk_message(
                user_id=int(reviewer.vk_id),
                message=admin_text,
                keyboard=vk_bet_receipt_manual_keyboard(
                    receipt_row_id=int(manual_receipt.row_id),
                    bets=unpaid,
                    selected_ids=[],
                    page=0,
                ),
            )
        await session.commit()
        await state.clear()
        await message.answer(
            Text.user.BETTING_PAY_NEED_MANUAL.value, reply_markup=await _betting_tg_keyboard()
        )
        return
