import asyncio
from datetime import date

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.bet import BetUseCases
from app.db.base import Base
from app.db.models.bet import Bet
from app.db.models.bet_param import BetParam
from app.db.models.bet_tournament import BetTournament
from app.db.models.bet_tournament_param import BetTournamentParam
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.user import User
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import (
    BetTournamentParamRepository,
)
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository


async def _store(tmp_path, name):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")

    @event.listens_for(engine.sync_engine, "connect")
    def configure_sqlite(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                PokerParam.__table__,
                Poker.__table__,
                PokerData.__table__,
                Bet.__table__,
                BetParam.__table__,
                BetTournament.__table__,
                BetTournamentParam.__table__,
            ],
        )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed(sessions):
    game_date = date(2026, 9, 26)
    async with sessions() as session:
        linked = User(
            name="Same Name",
            telegram_id=101,
            vk_id=202,
            is_approved=True,
        )
        other = User(name="Same Name", telegram_id=303, is_approved=True)
        poker_params = PokerParam(
            buyin_size_chips=200,
            buyin_size_kopecks=20_000,
            bb_size_chips=10,
            max_buyins=3,
            big_buyin=5,
            king_buyin=15,
            super_buyin=10,
        )
        bet_params = BetParam(
            small_size_kopecks=10_000,
            small_score=1,
            small_score_combo=2,
            big_size_kopecks=20_000,
            big_score=2,
            big_score_combo=4,
            percent_to_regular_bank_if_it_is_going=100,
        )
        session.add_all([linked, other, poker_params, bet_params])
        await session.flush()
        session.add_all(
            [
                Poker(
                    params_id=int(poker_params.row_id),
                    date=game_date,
                    is_going=True,
                    is_bettable=True,
                ),
                BetTournamentParam(
                    tournament_type="regular",
                    bet_param_id=int(bet_params.row_id),
                ),
                BetTournament(
                    params_id=int(bet_params.row_id),
                    tournament_type="regular",
                    start_date=game_date,
                    end_date=game_date,
                    current_bank_kopecks=0,
                ),
            ]
        )
        await session.commit()
        return int(linked.row_id), int(other.row_id), game_date


def _use_case(session):
    return BetUseCases(
        user_repository=UserRepository(session),
        poker_repository=PokerRepository(session),
        bet_repository=BetRepository(session),
        bet_param_repository=BetParamRepository(session),
        bet_tournament_repository=BetTournamentRepository(session),
        bet_tournament_param_repository=BetTournamentParamRepository(session),
        poker_data_repository=PokerDataRepository(session),
    )


@pytest.mark.asyncio
async def test_sequential_duplicate_checks_use_canonical_user_id(tmp_path):
    engine, sessions = await _store(tmp_path, "sequential.db")
    linked_id, other_id, game_date = await _seed(sessions)
    try:
        async with sessions() as session:
            first = await _use_case(session).create_bet(
                better_id=101,
                tournament_type="single",
                amount_kopecks=10_000,
                winner_name="Winner",
                loser_name="Loser",
            )
        async with sessions() as session:
            linked = await session.get(User, linked_id)
            linked.name = "Renamed User"
            await session.commit()
        async with sessions() as session:
            linked_through_vk = await _use_case(session).create_bet(
                better_id=202,
                tournament_type="single",
                amount_kopecks=10_000,
                winner_name="Winner",
                loser_name="Loser",
            )
            other_same_name = await _use_case(session).create_bet(
                better_id=303,
                tournament_type="single",
                amount_kopecks=10_000,
                winner_name="Winner",
                loser_name="Loser",
            )
        async with sessions() as session:
            rows = (await session.execute(select(Bet).order_by(Bet.row_id))).scalars().all()

        assert first[1] == "ok"
        assert linked_through_vk == (None, "already_bet")
        assert other_same_name[1] == "ok"
        assert [(row.better_id, row.better_name, row.date) for row in rows] == [
            (linked_id, "Same Name", game_date),
            (other_id, "Same Name", game_date),
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_platform_id_collision_is_resolved_as_telegram_first(tmp_path):
    engine, sessions = await _store(tmp_path, "platform-id-collision.db")
    await _seed(sessions)
    try:
        async with sessions() as session:
            telegram_user = User(
                name="Telegram Owner", telegram_id=777, is_approved=True
            )
            vk_user = User(name="VK Owner", vk_id=777, is_approved=True)
            session.add_all([telegram_user, vk_user])
            await session.commit()
            telegram_user_id = int(telegram_user.row_id)
            vk_user_id = int(vk_user.row_id)

        async with sessions() as session:
            created, status = await _use_case(session).create_bet(
                better_id=777,
                tournament_type="single",
                amount_kopecks=10_000,
                winner_name="Winner",
                loser_name="Loser",
            )

        assert status == "ok" and created is not None
        assert created.better_id == telegram_user_id
        assert created.better_id != vk_user_id
        assert created.better_name == "Telegram Owner"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_name", "external_ids"),
    [
        ("telegram-telegram", (101, 101)),
        ("vk-vk", (202, 202)),
        ("telegram-vk", (101, 202)),
    ],
)
async def test_concurrent_duplicate_checks_create_two_bets_and_double_bank(
    tmp_path, monkeypatch, case_name, external_ids
):
    engine, sessions = await _store(tmp_path, f"concurrent-{case_name}.db")
    linked_id, _, game_date = await _seed(sessions)
    original = BetRepository.get_by_poker_user_and_tournament
    calls_by_session = {}
    both_second_checks_complete = asyncio.Event()
    second_check_count = 0
    observed = []

    async def synchronized_check(repository, **kwargs):
        nonlocal second_check_count
        result = await original(repository, **kwargs)
        key = id(repository.session)
        calls_by_session[key] = calls_by_session.get(key, 0) + 1
        if calls_by_session[key] == 2:
            observed.append(result)
            second_check_count += 1
            if second_check_count == 2:
                both_second_checks_complete.set()
            await asyncio.wait_for(both_second_checks_complete.wait(), timeout=2)
        return result

    monkeypatch.setattr(
        BetRepository,
        "get_by_poker_user_and_tournament",
        synchronized_check,
    )

    async def submit(external_id):
        async with sessions() as session:
            return await _use_case(session).create_bet(
                better_id=external_id,
                tournament_type="single",
                amount_kopecks=10_000,
                winner_name="Winner",
                loser_name="Loser",
            )

    try:
        outcomes = await asyncio.gather(
            *(submit(external_id) for external_id in external_ids),
            return_exceptions=True,
        )
        async with sessions() as session:
            rows = (
                await session.execute(select(Bet).order_by(Bet.row_id))
            ).scalars().all()
            tournament = (
                await session.execute(select(BetTournament))
            ).scalar_one()

        assert observed == [None, None]
        assert [result[1] for result in outcomes] == ["ok", "ok"]
        assert [(row.better_id, row.date) for row in rows] == [
            (linked_id, game_date),
            (linked_id, game_date),
        ]
        assert tournament.current_bank_kopecks == 20_000
    finally:
        await engine.dispose()
