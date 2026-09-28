
from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.betting_tournament_periods import (
    default_betting_tournament_period_ids,
    list_betting_tournament_periods,
    parse_betting_tournament_period_ids,
)
from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.inline.vk.user import betting_stats as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
    send_vk_photo,
)
from app.bot.vk.keyboards import (
    betting_current_keyboard,
    betting_stat_indicators_keyboard,
    betting_tournament_periods_keyboard,
    stat_sort_keyboard,
)
from app.bot.vk.state import (
    vk_user_contexts,
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
    HANDLER_UNMATCHED,
    STAT_SNACKBAR,
    _betting_vk_keyboard,
    _delete_event_message_if_possible,
)
from .stat_helpers import (
    _default_betting_indicator,
    _filter_betting_indicators_by_mode,
    _format_stat_caption,
)


async def handle_betstat_page_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "betstat_page":
        page = callback_payload.get("page")
        if not isinstance(page, int):
            return PlainTextResponse("ok")
        user_ctx = vk_user_contexts.get(user_id, {})
        mode = user_ctx.get("betstat_mode", "all")
        selected_ids = [int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x]
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
        indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.user.STAT_CHOOSE_PARAMS.value,
            keyboard=betting_stat_indicators_keyboard(
                indicators=indicators, page=page, selected_ids=selected_ids
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betstat_toggle_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "betstat_toggle":
        indicator_id = callback_payload.get("indicator_id")
        page = callback_payload.get("page", 0)
        if not isinstance(indicator_id, int):
            return PlainTextResponse("ok")
        mode = vk_user_contexts.get(user_id, {}).get("betstat_mode", "all")
        selected = {
            int(x)
            for x in vk_user_contexts.get(user_id, {}).get("betstat_selected_ids", "").split(",")
            if x
        }
        if indicator_id in selected:
            selected.remove(indicator_id)
        else:
            selected.add(indicator_id)
        vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ",".join(
            str(x) for x in sorted(selected)
        )
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
        indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.user.STAT_CHOOSE_PARAMS.value,
            keyboard=betting_stat_indicators_keyboard(
                indicators=indicators,
                page=int(page) if isinstance(page, int) else 0,
                selected_ids=list(selected),
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betstat_mode_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "betstat_mode":
        mode = callback_payload.get("mode")
        if mode not in {"all", "regular", "year"}:
            return PlainTextResponse("ok")
        vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = mode
        vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
        indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        if not indicators:
            await send_vk_message(user_id=user_id, message=Text.user.BETTING_CURRENT_EMPTY.value)
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.STAT_CHOOSE_PARAMS.value,
            keyboard=betting_stat_indicators_keyboard(
                indicators=indicators, page=0, selected_ids=[]
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betting_tournament_actions_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action not in {
        "betstattour_toggle",
        "betstattour_page",
        "betstattour_done",
        "betstattour_cancel",
    }:
        return HANDLER_UNMATCHED
    user_ctx = vk_user_contexts.setdefault(user_id, {})
    page = callback_payload.get("page", 0)
    selected = {
        value for value in user_ctx.get("betstat_period_ids", "").split(",") if value
    }
    async with SessionFactory() as session:
        periods = list_betting_tournament_periods(
            await BetTournamentRepository(session).list_active()
        )
    if action == "betstattour_toggle":
        period_id = callback_payload.get("period_id")
        valid_ids = {period.selection_id for period in periods}
        if not isinstance(period_id, str) or period_id not in valid_ids:
            return PlainTextResponse("ok")
        if period_id in selected:
            selected.remove(period_id)
        else:
            selected.add(period_id)
        user_ctx["betstat_period_ids"] = ",".join(sorted(selected))
        user_ctx["betstat_selected_ids"] = ""
    if action == "betstattour_done":
        if not selected:
            selected = default_betting_tournament_period_ids(periods)
            user_ctx["betstat_period_ids"] = ",".join(sorted(selected))
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
        indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode="all")
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.user.STAT_CHOOSE_PARAMS.value,
            keyboard=betting_stat_indicators_keyboard(
                indicators=indicators, page=0, selected_ids=[]
            ),
        )
        return PlainTextResponse("ok")
    if action == "betstattour_cancel":
        user_ctx["betstat_period_ids"] = ""
        user_ctx["betstat_selected_ids"] = ""
        user_ctx["betstat_mode"] = "all"
        user_ctx["betstat_sort_id"] = ""
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
        message=Text.user.STAT_CHOOSE_BETTING_TOURNAMENT.value,
        keyboard=betting_tournament_periods_keyboard(
            periods=periods,
            selected_period_ids=selected,
            page=int(page) if isinstance(page, int) else 0,
        ),
    )
    return PlainTextResponse("ok")


