from app.db.models.bet import Bet
from app.db.models.poker import Poker
from app.db.models.user import User
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
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
    bet_tournament_repository: BetTournamentRepository,
    bet_tournament_param_repository: BetTournamentParamRepository,
  ) -> None:
    self.user_repository = user_repository
    self.poker_repository = poker_repository
    self.bet_repository = bet_repository
    self.bet_tournament_repository = bet_tournament_repository
    self.bet_tournament_param_repository = bet_tournament_param_repository

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
  ) -> tuple[Bet | None, str]:
    if tournament_type not in self.TOURNAMENT_TYPES:
      return None, "invalid_tournament"
    if amount_kopecks <= 0:
      return None, "invalid_amount"

    poker = await self.get_active_bettable_poker()
    if poker is None:
      return None, "betting_closed"

    user = await self._get_approved_user(better_id=better_id)
    if user is None:
      return None, "user_not_approved"

    existing = await self.bet_repository.get_by_poker_user_and_tournament(
      poker_id=poker.row_id,
      better_id=better_id,
      tournament_type=tournament_type,
    )
    if existing is not None:
      return None, "already_bet"

    tournament_params = await self.bet_tournament_param_repository.get_by_tournament_type(
      tournament_type=tournament_type
    )
    params_id = tournament_params.bet_param_id if tournament_params is not None else None

    created = await self.bet_repository.create(
      poker_id=poker.row_id,
      better_id=better_id,
      better_name=user.name,
      tournament_type=tournament_type,
      amount_kopecks=amount_kopecks,
      params_id=params_id,
    )
    await self.bet_tournament_repository.add_to_bank(
      tournament_type=tournament_type,
      amount_kopecks=amount_kopecks,
    )
    await self.bet_repository.session.commit()
    return created, "ok"

  async def list_user_bets_for_current_poker(self, *, better_id: int) -> list[Bet]:
    poker = await self.get_active_bettable_poker()
    if poker is None:
      return []
    return await self.bet_repository.list_for_user_in_poker(
      poker_id=poker.row_id,
      better_id=better_id,
    )

  async def _get_approved_user(self, *, better_id: int) -> User | None:
    user = await self.user_repository.get_by_telegram_id(better_id)
    if user is None:
      user = await self.user_repository.get_by_vk_id(better_id)
    if user is None or not user.is_approved:
      return None
    return user
