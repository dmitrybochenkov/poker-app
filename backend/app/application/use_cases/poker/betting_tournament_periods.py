from dataclasses import dataclass
from datetime import date

_SHORT_RUSSIAN_MONTHS = (
    "",
    "янв",
    "фев",
    "мар",
    "апр",
    "май",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
)
_TYPE_CODES = {"regular": "r", "year": "y"}
_TYPES_BY_CODE = {value: key for key, value in _TYPE_CODES.items()}


@dataclass(frozen=True, slots=True)
class BettingTournamentPeriod:
    tournament_type: str
    start_date: date
    end_date: date

    @property
    def selection_id(self) -> str:
        type_code = _TYPE_CODES[self.tournament_type]
        return f"{type_code}:{self.start_date:%Y%m%d}:{self.end_date:%Y%m%d}"

    @property
    def label(self) -> str:
        if self.tournament_type == "year":
            return f"Годовой {self.end_date.year}"
        return (
            f"Регулярный {_SHORT_RUSSIAN_MONTHS[self.start_date.month]} – "
            f"{_SHORT_RUSSIAN_MONTHS[self.end_date.month]}"
        )

    @classmethod
    def from_selection_id(cls, value: str) -> "BettingTournamentPeriod":
        type_code, start_raw, end_raw = value.split(":")
        return cls(
            tournament_type=_TYPES_BY_CODE[type_code],
            start_date=date.fromisoformat(
                f"{start_raw[:4]}-{start_raw[4:6]}-{start_raw[6:]}"
            ),
            end_date=date.fromisoformat(f"{end_raw[:4]}-{end_raw[4:6]}-{end_raw[6:]}")
        )


def list_betting_tournament_periods(tournaments: list) -> list[BettingTournamentPeriod]:
    periods = {
        BettingTournamentPeriod(
            tournament_type=str(item.tournament_type),
            start_date=item.start_date,
            end_date=item.end_date,
        )
        for item in tournaments
        if item.tournament_type in _TYPE_CODES
        and item.start_date is not None
        and item.end_date is not None
    }
    return sorted(
        periods,
        key=lambda item: (
            item.start_date,
            item.tournament_type == "regular",
            item.end_date,
        ),
        reverse=True,
    )


def default_betting_tournament_period_ids(
    periods: list[BettingTournamentPeriod], *, today: date | None = None
) -> set[str]:
    if not periods:
        return set()
    current_date = today or date.today()
    active = {
        period.selection_id
        for period in periods
        if period.start_date <= current_date <= period.end_date
    }
    return active or {periods[0].selection_id}


def parse_betting_tournament_period_ids(
    values: list[str] | set[str],
) -> list[BettingTournamentPeriod]:
    periods: list[BettingTournamentPeriod] = []
    for value in values:
        try:
            periods.append(BettingTournamentPeriod.from_selection_id(value))
        except (KeyError, TypeError, ValueError):
            continue
    return periods
