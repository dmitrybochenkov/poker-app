from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.http.vk_webhook import vk_webhook
from app.application.use_cases.poker.start_betting import (
    ActivePokerNotFoundError,
    BettingAlreadyOpenError,
    PokerAwaitingChipsError,
)
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.telegram.handlers.admin import start_betting as tg_start_betting
from app.bot.telegram.handlers.admin import start_poker as tg_start_poker
from app.bot.vk.handlers.admin import polls as vk_admin_polls
from app.bot.vk.handlers.admin import start_betting as vk_start_betting
from app.bot.vk.handlers.admin import start_poker as vk_start_poker


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_telegram_start_betting_calls_shared_application_flow(monkeypatch):
    execute = AsyncMock()
    monkeypatch.setattr(tg_start_betting, "SessionFactory", _Session)
    monkeypatch.setattr(tg_start_betting, "execute_start_betting", execute)
    monkeypatch.setattr(
        tg_start_betting,
        "resolve_telegram_user_id",
        AsyncMock(return_value=9),
    )
    message = SimpleNamespace(from_user=SimpleNamespace(id=77), answer=AsyncMock())

    await tg_start_betting.start_betting(message)

    execute.assert_awaited_once_with(actor_user_id=9)
    message.answer.assert_awaited_once_with(Text.admin.BETTING_START_SUCCESS.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ActivePokerNotFoundError(), Text.admin.POKER_ACTIVE_NOT_FOUND.value),
        (PokerAwaitingChipsError(), Text.user.FINISH_CHIPS_NOT_READY.value),
        (BettingAlreadyOpenError(), Text.admin.BETTING_ALREADY_OPEN.value),
    ],
)
async def test_telegram_start_betting_maps_application_errors(monkeypatch, error, expected):
    monkeypatch.setattr(tg_start_betting, "SessionFactory", _Session)
    monkeypatch.setattr(tg_start_betting, "execute_start_betting", AsyncMock(side_effect=error))

    monkeypatch.setattr(
        tg_start_betting,
        "resolve_telegram_user_id",
        AsyncMock(return_value=9),
    )
    assert await tg_start_betting._execute_for_telegram_id(77) == expected


@pytest.mark.asyncio
async def test_telegram_start_poker_resolves_canonical_actor_and_calls_shared_flow(monkeypatch):
    execute = AsyncMock()
    monkeypatch.setattr(tg_start_poker, "SessionFactory", _Session)
    monkeypatch.setattr(tg_start_poker, "execute_start_poker", execute)
    monkeypatch.setattr(tg_start_poker, "_clear_inline_keyboard", AsyncMock())
    monkeypatch.setattr(
        tg_start_poker,
        "resolve_telegram_user_id",
        AsyncMock(return_value=9),
    )
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        data="pokerstart:7",
        message=None,
        answer=AsyncMock(),
    )

    await tg_start_poker.start_poker_with_param(callback)

    execute.assert_awaited_once_with(actor_user_id=9, params_id=7)
    callback.answer.assert_awaited_once_with(Text.admin.POKER_START_SUCCESS.value)


@pytest.mark.asyncio
async def test_vk_start_poker_post_save_path_returns_success_without_approved_users_scope_bug(
    monkeypatch,
):
    execute = AsyncMock()
    send_vk = AsyncMock()
    event_answer = AsyncMock()
    cleanup = AsyncMock()
    monkeypatch.setattr(vk_start_poker, "SessionFactory", _Session)
    monkeypatch.setattr(vk_start_poker, "execute_start_poker", execute)
    monkeypatch.setattr(vk_start_poker, "send_vk_message", send_vk)
    monkeypatch.setattr(vk_start_poker, "send_vk_message_event_answer", event_answer)
    monkeypatch.setattr(vk_start_poker, "_clear_event_inline_keyboard_if_possible", cleanup)
    monkeypatch.setattr(
        vk_start_poker,
        "resolve_vk_user_id",
        AsyncMock(return_value=9),
    )

    result = await vk_start_poker.handle_poker_start_param_event(
        admin_user_id=99,
        peer_id=100,
        event_id="event",
        conversation_message_id=5,
        callback_payload={"params_id": 7},
        action="poker_start_param",
        handle_admin_text_commands=AsyncMock(),
    )

    assert result is None
    execute.assert_awaited_once_with(actor_user_id=9, params_id=7)
    event_answer.assert_awaited_once_with(
        event_id="event",
        user_id=99,
        peer_id=100,
        text=Text.admin.POKER_START_SUCCESS.value,
    )
    cleanup.assert_awaited_once_with(peer_id=100, conversation_message_id=5)
    send_vk.assert_awaited_once_with(
        user_id=99,
        message=Text.admin.POKER_START_SUCCESS.value,
    )


@pytest.mark.asyncio
async def test_vk_admin_poll_cancel_uses_existing_keyboard_cleanup(monkeypatch):
    cleanup = AsyncMock()
    monkeypatch.setattr(vk_admin_polls, "_clear_event_inline_keyboard_if_possible", cleanup)
    monkeypatch.setattr(vk_admin_polls, "send_vk_message_event_answer", AsyncMock())
    monkeypatch.setattr(vk_admin_polls, "send_vk_message", AsyncMock())

    result = await vk_admin_polls.handle_polladmin_cancel_event(
        admin_user_id=1,
        peer_id=1,
        event_id="event",
        conversation_message_id=9,
        callback_payload={},
        action="polladmin_cancel",
        handle_admin_text_commands=None,
    )

    assert result.body == b"ok"
    cleanup.assert_awaited_once_with(peer_id=1, conversation_message_id=9)


@pytest.mark.asyncio
async def test_vk_start_betting_calls_shared_application_flow(monkeypatch):
    execute = AsyncMock()
    send_vk = AsyncMock()
    monkeypatch.setattr(vk_start_betting, "SessionFactory", _Session)
    monkeypatch.setattr(vk_start_betting, "execute_start_betting", execute)
    monkeypatch.setattr(vk_start_betting, "send_vk_message", send_vk)
    monkeypatch.setattr(
        vk_start_betting,
        "resolve_vk_user_id",
        AsyncMock(return_value=9),
    )

    result = await vk_start_betting.handle_admin_room_start_betting_text(
        user_id=99, text=Buttons.admin_room.START_BETTING.value
    )

    assert result.body == b"ok"
    execute.assert_awaited_once_with(actor_user_id=9)
    send_vk.assert_awaited_once_with(
        user_id=99,
        message=Text.admin.BETTING_START_SUCCESS.value,
    )


@pytest.mark.asyncio
async def test_vk_webhook_rejects_missing_secret(monkeypatch):
    from app.api.http import vk_webhook as webhook_module

    monkeypatch.setattr(webhook_module.settings, "vk_secret_key", "expected")
    with pytest.raises(HTTPException) as error:
        await vk_webhook({"type": "confirmation"})
    assert error.value.status_code == 403

    accepted = await vk_webhook({"type": "confirmation", "secret": "expected"})
    assert accepted.body == webhook_module.settings.vk_confirmation_token.encode()
