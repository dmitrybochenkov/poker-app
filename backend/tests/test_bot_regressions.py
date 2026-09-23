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
from app.bot.telegram import runtime as tg_runtime
from app.bot.telegram.handlers.admin import poker as tg_admin_poker
from app.bot.telegram.handlers.admin import start_betting as tg_start_betting
from app.bot.vk.handlers.admin import polls as vk_admin_polls
from app.bot.vk.handlers.admin import poker as vk_admin_poker
from app.bot.vk.handlers.admin import start_betting as vk_start_betting


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

    class UserRepo:
        def __init__(self, session):
            pass

        async def get_by_telegram_id(self, telegram_id):
            assert telegram_id == 77
            return SimpleNamespace(row_id=9)

    monkeypatch.setattr(tg_start_betting, "UserRepository", UserRepo)
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

    class UserRepo:
        def __init__(self, session):
            pass

        async def get_by_telegram_id(self, telegram_id):
            return SimpleNamespace(row_id=9)

    monkeypatch.setattr(tg_start_betting, "UserRepository", UserRepo)
    assert await tg_start_betting._execute_for_telegram_id(77) == expected


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
async def test_telegram_start_poker_adds_starter_and_notifies_every_bound_platform(monkeypatch):
    sent_tg = AsyncMock()
    sent_vk = AsyncMock()
    add_starter = AsyncMock()
    monkeypatch.setattr(tg_runtime, "telegram_bot", SimpleNamespace(send_message=sent_tg))
    monkeypatch.setattr(tg_admin_poker, "SessionFactory", _Session)
    monkeypatch.setattr(tg_admin_poker, "send_vk_message", sent_vk)
    monkeypatch.setattr(tg_admin_poker, "_clear_inline_keyboard", AsyncMock())
    monkeypatch.setattr(tg_admin_poker, "_ensure_tg_admin_callback", AsyncMock(return_value=True))

    starter = SimpleNamespace(row_id=9, name="Admin")
    dual_platform_user = SimpleNamespace(
        row_id=10,
        telegram_id=11,
        vk_id=21,
        notification_platform="tg",
        is_admin=False,
    )

    class UserRepo:
        def __init__(self, session):
            pass

        async def get_by_telegram_id(self, user_id):
            assert user_id == 1
            return starter

        async def list_approved(self):
            return [dual_platform_user]

    class UseCase:
        def __init__(self, **kwargs):
            pass

        async def execute(self, *, params_id):
            assert params_id == 7
            return object()

    class ManagePlayers:
        def __init__(self, **kwargs):
            pass

        add_player_to_active_poker = add_starter

    monkeypatch.setattr(tg_admin_poker, "UserRepository", UserRepo)
    monkeypatch.setattr(tg_admin_poker, "StartPokerUseCase", UseCase)
    monkeypatch.setattr(tg_admin_poker, "ManagePokerPlayersUseCase", ManagePlayers)
    monkeypatch.setattr(tg_admin_poker, "PokerRepository", lambda session: None)
    monkeypatch.setattr(tg_admin_poker, "PokerDataRepository", lambda session: None)
    monkeypatch.setattr(tg_admin_poker, "PokerParamRepository", lambda session: None)
    monkeypatch.setattr(tg_admin_poker, "PokerRoomDeniedRepository", lambda session: None)
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        data="pokerstart:7",
        message=None,
        answer=AsyncMock(),
    )

    await tg_admin_poker.start_poker_with_param(callback)

    add_starter.assert_awaited_once_with(player_id=9, player_name="Admin")
    assert [call.kwargs["chat_id"] for call in sent_tg.await_args_list] == [11]
    assert [call.kwargs["user_id"] for call in sent_vk.await_args_list] == [21]
    callback.answer.assert_awaited_once_with(Text.admin.POKER_START_SUCCESS.value)


@pytest.mark.asyncio
async def test_vk_start_poker_post_save_path_keeps_approved_users_for_broadcast(monkeypatch):
    sent_tg = AsyncMock()
    sent_vk = AsyncMock()
    add_starter = AsyncMock()
    monkeypatch.setattr(tg_runtime, "telegram_bot", SimpleNamespace(send_message=sent_tg))
    monkeypatch.setattr(vk_admin_poker, "SessionFactory", _Session)
    monkeypatch.setattr(vk_admin_poker, "is_vk_admin", AsyncMock(return_value=True))
    monkeypatch.setattr(vk_admin_poker, "send_vk_message", sent_vk)
    monkeypatch.setattr(vk_admin_poker, "send_vk_message_event_answer", AsyncMock())
    monkeypatch.setattr(
        vk_admin_poker,
        "_clear_event_inline_keyboard_if_possible",
        AsyncMock(),
    )

    starter = SimpleNamespace(row_id=9, name="Admin")
    dual_platform_user = SimpleNamespace(
        row_id=10,
        telegram_id=11,
        vk_id=21,
        notification_platform="vk",
        is_admin=True,
    )

    class UserRepo:
        def __init__(self, session):
            pass

        async def get_by_vk_id(self, user_id):
            assert user_id == 99
            return starter

        async def list_approved(self):
            return [dual_platform_user]

    class UseCase:
        def __init__(self, **kwargs):
            pass

        async def execute(self, *, params_id):
            assert params_id == 7
            return object()

    class ManagePlayers:
        def __init__(self, **kwargs):
            pass

        add_player_to_active_poker = add_starter

    monkeypatch.setattr(vk_admin_poker, "UserRepository", UserRepo)
    monkeypatch.setattr(vk_admin_poker, "StartPokerUseCase", UseCase)
    monkeypatch.setattr(vk_admin_poker, "ManagePokerPlayersUseCase", ManagePlayers)
    monkeypatch.setattr(vk_admin_poker, "PokerRepository", lambda session: None)
    monkeypatch.setattr(vk_admin_poker, "PokerDataRepository", lambda session: None)
    monkeypatch.setattr(vk_admin_poker, "PokerParamRepository", lambda session: None)
    monkeypatch.setattr(vk_admin_poker, "PokerRoomDeniedRepository", lambda session: None)

    result = await vk_admin_poker.handle_poker_start_param_event(
        admin_user_id=99,
        peer_id=100,
        event_id="event",
        conversation_message_id=5,
        callback_payload={"params_id": 7},
        action="poker_start_param",
        handle_admin_text_commands=AsyncMock(),
    )

    assert result is None
    add_starter.assert_awaited_once_with(player_id=9, player_name="Admin")
    assert [call.kwargs["chat_id"] for call in sent_tg.await_args_list] == [11]
    assert [call.kwargs["user_id"] for call in sent_vk.await_args_list] == [99, 21]


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

    class UserRepo:
        def __init__(self, session):
            pass

        async def get_by_vk_id(self, vk_id):
            assert vk_id == 99
            return SimpleNamespace(row_id=9)

    monkeypatch.setattr(vk_start_betting, "UserRepository", UserRepo)

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
