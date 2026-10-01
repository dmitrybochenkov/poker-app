from datetime import date

from app.application.use_cases.poker.betting_tournament_periods import BettingTournamentPeriod
from app.application.use_cases.poker.close_betting_tournament import CloseBettingTournamentUseCase
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.bet_tournament_result_repository import BetTournamentResultRepository
from app.db.repositories.bet_tournament_role_result_repository import BetTournamentRoleResultRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.user_repository import UserRepository


def build_close_tournament_use_case(session):
    return CloseBettingTournamentUseCase(
        session=session,
        user_repository=UserRepository(session),
        tournament_repository=BetTournamentRepository(session),
        tournament_param_repository=BetTournamentParamRepository(session),
        bet_repository=BetRepository(session),
        tournament_result_repository=BetTournamentResultRepository(session),
        tournament_role_result_repository=BetTournamentRoleResultRepository(session),
        poker_data_repository=PokerDataRepository(session),
    )


def format_kopecks(value: int) -> str:
    rubles, kopecks = divmod(int(value), 100)
    base = f"{rubles:,}".replace(",", " ")
    return base if not kopecks else f"{base},{kopecks:02d}"


def format_preview(tournament, result) -> str:
    title = BettingTournamentPeriod(
        str(tournament.tournament_type), tournament.start_date, tournament.end_date
    ).label
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [f"🏁 {title}", "", f"Банк: {format_kopecks(tournament.current_bank_kopecks)} ₽", ""]
    lines.extend(
        f"{medals[item.position]} {item.player_name} — {format_kopecks(item.amount_kopecks)} ₽"
        for item in result.payouts
    )
    lines.extend(
        [
            "",
            f"К выплате: {format_kopecks(result.total_payout_kopecks)} ₽",
            f"Остаток: {format_kopecks(result.remainder_kopecks)} ₽",
        ]
    )
    return "\n".join(lines)


TODAY = date.today
