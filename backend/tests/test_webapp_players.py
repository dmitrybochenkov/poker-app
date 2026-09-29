from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.http.webapp import webapp_players
from app.db.base import Base
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.user import User


@pytest.mark.asyncio
async def test_webapp_players_preserves_or_matching_for_duplicate_names() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[User.__table__, Poker.__table__, PokerData.__table__],
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        first_alex = User(name="Алекс", telegram_id=11, is_approved=True)
        second_alex = User(name="Алекс", telegram_id=12, is_approved=True)
        boris = User(name="Борис", telegram_id=13, is_approved=True)
        session.add_all([first_alex, second_alex, boris])
        await session.flush()
        pokers = [
            Poker(params_id=1, date=date(2026, 9, day), is_going=False)
            for day in (1, 2, 3)
        ]
        session.add_all(pokers)
        await session.flush()
        session.add_all(
            [
                PokerData(
                    poker_id=pokers[0].row_id,
                    date=date(2026, 9, 1),
                    player_id=999,
                    player_name="Алекс",
                    money_kopecks=10_000,
                ),
                PokerData(
                    poker_id=pokers[1].row_id,
                    date=date(2026, 9, 2),
                    player_id=first_alex.row_id,
                    player_name="Алекс",
                    money_kopecks=20_000,
                ),
                PokerData(
                    poker_id=pokers[2].row_id,
                    date=date(2026, 9, 3),
                    player_id=boris.row_id,
                    player_name="Борис",
                    money_kopecks=30_000,
                ),
            ]
        )
        await session.commit()

        cards = await webapp_players(session=session)

    cards_by_id = {card.player_id: card for card in cards}
    for alex_id in (first_alex.row_id, second_alex.row_id):
        assert cards_by_id[alex_id].games == 2
        assert cards_by_id[alex_id].profit_rub == 300

    assert cards_by_id[boris.row_id].games == 1
    assert cards_by_id[boris.row_id].profit_rub == 300
    await engine.dispose()
