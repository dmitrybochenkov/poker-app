from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.shared.texts.texts import Text
from app.services import start_betting_flow as flow_module
from app.services import start_betting_notifications as notification_module


class _TrackedSession:
    def __init__(self, events):
        self.events = events

    async def __aenter__(self):
        self.events.append("session_enter")
        return self

    async def __aexit__(self, *args):
        self.events.append("session_exit")
        return False


@pytest.mark.asyncio
async def test_start_betting_flow_notifies_only_after_use_case_session_closes(monkeypatch):
    events = []
    result = SimpleNamespace(poker_id=7, recipient_user_ids=(1, 2))

    class UseCase:
        def __init__(self, session):
            assert isinstance(session, _TrackedSession)

        async def execute(self, *, actor_user_id):
            assert actor_user_id == 9
            events.append("use_case")
            return result

    class Notifier:
        async def notify(self, *, user_ids):
            assert user_ids == (1, 2)
            events.append("notify")

    monkeypatch.setattr(flow_module, "StartBettingUseCase", UseCase)
    flow = flow_module.StartBettingFlow(
        session_factory=lambda: _TrackedSession(events),
        notifier=Notifier(),
    )

    assert await flow.execute(actor_user_id=9) is result
    assert events == ["session_enter", "use_case", "session_exit", "notify"]


@pytest.mark.asyncio
async def test_start_betting_flow_keeps_committed_result_when_notifier_fails(monkeypatch):
    result = SimpleNamespace(poker_id=7, recipient_user_ids=(1,))

    class UseCase:
        def __init__(self, session):
            pass

        async def execute(self, *, actor_user_id):
            return result

    class Notifier:
        async def notify(self, *, user_ids):
            raise RuntimeError("network unavailable")

    monkeypatch.setattr(flow_module, "StartBettingUseCase", UseCase)
    flow = flow_module.StartBettingFlow(
        session_factory=lambda: _TrackedSession([]),
        notifier=Notifier(),
    )

    assert await flow.execute(actor_user_id=9) is result


@pytest.mark.asyncio
async def test_betting_started_adapter_preserves_platform_delivery_and_cleanup(monkeypatch):
    sent_tg = AsyncMock(side_effect=[RuntimeError("blocked"), None])
    sent_vk = AsyncMock()
    telegram_bot = SimpleNamespace(
        send_message=sent_tg,
        unpin_chat_message=AsyncMock(),
        delete_message=AsyncMock(),
    )
    monkeypatch.setattr(notification_module.telegram_runtime, "telegram_bot", telegram_bot)
    monkeypatch.setattr(notification_module, "send_vk_message", sent_vk)
    monkeypatch.setattr(notification_module, "unpin_vk_message", AsyncMock())
    monkeypatch.setattr(notification_module, "delete_vk_message_by_id", AsyncMock())
    tg_status = {31: 301}
    vk_status = {41: 401}
    monkeypatch.setattr(notification_module, "TG_ADMIN_ROOM_STATUS_MSG_IDS", tg_status)
    monkeypatch.setattr(notification_module, "VK_ADMIN_ROOM_STATUS_MSG_IDS", vk_status)

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class Repository:
        def __init__(self, session):
            pass

        async def list_by_row_ids(self, row_ids):
            assert row_ids == (1, 2, 3)
            return [
                SimpleNamespace(notification_platform="tg", telegram_id=11, vk_id=None),
                SimpleNamespace(notification_platform="tg", telegram_id=12, vk_id=None),
                SimpleNamespace(notification_platform="vk", telegram_id=None, vk_id=21),
            ]

    monkeypatch.setattr(notification_module, "SessionFactory", Session)
    monkeypatch.setattr(notification_module, "UserRepository", Repository)

    await notification_module.BettingStartedNotificationAdapter().notify(
        user_ids=(1, 2, 3)
    )

    assert [call.kwargs["chat_id"] for call in sent_tg.await_args_list] == [11, 12]
    assert [call.kwargs["user_id"] for call in sent_vk.await_args_list] == [21]
    assert all(
        call.kwargs["text"] == Text.user.START_BETTING.value for call in sent_tg.await_args_list
    )
    assert all(
        call.kwargs["message"] == Text.user.START_BETTING.value for call in sent_vk.await_args_list
    )
    assert all(
        call.kwargs["reply_markup"] is notification_module.tg_betting_keyboard
        for call in sent_tg.await_args_list
    )
    assert all(
        call.kwargs["keyboard"] is notification_module.vk_betting_keyboard
        for call in sent_vk.await_args_list
    )
    assert tg_status == {}
    assert vk_status == {}
