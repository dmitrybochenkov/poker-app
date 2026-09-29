from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TournamentPayout:
    player_name: str
    score: int
    position: int
    amount_kopecks: int


@dataclass(frozen=True)
class TournamentPayoutResult:
    payouts: tuple[TournamentPayout, ...]
    place_names: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]
    total_payout_kopecks: int
    remainder_kopecks: int


def calculate_payout_amounts(
    *,
    bank_kopecks: int,
    place_names: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]],
    prize_percents: tuple[int, int, int],
) -> tuple[dict[str, int], int, int]:
    bank = int(bank_kopecks)
    percents = tuple(int(value) for value in prize_percents)
    if bank < 0 or any(value < 0 for value in percents) or sum(percents) > 100:
        raise ValueError("Invalid tournament bank or prize percentages")

    amounts: dict[str, int] = {}
    cursor = 0
    while cursor < len(place_names):
        group = tuple(place_names[cursor])
        if not group:
            cursor += 1
            continue
        occupied = [cursor]
        next_position = cursor + 1
        while next_position < len(place_names) and tuple(place_names[next_position]) == group:
            occupied.append(next_position)
            next_position += 1
        pool = sum((bank * percents[position]) // 100 for position in occupied)
        individual = pool // len(group)
        for name in group:
            amounts[name] = amounts.get(name, 0) + individual
        cursor = next_position

    total = sum(amounts.values())
    if total > bank:
        raise ValueError("Tournament payout exceeds bank")
    return amounts, total, bank - total


def calculate_payouts(
    *, bank_kopecks: int, scores: dict[str, int], prize_percents: tuple[int, int, int]
) -> TournamentPayoutResult:
    bank = int(bank_kopecks)
    percents = tuple(int(value) for value in prize_percents)
    if bank < 0 or any(value < 0 for value in percents) or sum(percents) > 100:
        raise ValueError("Invalid tournament bank or prize percentages")
    ranked = sorted(scores.items(), key=lambda item: (-int(item[1]), item[0]))
    place_names: list[tuple[str, ...]] = [(), (), ()]
    cursor = 0
    while cursor < len(ranked) and cursor < 3:
        score = int(ranked[cursor][1])
        group = [name for name, value in ranked if int(value) == score]
        start = cursor
        occupied = tuple(position for position in range(start, min(start + len(group), 3)))
        if not occupied:
            break
        for position in occupied:
            place_names[position] = tuple(group)
        cursor += len(group)
    normalized_places = tuple(place_names)
    amounts, total, remainder = calculate_payout_amounts(
        bank_kopecks=bank,
        place_names=normalized_places,
        prize_percents=percents,
    )
    positions: dict[str, int] = {}
    for position, group in enumerate(normalized_places, start=1):
        for name in group:
            positions.setdefault(name, position)
    payouts = [
        TournamentPayout(name, int(score), positions[name], amounts[name])
        for name, score in ranked
        if name in amounts
    ]
    return TournamentPayoutResult(tuple(payouts), normalized_places, total, remainder)


class CloseBettingTournamentUseCase:
    def __init__(
        self,
        *,
        session,
        user_repository,
        tournament_repository,
        tournament_param_repository,
        bet_repository,
    ):
        self.session = session
        self.users = user_repository
        self.tournaments = tournament_repository
        self.params = tournament_param_repository
        self.bets = bet_repository

    async def list_eligible(self, *, actor_user_id: int, today: date):
        await self._require_admin(actor_user_id)
        return await self.tournaments.list_eligible_for_finalization(today=today)

    async def preview(self, *, actor_user_id: int, tournament_id: int, today: date):
        await self._require_admin(actor_user_id)
        tournament = await self._eligible(tournament_id=tournament_id, today=today)
        return tournament, await self._calculate(tournament)

    async def confirm(self, *, actor_user_id: int, tournament_id: int, today: date):
        await self._require_admin(actor_user_id)
        tournament = await self._eligible(tournament_id=tournament_id, today=today)
        result = await self._calculate(tournament)
        names = [", ".join(group) if group else "" for group in result.place_names]
        applied = await self.tournaments.finalize_if_unpaid(
            tournament_id=tournament_id,
            first_place_name=names[0],
            second_place_name=names[1],
            third_place_name=names[2],
        )
        if not applied:
            await self.session.rollback()
            raise ValueError("Tournament already finalized")
        await self.session.commit()
        return tournament, result

    async def _require_admin(self, actor_user_id: int):
        actor = await self.users.get_by_row_id(actor_user_id)
        if actor is None or not actor.is_approved or not actor.is_admin:
            raise PermissionError("Admin access required")

    async def _eligible(self, *, tournament_id: int, today: date):
        tournament = await self.tournaments.get_by_id(row_id=tournament_id)
        if (
            tournament is None
            or tournament.end_date is None
            or tournament.end_date >= today
            or tournament.is_paid
        ):
            raise ValueError("Tournament is not eligible")
        return tournament

    async def _calculate(self, tournament):
        params = await self.params.get_for_tournament(
            tournament_type=str(tournament.tournament_type), bet_param_id=int(tournament.params_id)
        )
        if params is None:
            raise ValueError("Tournament prize parameters are missing")
        bets = await self.bets.list_for_period(
            start_date=tournament.start_date, end_date=tournament.end_date
        )
        scores: dict[str, int] = {}
        for bet in bets:
            scores[bet.better_name] = scores.get(bet.better_name, 0) + int(bet.score or 0)
        return calculate_payouts(
            bank_kopecks=int(tournament.current_bank_kopecks or 0),
            scores=scores,
            prize_percents=(
                int(params.percent_to_first),
                int(params.percent_to_second),
                int(params.percent_to_third),
            ),
        )
