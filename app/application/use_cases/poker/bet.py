from app.db.models.bet import Bet
from app.db.models.bet_param import BetParam
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.user import User
from app.db.repositories.bet_param_repository import BetParamRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository


class BetUseCases:
  TOURNAMENT_REGULAR = "regular"
  TOURNAMENT_YEAR = "year"
  TOURNAMENT_TYPES = {TOURNAMENT_REGULAR, TOURNAMENT_YEAR}

  def __init__(
    self,
    *,
    user_repository: UserRepository,
    poker_repository: PokerRepository,
    bet_repository: BetRepository,
    bet_param_repository: BetParamRepository,
    bet_tournament_repository: BetTournamentRepository,
    bet_tournament_param_repository: BetTournamentParamRepository,
    poker_data_repository: PokerDataRepository,
  ) -> None:
    self.user_repository = user_repository
    self.poker_repository = poker_repository
    self.bet_repository = bet_repository
    self.bet_param_repository = bet_param_repository
    self.bet_tournament_repository = bet_tournament_repository
    self.bet_tournament_param_repository = bet_tournament_param_repository
    self.poker_data_repository = poker_data_repository

  async def get_active_bettable_poker(self) -> Poker | None:
    started = await self.poker_repository.get_started()
    if started is None:
      return None
    poker, _ = started
    if not poker.is_bettable:
      return None
    return poker

  async def list_current_tournaments(self) -> list[str]:
    poker = await self.get_active_bettable_poker()
    if poker is None:
      return []
    return [self.TOURNAMENT_REGULAR, self.TOURNAMENT_YEAR]

  async def list_current_tournaments_with_banks(self) -> list[tuple[str, int]]:
    poker = await self.get_active_bettable_poker()
    if poker is None:
      return []
    tournaments = await self.bet_tournament_repository.list_active()
    bank_by_type = {item.tournament_type: item.current_bank_kopecks for item in tournaments}
    return [
      (self.TOURNAMENT_REGULAR, int(bank_by_type.get(self.TOURNAMENT_REGULAR, 0))),
      (self.TOURNAMENT_YEAR, int(bank_by_type.get(self.TOURNAMENT_YEAR, 0))),
    ]

  async def create_bet(
    self,
    *,
    better_id: int,
    tournament_type: str,
    amount_kopecks: int,
    winner_name: str | None = None,
    loser_name: str | None = None,
  ) -> tuple[Bet | None, str]:
    if amount_kopecks <= 0:
      return None, "invalid_amount"

    poker = await self.get_active_bettable_poker()
    if poker is None:
      return None, "betting_closed"

    user = await self._get_approved_user(better_id=better_id)
    if user is None:
      return None, "user_not_approved"
    better_row_id = int(user.row_id)

    existing = await self.bet_repository.get_by_poker_user_and_tournament(
      date=poker.date,
      better_id=better_row_id,
      tournament_type=tournament_type,
    )
    if existing is not None:
      return None, "already_bet"

    tournament_params = await self.bet_tournament_param_repository.get_by_tournament_type(
      tournament_type=self.TOURNAMENT_REGULAR
    )
    params_id = tournament_params.bet_param_id if tournament_params is not None else 1
    if params_id is None:
      return None, "missing_params"

    created = await self.bet_repository.create(
      poker_id=poker.row_id,
      date=poker.date,
      better_id=better_row_id,
      better_name=user.name,
      tournament_type=tournament_type,
      amount_kopecks=amount_kopecks,
      params_id=params_id,
      winner_name=winner_name,
      loser_name=loser_name,
      is_paid=False,
    )
    await self._add_bet_to_current_tournament_banks(
      poker_date=poker.date,
      params_id=int(params_id),
      amount_kopecks=int(amount_kopecks),
    )
    await self.bet_repository.session.commit()
    return created, "ok"

  async def _add_bet_to_current_tournament_banks(
    self,
    *,
    poker_date,
    params_id: int,
    amount_kopecks: int,
  ) -> None:
    if amount_kopecks <= 0:
      return
    tournaments = await self.bet_tournament_repository.list_active()
    current = [
      item for item in tournaments
      if item.start_date is not None
      and item.end_date is not None
      and item.start_date <= poker_date <= item.end_date
    ]
    if not current:
      return

    if len(current) == 1:
      current[0].current_bank_kopecks = int(current[0].current_bank_kopecks or 0) + int(amount_kopecks)
      await self.bet_repository.session.flush()
      return

    params = await self.bet_param_repository.get_by_id(row_id=int(params_id))
    regular_percent = int(params.percent_to_regular_bank_if_it_is_going or 0) if params is not None else 80
    regular_percent = max(0, min(100, regular_percent))

    regular_tournament = next((item for item in current if item.tournament_type == self.TOURNAMENT_REGULAR), None)
    other_tournament = next((item for item in current if item.tournament_type != self.TOURNAMENT_REGULAR), None)

    if regular_tournament is None or other_tournament is None:
      # Fallback: split equally between all currently running tournaments.
      base = int(amount_kopecks) // len(current)
      remainder = int(amount_kopecks) - base * len(current)
      for index, item in enumerate(current):
        bonus = 1 if index < remainder else 0
        item.current_bank_kopecks = int(item.current_bank_kopecks or 0) + base + bonus
      await self.bet_repository.session.flush()
      return

    regular_amount = (int(amount_kopecks) * regular_percent) // 100
    other_amount = int(amount_kopecks) - regular_amount
    regular_tournament.current_bank_kopecks = int(regular_tournament.current_bank_kopecks or 0) + regular_amount
    other_tournament.current_bank_kopecks = int(other_tournament.current_bank_kopecks or 0) + other_amount
    await self.bet_repository.session.flush()

  async def get_bet_draft_data(self, *, better_id: int, tournament_type: str) -> tuple[BetParam | None, list[PokerData], str]:
    poker = await self.get_active_bettable_poker()
    if poker is None:
      return None, [], "betting_closed"
    user = await self._get_approved_user(better_id=better_id)
    if user is None:
      return None, [], "user_not_approved"
    better_row_id = int(user.row_id)
    existing = await self.bet_repository.get_by_poker_user_and_tournament(
      date=poker.date,
      better_id=better_row_id,
      tournament_type=tournament_type,
    )
    if existing is not None:
      return None, [], "already_bet"
    tournament_params = await self.bet_tournament_param_repository.get_by_tournament_type(
      tournament_type=self.TOURNAMENT_REGULAR
    )
    if tournament_params is None:
      return None, [], "missing_params"
    bet_params = await self.bet_param_repository.get_by_id(row_id=int(tournament_params.bet_param_id))
    if bet_params is None:
      return None, [], "missing_params"
    players = await self.poker_data_repository.list_players(date=poker.date)
    if not players:
      return None, [], "no_players"
    return bet_params, players, "ok"

  async def list_user_bets_for_current_poker(self, *, better_id: int) -> list[Bet]:
    poker = await self.get_active_bettable_poker()
    if poker is None:
      return []
    user = await self._get_approved_user(better_id=better_id)
    if user is None:
      return []
    return await self.bet_repository.list_for_user_in_poker(
      date=poker.date,
      better_id=int(user.row_id),
    )

  async def _get_approved_user(self, *, better_id: int) -> User | None:
    user = await self.user_repository.get_by_telegram_id(better_id)
    if user is None:
      user = await self.user_repository.get_by_vk_id(better_id)
    if user is None or not user.is_approved:
      return None
    return user
