from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.telegram.handlers.admin import bets as tg_bets
from app.bot.vk.handlers.admin import bets as vk_bets


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _AcceptedReceiptRepository:
    def __init__(self, session):
        pass

    async def get_by_row_id(self, *, row_id):
        return SimpleNamespace(row_id=row_id, user_row_id=42, status="accepted_manual")


class _FailIfBetsAreRead:
    def __init__(self, session):
        pass

    async def list_unpaid_for_user(self, *, better_id):
        raise AssertionError("an accepted receipt must not be processed again")


@pytest.mark.asyncio
async def test_tg_manual_receipt_callback_rejects_already_accepted_receipt(monkeypatch):
    monkeypatch.setattr(tg_bets, "SessionFactory", _Session)
    monkeypatch.setattr(tg_bets, "BetPaymentReceiptRepository", _AcceptedReceiptRepository)
    monkeypatch.setattr(tg_bets, "BetRepository", _FailIfBetsAreRead)
    monkeypatch.setattr(tg_bets, "_ensure_tg_admin_callback", AsyncMock(return_value=True))

    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=7),
        data="bet_receipt:done:11",
        answer=AsyncMock(),
        message=None,
    )

    await tg_bets.bet_receipt_manual_callback(callback)

    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_vk_manual_receipt_callback_rejects_already_accepted_receipt(monkeypatch):
    monkeypatch.setattr(vk_bets, "SessionFactory", _Session)
    monkeypatch.setattr(vk_bets, "BetPaymentReceiptRepository", _AcceptedReceiptRepository)
    monkeypatch.setattr(vk_bets, "BetRepository", _FailIfBetsAreRead)
    monkeypatch.setattr(vk_bets, "is_vk_admin", AsyncMock(return_value=True))
    event_answer = AsyncMock()
    monkeypatch.setattr(vk_bets, "send_vk_message_event_answer", event_answer)

    response = await vk_bets.handle_bet_receipt_actions_event(
        admin_user_id=7,
        peer_id=7,
        event_id="event",
        conversation_message_id=3,
        callback_payload={"receipt_row_id": 11},
        action="bet_receipt_done",
        handle_admin_text_commands=AsyncMock(),
    )

    assert response.body == b"ok"
    event_answer.assert_awaited_once()