async def handle_betstat_done_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "betstat_done":
        user_ctx = vk_user_contexts.get(user_id, {})
        mode = user_ctx.get("betstat_mode", "all")
        selected_ids = {int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x}
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
            indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
            if not selected_ids:
                default_indicator = _default_betting_indicator(indicators=indicators, mode=mode)
                selected_ids = (
                    {int(default_indicator.row_id)} if default_indicator is not None else set()
                )
                vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ",".join(
                    str(x) for x in sorted(selected_ids)
                )
            selected = [item for item in indicators if int(item.row_id) in selected_ids]
            if len(selected) == 1:
                selected_periods = parse_betting_tournament_period_ids(
                    [x for x in user_ctx.get("betstat_period_ids", "").split(",") if x]
                )
                report = await StatUseCases(
                    bet_repository=BetRepository(session),
                    achievement_repository=AchievementRepository(session),
                    bet_tournament_repository=BetTournamentRepository(session),
                    bet_tournament_param_repository=BetTournamentParamRepository(session),
                    poker_repository=PokerRepository(session),
                ).get_betting_stat(
                    indicators=selected,
                    mode=mode,
                    tournament_periods=selected_periods if mode == "all" else None,
                    sort_pic=selected[0].pic,
                )
                await send_vk_message_event_answer(
                    event_id=event_id, user_id=user_id, peer_id=peer_id, text=InlineText.EVENT_0_37_TEXT_01
                )
                await _delete_event_message_if_possible(
                    peer_id=peer_id, conversation_message_id=conversation_message_id
                )
                image_bytes = render_stat_table_png(title="", report=report)
                await send_vk_photo(
                    user_id=user_id,
                    image_bytes=image_bytes,
                    filename="betting_stat.png",
                    message=_format_stat_caption(
                        report_type=(
                            InlineText.EVENT_0_37_TEXT_02
                            if mode == "regular"
                            else InlineText.EVENT_0_37_TEXT_03
                            if mode == "year"
                            else InlineText.EVENT_0_37_TEXT_04
                        ),
                        indicators=selected,
                        period_labels=[item.label for item in selected_periods],
                        include_period=(mode == "all"),
                    ),
                )
                vk_user_contexts.setdefault(user_id, {})["betstat_period_ids"] = ""
                vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
                vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = "all"
                vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = ""
                return PlainTextResponse("ok")
        vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = ""
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
            keyboard=stat_sort_keyboard(
                action="betstat_sort",
                indicators=selected,
                selected_ids=list(selected_ids),
                selected_sort_id=None,
                page=0,
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betstat_sort_page_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "betstat_sort_page":
        page = callback_payload.get("page", 0)
        user_ctx = vk_user_contexts.get(user_id, {})
        mode = user_ctx.get("betstat_mode", "all")
        selected_ids = {int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x}
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
            indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
            selected = [item for item in indicators if int(item.row_id) in selected_ids]
        sort_id_raw = user_ctx.get("betstat_sort_id")
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
            message=f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
            keyboard=stat_sort_keyboard(
                action="betstat_sort",
                indicators=selected,
                selected_ids=list(selected_ids),
                selected_sort_id=sort_id,
                page=int(page) if isinstance(page, int) else 0,
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betstat_sort_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "betstat_sort":
        indicator_id = callback_payload.get("indicator_id")
        if not isinstance(indicator_id, int):
            return PlainTextResponse("ok")
        page = callback_payload.get("page", 0)
        user_ctx = vk_user_contexts.get(user_id, {})
        current_sort_id_raw = user_ctx.get("betstat_sort_id")
        current_sort_id = (
            int(current_sort_id_raw)
            if isinstance(current_sort_id_raw, str) and current_sort_id_raw.isdigit()
            else None
        )
        new_sort_id = None if current_sort_id == indicator_id else indicator_id
        vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = (
            str(new_sort_id) if new_sort_id is not None else ""
        )
        mode = user_ctx.get("betstat_mode", "all")
        selected_ids = {int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x}
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
            indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
            selected = [item for item in indicators if int(item.row_id) in selected_ids]
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=f"{Text.user.BET_STAT_CHOOSE_SORT.value}\n{Text.user.BET_STAT_CHOOSED_SORT_DEFAULT.value}",
            keyboard=stat_sort_keyboard(
                action="betstat_sort",
                indicators=selected,
                selected_ids=list(selected_ids),
                selected_sort_id=new_sort_id,
                page=int(page) if isinstance(page, int) else 0,
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betstat_sort_done_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "betstat_sort_done":
        user_ctx = vk_user_contexts.get(user_id, {})
        mode = user_ctx.get("betstat_mode", "all")
        selected_ids = {int(x) for x in user_ctx.get("betstat_selected_ids", "").split(",") if x}
        selected_periods = parse_betting_tournament_period_ids(
            [x for x in user_ctx.get("betstat_period_ids", "").split(",") if x]
        )
        sort_id_raw = user_ctx.get("betstat_sort_id")
        sort_id = (
            int(sort_id_raw) if isinstance(sort_id_raw, str) and sort_id_raw.isdigit() else None
        )
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
            indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
            selected = [item for item in indicators if int(item.row_id) in selected_ids]
            sort_indicator = next(
                (item for item in selected if sort_id is not None and int(item.row_id) == sort_id),
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
                tournament_periods=selected_periods if mode == "all" else None,
                sort_pic=sort_pic,
            )
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=InlineText.EVENT_0_40_TEXT_01
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        image_bytes = render_stat_table_png(title="", report=report)
        await send_vk_photo(
            user_id=user_id,
            image_bytes=image_bytes,
            filename="betting_stat.png",
            message=_format_stat_caption(
                report_type=(
                    InlineText.EVENT_0_40_TEXT_02
                    if mode == "regular"
                    else InlineText.EVENT_0_40_TEXT_03
                    if mode == "year"
                    else InlineText.EVENT_0_40_TEXT_04
                ),
                indicators=selected,
                period_labels=[item.label for item in selected_periods],
                include_period=(mode == "all"),
            ),
        )
        vk_user_contexts.setdefault(user_id, {})["betstat_period_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = "all"
        vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = ""
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betstat_sort_cancel_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "betstat_sort_cancel":
        vk_user_contexts.setdefault(user_id, {})["betstat_period_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = "all"
        vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = ""
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


async def handle_betstat_cancel_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "betstat_cancel":
        vk_user_contexts.setdefault(user_id, {})["betstat_period_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["betstat_selected_ids"] = ""
        vk_user_contexts.setdefault(user_id, {})["betstat_mode"] = "all"
        vk_user_contexts.setdefault(user_id, {})["betstat_sort_id"] = ""
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


async def handle_betting_current_tours_text(*, user_id, text, raw_message):
    if text == Buttons.betting.CURRENT_TOURS.value:
        await send_vk_message(
            user_id=user_id,
            message=Text.user.BETTING_CURRENT_MENU.value,
            keyboard=betting_current_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betting_betting_stat_text(*, user_id, text, raw_message):
    if text == Buttons.betting.BETTING_STAT.value:
        user_ctx = vk_user_contexts.setdefault(user_id, {})
        user_ctx["betstat_period_ids"] = ""
        user_ctx["betstat_selected_ids"] = ""
        user_ctx["betstat_mode"] = "all"
        user_ctx["betstat_sort_id"] = ""
        async with SessionFactory() as session:
            periods = list_betting_tournament_periods(
                await BetTournamentRepository(session).list_active()
            )
        if not periods:
            await send_vk_message(user_id=user_id, message=InlineText.TEXT_1_23_TEXT_01)
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.STAT_CHOOSE_BETTING_TOURNAMENT.value,
            keyboard=betting_tournament_periods_keyboard(
                periods=periods, selected_period_ids=set(), page=0
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_current_tournament_stat_text(*, user_id, text, raw_message):
    if text in {
        Buttons.betting_current.REG_TOURNAMENT.value,
        Buttons.betting_current.YEAR_TOURNAMENT.value,
    }:
        user_ctx = vk_user_contexts.setdefault(user_id, {})
        user_ctx["betstat_selected_ids"] = ""
        user_ctx["betstat_mode"] = (
            "regular" if text == Buttons.betting_current.REG_TOURNAMENT.value else "year"
        )
        user_ctx["betstat_sort_id"] = ""
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
        indicators = _filter_betting_indicators_by_mode(
            indicators=indicators, mode=user_ctx["betstat_mode"]
        )
        if not indicators:
            await send_vk_message(user_id=user_id, message=Text.user.BETTING_CURRENT_EMPTY.value)
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.STAT_CHOOSE_PARAMS.value,
            keyboard=betting_stat_indicators_keyboard(
                indicators=indicators, page=0, selected_ids=[]
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betstat_open_event(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action != "betstat_open":
        return HANDLER_UNMATCHED
    mode = callback_payload.get("mode")
    if mode not in {"regular", "year"}:
        return PlainTextResponse("ok")
    await send_vk_message_event_answer(
        event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
    )
    await _delete_event_message_if_possible(
        peer_id=peer_id, conversation_message_id=conversation_message_id
    )
    text = (
        Buttons.betting_current.REG_TOURNAMENT.value
        if mode == "regular"
        else Buttons.betting_current.YEAR_TOURNAMENT.value
    )
    return await handle_current_tournament_stat_text(
        user_id=user_id, text=text, raw_message={}
    )


async def handle_betting_current_to_main_text(*, user_id, text, raw_message):
    if text == Buttons.betting_current.TO_MAIN.value:
        await send_vk_message(
            user_id=user_id,
            message=Text.user.BETTING_MENU.value,
            keyboard=await _betting_vk_keyboard(),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
