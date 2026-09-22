from datetime import date

from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.bot.shared.texts.inline.telegram.user import polls as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    new_user_keyboard,
    poll_menu_keyboard,
    poll_month_keyboard,
)
from app.bot.telegram.states import PollState
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.poll_vote_repository import PollVoteRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    _approved_tg_keyboard,
    _delete_message_if_possible,
    _ensure_approved_telegram_callback_user,
    _format_poll_summary,
    _get_telegram_user,
    _month_bounds,
    _month_name_ru_upper,
    _parse_custom_day_input,
    _parse_iso_dates,
    _parse_month_key,
    _poll_all_days_for_month,
    _poll_choose_text,
    _render_poll_results_chart,
    _safe_edit_reply_markup,
)


async def start_room_poll(message: Message, state: FSMContext) -> None:
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

    async with SessionFactory() as session:
        month = await PollConfigRepository(session).get_active_month()
    if month is None:
        await message.answer(
            Text.user.POLL_NOT_ACTIVE.value, reply_markup=await _approved_tg_keyboard(user)
        )
        return
    month_start, month_end = _month_bounds(month)
    async with SessionFactory() as session:
        all_days = await _poll_all_days_for_month(session=session, month=month)
        selected = await PollVoteRepository(session).get_user_month_votes(
            player_row_id=int(user.row_id),
            month_start=month_start,
            month_end=month_end,
        )
    await state.update_data(
        poll_month=f"{month.year}-{month.month:02d}",
        poll_page=0,
        poll_selected=[item.isoformat() for item in selected],
    )
    await message.answer(
        _poll_choose_text(month),
        reply_markup=poll_month_keyboard(
            month=month, page=0, selected_dates=selected, extra_dates=all_days
        ),
    )


async def show_poll_results(message: Message) -> None:
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

    async with SessionFactory() as session:
        month = await PollConfigRepository(session).get_active_month()
        if month is None:
            await message.answer(
                Text.user.POLL_NOT_ACTIVE.value, reply_markup=await _approved_tg_keyboard(user)
            )
            return
        month_start, month_end = _month_bounds(month)
        poll_repo = PollVoteRepository(session)
        month_counts = await poll_repo.get_month_counts(
            month_start=month_start, month_end=month_end
        )
        month_votes = await poll_repo.get_month_votes(month_start=month_start, month_end=month_end)
        user_ids = sorted({int(player_row_id) for _, player_row_id in month_votes})
        user_repository = UserRepository(session)
        user_names: dict[int, str] = {}
        for row_id in user_ids:
            poll_user = await user_repository.get_by_row_id(row_id)
            user_names[row_id] = poll_user.name if poll_user is not None else f"ID {row_id}"
        all_days = await _poll_all_days_for_month(session=session, month=month)
    image_bytes = _render_poll_results_chart(
        month=month,
        month_counts=month_counts,
        month_votes=month_votes,
        user_names=user_names,
        days=all_days,
    )
    try:
        await message.answer_photo(
            photo=BufferedInputFile(image_bytes, filename="poll_results.png"),
            caption=f'{InlineText.SHOW_POLL_RESULTS_TEXT_01_PART_1}{month.strftime('%m.%Y')}',
            reply_markup=poll_menu_keyboard,
        )
    except Exception:
        await message.answer_document(
            document=BufferedInputFile(image_bytes, filename="poll_results.png"),
            caption=f'{InlineText.SHOW_POLL_RESULTS_TEXT_02_PART_1}{month.strftime('%m.%Y')}',
            reply_markup=poll_menu_keyboard,
        )


async def poll_noop(callback: CallbackQuery) -> None:
    await callback.answer()


