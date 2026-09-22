from datetime import date

from fastapi.responses import PlainTextResponse

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.inline.vk.user import polls as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
    send_vk_photo,
)
from app.bot.vk.keyboards import (
    new_user_keyboard,
    poll_menu_keyboard,
    poll_month_keyboard,
)
from app.bot.vk.state import (
    WAITING_FOR_POLL_CUSTOM_DAY,
    vk_user_contexts,
    vk_user_states,
)
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.poll_vote_repository import PollVoteRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    HANDLER_UNMATCHED,
    STAT_SNACKBAR,
    _approved_vk_keyboard,
    _delete_event_message_if_possible,
    _format_poll_summary,
    _get_vk_user,
    _month_bounds,
    _month_name_ru_upper,
    _parse_custom_day_input,
    _parse_iso_dates,
    _parse_month_key,
    _poll_all_days_for_month,
    _poll_choose_text,
    _render_poll_results_chart,
)


async def _event_0_00(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "poll_noop":
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_01(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "poll_month":
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_02(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "poll_page":
        month_key = callback_payload.get("month")
        page = callback_payload.get("page")
        if not isinstance(month_key, str) or not isinstance(page, int):
            return PlainTextResponse("ok")
        month = _parse_month_key(month_key)
        async with SessionFactory() as session:
            allowed_days = await _poll_all_days_for_month(session=session, month=month)
        max_page = max(0, (len(allowed_days) - 1) // 4)
        page = max(0, min(int(page), max_page))
        ctx = vk_user_contexts.setdefault(user_id, {})
        selected = _parse_iso_dates(ctx.get("poll_selected"))
        ctx["poll_month"] = month_key
        ctx["poll_page"] = str(page)
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=_poll_choose_text(month),
            keyboard=poll_month_keyboard(
                month=month, page=page, selected_dates=selected, extra_dates=allowed_days
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_03(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "poll_day":
        day_iso = callback_payload.get("date")
        page = callback_payload.get("page")
        if not isinstance(day_iso, str) or not isinstance(page, int):
            return PlainTextResponse("ok")
        try:
            day = date.fromisoformat(day_iso)
        except Exception:
            return PlainTextResponse("ok")
        ctx = vk_user_contexts.setdefault(user_id, {})
        selected = set(item.isoformat() for item in _parse_iso_dates(ctx.get("poll_selected")))
        if day_iso in selected:
            selected.remove(day_iso)
        else:
            selected.add(day_iso)
        selected_dates = _parse_iso_dates("|".join(sorted(selected)))
        month = date(day.year, day.month, 1)
        ctx["poll_month"] = f"{day.year}-{day.month:02d}"
        ctx["poll_page"] = str(page)
        ctx["poll_selected"] = "|".join(item.isoformat() for item in selected_dates)
        async with SessionFactory() as session:
            allowed_days = await _poll_all_days_for_month(session=session, month=month)
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=_poll_choose_text(month),
            keyboard=poll_month_keyboard(
                month=month, page=page, selected_dates=selected_dates, extra_dates=allowed_days
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_04(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "poll_suggest":
        month_key = callback_payload.get("month")
        if not isinstance(month_key, str):
            return PlainTextResponse("ok")
        month = _parse_month_key(month_key)
        vk_user_states[user_id] = WAITING_FOR_POLL_CUSTOM_DAY
        ctx = vk_user_contexts.setdefault(user_id, {})
        ctx["poll_suggest_month"] = month_key
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id, message=f'{InlineText.EVENT_0_04_TEXT_01_PART_1}{_month_name_ru_upper(month)}{InlineText.EVENT_0_04_TEXT_01_PART_2}'
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_05(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "poll_done":
        user = await _get_vk_user(user_id)
        if user is None or not user.is_approved:
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.STATUS_NEED_REGISTRATION.value,
            )
            return PlainTextResponse("ok")
        ctx = vk_user_contexts.setdefault(user_id, {})
        month = _parse_month_key(ctx.get("poll_month"))
        month_start, month_end = _month_bounds(month)
        async with SessionFactory() as session:
            allowed = set(await _poll_all_days_for_month(session=session, month=month))
        selected = [
            item
            for item in _parse_iso_dates(ctx.get("poll_selected"))
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
        ctx.pop("poll_month", None)
        ctx.pop("poll_page", None)
        ctx.pop("poll_selected", None)
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=_format_poll_summary(
                month=month, selected_dates=selected, month_counts=month_counts
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_06(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "poll_cancel":
        ctx = vk_user_contexts.setdefault(user_id, {})
        ctx.pop("poll_month", None)
        ctx.pop("poll_page", None)
        ctx.pop("poll_selected", None)
        await send_vk_message_event_answer(
            event_id=event_id, user_id=user_id, peer_id=peer_id, text=STAT_SNACKBAR
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=user_id, message=Text.user.POLL_CANCELED.value)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_32(*, user_id, text, raw_message):
    if text in {Buttons.poker.POLL.value, Buttons.poll_menu.VOTE.value}:
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        if not user.is_approved:
            await send_vk_message(
                user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard
            )
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            month = await PollConfigRepository(session).get_active_month()
        if month is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.POLL_NOT_ACTIVE.value,
                keyboard=await _approved_vk_keyboard(user),
            )
            return PlainTextResponse("ok")
        month_start, month_end = _month_bounds(month)
        async with SessionFactory() as session:
            selected = await PollVoteRepository(session).get_user_month_votes(
                player_row_id=int(user.row_id),
                month_start=month_start,
                month_end=month_end,
            )
            all_days = await _poll_all_days_for_month(session=session, month=month)
        ctx = vk_user_contexts.setdefault(user_id, {})
        ctx["poll_month"] = f"{month.year}-{month.month:02d}"
        ctx["poll_page"] = "0"
        ctx["poll_selected"] = "|".join(item.isoformat() for item in selected)
        await send_vk_message(
            user_id=user_id,
            message=_poll_choose_text(month),
            keyboard=poll_month_keyboard(
                month=month, page=0, selected_dates=selected, extra_dates=all_days
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_33(*, user_id, text, raw_message):
    if text == Buttons.poll_menu.RESULTS.value:
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        if not user.is_approved:
            await send_vk_message(
                user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard
            )
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            month = await PollConfigRepository(session).get_active_month()
            if month is None:
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.POLL_NOT_ACTIVE.value,
                    keyboard=await _approved_vk_keyboard(user),
                )
                return PlainTextResponse("ok")
            month_start, month_end = _month_bounds(month)
            poll_repo = PollVoteRepository(session)
            month_counts = await poll_repo.get_month_counts(
                month_start=month_start, month_end=month_end
            )
            month_votes = await poll_repo.get_month_votes(
                month_start=month_start, month_end=month_end
            )
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
            await send_vk_photo(
                user_id=user_id, image_bytes=image_bytes, filename="poll_results.png"
            )
        except Exception:
            await send_vk_message(
                user_id=user_id, message=InlineText.TEXT_1_33_TEXT_01
            )
        await send_vk_message(
            user_id=user_id,
            message=f'{InlineText.TEXT_1_33_TEXT_02_PART_1}{month.strftime('%m.%Y')}',
            keyboard=poll_menu_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_37(*, user_id, text, raw_message):
    if vk_user_states.get(user_id) == WAITING_FOR_POLL_CUSTOM_DAY:
        user = await _get_vk_user(user_id)
        if user is None or not user.is_approved:
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        ctx = vk_user_contexts.setdefault(user_id, {})
        month = _parse_month_key(ctx.get("poll_suggest_month"))
        chosen = _parse_custom_day_input(text, month=month)
        if chosen is None:
            await send_vk_message(
                user_id=user_id,
                message=f'{InlineText.TEXT_1_37_TEXT_01_PART_1}{_month_name_ru_upper(month)}{InlineText.TEXT_1_37_TEXT_01_PART_2}',
            )
            return PlainTextResponse("ok")
        month_start, month_end = _month_bounds(month)
        async with SessionFactory() as session:
            repo = PollVoteRepository(session)
            existing_days = await _poll_all_days_for_month(session=session, month=month)
            if chosen in existing_days:
                await send_vk_message(user_id=user_id, message=InlineText.TEXT_1_37_TEXT_02)
                return PlainTextResponse("ok")
            await repo.add_month_extra_date(poll_date=chosen)
            selected = await repo.get_user_month_votes(
                player_row_id=int(user.row_id),
                month_start=month_start,
                month_end=month_end,
            )
            all_days = await _poll_all_days_for_month(session=session, month=month)
            await session.commit()
        vk_user_states.pop(user_id, None)
        ctx["poll_month"] = f"{month.year}-{month.month:02d}"
        ctx["poll_page"] = "0"
        ctx["poll_selected"] = "|".join(item.isoformat() for item in selected)
        ctx.pop("poll_suggest_month", None)
        await send_vk_message(
            user_id=user_id,
            message=_poll_choose_text(month),
            keyboard=poll_month_keyboard(
                month=month, page=0, selected_dates=selected, extra_dates=all_days
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
