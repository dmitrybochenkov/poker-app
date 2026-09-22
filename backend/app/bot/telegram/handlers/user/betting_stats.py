from datetime import datetime

from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    betting_current_keyboard,
    betting_stat_indicators_keyboard,
    stat_sort_keyboard,
    stat_year_keyboard,
)
from app.db.repositories.achievement_repository import AchievementRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository
from app.db.session import SessionFactory
from app.services.stat_image import render_stat_table_png

from .common import (
    _betting_tg_keyboard,
    _default_betting_indicator,
    _delete_message_if_possible,
    _ensure_approved_telegram_callback_user,
    _ensure_approved_telegram_user,
    _filter_betting_indicators_by_mode,
    _format_stat_caption,
    _start_betting_stat_flow,
)


async def show_current_betting_tournaments(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await message.answer(
        Text.user.BETTING_CURRENT_MENU.value, reply_markup=betting_current_keyboard
    )


async def show_regular_betting_tournament_stat(message: Message, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await _start_betting_stat_flow(message=message, state=state, mode="regular")


async def show_year_betting_tournament_stat(message: Message, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await _start_betting_stat_flow(message=message, state=state, mode="year")


async def back_to_betting_from_current_tournaments(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await message.answer(Text.user.BETTING_MENU.value, reply_markup=await _betting_tg_keyboard())


async def show_betting_stat_indicators(message: Message, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await _start_betting_stat_flow(message=message, state=state, mode="all")


async def betting_stat_year_page(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected_years: list[int] = data.get("betstat_years", [])
    async with SessionFactory() as session:
        bets = await BetRepository(session).list_all()
    years = sorted({int(item.date.year) for item in bets if item.date is not None}, reverse=True)
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_YEAR.value,
        reply_markup=stat_year_keyboard(
            prefix="betstatyear", years=years, selected_years=selected_years, page=page
        ),
    )
    await callback.answer()


async def betting_stat_year_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    _, year_raw, page_raw = callback.data.split(":")
    year = int(year_raw)
    page = int(page_raw)
    data = await state.get_data()
    selected_years = set(data.get("betstat_years", []))
    if year in selected_years:
        selected_years.remove(year)
    else:
        selected_years.add(year)
    await state.update_data(betstat_years=sorted(selected_years), betstat_selected_ids=[])
    async with SessionFactory() as session:
        bets = await BetRepository(session).list_all()
    years = sorted({int(item.date.year) for item in bets if item.date is not None}, reverse=True)
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_YEAR.value,
        reply_markup=stat_year_keyboard(
            prefix="betstatyear", years=years, selected_years=sorted(selected_years), page=page
        ),
    )
    await callback.answer()


async def betting_stat_year_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    await state.update_data(
        betstat_years=[], betstat_selected_ids=[], betstat_mode="all", betstat_sort_id=None
    )
    await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
    await callback.answer()


async def betting_stat_year_done(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    data = await state.get_data()
    selected_years: list[int] = data.get("betstat_years", [])
    mode = data.get("betstat_mode", "all")
    if not selected_years:
        async with SessionFactory() as session:
            bets = await BetRepository(session).list_all()
        years = sorted(
            {int(item.date.year) for item in bets if item.date is not None}, reverse=True
        )
        if not years:
            await callback.message.edit_text("Нет данных по ставкам.")
            await callback.answer()
            return
        current_year = datetime.now().year
        selected_years = [current_year] if current_year in years else [years[0]]
        await state.update_data(betstat_years=selected_years)
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    if not indicators:
        await callback.message.edit_text(Text.user.BETTING_CURRENT_EMPTY.value)
        await callback.answer()
        return
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_PARAMS.value,
        reply_markup=betting_stat_indicators_keyboard(
            indicators=indicators, page=0, selected_ids=[]
        ),
    )
    await callback.answer()


async def betting_stat_mode_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    mode = callback.data.split(":", 1)[1]
    if mode not in {"all", "regular", "year"}:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    await state.update_data(betstat_mode=mode, betstat_selected_ids=[])
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    if not indicators:
        await callback.message.edit_text(Text.user.BETTING_CURRENT_EMPTY.value)
        await callback.answer()
        return
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_PARAMS.value,
        reply_markup=betting_stat_indicators_keyboard(
            indicators=indicators, page=0, selected_ids=[]
        ),
    )
    await callback.answer()


async def betting_stat_page(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected_ids: list[int] = data.get("betstat_selected_ids", [])
    mode = data.get("betstat_mode", "all")
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_PARAMS.value,
        reply_markup=betting_stat_indicators_keyboard(
            indicators=indicators, page=page, selected_ids=selected_ids
        ),
    )
    await callback.answer()


async def betting_stat_indicator_selected(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    _, indicator_id_raw, page_raw = callback.data.split(":")
    indicator_id = int(indicator_id_raw)
    page = int(page_raw)
    data = await state.get_data()
    selected = set(data.get("betstat_selected_ids", []))
    mode = data.get("betstat_mode", "all")
    if indicator_id in selected:
        selected.remove(indicator_id)
    else:
        selected.add(indicator_id)
    await state.update_data(betstat_selected_ids=list(selected))
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
    await callback.message.edit_text(
        Text.user.STAT_CHOOSE_PARAMS.value,
        reply_markup=betting_stat_indicators_keyboard(
            indicators=indicators, page=page, selected_ids=list(selected)
        ),
    )
    await callback.answer()


async def betting_stat_done(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    data = await state.get_data()
    selected_ids: list[int] = data.get("betstat_selected_ids", [])
    mode = data.get("betstat_mode", "all")
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
        indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
        if not selected_ids:
            default_indicator = _default_betting_indicator(indicators=indicators, mode=mode)
            selected_ids = [int(default_indicator.row_id)] if default_indicator is not None else []
            await state.update_data(betstat_selected_ids=selected_ids)
        selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
        if len(selected) == 1:
            selected_years: list[int] = data.get("betstat_years", [])
            report = await StatUseCases(
                bet_repository=BetRepository(session),
                achievement_repository=AchievementRepository(session),
                bet_tournament_repository=BetTournamentRepository(session),
                bet_tournament_param_repository=BetTournamentParamRepository(session),
                poker_repository=PokerRepository(session),
            ).get_betting_stat(
                indicators=selected,
                mode=mode,
                years=selected_years,
                sort_pic=selected[0].pic,
            )
            image_bytes = render_stat_table_png(title="", report=report)
            await _delete_message_if_possible(callback)
            await callback.message.answer_photo(
                photo=BufferedInputFile(image_bytes, filename="betting_stat.png"),
                caption=_format_stat_caption(
                    report_type=(
                        "Регулярный турнир"
                        if mode == "regular"
                        else "Годовой турнир"
                        if mode == "year"
                        else "Статистика ставок"
                    ),
                    indicators=selected,
                    years=selected_years,
                    include_period=(mode == "all"),
                ),
            )
            await state.update_data(
                betstat_years=[], betstat_selected_ids=[], betstat_mode="all", betstat_sort_id=None
            )
            await callback.answer()
            return
    await callback.message.edit_text(
        f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
        reply_markup=stat_sort_keyboard(
            prefix="betstatsort",
            indicators=selected,
            selected_ids=selected_ids,
            selected_sort_id=None,
            page=0,
        ),
    )
    await state.update_data(betstat_sort_id=None)
    await callback.answer()


async def betting_stat_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    await state.update_data(
        betstat_years=[], betstat_selected_ids=[], betstat_mode="all", betstat_sort_id=None
    )
    await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
    await callback.answer()


async def betting_stat_sort_page(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected_ids: list[int] = data.get("betstat_selected_ids", [])
    mode = data.get("betstat_mode", "all")
    selected_sort_id = data.get("betstat_sort_id")
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
        indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
        selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
    await callback.message.edit_text(
        f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
        reply_markup=stat_sort_keyboard(
            prefix="betstatsort",
            indicators=selected,
            selected_ids=selected_ids,
            selected_sort_id=int(selected_sort_id) if selected_sort_id is not None else None,
            page=page,
        ),
    )
    await callback.answer()


async def betting_stat_sort_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    _, indicator_id_raw, page_raw = callback.data.split(":")
    indicator_id = int(indicator_id_raw)
    page = int(page_raw)
    data = await state.get_data()
    current_sort_id = data.get("betstat_sort_id")
    new_sort_id = (
        None
        if current_sort_id is not None and int(current_sort_id) == indicator_id
        else indicator_id
    )
    await state.update_data(betstat_sort_id=new_sort_id)
    selected_ids: list[int] = data.get("betstat_selected_ids", [])
    mode = data.get("betstat_mode", "all")
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
        indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
        selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
    await callback.message.edit_text(
        f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
        reply_markup=stat_sort_keyboard(
            prefix="betstatsort",
            indicators=selected,
            selected_ids=selected_ids,
            selected_sort_id=new_sort_id,
            page=page,
        ),
    )
    await callback.answer()


async def betting_stat_sort_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    await state.update_data(
        betstat_years=[], betstat_selected_ids=[], betstat_mode="all", betstat_sort_id=None
    )
    await callback.message.edit_text(Text.user.STAT_EXPORT_CANCELED.value)
    await callback.answer()


async def betting_stat_sort_done(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return
    if not await _ensure_approved_telegram_callback_user(callback):
        return
    data = await state.get_data()
    selected_ids: list[int] = data.get("betstat_selected_ids", [])
    mode = data.get("betstat_mode", "all")
    selected_years: list[int] = data.get("betstat_years", [])
    sort_id = data.get("betstat_sort_id")
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
        indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
        selected = [item for item in indicators if int(item.row_id) in set(selected_ids)]
        sort_indicator = next(
            (item for item in selected if sort_id is not None and int(item.row_id) == int(sort_id)),
            None,
        )
        sort_pic = sort_indicator.pic if sort_indicator is not None else None
        report = await StatUseCases(
            bet_repository=BetRepository(session),
            achievement_repository=AchievementRepository(session),
            bet_tournament_repository=BetTournamentRepository(session),
            bet_tournament_param_repository=BetTournamentParamRepository(session),
            poker_repository=PokerRepository(session),
        ).get_betting_stat(
            indicators=selected,
            mode=mode,
            years=selected_years,
            sort_pic=sort_pic,
        )
    image_bytes = render_stat_table_png(title="", report=report)
    await _delete_message_if_possible(callback)
    await callback.message.answer_photo(
        photo=BufferedInputFile(image_bytes, filename="betting_stat.png"),
        caption=_format_stat_caption(
            report_type=(
                "Регулярный турнир"
                if mode == "regular"
                else "Годовой турнир"
                if mode == "year"
                else "Статистика ставок"
            ),
            indicators=selected,
            years=selected_years,
            include_period=(mode == "all"),
        ),
    )
    await state.update_data(
        betstat_years=[], betstat_selected_ids=[], betstat_mode="all", betstat_sort_id=None
    )
    await callback.answer()