async def poll_page_nav(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    _, month_key, page_s = str(callback.data).split(":")
    month = _parse_month_key(month_key)
    async with SessionFactory() as session:
        allowed_days = await _poll_all_days_for_month(session=session, month=month)
    max_page = max(0, (len(allowed_days) - 1) // 4)
    page = max(0, min(int(page_s), max_page))
    data = await state.get_data()
    selected = _parse_iso_dates(data.get("poll_selected", []))
    await state.update_data(poll_month=f"{month.year}-{month.month:02d}", poll_page=page)
    await _safe_edit_reply_markup(
        callback.message,
        poll_month_keyboard(
            month=month, page=page, selected_dates=selected, extra_dates=allowed_days
        ),
    )
    await callback.answer()


async def poll_day_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    _, day_iso, page_s = str(callback.data).split(":")
    day = date.fromisoformat(day_iso)
    data = await state.get_data()
    selected_set = set(data.get("poll_selected", []))
    if day_iso in selected_set:
        selected_set.remove(day_iso)
    else:
        selected_set.add(day_iso)
    selected = _parse_iso_dates(list(selected_set))
    async with SessionFactory() as session:
        allowed_days = await _poll_all_days_for_month(
            session=session, month=date(day.year, day.month, 1)
        )
    await state.update_data(
        poll_month=f"{day.year}-{day.month:02d}",
        poll_page=int(page_s),
        poll_selected=[item.isoformat() for item in selected],
    )
    await _safe_edit_reply_markup(
        callback.message,
        poll_month_keyboard(
            month=date(day.year, day.month, 1),
            page=int(page_s),
            selected_dates=selected,
            extra_dates=allowed_days,
        ),
    )
    await callback.answer()


async def poll_suggest_day(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    month_key = str(callback.data).split(":", 1)[1]
    month = _parse_month_key(month_key)
    await state.set_state(PollState.waiting_for_custom_day)
    await state.update_data(poll_suggest_month=f"{month.year}-{month.month:02d}")
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(f'{InlineText.POLL_SUGGEST_DAY_TEXT_01_PART_1}{_month_name_ru_upper(month)}{InlineText.POLL_SUGGEST_DAY_TEXT_01_PART_2}')


async def poll_suggest_day_input(message: Message, state: FSMContext) -> None:
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
    data = await state.get_data()
    month = _parse_month_key(data.get("poll_suggest_month"))
    chosen = _parse_custom_day_input(message.text or "", month=month)
    if chosen is None:
        await message.answer(
            f'{InlineText.POLL_SUGGEST_DAY_INPUT_TEXT_01_PART_1}{_month_name_ru_upper(month)}{InlineText.POLL_SUGGEST_DAY_INPUT_TEXT_01_PART_2}'
        )
        return

    month_start, month_end = _month_bounds(month)
    async with SessionFactory() as session:
        repo = PollVoteRepository(session)
        existing_days = await _poll_all_days_for_month(session=session, month=month)
        if chosen in existing_days:
            await message.answer(InlineText.POLL_SUGGEST_DAY_INPUT_TEXT_02)
            return
        await repo.add_month_extra_date(poll_date=chosen)
        selected = await repo.get_user_month_votes(
            player_row_id=int(user.row_id),
            month_start=month_start,
            month_end=month_end,
        )
        all_days = await _poll_all_days_for_month(session=session, month=month)
        await session.commit()

    await state.update_data(
        poll_month=f"{month.year}-{month.month:02d}",
        poll_page=0,
        poll_selected=[item.isoformat() for item in selected],
    )
    await state.set_state(None)
    await message.answer(
        _poll_choose_text(month),
        reply_markup=poll_month_keyboard(
            month=month, page=0, selected_dates=selected, extra_dates=all_days
        ),
    )


async def poll_done(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    user = await _get_telegram_user(callback.from_user.id)
    if user is None or not user.is_approved:
        await callback.answer(Text.user.STATUS_NEED_REGISTRATION.value, show_alert=True)
        return
    data = await state.get_data()
    month = _parse_month_key(data.get("poll_month"))
    month_start, month_end = _month_bounds(month)
    async with SessionFactory() as session:
        allowed = set(await _poll_all_days_for_month(session=session, month=month))
    selected = [
        item
        for item in _parse_iso_dates(data.get("poll_selected", []))
        if item in allowed and month_start <= item <= month_end
    ]
    async with SessionFactory() as session:
        repository = PollVoteRepository(session)
        await repository.replace_user_month_votes(
            player_row_id=int(user.row_id),
            month_start=month_start,
            month_end=month_end,
            selected_dates=selected,
        )
        month_counts = await repository.get_month_counts(
            month_start=month_start, month_end=month_end
        )
        await session.commit()
    await state.clear()
    await _delete_message_if_possible(callback)
    if callback.message is not None:
        await callback.message.answer(
            _format_poll_summary(month=month, selected_dates=selected, month_counts=month_counts)
        )
    await callback.answer()


async def poll_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _delete_message_if_possible(callback)
    if callback.message is not None:
        await callback.message.answer(Text.user.POLL_CANCELED.value)
    await callback.answer()
