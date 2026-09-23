from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.telegram.handlers.admin import poker as tg_poker
from app.bot.vk.handlers.admin import poker as vk_poker


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_telegram_finish_poker_legacy_transition_and_side_effect_order(monkeypatch):
    events = []
    poker = SimpleNamespace(date="2026-09-23")
    players = [SimpleNamespace(player_id=10, date=poker.date)]

    class PokerRepo:
        def __init__(self, session):
            pass

        async def get_started(self):
            return poker, object()

        async def finish(self, item):
            assert item is poker
            events.append("finish_commit")

    class PokerDataRepo:
        def __init__(self, session):
            pass

        async def list_players(self, *, date):
            assert date == poker.date
            return players

    class DeniedRepo:
        def __init__(self, session):
            pass

        async def clear_all(self):
            events.append("deny_list_commit")

    async def notify(*, players):
        assert players == [players[0]]
        events.append("notify_players")

    async def upsert(*, session, poker_date):
        assert poker_date == poker.date
        events.append("chips_status")

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=77),
        answer=AsyncMock(side_effect=lambda text: events.append(f"answer:{text}")),
    )
    monkeypatch.setattr(tg_poker, "SessionFactory", _Session)
    monkeypatch.setattr(tg_poker, "_ensure_tg_admin_message", AsyncMock(return_value=True))
    monkeypatch.setattr(tg_poker, "PokerRepository", PokerRepo)
    monkeypatch.setattr(tg_poker, "PokerDataRepository", PokerDataRepo)
    monkeypatch.setattr(tg_poker, "PokerRoomDeniedRepository", DeniedRepo)
    monkeypatch.setattr(tg_poker, "_notify_players_about_finish", notify)
    monkeypatch.setattr(tg_poker, "_upsert_tg_admin_chips_status", upsert)

    await tg_poker.finish_poker(message)

    assert events == [
        "finish_commit",
        "deny_list_commit",
        "notify_players",
        f"answer:{Text.admin.POKER_FINISH_SUCCESS.value}",
        "chips_status",
    ]


@pytest.mark.asyncio
async def test_vk_finish_poker_legacy_transition_and_side_effect_order(monkeypatch):
    events = []
    poker = SimpleNamespace(date="2026-09-23")
    players = [SimpleNamespace(player_id=10, date=poker.date)]

    class PokerRepo:
        def __init__(self, session):
            pass

        async def get_started(self):
            return poker, object()

        async def finish(self, item):
            assert item is poker
            events.append("finish_commit")

    class PokerDataRepo:
        def __init__(self, session):
            pass

        async def list_players(self, *, date):
            assert date == poker.date
            return players

    class DeniedRepo:
        def __init__(self, session):
            pass

        async def clear_all(self):
            events.append("deny_list_commit")

    async def notify(*, players):
        assert players == [players[0]]
        events.append("notify_players")

    async def send(*, user_id, message):
        assert user_id == 88
        events.append(f"answer:{message}")

    async def upsert(*, session, poker_date):
        assert poker_date == poker.date
        events.append("chips_status")

    monkeypatch.setattr(vk_poker, "SessionFactory", _Session)
    monkeypatch.setattr(vk_poker, "is_vk_admin", AsyncMock(return_value=True))
    monkeypatch.setattr(vk_poker, "PokerRepository", PokerRepo)
    monkeypatch.setattr(vk_poker, "PokerDataRepository", PokerDataRepo)
    monkeypatch.setattr(vk_poker, "PokerRoomDeniedRepository", DeniedRepo)
    monkeypatch.setattr(vk_poker, "_notify_players_about_finish", notify)
    monkeypatch.setattr(vk_poker, "send_vk_message", send)
    monkeypatch.setattr(vk_poker, "_upsert_vk_admin_chips_status", upsert)

    result = await vk_poker.handle_admin_room_finish_poker_text(
        user_id=88,
        text=Buttons.admin_room.FINISH_POKER.value,
    )

    assert result.body == b"ok"
    assert events == [
        "finish_commit",
        "deny_list_commit",
        "notify_players",
        f"answer:{Text.admin.POKER_FINISH_SUCCESS.value}",
        "chips_status",
    ]
