from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.poker.calculate_bet_scores import CalculateBetScoresUseCase
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository


class CalculatePokerNotAuthorizedError(Exception): pass
class PokerNotReadyForCalculationError(Exception): pass
class MissingPlayerChipsError(Exception):
  def __init__(self, player_names: tuple[str, ...]) -> None:
    self.player_names = player_names
class PokerChipTotalMismatchError(Exception):
  def __init__(self, diff: int) -> None:
    self.diff = diff
class PokerCalculationAlreadyCompletedError(Exception): pass


@dataclass(frozen=True)
class CalculatedPlayer:
  player_id: int
  player_name: str
  money_kopecks: int


@dataclass(frozen=True)
class CalculatedBet:
  row_id: int
  better_id: int
  better_name: str
  amount_kopecks: int
  winner_name: str | None
  loser_name: str | None
  score: int


@dataclass(frozen=True)
class PokerTransfer:
  from_name: str
  to_name: str
  amount_kopecks: int


@dataclass(frozen=True)
class CalculatePokerResult:
  poker_id: int
  poker_date: date
  players: tuple[CalculatedPlayer, ...]
  bets: tuple[CalculatedBet, ...]
  winners: tuple[str, ...]
  losers: tuple[str, ...]
  transfers: tuple[PokerTransfer, ...]
  previous_winners: frozenset[str]
  recipient_user_ids: tuple[int, ...]


def _calculate_transfers(players: list[CalculatedPlayer]) -> tuple[PokerTransfer, ...]:
  rows = [{"name": row.player_name, "money": row.money_kopecks} for row in players]
  transfers: list[PokerTransfer] = []
  while True:
    loser = min(rows, key=lambda row: int(row["money"]))
    winner = max(rows, key=lambda row: int(row["money"]))
    transfer = min(-int(loser["money"]), int(winner["money"]))
    if transfer <= 0:
      break
    loser["money"] = int(loser["money"]) + transfer
    winner["money"] = int(winner["money"]) - transfer
    transfers.append(PokerTransfer(str(loser["name"]), str(winner["name"]), transfer))
  return tuple(transfers)


class CalculatePokerResultUseCase:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.user_repository = UserRepository(session)
    self.poker_repository = PokerRepository(session)
    self.poker_data_repository = PokerDataRepository(session)
    self.bet_repository = BetRepository(session)
    self.bet_scores = CalculateBetScoresUseCase(
      bet_repository=self.bet_repository,
      bet_param_repository=BetParamRepository(session),
      bet_tournament_param_repository=BetTournamentParamRepository(session),
      poker_data_repository=self.poker_data_repository,
    )

  async def execute(self, *, actor_user_id: int) -> CalculatePokerResult:
    try:
      actor = await self.user_repository.get_by_row_id(int(actor_user_id))
      if actor is None or not actor.is_approved or not actor.is_admin:
        raise CalculatePokerNotAuthorizedError
      ready = await self.poker_repository.get_latest_ready_for_chips_with_params()
      if ready is None:
        raise PokerNotReadyForCalculationError
      poker, params = ready
      participants = await self.poker_data_repository.list_players(date=poker.date)
      if not participants:
        raise PokerNotReadyForCalculationError
      missing = tuple(row.player_name for row in participants if row.chips is None)
      if missing:
        raise MissingPlayerChipsError(missing)
      chips_in_game = sum(int(row.buyins) * int(params.buyin_size_chips) for row in participants)
      chips_entered = sum(int(row.chips) for row in participants)
      if chips_entered != chips_in_game:
        raise PokerChipTotalMismatchError(chips_entered - chips_in_game)

      players: list[CalculatedPlayer] = []
      for participant in participants:
        money = (
          (int(participant.chips) - int(participant.buyins) * int(params.buyin_size_chips))
          * int(params.buyin_size_kopecks)
        ) // int(params.buyin_size_chips)
        updated = await self.poker_data_repository.set_cashout_without_commit(
          date=poker.date, player_id=int(participant.player_id), money_kopecks=money
        )
        if updated is None:
          raise PokerNotReadyForCalculationError
        players.append(CalculatedPlayer(int(updated.player_id), updated.player_name, money))

      max_money = max(row.money_kopecks for row in players)
      min_money = min(row.money_kopecks for row in players)
      winners = tuple(row.player_name for row in players if row.money_kopecks == max_money)
      losers = tuple(row.player_name for row in players if row.money_kopecks == min_money)
      await self.bet_scores.execute_without_commit(poker_id=poker.row_id, poker_date=poker.date)
      bet_rows = await self.bet_repository.list_for_poker(date=poker.date)
      bets = tuple(
        CalculatedBet(int(b.row_id), int(b.better_id), b.better_name, int(b.amount_kopecks),
                      b.winner_name, b.loser_name, int(b.score))
        for b in bet_rows
      )
      all_pokers = await self.poker_repository.list_all()
      previous = next((old for old in sorted(all_pokers, key=lambda x: int(x.row_id), reverse=True)
                       if int(old.row_id) != int(poker.row_id) and bool(old.winners)), None)
      previous_winners = frozenset(
        item.strip() for item in str(previous.winners).split(",") if item.strip()
      ) if previous is not None else frozenset()
      finished = await self.poker_repository.finish_chips_entering_without_commit(
        poker_id=int(poker.row_id), winners=", ".join(winners), loosers=", ".join(losers)
      )
      if not finished:
        raise PokerCalculationAlreadyCompletedError
      await self.session.commit()
      recipients = tuple(sorted({row.player_id for row in players} | {bet.better_id for bet in bets}))
      return CalculatePokerResult(
        int(poker.row_id), poker.date, tuple(players), bets, winners, losers,
        _calculate_transfers(players), previous_winners, recipients,
      )
    except Exception:
      await self.session.rollback()
      raise
