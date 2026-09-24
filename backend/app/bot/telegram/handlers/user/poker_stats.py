from datetime import date, datetime

from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.texts.inline.telegram.user import poker_stats as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    poker_history_dates_keyboard,
    poker_history_year_keyboard,
    poker_info_keyboard,
    poker_keyboard,
    poker_stat_indicators_keyboard,
    stat_sort_keyboard,
    stat_year_keyboard,
)
from app.db.repositories.achievement_repository import AchievementRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository
from app.db.session import SessionFactory
from app.services.stat_image import render_stat_table_png

from .common import (
    _clear_inline_keyboard,
    _delete_message_if_possible,
    _ensure_approved_telegram_callback_user,
    _ensure_approved_telegram_user,
)
from .poker_history_helpers import _build_poker_history_buyins_chart, _build_poker_history_report
from .stat_helpers import _format_stat_caption


async def show_poker_history_years(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    async with SessionFactory() as session:
        pokers = await PokerRepository(session).list_all()
    years = sorted(
        {
            int(item.date.year)
            for item in pokers
            if item.date is not None and not bool(item.is_going)
        },
        reverse=True,
    )
    if not years:
        await message.answer(InlineText.SHOW_POKER_HISTORY_YEARS_TEXT_01, reply_markup=poker_info_keyboard)
        return
    await message.answer(
        InlineText.SHOW_POKER_HISTORY_YEARS_TEXT_02,
        reply_markup=poker_history_year_keyboard(years=years),
    )


async def poker_history_cancel(callback: CallbackQuery) -> None:
    await _clear_inline_keyboard(callback)
    await callback.answer(InlineText.POKER_HISTORY_CANCEL_TEXT_01)


async def poker_history_year_pick(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    year = int(str(callback.data).split(":", 1)[1])
    async with SessionFactory() as session:
        pokers = await PokerRepository(session).list_all()
    dates = sorted(
        {
            item.date
            for item in pokers
            if item.date is not None
            and not bool(item.is_going)
            and int(item.date.year) == int(year)
        },
    )
    if not dates:
        await callback.answer(InlineText.POKER_HISTORY_YEAR_PICK_TEXT_01, show_alert=True)
        return
    await callback.message.edit_text(
        f'{InlineText.POKER_HISTORY_YEAR_PICK_TEXT_02_PART_1}{year}{InlineText.POKER_HISTORY_YEAR_PICK_TEXT_02_PART_2}',
        reply_markup=poker_history_dates_keyboard(year=year, dates=list(dates), page=0),
    )
    await callback.answer()


async def poker_history_page(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    _, year_s, page_s = str(callback.data).split(":")
    year = int(year_s)
    page = int(page_s)
    async with SessionFactory() as session:
        pokers = await PokerRepository(session).list_all()
    dates = sorted(
        {
            item.date
            for item in pokers
            if item.date is not None
            and not bool(item.is_going)
            and int(item.date.year) == int(year)
        },
    )
    await callback.message.edit_text(
        f'{InlineText.POKER_HISTORY_PAGE_TEXT_01_PART_1}{year}{InlineText.POKER_HISTORY_PAGE_TEXT_01_PART_2}',
        reply_markup=poker_history_dates_keyboard(year=year, dates=list(dates), page=page),
    )
    await callback.answer()


async def poker_history_date_pick(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    parts = str(callback.data).split(":")
    if len(parts) != 4:
        await callback.answer(InlineText.POKER_HISTORY_DATE_PICK_TEXT_01, show_alert=True)
        return
    try:
        await callback.message.delete()
    except Exception:
        await _clear_inline_keyboard(callback)
    target_date = date.fromisoformat(parts[3])
    async with SessionFactory() as session:
        report = await _build_poker_history_report(session=session, target_date=target_date)
        chart_png = await _build_poker_history_buyins_chart(
            session=session, target_date=target_date
        )
    await callback.message.answer(report, reply_markup=poker_keyboard)
    if chart_png is not None:
        await callback.message.answer_photo(
            photo=BufferedInputFile(chart_png, filename="poker_buyins_history.png"),
            caption=InlineText.POKER_HISTORY_DATE_PICK_TEXT_02,
            reply_markup=poker_keyboard,
        )
    await callback.answer()


async def show_poker_stat_indicators(message: Message, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await state.update_data(
        pokerstat_years=[],
        pokerstat_selected_ids=[],
        pokerstat_sort_id=None,
    )
    async with SessionFactory() as session:
        rows = await PokerDataRepository(session).list_all()
    years = sorted({int(item.date.year) for item in rows if item.date is not None}, reverse=True)
    if not years:
        await message.answer(
            Text.user.POKER_STAT_REPORT.value.format(report=InlineText.SHOW_POKER_STAT_INDICATORS_TEXT_01)
        )
        return
    await message.answer(
        Text.user.STAT_CHOOSE_YEAR.value,
        reply_markup=stat_year_keyboard(
            prefix="pokerstatyear", years=years, selected_years=[], page=0
        ),
    )


async def poker_stat_year_page(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected_years: list[int] = data.get("pokerstat_years", [])
    async with SessionFactory() as session:
        rows = await PokerDataRepository(session).list_all()
    years = sorted({int(item.date.year) for item in rows if item.date is not None}, reverse=True)
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_YEAR.value,
        reply_markup=stat_year_keyboard(
            prefix="pokerstatyear", years=years, selected_years=selected_years, page=page
        ),
    )
    await callback.answer()


async def poker_stat_year_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    _, year_raw, page_raw = callback.data.split(":")
    year = int(year_raw)
    page = int(page_raw)
    data = await state.get_data()
    selected_years = set(data.get("pokerstat_years", []))
    if year in selected_years:
        selected_years.remove(year)
    else:
        selected_years.add(year)
    await state.update_data(pokerstat_years=sorted(selected_years), pokerstat_selected_ids=[])
    async with SessionFactory() as session:
        rows = await PokerDataRepository(session).list_all()
    years = sorted({int(item.date.year) for item in rows if item.date is not None}, reverse=True)
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_YEAR.value,
        reply_markup=stat_year_keyboard(
            prefix="pokerstatyear", years=years, selected_years=sorted(selected_years), page=page
        ),
    )
    await callback.answer()


async def poker_stat_year_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    await state.update_data(pokerstat_years=[], pokerstat_selected_ids=[], pokerstat_sort_id=None)
    await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
    await callback.answer()


async def poker_stat_year_done(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    data = await state.get_data()
    selected_years: list[int] = data.get("pokerstat_years", [])
    if not selected_years:
        async with SessionFactory() as session:
            rows = await PokerDataRepository(session).list_all()
        years = sorted(
            {int(item.date.year) for item in rows if item.date is not None}, reverse=True
        )
        if not years:
            await callback.message.edit_text(
                Text.user.POKER_STAT_REPORT.value.format(report=InlineText.POKER_STAT_YEAR_DONE_TEXT_01)
            )
            await callback.answer()
            return
        current_year = datetime.now().year
        selected_years = [current_year] if current_year in years else [years[0]]
        await state.update_data(pokerstat_years=selected_years)
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    if not indicators:
        await callback.message.edit_text(
            Text.user.POKER_STAT_REPORT.value.format(report=InlineText.POKER_STAT_YEAR_DONE_TEXT_02)
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_PARAMS.value,
        reply_markup=poker_stat_indicators_keyboard(indicators=indicators, page=0, selected_ids=[]),
    )
    await callback.answer()


async def poker_stat_page(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected_ids: list[int] = data.get("pokerstat_selected_ids", [])
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_PARAMS.value,
        reply_markup=poker_stat_indicators_keyboard(
            indicators=indicators, page=page, selected_ids=selected_ids
        ),
    )
    await callback.answer()


async def poker_stat_indicator_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    _, indicator_id_raw, page_raw = callback.data.split(":")
    indicator_id = int(indicator_id_raw)
    page = int(page_raw)
    data = await state.get_data()
    selected = set(data.get("pokerstat_selected_ids", []))
    if indicator_id in selected:
        selected.remove(indicator_id)
    else:
        selected.add(indicator_id)
    await state.update_data(pokerstat_selected_ids=list(selected))
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_PARAMS.value,
        reply_markup=poker_stat_indicators_keyboard(
            indicators=indicators, page=page, selected_ids=list(selected)
        ),
    )
    await callback.answer()


async def poker_stat_done(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    data = await state.get_data()
    selected_ids: list[int] = data.get("pokerstat_selected_ids", [])
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
        if not selected_ids:
            default_indicator = next(
                (item for item in indicators if str(item.description).strip() == InlineText.POKER_STAT_DONE_TEXT_01),
                None,
            )
            if default_indicator is None and indicators:
                default_indicator = indicators[0]
            selected_ids = [int(default_indicator.row_id)] if default_indicator is not None else []
            await state.update_data(pokerstat_selected_ids=selected_ids)
        selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
        if len(selected) == 1:
            selected_years: list[int] = data.get("pokerstat_years", [])
            report = await StatUseCases(
                bet_repository=BetRepository(session),
                poker_data_repository=PokerDataRepository(session),
                achievement_repository=AchievementRepository(session),
                bet_tournament_repository=BetTournamentRepository(session),
                bet_tournament_param_repository=BetTournamentParamRepository(session),
                poker_repository=PokerRepository(session),
            ).get_poker_stat(
                indicators=selected,
                years=selected_years,
                sort_pic=selected[0].pic,
            )
            image_bytes = render_stat_table_png(title="", report=report)
            await callback.message.answer_photo(
                photo=BufferedInputFile(image_bytes, filename="poker_stat.png"),
                caption=_format_stat_caption(
                    report_type=InlineText.POKER_STAT_DONE_TEXT_02,
                    indicators=selected,
                    years=selected_years,
                    include_period=True,
                ),
                reply_markup=poker_keyboard,
            )
            await state.update_data(
                pokerstat_years=[], pokerstat_selected_ids=[], pokerstat_sort_id=None
            )
            await callback.answer()
            return
    await callback.message.edit_text(
        f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
        reply_markup=stat_sort_keyboard(
            prefix="pokerstatsort",
            indicators=selected,
            selected_ids=selected_ids,
            selected_sort_id=None,
            page=0,
        ),
    )
    await state.update_data(pokerstat_sort_id=None)
    await callback.answer()


async def poker_stat_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    await state.update_data(pokerstat_years=[], pokerstat_selected_ids=[], pokerstat_sort_id=None)
    await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
    await callback.answer()


async def poker_stat_sort_page(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected_ids: list[int] = data.get("pokerstat_selected_ids", [])
    selected_sort_id = data.get("pokerstat_sort_id")
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
        selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
    await callback.message.edit_text(
        f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
        reply_markup=stat_sort_keyboard(
            prefix="pokerstatsort",
            indicators=selected,
            selected_ids=selected_ids,
            selected_sort_id=int(selected_sort_id) if selected_sort_id is not None else None,
            page=page,
        ),
    )
    await callback.answer()


async def poker_stat_sort_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    _, indicator_id_raw, page_raw = callback.data.split(":")
    indicator_id = int(indicator_id_raw)
    page = int(page_raw)
    data = await state.get_data()
    current_sort_id = data.get("pokerstat_sort_id")
    new_sort_id = (
        None
        if current_sort_id is not None and int(current_sort_id) == indicator_id
        else indicator_id
    )
    await state.update_data(pokerstat_sort_id=new_sort_id)
    selected_ids: list[int] = data.get("pokerstat_selected_ids", [])
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
        selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
    await callback.message.edit_text(
        f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
        reply_markup=stat_sort_keyboard(
            prefix="pokerstatsort",
            indicators=selected,
            selected_ids=selected_ids,
            selected_sort_id=new_sort_id,
            page=page,
        ),
    )
    await callback.answer()


async def poker_stat_sort_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    await state.update_data(pokerstat_years=[], pokerstat_selected_ids=[], pokerstat_sort_id=None)
    await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
    await callback.answer()


async def poker_stat_sort_done(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    data = await state.get_data()
    selected_ids: list[int] = data.get("pokerstat_selected_ids", [])
    selected_years: list[int] = data.get("pokerstat_years", [])
    sort_id = data.get("pokerstat_sort_id")
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
        selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
        sort_indicator = next(
            (item for item in selected if sort_id is not None and int(item.row_id) == int(sort_id)),
            None,
        )
        sort_pic = sort_indicator.pic if sort_indicator is not None else None
        report = await StatUseCases(
            bet_repository=BetRepository(session),
            poker_data_repository=PokerDataRepository(session),
            achievement_repository=AchievementRepository(session),
            bet_tournament_repository=BetTournamentRepository(session),
            bet_tournament_param_repository=BetTournamentParamRepository(session),
            poker_repository=PokerRepository(session),
        ).get_poker_stat(
            indicators=selected,
            years=selected_years,
            sort_pic=sort_pic,
        )
    image_bytes = render_stat_table_png(title="", report=report)
    await _delete_message_if_possible(callback)
    await callback.message.answer_photo(
        photo=BufferedInputFile(image_bytes, filename="poker_stat.png"),
        caption=_format_stat_caption(
            report_type=InlineText.POKER_STAT_SORT_DONE_TEXT_01,
            indicators=selected,
            years=selected_years,
            include_period=True,
        ),
        reply_markup=poker_keyboard,
    )
    await state.update_data(pokerstat_years=[], pokerstat_selected_ids=[], pokerstat_sort_id=None)
    await callback.answer()
