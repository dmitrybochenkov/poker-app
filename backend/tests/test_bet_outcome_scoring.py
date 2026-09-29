from types import SimpleNamespace

import pytest

from app.application.use_cases.poker.calculate_bet_scores import CalculateBetScoresUseCase


class _Params:
  async def get_by_id(self, *, row_id):
    return SimpleNamespace(
      row_id=row_id,
      small_size_kopecks=10_000,
      small_score=2,
      small_score_combo=5,
      big_size_kopecks=40_000,
      big_score=4,
      big_score_combo=10,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
  ("winner_id", "loser_id", "winners", "losers", "expected"),
  [
    (10, 20, {10}, {20}, 5),
    (10, 20, {10}, {30}, 2),
    (10, 20, {30}, {20}, 2),
    (10, 20, {30}, {40}, 0),
    (10, 20, {10, 11}, {20, 21}, 5),
    (10, 10, {10}, {10}, 5),
  ],
)
async def test_scoring_uses_canonical_outcome_ids(
  winner_id, loser_id, winners, losers, expected,
):
  use_case = CalculateBetScoresUseCase(
    bet_repository=None,
    bet_param_repository=_Params(),
    bet_tournament_param_repository=None,
    poker_data_repository=None,
  )
  bet = SimpleNamespace(
    params_id=1,
    amount_kopecks=10_000,
    winner_id=winner_id,
    loser_id=loser_id,
    winner_name="Renamed or duplicate label",
    loser_name="Renamed or duplicate label",
  )

  assert await use_case._calculate_score_for_bet(
    bet=bet, winners=winners, losers=losers,
  ) == expected
