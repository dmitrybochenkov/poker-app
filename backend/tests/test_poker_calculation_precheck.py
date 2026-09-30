from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.shared.texts.texts import Text
from app.bot.telegram.handlers.admin import calculation as tg_poker
from app.bot.vk.handlers.admin import chips as vk_chips


class _Session:
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb): return None


class _PokerRepository:
    def __init__(self, session): pass
    async def get_latest_ready_for_chips_with_params(self):
        return SimpleNamespace(row_id=1, date="date"), SimpleNamespace(buyin_size_chips=200)


class _PokerDataRepository:
    def __init__(self, session): pass
    async def list_players(self, *, poker_id):
        return [
            SimpleNamespace(player_name="Waiting Player", buyins=1, chips=None),
            SimpleNamespace(player_name="Entered Player", buyins=1, chips=395),
        ]


@pytest.mark.asyncio
async def test_tg_calculation_precheck_reports_missing_chips_before_total_mismatch(monkeypatch):
    monkeypatch.setattr(tg_poker, "SessionFactory", _Session)
    monkeypatch.setattr(tg_poker, "PokerRepository", _PokerRepository)
    monkeypatch.setattr(tg_poker, "PokerDataRepository", _PokerDataRepository)
    monkeypatch.setattr(tg_poker, "is_tg_admin", AsyncMock(return_value=True))
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        message=SimpleNamespace(answer=AsyncMock()),
        answer=AsyncMock(),
    )

    await tg_poker.calculate_poker_inline(callback)

    callback.answer.assert_awaited_once_with(
        Text.admin.POKER_CHIPS_WAITING.value.format(players="Waiting Player"),
        show_alert=True,
    )


@pytest.mark.asyncio
async def test_vk_calculation_precheck_reports_missing_chips_before_total_mismatch(monkeypatch):
    monkeypatch.setattr(vk_chips, "SessionFactory", _Session)
    monkeypatch.setattr(vk_chips, "PokerRepository", _PokerRepository)
    monkeypatch.setattr(vk_chips, "PokerDataRepository", _PokerDataRepository)
    monkeypatch.setattr(vk_chips, "is_vk_admin", AsyncMock(return_value=True))
    event_answer = AsyncMock()
    monkeypatch.setattr(vk_chips, "send_vk_message_event_answer", event_answer)

    await vk_chips.handle_poker_calc_run_event(
        admin_user_id=1,
        peer_id=1,
        event_id="event",
        conversation_message_id=1,
        callback_payload={},
        action="poker_calc_run",
        handle_admin_text_commands=AsyncMock(),
    )

    event_answer.assert_awaited_once_with(
        event_id="event",
        user_id=1,
        peer_id=1,
        text=Text.admin.POKER_CHIPS_WAITING.value.format(players="Waiting Player"),
    )
