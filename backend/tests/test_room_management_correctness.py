import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.manage_players import (
    CashierCandidateNotParticipantError,
    ManagePokerPlayersUseCase,
)
from app.bot.shared.texts.texts import Text
from app.bot.telegram.handlers.admin import cashier as tg_cashier
from app.bot.telegram.handlers.admin import players as tg_players
from app.bot.vk.handlers.admin import cashier as vk_cashier
from app.bot.vk.handlers.admin import players as vk_players
from app.db.base import Base
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.poker_room_denied import PokerRoomDenied
from app.db.models.user import User
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository


@pytest.fixture
async def room_store(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'room.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                PokerParam.__table__,
                Poker.__table__,
                PokerData.__table__,
                PokerRoomDenied.__table__,
            ],
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        params = PokerParam(
            buyin_size_chips=200,
            buyin_size_kopecks=20_000,
            bb_size_chips=10,
            max_buyins=3,
        )
        admin = User(name="Admin", telegram_id=1, is_approved=True, is_admin=True)
        target = User(name="Target", telegram_id=2, vk_id=22, is_approved=True)
        replacement = User(name="Replacement", telegram_id=3, is_approved=True)
        outsider = User(name="Outsider", telegram_id=4, is_approved=True)
        session.add_all([params, admin, target, replacement, outsider])
        await session.flush()
        poker = Poker(params_id=int(params.row_id))
        session.add(poker)
        await session.flush()
        session.add(PokerRoomDenied(user_row_id=int(target.row_id)))
        await session.commit()
        ids = {
            "admin": int(admin.row_id),
            "target": int(target.row_id),
            "replacement": int(replacement.row_id),
            "outsider": int(outsider.row_id),
            "poker": int(poker.row_id),
        }
    yield sessions, ids
    await engine.dispose()


def _use_case(session):
    return ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
        poker_room_denied_repository=PokerRoomDeniedRepository(session),
    )


@pytest.mark.parametrize(
    "handler",
    [
        tg_players.poker_room_approve_callback,
        tg_players.add_player_callback,
        tg_players.add_new_player_name_input,
        vk_players.handle_poker_add_player_select_event,
        vk_players.handle_poker_room_approve_select_event,
        vk_players.handle_admin_new_player_name_text,
    ],
)
def test_tg_vk_admin_add_handlers_use_atomic_operation(handler):
    source = inspect.getsource(handler)
    assert "add_player_to_active_poker_and_allow" in source
    assert "remove_denied_for_active_poker" not in source


@pytest.mark.asyncio
async def test_admin_add_and_allow_commit_once(room_store):
    sessions, ids = room_store
    commits = 0

    async with sessions() as session:
        @event.listens_for(session.sync_session, "after_commit")
        def count_commit(_session):
            nonlocal commits
            commits += 1

        created = await _use_case(session).add_player_to_active_poker_and_allow(
            player_id=ids["target"],
            player_name="Target",
        )

    async with sessions() as session:
        participant = await session.scalar(
            select(PokerData).where(PokerData.player_id == ids["target"])
        )
        denied = await session.get(PokerRoomDenied, ids["target"])

    assert created is not None
    assert participant is not None
    assert denied is None
    assert commits == 1


@pytest.mark.asyncio
async def test_admin_add_rolls_back_participant_when_allow_fails(room_store, monkeypatch):
    sessions, ids = room_store

    async def fail_allow(self, *, user_row_id):
        raise RuntimeError("allow failed")

    monkeypatch.setattr(PokerRoomDeniedRepository, "remove_without_commit", fail_allow)
    async with sessions() as session:
        with pytest.raises(RuntimeError, match="allow failed"):
            await _use_case(session).add_player_to_active_poker_and_allow(
                player_id=ids["target"],
                player_name="Target",
            )

    async with sessions() as session:
        participant = await session.scalar(
            select(PokerData).where(PokerData.player_id == ids["target"])
        )
        denied = await session.get(PokerRoomDenied, ids["target"])

    assert participant is None
    assert denied is not None


@pytest.mark.asyncio
async def test_admin_add_existing_participant_still_reconciles_denied_state(room_store):
    sessions, ids = room_store
    async with sessions() as session:
        poker = await session.get(Poker, ids["poker"])
        session.add(
            PokerData(
                date=poker.date,
                player_id=ids["target"],
                player_name="Target",
            )
        )
        await session.commit()
    async with sessions() as session:
        existing = await _use_case(session).add_player_to_active_poker_and_allow(
            player_id=ids["target"],
            player_name="Target",
        )
    async with sessions() as session:
        rows = (
            await session.execute(
                select(PokerData).where(PokerData.player_id == ids["target"])
            )
        ).scalars().all()
        denied = await session.get(PokerRoomDenied, ids["target"])
    assert existing is not None
    assert len(rows) == 1
    assert denied is None


