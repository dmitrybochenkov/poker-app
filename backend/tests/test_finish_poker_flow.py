from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.shared.texts.texts import Text
from app.services import finish_poker_flow as flow_module
from app.services import finish_poker_notifications as notification_module


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
async def test_finish_poker_flow_notifies_after_use_case_session_closes(monkeypatch):
    events = []
    result = SimpleNamespace(poker_id=7, participant_user_ids=(1, 2))

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

    monkeypatch.setattr(flow_module, "FinishPokerUseCase", UseCase)
    flow = flow_module.FinishPokerFlow(
        session_factory=lambda: _TrackedSession(events),
        notifier=Notifier(),
    )

    assert await flow.execute(actor_user_id=9) is result
    assert events == ["session_enter", "use_case", "session_exit", "notify"]


@pytest.mark.asyncio
async def test_finished_adapter_preserves_player_recipient_semantics(monkeypatch):
    sent_tg = AsyncMock(side_effect=[RuntimeError("blocked"), None])
    sent_vk = AsyncMock()
    monkeypatch.setattr(
        notification_module.telegram_runtime,
        "telegram_bot",
        SimpleNamespace(send_message=sent_tg),
    )
    monkeypatch.setattr(notification_module, "send_vk_message", sent_vk)

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class Repository:
        def __init__(self, session):
            pass

        async def list_by_row_ids(self, row_ids):
            assert row_ids == (1, 2, 3, 4, 5)
            return [
                SimpleNamespace(
                    is_admin=False,
                    notification_platform="tg",
                    telegram_id=11,
                    vk_id=21,
                ),
                SimpleNamespace(
                    is_admin=False,
                    notification_platform="tg",
                    telegram_id=12,
                    vk_id=None,
                ),
                SimpleNamespace(
                    is_admin=False,
                    notification_platform="vk",
                    telegram_id=None,
                    vk_id=22,
                ),
                SimpleNamespace(
                    is_admin=True,
                    notification_platform="vk",
                    telegram_id=None,
                    vk_id=23,
                ),
                SimpleNamespace(
                    is_admin=False,
                    notification_platform=None,
                    telegram_id=13,
                    vk_id=None,
                ),
            ]

    monkeypatch.setattr(notification_module, "SessionFactory", Session)
    monkeypatch.setattr(notification_module, "UserRepository", Repository)

    await notification_module.PokerFinishedNotificationAdapter().notify(
        user_ids=(1, 2, 3, 4, 5)
    )

    assert [call.kwargs["chat_id"] for call in sent_tg.await_args_list] == [11, 12]
    assert [call.kwargs["user_id"] for call in sent_vk.await_args_list] == [22]
    assert all(
        call.kwargs["text"] == Text.user.POKER_FINISHED_ENTER_CHIPS.value
        for call in sent_tg.await_args_list
    )
    assert all(
        call.kwargs["message"] == Text.user.POKER_FINISHED_ENTER_CHIPS.value
        for call in sent_vk.await_args_list
    )
