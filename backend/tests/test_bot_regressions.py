from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.http.vk_webhook import vk_webhook
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.telegram import runtime as tg_runtime
from app.bot.telegram.handlers.admin import common as tg_admin_common
from app.bot.telegram.handlers.admin import poker as tg_admin_poker
from app.bot.vk.handlers.admin import bets as vk_admin_bets
from app.bot.vk.handlers.admin import polls as vk_admin_polls


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_telegram_start_betting_sends_both_platform_notifications(monkeypatch):
    sent_tg = AsyncMock(side_effect=[RuntimeError("blocked user"), None])
    sent_vk = AsyncMock()
    started = AsyncMock()
    monkeypatch.setattr(tg_runtime, "telegram_bot", SimpleNamespace(send_message=sent_tg))
    monkeypatch.setattr(tg_admin_common, "SessionFactory", _Session)
    monkeypatch.setattr(tg_admin_common, "TG_ADMIN_ROOM_STATUS_MSG_IDS", {})
    monkeypatch.setattr(tg_admin_common, "VK_ADMIN_ROOM_STATUS_MSG_IDS", {})
    monkeypatch.setattr(tg_admin_common, "send_vk_message", sent_vk)

    class UserRepo:
        def __init__(self, session):
            pass

        async def list_approved_tg_ids(self):
            return [11, 12]

        async def list_approved_vk_ids(self):
            return [21]

    class PokerRepo:
        def __init__(self, session):
            pass

        async def get_started(self):
            return SimpleNamespace(is_ready_for_chips_entering=False, is_bettable=False), None

        async def start_betting(self, poker):
            await started(poker)

    monkeypatch.setattr(tg_admin_common, "UserRepository", UserRepo)
    monkeypatch.setattr(tg_admin_common, "PokerRepository", PokerRepo)

    result = await tg_admin_common._start_betting_flow(admin_tg_id=1)

    assert result == Text.admin.BETTING_START_SUCCESS.value
    started.assert_awaited_once()
    assert [call.kwargs["chat_id"] for call in sent_tg.await_args_list] == [11, 12]
    assert [call.kwargs["user_id"] for call in sent_vk.await_args_list] == [21]


@pytest.mark.asyncio
async def test_telegram_start_poker_notifies_approved_users(monkeypatch):
    sent_tg = AsyncMock()
    sent_vk = AsyncMock()
    monkeypatch.setattr(tg_runtime, "telegram_bot", SimpleNamespace(send_message=sent_tg))
    monkeypatch.setattr(tg_admin_poker, "SessionFactory", _Session)
    monkeypatch.setattr(tg_admin_poker, "send_vk_message", sent_vk)
    monkeypatch.setattr(tg_admin_poker, "_clear_inline_keyboard", AsyncMock())
    monkeypatch.setattr(tg_admin_poker, "_ensure_tg_admin_callback", AsyncMock(return_value=True))

    class UserRepo:
        def __init__(self, session):
            pass

        async def get_by_telegram_id(self, user_id):
            return None

        async def list_approved(self):
            return [
                SimpleNamespace(telegram_id=11, vk_id=None, is_admin=False),
                SimpleNamespace(telegram_id=None, vk_id=21, is_admin=True),
            ]

    class UseCase:
        def __init__(self, **kwargs):
            pass

        async def execute(self, *, params_id):
            assert params_id == 7
            return object()

    monkeypatch.setattr(tg_admin_poker, "UserRepository", UserRepo)
    monkeypatch.setattr(tg_admin_poker, "StartPokerUseCase", UseCase)
    monkeypatch.setattr(tg_admin_poker, "PokerRepository", lambda session: None)
    monkeypatch.setattr(tg_admin_poker, "PokerParamRepository", lambda session: None)
    monkeypatch.setattr(tg_admin_poker, "PokerRoomDeniedRepository", lambda session: None)
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        data="pokerstart:7",
        message=None,
        answer=AsyncMock(),
    )

    await tg_admin_poker.start_poker_with_param(callback)

    assert [call.kwargs["chat_id"] for call in sent_tg.await_args_list] == [11]
    assert [call.kwargs["user_id"] for call in sent_vk.await_args_list] == [21]


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
async def test_vk_start_betting_continues_after_one_failed_delivery(monkeypatch):
    sent_vk = []

    async def send_vk(*, user_id, message, keyboard=None):
        sent_vk.append(user_id)
        if user_id == 21:
            raise RuntimeError("blocked user")

    monkeypatch.setattr(tg_runtime, "telegram_bot", SimpleNamespace(send_message=AsyncMock()))
    monkeypatch.setattr(vk_admin_bets, "SessionFactory", _Session)
    monkeypatch.setattr(vk_admin_bets, "is_vk_admin", AsyncMock(return_value=True))
    monkeypatch.setattr(vk_admin_bets, "send_vk_message", send_vk)
    monkeypatch.setattr(vk_admin_bets, "TG_ADMIN_ROOM_STATUS_MSG_IDS", {})
    monkeypatch.setattr(vk_admin_bets, "VK_ADMIN_ROOM_STATUS_MSG_IDS", {})

    class UserRepo:
        def __init__(self, session):
            pass

        async def list_approved_tg_ids(self):
            return [11]

        async def list_approved_vk_ids(self):
            return [21, 22]

    class PokerRepo:
        def __init__(self, session):
            pass

        async def get_started(self):
            return SimpleNamespace(is_ready_for_chips_entering=False, is_bettable=False), None

        async def start_betting(self, poker):
            return poker

    monkeypatch.setattr(vk_admin_bets, "UserRepository", UserRepo)
    monkeypatch.setattr(vk_admin_bets, "PokerRepository", PokerRepo)

    result = await vk_admin_bets.handle_admin_room_start_betting_text(
        user_id=99, text=Buttons.admin_room.START_BETTING.value
    )

    assert result.body == b"ok"
    assert sent_vk == [21, 22, 99]


@pytest.mark.asyncio
async def test_vk_webhook_rejects_missing_secret(monkeypatch):
    from app.api.http import vk_webhook as webhook_module

    monkeypatch.setattr(webhook_module.settings, "vk_secret_key", "expected")
    with pytest.raises(HTTPException) as error:
        await vk_webhook({"type": "confirmation"})
    assert error.value.status_code == 403

    accepted = await vk_webhook({"type": "confirmation", "secret": "expected"})
    assert accepted.body == webhook_module.settings.vk_confirmation_token.encode()
