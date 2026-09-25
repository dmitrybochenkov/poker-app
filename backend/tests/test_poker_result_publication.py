from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.bot.shared.buttons.buttons import Buttons
from app.bot.telegram.handlers.admin import calculation as tg_poker
from app.bot.telegram import runtime as tg_runtime
from app.bot.vk import api as vk_api
from app.bot.vk.handlers.admin import chips as vk_chips
from app.db.models.bet import Bet
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.user import User
from test_calculate_poker_result_use_case import _setup


class _Session:
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc, tb): return None


class _UseCase:
    def __init__(self, session): pass
    async def execute(self, *, actor_user_id):
        player = SimpleNamespace(player_id=1, player_name="Player", money_kopecks=0)
        return SimpleNamespace(
            poker_id=5, poker_date=date(2026, 9, 24), players=(player,), bets=(),
            winners=("Player",), losers=("Player",), previous_winners=frozenset(),
            recipient_user_ids=(1, 2, 3), transfers=(),
        )


def _user(row_id, *, platform):
    return SimpleNamespace(
        row_id=row_id, name=f"User {row_id}", notification_platform=platform,
        telegram_id=100 + row_id, vk_id=200 + row_id,
        tel_number=None, bank_name=None,
    )


def _users(platform):
    class Users:
        def __init__(self, session): pass
        async def list_approved(self): return []
        async def get_by_row_id(self, row_id): return _user(row_id, platform=platform)
        async def get_by_telegram_id(self, value): return None
        async def get_by_vk_id(self, value): return None
    return Users


def _common(monkeypatch, module, platform):
    monkeypatch.setattr(module, "SessionFactory", _Session)
    monkeypatch.setattr(module, "CalculatePokerResultUseCase", _UseCase)
    monkeypatch.setattr(module, "UserRepository", _users(platform))
    monkeypatch.setattr(module, "backup_tables_to_google", AsyncMock())
    monkeypatch.setattr(module, "_build_poker_buyins_session_chart", AsyncMock(return_value=b"png"))


@pytest.mark.asyncio
async def test_tg_middle_recipient_failure_does_not_stop_later_recipient(monkeypatch):
    _common(monkeypatch, tg_poker, "tg")
    monkeypatch.setattr(tg_poker, "resolve_telegram_user_id", AsyncMock(return_value=9))
    sent = []
    async def send_message(*, chat_id, **kwargs):
        sent.append((chat_id, "text"))
        if chat_id == 102: raise RuntimeError("TG blocked")
    bot = SimpleNamespace(send_message=send_message, send_photo=AsyncMock(side_effect=lambda **k: sent.append((k["chat_id"], "graph"))))
    monkeypatch.setattr(tg_runtime, "telegram_bot", bot)
    cleanup = AsyncMock(side_effect=RuntimeError("cleanup failed"))
    monkeypatch.setattr(tg_poker, "_clear_tg_admin_chips_calc_buttons", cleanup)
    message = SimpleNamespace(from_user=SimpleNamespace(id=9), answer=AsyncMock())

    await tg_poker.calculate_poker(message)

    assert (101, "text") in sent
    assert (103, "text") in sent
    assert (102, "graph") not in sent
    assert sent.index((101, "text")) < sent.index((101, "graph"))
    cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_vk_middle_recipient_failure_does_not_stop_later_recipient(monkeypatch):
    _common(monkeypatch, vk_chips, "vk")
    monkeypatch.setattr(vk_chips, "resolve_vk_user_id", AsyncMock(return_value=9))
    sent = []
    async def send_message(*, user_id, **kwargs):
        sent.append((user_id, "text"))
        if user_id == 202: raise RuntimeError("VK blocked")
    monkeypatch.setattr(vk_chips, "send_vk_message", send_message)
    monkeypatch.setattr(vk_chips, "send_vk_photo", AsyncMock(side_effect=lambda **k: sent.append((k["user_id"], "graph"))))
    monkeypatch.setattr(vk_chips, "_clear_vk_admin_chips_calc_buttons", AsyncMock())

    await vk_chips.handle_admin_room_calculate_poker_text(
        user_id=9, text=Buttons.admin_room.CALCULATE_POKER.value
    )

    assert (201, "text") in sent
    assert (203, "text") in sent
    assert (202, "graph") not in sent
    assert sent.index((201, "text")) < sent.index((201, "graph"))


@pytest.mark.asyncio
async def test_graph_failure_keeps_text_and_does_not_stop_later_recipient(monkeypatch):
    _common(monkeypatch, tg_poker, "tg")
    monkeypatch.setattr(tg_poker, "resolve_telegram_user_id", AsyncMock(return_value=9))
    sent = []
    async def send_photo(*, chat_id, **kwargs):
        sent.append((chat_id, "graph"))
        if chat_id == 102: raise RuntimeError("graph failed")
    bot = SimpleNamespace(
        send_message=AsyncMock(side_effect=lambda **k: sent.append((k["chat_id"], "text"))),
        send_photo=send_photo,
    )
    monkeypatch.setattr(tg_runtime, "telegram_bot", bot)
    monkeypatch.setattr(tg_poker, "_clear_tg_admin_chips_calc_buttons", AsyncMock())
    message = SimpleNamespace(from_user=SimpleNamespace(id=9), answer=AsyncMock())

    await tg_poker.calculate_poker(message)

    assert (102, "text") in sent
    assert (103, "text") in sent


