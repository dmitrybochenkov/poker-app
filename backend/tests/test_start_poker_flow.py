from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.shared.texts.texts import Text
from app.services import start_poker_flow as flow_module
from app.services import start_poker_notifications as notification_module


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
async def test_start_poker_flow_notifies_after_use_case_session_closes(monkeypatch):
  events = []
  result = SimpleNamespace(poker_id=7, recipient_user_ids=(1, 2))

  class UseCase:
    def __init__(self, session):
      assert isinstance(session, _TrackedSession)

    async def execute(self, *, actor_user_id, params_id):
      assert (actor_user_id, params_id) == (9, 4)
      events.append("use_case")
      return result

  class Notifier:
    async def notify(self, *, recipient_user_ids):
      assert recipient_user_ids == (1, 2)
      events.append("notify")

  monkeypatch.setattr(flow_module, "StartPokerUseCase", UseCase)
  flow = flow_module.StartPokerFlow(
    session_factory=lambda: _TrackedSession(events),
    notifier=Notifier(),
  )

  assert await flow.execute(actor_user_id=9, params_id=4) is result
  assert events == ["session_enter", "use_case", "session_exit", "notify"]


@pytest.mark.asyncio
async def test_poker_started_adapter_preserves_dual_platform_delivery(monkeypatch):
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
      assert row_ids == (1, 2)
      return [
        SimpleNamespace(telegram_id=11, vk_id=21, is_admin=True),
        SimpleNamespace(telegram_id=12, vk_id=None, is_admin=False),
      ]

  monkeypatch.setattr(notification_module, "SessionFactory", Session)
  monkeypatch.setattr(notification_module, "UserRepository", Repository)

  await notification_module.PokerStartedNotificationAdapter().notify(
    recipient_user_ids=(1, 2)
  )

  assert [call.kwargs["chat_id"] for call in sent_tg.await_args_list] == [11, 12]
  assert [call.kwargs["user_id"] for call in sent_vk.await_args_list] == [21]
  assert all(call.kwargs["text"] == Text.user.START_POKER.value for call in sent_tg.await_args_list)
  assert all(call.kwargs["message"] == Text.user.START_POKER.value for call in sent_vk.await_args_list)
