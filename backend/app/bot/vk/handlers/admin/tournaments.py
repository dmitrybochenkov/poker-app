from fastapi.responses import PlainTextResponse

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.identity import resolve_vk_user_id
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import send_vk_message, send_vk_message_event_answer
from app.bot.vk.keyboards import (
    admin_betting_keyboard,
    admin_main_keyboard,
    tournament_close_keyboard,
    tournament_confirm_keyboard,
)
from app.db.session import SessionFactory
from app.services.close_betting_tournament_flow import (
    TODAY,
    build_close_tournament_use_case,
    format_preview,
)

from .common import HANDLER_UNMATCHED


async def handle_text(*, user_id, text):
    if text not in {
        item.value
        for item in (
            Buttons.admin_main.BETTING,
            Buttons.admin_betting.OPEN,
            Buttons.admin_betting.CLOSE,
            Buttons.admin_betting.BACK,
        )
    }:
        return HANDLER_UNMATCHED
    async with SessionFactory() as session:
        if not await is_vk_admin(session=session, vk_id=user_id):
            await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
            return PlainTextResponse("ok")
    if text == Buttons.admin_main.BETTING.value:
        await send_vk_message(
            user_id=user_id,
            message=Text.admin.TOURNAMENT_MENU.value,
            keyboard=admin_betting_keyboard,
        )
    elif text == Buttons.admin_betting.OPEN.value:
        await send_vk_message(
            user_id=user_id,
            message=Text.admin.TOURNAMENT_OPEN_PLACEHOLDER.value,
            keyboard=admin_betting_keyboard,
        )
    elif text == Buttons.admin_betting.BACK.value:
        await send_vk_message(
            user_id=user_id, message=Text.admin.ADMIN_PANEL.value, keyboard=admin_main_keyboard
        )
    elif text == Buttons.admin_betting.CLOSE.value:
        async with SessionFactory() as session:
            actor = await resolve_vk_user_id(session=session, vk_id=user_id)
            try:
                items = await build_close_tournament_use_case(session).list_eligible(
                    actor_user_id=actor or 0, today=TODAY()
                )
            except PermissionError:
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.admin.TOURNAMENT_CLOSE_CHOOSE.value
            if items
            else Text.admin.TOURNAMENT_CLOSE_EMPTY.value,
            keyboard=tournament_close_keyboard(tournaments=items)
            if items
            else admin_betting_keyboard,
        )
    else:
        return HANDLER_UNMATCHED
    return PlainTextResponse("ok")


async def handle_event(*, admin_user_id, peer_id, event_id, callback_payload, action, **kwargs):
    if action == "tour_close_cancel":
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=Text.admin.TOURNAMENT_CANCELED.value,
        )
        return PlainTextResponse("ok")
    if action not in {"tour_close_preview", "tour_close_confirm"}:
        return HANDLER_UNMATCHED
    tournament_id = callback_payload.get("tournament_id")
    async with SessionFactory() as session:
        actor = await resolve_vk_user_id(session=session, vk_id=admin_user_id)
        use_case = build_close_tournament_use_case(session)
        try:
            if action == "tour_close_preview":
                tournament, result = await use_case.preview(
                    actor_user_id=actor or 0, tournament_id=tournament_id, today=TODAY()
                )
            else:
                tournament, result = await use_case.confirm(
                    actor_user_id=actor or 0, tournament_id=tournament_id, today=TODAY()
                )
        except (PermissionError, ValueError):
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=admin_user_id,
                peer_id=peer_id,
                text=Text.admin.TOURNAMENT_ALREADY_FINALIZED.value,
            )
            return PlainTextResponse("ok")
    await send_vk_message(
        user_id=admin_user_id,
        message=format_preview(tournament, result),
        keyboard=tournament_confirm_keyboard(tournament_id=tournament_id)
        if action == "tour_close_preview"
        else None,
    )
    return PlainTextResponse("ok")
