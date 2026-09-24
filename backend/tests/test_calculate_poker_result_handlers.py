from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.shared.buttons.buttons import Buttons
from app.bot.telegram.handlers.admin import poker as tg_poker
from app.bot.vk.handlers.admin import chips as vk_chips


class _Session:
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb): return None


def _result():
    player = SimpleNamespace(player_id=10, player_name="Player", money_kopecks=0)
    return SimpleNamespace(
        poker_id=3,
        poker_date=date(2026, 9, 24),
        players=(player,),
        bets=(),
        winners=("Player",),
        losers=("Player",),
        previous_winners=frozenset(),
        recipient_user_ids=(),
        transfers=(),
    )


class _UseCase:
    result = _result()
    events = None

    def __init__(self, session): pass

    async def execute(self, *, actor_user_id):
        self.events.append("commit")
        return self.result


class _Users:
    def __init__(self, session): pass
    async def list_approved(self): return []
    async def get_by_telegram_id(self, value): return None
    async def get_by_vk_id(self, value): return None
    async def get_by_row_id(self, value): return None


@pytest.mark.asyncio
async def test_tg_final_calculation_starts_side_effects_after_shared_operation(monkeypatch):
    events = []
    _UseCase.events = events
    monkeypatch.setattr(tg_poker, "SessionFactory", _Session)
    monkeypatch.setattr(tg_poker, "resolve_telegram_user_id", AsyncMock(return_value=1))
    monkeypatch.setattr(tg_poker, "CalculatePokerResultUseCase", _UseCase)
    monkeypatch.setattr(tg_poker, "UserRepository", _Users)
    monkeypatch.setattr(tg_poker, "backup_tables_to_google", AsyncMock(side_effect=lambda **k: events.append("backup")))
    monkeypatch.setattr(tg_poker, "_build_poker_buyins_session_chart", AsyncMock(return_value=None))
    monkeypatch.setattr(tg_poker, "_clear_tg_admin_chips_calc_buttons", AsyncMock())
    message = SimpleNamespace(from_user=SimpleNamespace(id=7), answer=AsyncMock())

    await tg_poker.calculate_poker(message)

    assert events == ["commit", "backup"]


@pytest.mark.asyncio
async def test_vk_final_calculation_starts_side_effects_after_shared_operation(monkeypatch):
    events = []
    _UseCase.events = events
    monkeypatch.setattr(vk_chips, "SessionFactory", _Session)
    monkeypatch.setattr(vk_chips, "resolve_vk_user_id", AsyncMock(return_value=1))
    monkeypatch.setattr(vk_chips, "CalculatePokerResultUseCase", _UseCase)
    monkeypatch.setattr(vk_chips, "UserRepository", _Users)
    monkeypatch.setattr(vk_chips, "backup_tables_to_google", AsyncMock(side_effect=lambda **k: events.append("backup")))
    monkeypatch.setattr(vk_chips, "_build_poker_buyins_session_chart", AsyncMock(return_value=None))
    monkeypatch.setattr(vk_chips, "_clear_vk_admin_chips_calc_buttons", AsyncMock())
    monkeypatch.setattr(vk_chips, "send_vk_message", AsyncMock())

    response = await vk_chips.handle_admin_room_calculate_poker_text(
        user_id=7, text=Buttons.admin_room.CALCULATE_POKER.value
    )

    assert response.body == b"ok"
    assert events == ["commit", "backup"]


@pytest.mark.asyncio
@pytest.mark.parametrize("module,handler_kind", [(tg_poker, "tg"), (vk_chips, "vk")])
async def test_failed_final_transaction_does_not_start_post_commit_work(
    monkeypatch, module, handler_kind
):
    class _FailingUseCase:
        def __init__(self, session): pass
        async def execute(self, *, actor_user_id): raise RuntimeError("transaction failed")

    backup = AsyncMock()
    monkeypatch.setattr(module, "SessionFactory", _Session)
    monkeypatch.setattr(module, "CalculatePokerResultUseCase", _FailingUseCase)
    monkeypatch.setattr(module, "backup_tables_to_google", backup)
    if handler_kind == "tg":
        monkeypatch.setattr(module, "resolve_telegram_user_id", AsyncMock(return_value=1))
        message = SimpleNamespace(from_user=SimpleNamespace(id=7), answer=AsyncMock())
        with pytest.raises(RuntimeError, match="transaction failed"):
            await module.calculate_poker(message)
    else:
        monkeypatch.setattr(module, "resolve_vk_user_id", AsyncMock(return_value=1))
        with pytest.raises(RuntimeError, match="transaction failed"):
            await module.handle_admin_room_calculate_poker_text(
                user_id=7, text=Buttons.admin_room.CALCULATE_POKER.value
            )
    backup.assert_not_awaited()
