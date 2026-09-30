import inspect
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.bet import Bet
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.user import User
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.poker_data_repository import PokerDataRepository


@pytest.mark.asyncio
async def test_single_poker_repository_operations_use_poker_id_and_preserve_snapshots():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                PokerParam.__table__,
                Poker.__table__,
                PokerData.__table__,
                Bet.__table__,
            ],
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    first_date = date(2026, 1, 1)
    second_date = date(2026, 1, 2)
    try:
        async with sessions() as session:
            player = User(name="Player", telegram_id=1, is_approved=True)
            bettor = User(name="Bettor", telegram_id=2, is_approved=True)
            params = PokerParam(
                buyin_size_chips=200,
                buyin_size_kopecks=20_000,
                bb_size_chips=10,
                max_buyins=3,
            )
            session.add_all([player, bettor, params])
            await session.flush()
            first_poker = Poker(params_id=int(params.row_id), date=first_date)
            second_poker = Poker(params_id=int(params.row_id), date=second_date)
            session.add_all([first_poker, second_poker])
            await session.flush()

            # Deliberately misleading snapshots expose any remaining date-as-identity lookup.
            first_player = PokerData(
                poker_id=int(first_poker.row_id),
                date=second_date,
                player_id=int(player.row_id),
                player_name="First snapshot",
                buyins=1,
            )
            second_player = PokerData(
                poker_id=int(second_poker.row_id),
                date=first_date,
                player_id=int(player.row_id),
                player_name="Second snapshot",
                buyins=5,
            )
            first_bet = Bet(
                poker_id=int(first_poker.row_id),
                date=second_date,
                better_id=int(bettor.row_id),
                better_name=bettor.name,
                amount_kopecks=10_000,
                winner_id=int(player.row_id),
                loser_id=int(bettor.row_id),
            )
            second_bet = Bet(
                poker_id=int(second_poker.row_id),
                date=first_date,
                better_id=int(bettor.row_id),
                better_name=bettor.name,
                amount_kopecks=20_000,
                winner_id=int(bettor.row_id),
                loser_id=int(player.row_id),
            )
            session.add_all([first_player, second_player, first_bet, second_bet])
            await session.commit()
            first_poker_id = int(first_poker.row_id)
            player_id = int(player.row_id)
            bettor_id = int(bettor.row_id)

        async with sessions() as session:
            players = PokerDataRepository(session)
            bets = BetRepository(session)
            selected_player = await players.get_player(
                poker_id=first_poker_id,
                player_id=player_id,
            )
            selected_players = await players.list_players(poker_id=first_poker_id)
            updated = await players.add_buyins_without_commit(
                poker_id=first_poker_id,
                player_id=player_id,
                buyins_count=2,
            )
            selected_bet = await bets.get_by_poker_user_and_tournament(
                poker_id=first_poker_id,
                better_id=bettor_id,
            )
            selected_bets = await bets.list_for_poker(poker_id=first_poker_id)
            user_bets = await bets.list_for_user_in_poker(
                poker_id=first_poker_id,
                better_id=bettor_id,
            )

        assert selected_player is not None and selected_player.player_name == "First snapshot"
        assert [row.player_name for row in selected_players] == ["First snapshot"]
        assert updated is not None and updated.buyins == 3
        assert updated.date == second_date
        assert selected_bet is not None and selected_bet.amount_kopecks == 10_000
        assert [row.amount_kopecks for row in selected_bets] == [10_000]
        assert [row.amount_kopecks for row in user_bets] == [10_000]
        assert selected_bet.date == second_date
    finally:
        await engine.dispose()


def test_single_poker_repository_contracts_do_not_accept_date_identity():
    poker_data_methods = [
        PokerDataRepository.get_player,
        PokerDataRepository.list_players,
        PokerDataRepository.add_buyins_without_commit,
        PokerDataRepository.remove_player_without_commit,
        PokerDataRepository.set_cashout_without_commit,
        PokerDataRepository.set_chips_and_cashout_without_commit,
    ]
    bet_methods = [
        BetRepository.get_by_poker_user_and_tournament,
        BetRepository.list_for_poker,
        BetRepository.list_for_user_in_poker,
    ]

    for method in poker_data_methods + bet_methods:
        parameters = inspect.signature(method).parameters
        assert "poker_id" in parameters
        assert parameters["poker_id"].default is inspect.Parameter.empty
        assert "date" not in parameters