@pytest.mark.asyncio
async def test_cashier_requires_current_participant_and_preserves_previous(room_store):
    sessions, ids = room_store
    async with sessions() as session:
        poker = await session.get(Poker, ids["poker"])
        session.add_all(
            [
                PokerData(date=poker.date, player_id=ids["target"], player_name="Target"),
                PokerData(
                    date=poker.date,
                    player_id=ids["replacement"],
                    player_name="Replacement",
                ),
            ]
        )
        await session.commit()

    async with sessions() as session:
        first = await _use_case(session).set_cashier_for_active_poker(
            cashier_id=ids["target"]
        )
        repeated = await _use_case(session).set_cashier_for_active_poker(
            cashier_id=ids["target"]
        )
    assert first is not None and repeated is not None

    for invalid_id in (ids["outsider"], 999_999):
        async with sessions() as session:
            with pytest.raises(CashierCandidateNotParticipantError):
                await _use_case(session).set_cashier_for_active_poker(
                    cashier_id=invalid_id
                )
        async with sessions() as session:
            poker = await session.get(Poker, ids["poker"])
            assert poker.cashier_id == ids["target"]

    async with sessions() as session:
        replacement = await _use_case(session).set_cashier_for_active_poker(
            cashier_id=ids["replacement"]
        )
    assert replacement is not None and replacement.cashier_id == ids["replacement"]


@pytest.mark.asyncio
async def test_removed_participant_is_rejected_as_stale_cashier_target(room_store):
    sessions, ids = room_store
    async with sessions() as session:
        poker = await session.get(Poker, ids["poker"])
        participant = PokerData(
            date=poker.date,
            player_id=ids["target"],
            player_name="Target",
        )
        session.add(participant)
        await session.commit()
        await session.delete(participant)
        await session.commit()
    async with sessions() as session:
        with pytest.raises(CashierCandidateNotParticipantError):
            await _use_case(session).set_cashier_for_active_poker(
                cashier_id=ids["target"]
            )
    async with sessions() as session:
        poker = await session.get(Poker, ids["poker"])
        assert poker.cashier_id is None


class _HandlerSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.mark.asyncio
async def test_tg_cashier_maps_stale_candidate_error(monkeypatch):
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        data="pokercashier:42",
        answer=AsyncMock(),
    )
    use_case = SimpleNamespace(
        set_cashier_for_active_poker=AsyncMock(
            side_effect=CashierCandidateNotParticipantError
        )
    )
    monkeypatch.setattr(tg_cashier, "SessionFactory", _HandlerSession)
    monkeypatch.setattr(tg_cashier, "_clear_inline_keyboard", AsyncMock())
    monkeypatch.setattr(tg_cashier, "_ensure_tg_admin_callback", AsyncMock(return_value=True))
    monkeypatch.setattr(tg_cashier, "ManagePokerPlayersUseCase", lambda **kwargs: use_case)
    monkeypatch.setattr(tg_cashier, "PokerRepository", Mock())
    monkeypatch.setattr(tg_cashier, "PokerDataRepository", Mock())
    monkeypatch.setattr(tg_cashier, "BuyinDataRepository", Mock())

    await tg_cashier.set_cashier_callback(callback)

    callback.answer.assert_awaited_once_with(
        Text.admin.POKER_CASHIER_NOT_PARTICIPANT.value,
        show_alert=True,
    )


@pytest.mark.asyncio
async def test_vk_cashier_maps_stale_candidate_error(monkeypatch):
    use_case = SimpleNamespace(
        set_cashier_for_active_poker=AsyncMock(
            side_effect=CashierCandidateNotParticipantError
        )
    )
    answer = AsyncMock()
    monkeypatch.setattr(vk_cashier, "SessionFactory", _HandlerSession)
    monkeypatch.setattr(vk_cashier, "is_vk_admin", AsyncMock(return_value=True))
    monkeypatch.setattr(vk_cashier, "ManagePokerPlayersUseCase", lambda **kwargs: use_case)
    monkeypatch.setattr(vk_cashier, "PokerRepository", Mock())
    monkeypatch.setattr(vk_cashier, "PokerDataRepository", Mock())
    monkeypatch.setattr(vk_cashier, "send_vk_message_event_answer", answer)
    monkeypatch.setattr(vk_cashier, "_clear_event_inline_keyboard_if_possible", AsyncMock())

    await vk_cashier.handle_poker_set_cashier_select_event(
        admin_user_id=1,
        peer_id=1,
        event_id="event",
        conversation_message_id=1,
        callback_payload={"player_id": 42},
        action="poker_set_cashier_select",
        handle_admin_text_commands=None,
    )

    assert answer.await_args.kwargs["text"] == Text.admin.POKER_CASHIER_NOT_PARTICIPANT.value
