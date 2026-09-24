from datetime import date, datetime

from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.inline.vk.user import poker_stats as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
    send_vk_photo,
)
from app.bot.vk.keyboards import (
    poker_history_dates_keyboard,
    poker_history_year_keyboard,
    poker_info_keyboard,
    poker_keyboard,
    poker_stat_indicators_keyboard,
    stat_sort_keyboard,
    stat_year_keyboard,
)
from app.bot.vk.state import (
    vk_user_contexts,
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
    HANDLER_UNMATCHED,
    STAT_SNACKBAR,
    _build_poker_history_buyins_chart,
    _build_poker_history_report,
    _delete_event_message_if_possible,
)
from .stat_helpers import _format_stat_caption


async def handle_pokerhist_cancel_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerhist_cancel":
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerhistyear_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerhistyear":
        year = callback_payload.get("year")
        if not isinstance(year, int):
            return PlainTextResponse("ok")
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
            await send_vk_message_event_answer(
                event_id=event_id, user_id=user_id, peer_id=peer_id, text=InlineText.EVENT_0_08_TEXT_01
            )
            return PlainTextResponse("ok")
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=f'{InlineText.EVENT_0_08_TEXT_02_PART_1}{int(year)}{InlineText.EVENT_0_08_TEXT_02_PART_2}',
            keyboard=poker_history_dates_keyboard(year=int(year), dates=list(dates), page=0),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerhistpage_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerhistpage":
        year = callback_payload.get("year")
        page = callback_payload.get("page")
        if not isinstance(year, int) or not isinstance(page, int):
            return PlainTextResponse("ok")
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
            await send_vk_message_event_answer(
                event_id=event_id, user_id=user_id, peer_id=peer_id, text=InlineText.EVENT_0_09_TEXT_01
            )
            return PlainTextResponse("ok")
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=f'{InlineText.EVENT_0_09_TEXT_02_PART_1}{int(year)}{InlineText.EVENT_0_09_TEXT_02_PART_2}',
            keyboard=poker_history_dates_keyboard(
                year=int(year), dates=list(dates), page=int(page)
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerhistdate_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerhistdate":
        target_date_raw = callback_payload.get("date")
        if not isinstance(target_date_raw, str):
            return PlainTextResponse("ok")
        try:
            target_date = date.fromisoformat(target_date_raw)
        except Exception:
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            report = await _build_poker_history_report(session=session, target_date=target_date)
            chart_png = await _build_poker_history_buyins_chart(
                session=session, target_date=target_date
            )
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=user_id, message=report, keyboard=poker_keyboard)
        if chart_png is not None:
            await send_vk_photo(
                user_id=user_id, image_bytes=chart_png, filename="poker_buyins_history.png"
            )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerstat_page_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerstat_page":
        page = callback_payload.get("page")
        if not isinstance(page, int):
            return PlainTextResponse("ok")
        selected_ids = [
            int(x)
            for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",")
            if x
        ]
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.user.STAT_CHOOSE_PARAMS.value,
            keyboard=poker_stat_indicators_keyboard(
                indicators=indicators, page=page, selected_ids=selected_ids
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerstat_toggle_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerstat_toggle":
        indicator_id = callback_payload.get("indicator_id")
        page = callback_payload.get("page", 0)
        if not isinstance(indicator_id, int):
            return PlainTextResponse("ok")
        selected = {
            int(x)
            for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",")
            if x
        }
        if indicator_id in selected:
            selected.remove(indicator_id)
        else:
            selected.add(indicator_id)
        vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ",".join(
            str(x) for x in sorted(selected)
        )
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.user.STAT_CHOOSE_PARAMS.value,
            keyboard=poker_stat_indicators_keyboard(
                indicators=indicators,
                page=int(page) if isinstance(page, int) else 0,
                selected_ids=list(selected),
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerstat_done_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerstat_done":
        selected_ids = {
            int(x)
            for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",")
            if x
        }
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
            if not selected_ids:
                default_indicator = next(
                    (item for item in indicators if str(item.description).strip() == InlineText.EVENT_0_30_TEXT_01),
                    None,
                )
                if default_indicator is None and indicators:
                    default_indicator = indicators[0]
                selected_ids = (
                    {int(default_indicator.row_id)} if default_indicator is not None else set()
                )
                vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ",".join(
                    str(x) for x in sorted(selected_ids)
                )
            selected = [item for item in indicators if int(item.row_id) in selected_ids]
            if len(selected) == 1:
                selected_years = [
                    int(x)
                    for x in vk_user_contexts.get(user_id, {}).get("pokerstat_years", "").split(",")
                    if x
                ]
                report = await StatUseCases(
                    bet_repository=BetRepository(session),
                    poker_data_repository=PokerDataRepository(session),
                    achievement_repository=AchievementRepository(session),
                    bet_tournament_repository=BetTournamentRepository(session),
                    bet_tournament_param_repository=BetTournamentParamRepository(session),
                    poker_repository=PokerRepository(session),
                ).get_poker_stat(
                    indicators=selected, years=selected_years, sort_pic=selected[0].pic
                )
                await send_vk_message_event_answer(
                    event_id=event_id, user_id=user_id, peer_id=peer_id, text=InlineText.EVENT_0_30_TEXT_02
                )
                await _delete_event_message_if_possible(
                    peer_id=peer_id, conversation_message_id=conversation_message_id
                )
                image_bytes = render_stat_table_png(title="", report=report)
                await send_vk_photo(
                    user_id=user_id,
                    image_bytes=image_bytes,
                    filename="poker_stat.png",
                    message=_format_stat_caption(
                        report_type=InlineText.EVENT_0_30_TEXT_03,
                        indicators=selected,
                        years=selected_years,
                        include_period=True,
                    ),
                    keyboard=poker_keyboard,
                )
                vk_user_contexts.setdefault(user_id, {})["pokerstat_years"] = ""
                vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ""
                vk_user_contexts.setdefault(user_id, {})["pokerstat_sort_id"] = ""
                return PlainTextResponse("ok")
        vk_user_contexts.setdefault(user_id, {})["pokerstat_sort_id"] = ""
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
            keyboard=stat_sort_keyboard(
                action="pokerstat_sort",
                indicators=selected,
                selected_ids=list(selected_ids),
                selected_sort_id=None,
                page=0,
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerstat_sort_page_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerstat_sort_page":
        page = callback_payload.get("page", 0)
        selected_ids = {
            int(x)
            for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",")
            if x
        }
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
            selected = [item for item in indicators if int(item.row_id) in selected_ids]
        sort_id_raw = vk_user_contexts.get(user_id, {}).get("pokerstat_sort_id")
        sort_id = (
            int(sort_id_raw) if isinstance(sort_id_raw, str) and sort_id_raw.isdigit() else None
        )
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
            keyboard=stat_sort_keyboard(
                action="pokerstat_sort",
                indicators=selected,
                selected_ids=list(selected_ids),
                selected_sort_id=sort_id,
                page=int(page) if isinstance(page, int) else 0,
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerstat_sort_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerstat_sort":
        indicator_id = callback_payload.get("indicator_id")
        if not isinstance(indicator_id, int):
            return PlainTextResponse("ok")
        page = callback_payload.get("page", 0)
        user_ctx = vk_user_contexts.setdefault(user_id, {})
        current_sort_id_raw = user_ctx.get("pokerstat_sort_id")
        current_sort_id = (
            int(current_sort_id_raw)
            if isinstance(current_sort_id_raw, str) and current_sort_id_raw.isdigit()
            else None
        )
        new_sort_id = None if current_sort_id == indicator_id else indicator_id
        user_ctx["pokerstat_sort_id"] = str(new_sort_id) if new_sort_id is not None else ""
        selected_ids = {
            int(x)
            for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",")
            if x
        }
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
            selected = [item for item in indicators if int(item.row_id) in selected_ids]
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=f"{Text.user.STAT_CHOOSE_SORT.value}\n{Text.user.STAT_CHOOSED_SORT_DEFAULT.value}",
            keyboard=stat_sort_keyboard(
                action="pokerstat_sort",
                indicators=selected,
                selected_ids=list(selected_ids),
                selected_sort_id=new_sort_id,
                page=int(page) if isinstance(page, int) else 0,
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerstat_sort_done_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerstat_sort_done":
        selected_ids = {
            int(x)
            for x in vk_user_contexts.get(user_id, {}).get("pokerstat_selected_ids", "").split(",")
            if x
        }
        selected_years = [
            int(x)
            for x in vk_user_contexts.get(user_id, {}).get("pokerstat_years", "").split(",")
            if x
        ]
        sort_id_raw = vk_user_contexts.get(user_id, {}).get("pokerstat_sort_id")
        sort_id = (
            int(sort_id_raw) if isinstance(sort_id_raw, str) and sort_id_raw.isdigit() else None
        )
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(indicator_type="poker")
            selected = [item for item in indicators if int(item.row_id) in selected_ids]
            sort_indicator = next(
                (item for item in selected if sort_id is not None and int(item.row_id) == sort_id),
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
            ).get_poker_stat(indicators=selected, years=selected_years, sort_pic=sort_pic)
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=InlineText.EVENT_0_33_TEXT_01
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        image_bytes = render_stat_table_png(title="", report=report)
        await send_vk_photo(
            user_id=user_id,
            image_bytes=image_bytes,
            filename="poker_stat.png",
            message=_format_stat_caption(
                report_type=InlineText.EVENT_0_33_TEXT_02,
                indicators=selected,
                years=selected_years,
                include_period=True,
            ),
            keyboard=poker_keyboard,
        )
        vk_user_contexts.setdefault(user_id, {})["pokerstat_years"] = ""
        vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["pokerstat_sort_id"] = ""
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerstat_sort_cancel_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerstat_sort_cancel":
        vk_user_contexts.setdefault(user_id, {})["pokerstat_years"] = ""
        vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["pokerstat_sort_id"] = ""
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.STAT_EXPORT_CANCELED.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=user_id, message=Text.user.STAT_EXPORT_CANCELED.value)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_stat_year_actions_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action in {
        "pokerstatyear_toggle",
        "pokerstatyear_page",
        "pokerstatyear_done",
        "pokerstatyear_cancel",
    }:
        user_ctx = vk_user_contexts.setdefault(user_id, {})
        page = callback_payload.get("page", 0)
        selected_years = [int(x) for x in user_ctx.get("pokerstat_years", "").split(",") if x]
        async with SessionFactory() as session:
            rows = await PokerDataRepository(session).list_all()
        years = sorted(
            {int(item.date.year) for item in rows if item.date is not None}, reverse=True
        )
        if action == "pokerstatyear_toggle":
            year = callback_payload.get("year")
            if not isinstance(year, int):
                return PlainTextResponse("ok")
            selected_set = set(selected_years)
            if year in selected_set:
                selected_set.remove(year)
            else:
                selected_set.add(year)
            selected_years = sorted(selected_set)
            user_ctx["pokerstat_years"] = ",".join(str(x) for x in selected_years)
            user_ctx["pokerstat_selected_ids"] = ""
        if action == "pokerstatyear_done":
            if not selected_years:
                current_year = datetime.now().year
                selected_years = (
                    [current_year] if current_year in years else ([years[0]] if years else [])
                )
                user_ctx["pokerstat_years"] = ",".join(str(x) for x in selected_years)
            user_ctx["pokerstat_selected_ids"] = ""
            async with SessionFactory() as session:
                indicators = await StatIndicatorRepository(session).list_by_type(
                    indicator_type="poker"
                )
            await send_vk_message_event_answer(
                event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
            )
            await _delete_event_message_if_possible(
                peer_id=peer_id, conversation_message_id=conversation_message_id
            )
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STAT_CHOOSE_PARAMS.value,
                keyboard=poker_stat_indicators_keyboard(
                    indicators=indicators, page=0, selected_ids=[]
                ),
            )
            return PlainTextResponse("ok")
        if action == "pokerstatyear_cancel":
            user_ctx["pokerstat_years"] = ""
            user_ctx["pokerstat_selected_ids"] = ""
            user_ctx["pokerstat_sort_id"] = ""
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.STAT_EXPORT_CANCELED.value,
            )
            await _delete_event_message_if_possible(
                peer_id=peer_id, conversation_message_id=conversation_message_id
            )
            await send_vk_message(user_id=user_id, message=Text.user.STAT_EXPORT_CANCELED.value)
            return PlainTextResponse("ok")
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.user.STAT_CHOOSE_YEAR.value,
            keyboard=stat_year_keyboard(
                action="pokerstatyear",
                years=years,
                selected_years=selected_years,
                page=int(page) if isinstance(page, int) else 0,
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_pokerstat_cancel_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "pokerstat_cancel":
        vk_user_contexts.setdefault(user_id, {})["pokerstat_years"] = ""
        vk_user_contexts.setdefault(user_id, {})["pokerstat_selected_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["pokerstat_sort_id"] = ""
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.STAT_EXPORT_CANCELED.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=user_id, message=Text.user.STAT_EXPORT_CANCELED.value)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_history_text(*, user_id, text, raw_message):
    if text in {Buttons.poker.HISTORY.value, Buttons.pokerInfo.HISTORY.value}:
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
            await send_vk_message(
                user_id=user_id, message=InlineText.TEXT_1_20_TEXT_01, keyboard=poker_info_keyboard
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=InlineText.TEXT_1_20_TEXT_02,
            keyboard=poker_history_year_keyboard(years=years),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_poker_stat_text(*, user_id, text, raw_message):
    if text == Buttons.poker.POKER_STAT.value:
        user_ctx = vk_user_contexts.setdefault(user_id, {})
        user_ctx["pokerstat_years"] = ""
        user_ctx["pokerstat_selected_ids"] = ""
        user_ctx["pokerstat_sort_id"] = ""
        async with SessionFactory() as session:
            rows = await PokerDataRepository(session).list_all()
        years = sorted(
            {int(item.date.year) for item in rows if item.date is not None}, reverse=True
        )
        if not years:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.POKER_STAT_REPORT.value.format(report=InlineText.TEXT_1_21_TEXT_01),
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.STAT_CHOOSE_YEAR.value,
            keyboard=stat_year_keyboard(
                action="pokerstatyear", years=years, selected_years=[], page=0
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
