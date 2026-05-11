from app.db.models.bet import Bet
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.poker_data_repository import PokerDataRepository


class CalculateBetScoresUseCase:
  def __init__(
    self,
    *,
    bet_repository: BetRepository,
    bet_param_repository: BetParamRepository,
    bet_tournament_param_repository: BetTournamentParamRepository,
    poker_data_repository: PokerDataRepository,
  ) -> None:
    self.bet_repository = bet_repository
    self.bet_param_repository = bet_param_repository
    self.bet_tournament_param_repository = bet_tournament_param_repository
    self.poker_data_repository = poker_data_repository

  async def execute(self, *, poker_id: int, poker_date) -> int:
    bets = await self.bet_repository.list_for_poker(poker_id=poker_id)
    if not bets:
      return 0

    players = await self.poker_data_repository.list_players(date=poker_date)
    if not players:
      return 0

    max_cashout = max(int(p.money_kopecks) for p in players)
    min_cashout = min(int(p.money_kopecks) for p in players)
    winners = {p.player_name for p in players if int(p.money_kopecks) == max_cashout}
    losers = {p.player_name for p in players if int(p.money_kopecks) == min_cashout}

    updated = 0
    for bet in bets:
      score = await self._calculate_score_for_bet(
        bet=bet,
        winners=winners,
        losers=losers,
      )
      await self.bet_repository.update_score(bet=bet, score=score)
      updated += 1

    await self.bet_repository.session.commit()
    return updated

  async def _calculate_score_for_bet(self, *, bet: Bet, winners: set[str], losers: set[str]) -> int:
    if not bet.winner_name or not bet.loser_name:
      return 0
    params = await self._resolve_bet_params(bet=bet)
    if params is None:
      return 0

    is_big = int(bet.amount_kopecks) >= int(params.big_size_kopecks)
    guessed_winner = bet.winner_name in winners
    guessed_loser = bet.loser_name in losers

    if guessed_winner and guessed_loser:
      return int(params.big_score_combo if is_big else params.small_score_combo)
    if guessed_winner or guessed_loser:
      return int(params.big_score if is_big else params.small_score)
    return 0

  async def _resolve_bet_params(self, *, bet: Bet):
    if bet.params_id is not None:
      direct = await self.bet_param_repository.get_by_id(row_id=int(bet.params_id))
      if direct is not None:
        return direct
    tournament_params = await self.bet_tournament_param_repository.get_by_tournament_type(
      tournament_type=bet.tournament_type
    )
    if tournament_params is None:
      return None
    return await self.bet_param_repository.get_by_id(row_id=int(tournament_params.bet_param_id))
