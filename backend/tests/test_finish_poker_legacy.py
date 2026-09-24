from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.telegram import runtime as tg_runtime
from app.bot.telegram.handlers.admin import finish_poker as tg_finish_poker
from app.bot.telegram.handlers.admin import player_notification_helpers as tg_notifications
from app.bot.vk.handlers.admin import finish_poker as vk_finish_poker
from app.bot.vk.handlers.admin import player_notification_helpers as vk_notifications


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_telegram_finish_poker_preserves_post_commit_side_effect_order(monkeypatch):
    events = []
    result = SimpleNamespace(
        poker_id=7,
        poker_date="2026-09-23",
        participant_user_ids=(10,),
    )

    async def execute(*, actor_user_id):
        assert actor_user_id == 9
        events.append("commit_then_notify")
        return result

    async def upsert(*, session, poker_date):
        assert poker_date == result.poker_date
        events.append("chips_status")

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=77),
        answer=AsyncMock(side_effect=lambda text: events.append(f"answer:{text}")),
    )
    monkeypatch.setattr(tg_finish_poker, "SessionFactory", _Session)
    monkeypatch.setattr(
        tg_finish_poker,
        "resolve_telegram_user_id",
        AsyncMock(return_value=9),
    )
    monkeypatch.setattr(tg_finish_poker, "execute_finish_poker", execute)
    monkeypatch.setattr(tg_finish_poker, "_upsert_tg_admin_chips_status", upsert)

    await tg_finish_poker.finish_poker(message)

    assert events == [
        "commit_then_notify",
        f"answer:{Text.admin.POKER_FINISH_SUCCESS.value}",
        "chips_status",
    ]


@pytest.mark.asyncio
async def test_vk_finish_poker_preserves_post_commit_side_effect_order(monkeypatch):
    events = []
    result = SimpleNamespace(
        poker_id=7,
        poker_date="2026-09-23",
        participant_user_ids=(10,),
    )

    async def execute(*, actor_user_id):
        assert actor_user_id == 9
        events.append("commit_then_notify")
        return result

    async def send(*, user_id, message):
        assert user_id == 88
        events.append(f"answer:{message}")

    async def upsert(*, session, poker_date):
        assert poker_date == result.poker_date
        events.append("chips_status")

    monkeypatch.setattr(vk_finish_poker, "SessionFactory", _Session)
    monkeypatch.setattr(
        vk_finish_poker,
        "resolve_vk_user_id",
        AsyncMock(return_value=9),
    )
    monkeypatch.setattr(vk_finish_poker, "execute_finish_poker", execute)
    monkeypatch.setattr(vk_finish_poker, "send_vk_message", send)
    monkeypatch.setattr(vk_finish_poker, "_upsert_vk_admin_chips_status", upsert)

    response = await vk_finish_poker.handle_admin_room_finish_poker_text(
        user_id=88,
        text=Buttons.admin_room.FINISH_POKER.value,
    )

    assert response.body == b"ok"
    assert events == [
        "commit_then_notify",
        f"answer:{Text.admin.POKER_FINISH_SUCCESS.value}",
        "chips_status",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("notification_module", [tg_notifications, vk_notifications])
async def test_finish_poker_notification_builds_keyboard_without_runtime_error(
    monkeypatch,
    notification_module,
):
    sent = AsyncMock()
    monkeypatch.setattr(tg_runtime, "telegram_bot", SimpleNamespace(send_message=sent))
    monkeypatch.setattr(notification_module, "SessionFactory", _Session)

    class UserRepo:
        def __init__(self, session):
            pass

        async def get_by_row_id(self, row_id):
            assert row_id == 10
            return SimpleNamespace(
                row_id=10,
                is_admin=False,
                notification_platform="tg",
                telegram_id=100,
                vk_id=None,
            )

    monkeypatch.setattr(notification_module, "UserRepository", UserRepo)

    await notification_module._notify_players_about_finish(
        players=[SimpleNamespace(player_id=10)]
    )

    sent.assert_awaited_once()
