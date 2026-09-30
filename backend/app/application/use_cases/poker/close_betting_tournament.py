from dataclasses import dataclass
from datetime import date
from typing import Hashable, TypeVar


ParticipantKey = TypeVar("ParticipantKey", bound=Hashable)


@dataclass(frozen=True)
class TournamentPayout:
    user_id: int
    player_name: str
    score: int
    position: int
    amount_kopecks: int


@dataclass(frozen=True)
class TournamentPayoutResult:
    payouts: tuple[TournamentPayout, ...]
    place_user_ids: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]
    place_names: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]
    total_payout_kopecks: int
    remainder_kopecks: int


def calculate_payout_amounts(
    *,
    bank_kopecks: int,
    place_members: tuple[
        tuple[ParticipantKey, ...],
        tuple[ParticipantKey, ...],
        tuple[ParticipantKey, ...],
    ],
    prize_percents: tuple[int, int, int],
) -> tuple[dict[ParticipantKey, int], int, int]:
    bank = int(bank_kopecks)
    percents = tuple(int(value) for value in prize_percents)
    if bank < 0 or any(value < 0 for value in percents) or sum(percents) > 100:
        raise ValueError("Invalid tournament bank or prize percentages")

    amounts: dict[ParticipantKey, int] = {}
    cursor = 0
    while cursor < len(place_members):
        group = tuple(place_members[cursor])
        if not group:
            cursor += 1
            continue
        occupied = [cursor]
        next_position = cursor + 1
        while next_position < len(place_members) and tuple(place_members[next_position]) == group:
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
    *,
    bank_kopecks: int,
    scores_by_user_id: dict[int, int],
    names_by_user_id: dict[int, str],
    prize_percents: tuple[int, int, int],
) -> TournamentPayoutResult:
    bank = int(bank_kopecks)
    percents = tuple(int(value) for value in prize_percents)
    if bank < 0 or any(value < 0 for value in percents) or sum(percents) > 100:
        raise ValueError("Invalid tournament bank or prize percentages")
    ranked = sorted(
        scores_by_user_id.items(),
        key=lambda item: (-int(item[1]), names_by_user_id[int(item[0])], int(item[0])),
    )
    place_user_ids: list[tuple[int, ...]] = [(), (), ()]
    cursor = 0
    while cursor < len(ranked) and cursor < 3:
        score = int(ranked[cursor][1])
        group = [int(user_id) for user_id, value in ranked if int(value) == score]
        start = cursor
        occupied = tuple(position for position in range(start, min(start + len(group), 3)))
        if not occupied:
            break
        for position in occupied:
            place_user_ids[position] = tuple(group)
        cursor += len(group)
    normalized_places = tuple(place_user_ids)
    amounts, total, remainder = calculate_payout_amounts(
        bank_kopecks=bank,
        place_members=normalized_places,
        prize_percents=percents,
    )
    positions: dict[int, int] = {}
    for position, group in enumerate(normalized_places, start=1):
        for user_id in group:
            positions.setdefault(user_id, position)
    payouts = [
        TournamentPayout(
            int(user_id),
            names_by_user_id[int(user_id)],
            int(score),
            positions[int(user_id)],
            amounts[int(user_id)],
        )
        for user_id, score in ranked
        if int(user_id) in amounts
    ]
    place_names = tuple(
        tuple(names_by_user_id[user_id] for user_id in group)
        for group in normalized_places
    )
    return TournamentPayoutResult(
        tuple(payouts), normalized_places, place_names, total, remainder
    )


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
        params = await self.params.get_by_id(row_id=int(tournament.params_id))
        if params is None:
            raise ValueError("Tournament prize parameters are missing")
        bets = await self.bets.list_for_period(
            start_date=tournament.start_date, end_date=tournament.end_date
        )
        scores_by_user_id: dict[int, int] = {}
        names_by_user_id: dict[int, str] = {}
        snapshot_order_by_user_id: dict[int, tuple] = {}
        for bet in bets:
            user_id = int(bet.better_id)
            scores_by_user_id[user_id] = scores_by_user_id.get(user_id, 0) + int(
                bet.score or 0
            )
            snapshot_order = (bet.date, int(bet.row_id))
            if snapshot_order > snapshot_order_by_user_id.get(user_id, (date.min, 0)):
                snapshot_order_by_user_id[user_id] = snapshot_order
                names_by_user_id[user_id] = str(bet.better_name)
        return calculate_payouts(
            bank_kopecks=int(tournament.current_bank_kopecks or 0),
            scores_by_user_id=scores_by_user_id,
            names_by_user_id=names_by_user_id,
            prize_percents=(
                int(params.percent_to_first),
                int(params.percent_to_second),
                int(params.percent_to_third),
            ),
        )