@pytest.mark.asyncio
async def test_tg_failure_does_not_prevent_vk_delivery(monkeypatch):
    _common(monkeypatch, tg_poker, "tg")
    monkeypatch.setattr(tg_poker, "resolve_telegram_user_id", AsyncMock(return_value=9))
    users = {1: _user(1, platform="tg"), 2: _user(2, platform="vk"), 3: _user(3, platform="vk")}
    class MixedUsers(_users("tg")):
        async def get_by_row_id(self, row_id): return users[row_id]
    monkeypatch.setattr(tg_poker, "UserRepository", MixedUsers)
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError("TG blocked")), send_photo=AsyncMock())
    monkeypatch.setattr(tg_runtime, "telegram_bot", bot)
    sent_vk = AsyncMock()
    monkeypatch.setattr(tg_poker, "send_vk_message", sent_vk)
    monkeypatch.setattr(vk_api, "send_vk_photo", AsyncMock())
    monkeypatch.setattr(tg_poker, "_clear_tg_admin_chips_calc_buttons", AsyncMock())
    message = SimpleNamespace(from_user=SimpleNamespace(id=9), answer=AsyncMock())

    await tg_poker.calculate_poker(message)

    assert [call.kwargs["user_id"] for call in sent_vk.await_args_list] == [202, 203]


@pytest.mark.asyncio
async def test_vk_failure_does_not_prevent_tg_delivery(monkeypatch):
    _common(monkeypatch, vk_chips, "vk")
    monkeypatch.setattr(vk_chips, "resolve_vk_user_id", AsyncMock(return_value=9))
    users = {1: _user(1, platform="vk"), 2: _user(2, platform="tg"), 3: _user(3, platform="tg")}
    class MixedUsers(_users("vk")):
        async def get_by_row_id(self, row_id): return users[row_id]
    monkeypatch.setattr(vk_chips, "UserRepository", MixedUsers)
    monkeypatch.setattr(vk_chips, "send_vk_message", AsyncMock(side_effect=RuntimeError("VK blocked")))
    sent_tg = AsyncMock()
    bot = SimpleNamespace(send_message=sent_tg, send_photo=AsyncMock())
    monkeypatch.setattr(tg_runtime, "telegram_bot", bot)
    monkeypatch.setattr(vk_chips, "_clear_vk_admin_chips_calc_buttons", AsyncMock())

    await vk_chips.handle_admin_room_calculate_poker_text(
        user_id=9, text=Buttons.admin_room.CALCULATE_POKER.value
    )

    assert [call.kwargs["chat_id"] for call in sent_tg.await_args_list] == [102, 103]


@pytest.mark.asyncio
async def test_chart_failure_still_publishes_text(monkeypatch):
    _common(monkeypatch, vk_chips, "vk")
    monkeypatch.setattr(vk_chips, "resolve_vk_user_id", AsyncMock(return_value=9))
    monkeypatch.setattr(
        vk_chips, "_build_poker_buyins_session_chart", AsyncMock(side_effect=RuntimeError("chart"))
    )
    sent = AsyncMock()
    monkeypatch.setattr(vk_chips, "send_vk_message", sent)
    photos = AsyncMock()
    monkeypatch.setattr(vk_chips, "send_vk_photo", photos)
    monkeypatch.setattr(vk_chips, "_clear_vk_admin_chips_calc_buttons", AsyncMock())

    await vk_chips.handle_admin_room_calculate_poker_text(
        user_id=9, text=Buttons.admin_room.CALCULATE_POKER.value
    )

    assert [call.kwargs["user_id"] for call in sent.await_args_list] == [201, 202, 203]
    photos.assert_not_awaited()


@pytest.mark.asyncio
async def test_initiator_receives_result_when_not_already_a_recipient(monkeypatch):
    _common(monkeypatch, tg_poker, None)
    monkeypatch.setattr(tg_poker, "resolve_telegram_user_id", AsyncMock(return_value=9))
    class Users(_users(None)):
        async def get_by_telegram_id(self, value): return _user(9, platform="tg")
    monkeypatch.setattr(tg_poker, "UserRepository", Users)
    monkeypatch.setattr(tg_poker, "_build_poker_buyins_session_chart", AsyncMock(return_value=None))
    sent = AsyncMock()
    monkeypatch.setattr(tg_runtime, "telegram_bot", SimpleNamespace(send_message=sent, send_photo=AsyncMock()))
    monkeypatch.setattr(tg_poker, "_clear_tg_admin_chips_calc_buttons", AsyncMock())
    message = SimpleNamespace(from_user=SimpleNamespace(id=9), answer=AsyncMock())

    await tg_poker.calculate_poker(message)

    sent.assert_awaited_once()
    assert sent.await_args.kwargs["chat_id"] == 109


