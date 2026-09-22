from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    admin_main_keyboard,
    betting_info_keyboard,
    main_info_keyboard,
    new_user_keyboard,
    poker_info_keyboard,
    poker_keyboard,
    poll_menu_keyboard,
)
from app.bot.telegram.states import RegistrationState
from app.db.repositories.achievement_repository import AchievementRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository
from app.db.session import SessionFactory

from .common import (
    _approved_tg_keyboard,
    _betting_tg_keyboard,
    _ensure_approved_telegram_user,
    _format_achievement_info_report,
    _format_stat_info_report,
    _get_telegram_user,
)


async def open_betting_menu(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await message.answer(Text.user.BETTING_MENU.value, reply_markup=await _betting_tg_keyboard())


async def open_poker_menu(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await message.answer(Text.user.POKER_MENU.value, reply_markup=poker_keyboard)


async def open_info_menu(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await message.answer("Раздел информации.", reply_markup=main_info_keyboard)


async def open_next_poker_date_menu(message: Message) -> None:
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
    await message.answer("О следующем покере.", reply_markup=poll_menu_keyboard)


async def open_admin_panel(message: Message) -> None:
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
        await message.answer(
            Text.admin.NO_RIGHTS.value, reply_markup=await _approved_tg_keyboard(user)
        )
        return
    await message.answer(Text.admin.ADMIN_PANEL.value, reply_markup=admin_main_keyboard)


async def back_from_admin_to_main(message: Message) -> None:
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
    await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


async def back_to_main_from_betting(message: Message, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    if await state.get_state() == RegistrationState.waiting_for_bet_payment_receipt.state:
        await state.clear()
    user = await _get_telegram_user(message.from_user.id)
    if user is None:
        await message.answer(
            Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
        )
        return
    await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


async def back_to_main_from_poker(message: Message, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    if await state.get_state() == RegistrationState.waiting_for_bet_payment_receipt.state:
        await state.clear()
    user = await _get_telegram_user(message.from_user.id)
    if user is None:
        await message.answer(
            Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
        )
        return
    await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


async def back_to_main_from_room(message: Message, state: FSMContext) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    if await state.get_state() == RegistrationState.waiting_for_bet_payment_receipt.state:
        await state.clear()
    user = await _get_telegram_user(message.from_user.id)
    if user is None:
        await message.answer(
            Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
        )
        return
    await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


async def back_to_main_from_poll_menu(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    user = await _get_telegram_user(message.from_user.id)
    if user is None:
        await message.answer(
            Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
        )
        return
    await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


async def show_poker_info(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await message.answer(Text.user.POKER_INFO.value, reply_markup=poker_info_keyboard)


async def show_betting_info(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await message.answer(Text.user.BETTING_MENU.value, reply_markup=betting_info_keyboard)


async def back_to_main_from_info(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    user = await _get_telegram_user(message.from_user.id)
    if user is None:
        await message.answer(
            Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
        )
        return
    await message.answer(Text.user.MAIN_MENU.value, reply_markup=await _approved_tg_keyboard(user))


async def show_betting_rules(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    await message.answer(
        Text.user.BET_RULES.value, reply_markup=betting_info_keyboard, parse_mode="HTML"
    )


async def show_betting_stat_info(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="betting")
    await message.answer(
        _format_stat_info_report(indicators), reply_markup=betting_info_keyboard, parse_mode="HTML"
    )


async def show_betting_achievement_info(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    async with SessionFactory() as session:
        achievement_repository = AchievementRepository(session)
        indicator_repository = StatIndicatorRepository(session)
        achievements = await achievement_repository.list_by_type(achievement_type="betting")
        indicators = await indicator_repository.list_by_type(indicator_type="betting")
    indicators_by_id = {int(item.row_id): (str(item.pic), item.description) for item in indicators}
    await message.answer(
        _format_achievement_info_report(achievements, indicators_by_id),
        reply_markup=betting_info_keyboard,
        parse_mode="HTML",
    )


async def show_poker_stat_info(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    async with SessionFactory() as session:
        indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
    await message.answer(
        _format_stat_info_report(indicators), reply_markup=poker_info_keyboard, parse_mode="HTML"
    )


async def show_poker_achievement_info(message: Message) -> None:
    if not await _ensure_approved_telegram_user(message):
        return
    async with SessionFactory() as session:
        achievement_repository = AchievementRepository(session)
        indicator_repository = StatIndicatorRepository(session)
        achievements = await achievement_repository.list_by_type(achievement_type="poker")
        indicators = await indicator_repository.list_by_type(indicator_type="poker")
    indicators_by_id = {int(item.row_id): (str(item.pic), item.description) for item in indicators}
    await message.answer(
        _format_achievement_info_report(achievements, indicators_by_id),
        reply_markup=poker_info_keyboard,
        parse_mode="HTML",
    )
