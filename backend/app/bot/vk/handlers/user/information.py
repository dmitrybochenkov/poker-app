from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
)
from app.bot.vk.keyboards import (
    betting_info_keyboard,
    poker_info_keyboard,
)
from app.db.repositories.achievement_repository import AchievementRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository
from app.db.session import SessionFactory
from fastapi.responses import PlainTextResponse

from .common import (
    HANDLER_UNMATCHED,
    _format_achievement_info_report,
    _format_stat_info_report,
    _strip_html_tags,
)


async def _text_1_15(*, user_id, text, raw_message):
    if text == Buttons.bettingInfo.BETTING_RULES.value:
        await send_vk_message(
            user_id=user_id,
            message=_strip_html_tags(Text.user.BET_RULES.value),
            keyboard=betting_info_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_16(*, user_id, text, raw_message):
    if text == Buttons.bettingInfo.BETTING_STAT_INFO.value:
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
        await send_vk_message(
            user_id=user_id,
            message=_format_stat_info_report(indicators),
            keyboard=betting_info_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_17(*, user_id, text, raw_message):
    if text == Buttons.bettingInfo.BETTING_ACH_INFO.value:
        async with SessionFactory() as session:
            achievements = await AchievementRepository(session).list_by_type(
                achievement_type="betting"
            )
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
        indicators_by_id = {
            int(item.row_id): (str(item.pic), item.description) for item in indicators
        }
        await send_vk_message(
            user_id=user_id,
            message=_format_achievement_info_report(achievements, indicators_by_id),
            keyboard=betting_info_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_18(*, user_id, text, raw_message):
    if text == Buttons.pokerInfo.POKER_STAT_INFO.value:
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
        await send_vk_message(
            user_id=user_id,
            message=_format_stat_info_report(indicators),
            keyboard=poker_info_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_19(*, user_id, text, raw_message):
    if text == Buttons.pokerInfo.POKER_ACH_INFO.value:
        async with SessionFactory() as session:
            achievements = await AchievementRepository(session).list_by_type(
                achievement_type="poker"
            )
            indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
        indicators_by_id = {
            int(item.row_id): (str(item.pic), item.description) for item in indicators
        }
        await send_vk_message(
            user_id=user_id,
            message=_format_achievement_info_report(achievements, indicators_by_id),
            keyboard=poker_info_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
