from sqlalchemy import Index, Text, UniqueConstraint

from app.db.models.bet import Bet
from app.db.models.buyin_data import BuyinData
from app.db.models.poker import Poker
from app.db.models.poll_vote import PollVote


def _index_contract(table) -> dict[str, tuple[str, ...]]:
    return {
        item.name: tuple(column.name for column in item.columns)
        for item in table.indexes
        if isinstance(item, Index)
    }


def test_bet_metadata_matches_accepted_legacy_schema():
    assert _index_contract(Bet.__table__) == {"ix_bets_date": ("date",)}
    assert {
        constraint.name
        for constraint in Bet.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {"uq_bets_date_better_id", "uq_bets_poker_better_id"}


def test_buyin_metadata_preserves_historical_index_names():
    assert _index_contract(BuyinData.__table__) == {
        "ix_buyin_data_created_at": ("created_at",),
        "ix_buyin_data_player_id": ("player_id",),
        "ix_buyin_data_poker_date": ("date",),
    }


def test_poker_result_lists_are_unbounded_text():
    assert isinstance(Poker.__table__.c.winners.type, Text)
    assert isinstance(Poker.__table__.c.loosers.type, Text)


def test_poll_vote_metadata_preserves_query_indexes():
    assert _index_contract(PollVote.__table__) == {
        "ix_poll_votes_player_row_id": ("player_row_id",),
        "ix_poll_votes_poll_date": ("poll_date",),
    }
