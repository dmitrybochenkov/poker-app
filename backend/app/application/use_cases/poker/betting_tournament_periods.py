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
            f"{_SHORT_RUSSIAN_MONTHS[self.end_date.month]} {self.end_date.year}"
        )

    def is_open(self, *, today: date | None = None) -> bool:
        current_date = today or date.today()
        return self.start_date <= current_date <= self.end_date

    def display_label(self, *, today: date | None = None) -> str:
        if self.tournament_type == "year":
            prefix = "🎄💰" if self.is_open(today=today) else "🏁🎄💰"
        else:
            prefix = "💰" if self.is_open(today=today) else "🏁💰"
        return f"{prefix} {self.label}"

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
            item.end_date,
            item.start_date,
            item.tournament_type == "year",
        ),
        reverse=True,
    )


def toggle_betting_tournament_selection(
    periods: list[BettingTournamentPeriod],
    selected_period_ids: set[str] | list[str],
    toggled_period_id: str,
    *,
    today: date | None = None,
) -> set[str]:
    periods_by_id = {period.selection_id: period for period in periods}
    toggled = periods_by_id.get(toggled_period_id)
    if toggled is None:
        return set(selected_period_ids) & periods_by_id.keys()
    if toggled.is_open(today=today):
        return {toggled_period_id}
    selected_closed = {
        period_id
        for period_id in selected_period_ids
        if period_id in periods_by_id
        and not periods_by_id[period_id].is_open(today=today)
    }
    if toggled_period_id in selected_closed:
        selected_closed.remove(toggled_period_id)
    else:
        selected_closed.add(toggled_period_id)
    return selected_closed


def betting_tournament_statistics_mode(
    periods: list[BettingTournamentPeriod],
    selected_period_ids: set[str] | list[str],
    *,
    today: date | None = None,
) -> str | None:
    periods_by_id = {period.selection_id: period for period in periods}
    selected = [periods_by_id[value] for value in selected_period_ids if value in periods_by_id]
    if not selected:
        return None
    open_periods = [period for period in selected if period.is_open(today=today)]
    if len(open_periods) == 1 and len(selected) == 1:
        return open_periods[0].tournament_type
    if not open_periods:
        return "all"
    return None


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