@pytest.mark.asyncio
async def test_committed_result_survives_publication_failure(monkeypatch):
    engine, sessions, admin_id, poker_id = await _setup()
    async with sessions() as session:
        users = (await session.execute(select(User))).scalars().all()
        for user in users:
            user.notification_platform = "tg"
        await session.commit()
    monkeypatch.setattr(tg_poker, "SessionFactory", sessions)
    monkeypatch.setattr(tg_poker, "backup_tables_to_google", AsyncMock())
    monkeypatch.setattr(tg_poker, "_build_poker_buyins_session_chart", AsyncMock(return_value=None))
    bot = SimpleNamespace(
        send_message=AsyncMock(side_effect=[None, RuntimeError("blocked"), None]),
        send_photo=AsyncMock(),
    )
    monkeypatch.setattr(tg_runtime, "telegram_bot", bot)
    monkeypatch.setattr(tg_poker, "_clear_tg_admin_chips_calc_buttons", AsyncMock())
    message = SimpleNamespace(from_user=SimpleNamespace(id=1), answer=AsyncMock())

    await tg_poker.calculate_poker(message)

    async with sessions() as session:
        poker = await session.get(Poker, poker_id)
        rows = sorted((await session.execute(select(PokerData))).scalars(), key=lambda row: row.row_id)
        bet = (await session.execute(select(Bet))).scalars().one()
        assert poker.is_ready_for_chips_entering is False
        assert (poker.winners, poker.loosers) == ("Second Player", "First Player")
        assert [row.money_kopecks for row in rows] == [-20_000, 20_000]
        assert bet.score == 5
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("module,platform", [(tg_poker, "tg"), (vk_chips, "vk")])
async def test_transfer_contact_comes_from_canonical_payee_with_overlapping_names(
    monkeypatch, module, platform
):
    payer = SimpleNamespace(player_id=1, player_name="Иван", money_kopecks=-10_000)
    payee = SimpleNamespace(player_id=2, player_name="Алексей Петров", money_kopecks=10_000)
    class TransferUseCase:
        def __init__(self, session): pass
        async def execute(self, *, actor_user_id):
            return SimpleNamespace(
                poker_id=5, poker_date=date(2026, 9, 24), players=(payer, payee), bets=(),
                winners=(payee.player_name,), losers=(payer.player_name,),
                previous_winners=frozenset(), recipient_user_ids=(2,),
                transfers=(SimpleNamespace(to_user_id=2),),
            )
    wrong = SimpleNamespace(
        row_id=3, name="Алексей Петрович", notification_platform=None,
        telegram_id=None, vk_id=None, tel_number="+7 WRONG", bank_name="Wrong Bank",
    )
    correct = _user(2, platform=platform)
    correct.name = payee.player_name
    correct.tel_number = "+7 CORRECT"
    correct.bank_name = "Correct Bank"
    class Users:
        def __init__(self, session): pass
        async def list_approved(self): return [wrong, correct]
        async def get_by_row_id(self, row_id): return correct
        async def get_by_telegram_id(self, value): return None
        async def get_by_vk_id(self, value): return None
    _common(monkeypatch, module, platform)
    monkeypatch.setattr(module, "CalculatePokerResultUseCase", TransferUseCase)
    monkeypatch.setattr(module, "UserRepository", Users)
    monkeypatch.setattr(module, "_build_poker_buyins_session_chart", AsyncMock(return_value=None))
    if platform == "tg":
        monkeypatch.setattr(module, "resolve_telegram_user_id", AsyncMock(return_value=9))
        sent = AsyncMock()
        monkeypatch.setattr(tg_runtime, "telegram_bot", SimpleNamespace(send_message=sent, send_photo=AsyncMock()))
        monkeypatch.setattr(module, "_clear_tg_admin_chips_calc_buttons", AsyncMock())
        await module.calculate_poker(SimpleNamespace(from_user=SimpleNamespace(id=9), answer=AsyncMock()))
        text = sent.await_args.kwargs["text"]
    else:
        monkeypatch.setattr(module, "resolve_vk_user_id", AsyncMock(return_value=9))
        sent = AsyncMock()
        monkeypatch.setattr(module, "send_vk_message", sent)
        monkeypatch.setattr(module, "_clear_vk_admin_chips_calc_buttons", AsyncMock())
        await module.handle_admin_room_calculate_poker_text(
            user_id=9, text=Buttons.admin_room.CALCULATE_POKER.value
        )
        text = sent.await_args.kwargs["message"]

    assert "+7 CORRECT" in text
    assert "+7 WRONG" not in text
