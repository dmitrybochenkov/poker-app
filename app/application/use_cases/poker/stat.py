import re

from app.db.models.bet import Bet
from app.db.models.poker_data import PokerData
from app.db.models.stat_indicator import StatIndicator
from app.db.repositories.achievement_repository import AchievementRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository


class StatUseCases:
  def __init__(
    self,
    *,
    bet_repository: BetRepository,
    poker_data_repository: PokerDataRepository | None = None,
    achievement_repository: AchievementRepository | None = None,
    bet_tournament_repository: BetTournamentRepository | None = None,
    bet_tournament_param_repository: BetTournamentParamRepository | None = None,
    poker_repository: PokerRepository | None = None,
  ) -> None:
    self.bet_repository = bet_repository
    self.poker_data_repository = poker_data_repository
    self.achievement_repository = achievement_repository
    self.bet_tournament_repository = bet_tournament_repository
    self.bet_tournament_param_repository = bet_tournament_param_repository
    self.poker_repository = poker_repository

  async def get_poker_stat(
    self,
    *,
    indicators: list[StatIndicator],
    year: int | None = None,
    years: list[int] | None = None,
    sort_pic: str | None = None,
  ) -> str:
    if self.poker_data_repository is None:
      return "Нет данных по покеру."

    all_rows = await self.poker_data_repository.list_all()
    rows = list(all_rows)
    year_set = {int(item) for item in years} if years else set()
    if year_set:
      rows = [item for item in rows if item.date is not None and int(item.date.year) in year_set]
    elif year is not None:
      rows = [item for item in rows if item.date is not None and int(item.date.year) == int(year)]
    if not rows:
      return "Нет данных по покеру."

    total_games = len({item.date for item in rows})
    grouped: dict[str, list[PokerData]] = {}
    for item in rows:
      grouped.setdefault(item.player_name, []).append(item)

    users = sorted(
      name for name, user_rows in grouped.items()
      if len({entry.date for entry in user_rows}) > 0.3 * total_games
    )
    if not users:
      return "Нет данных по покеру."

    by_date: dict = {}
    for item in rows:
      by_date.setdefault(item.date, []).append(item)
    winners_by_date: dict = {}
    losers_by_date: dict = {}
    for date_value, date_rows in by_date.items():
      max_money = max(int(entry.money_kopecks or 0) for entry in date_rows)
      min_money = min(int(entry.money_kopecks or 0) for entry in date_rows)
      winners_by_date[date_value] = {entry.player_name for entry in date_rows if int(entry.money_kopecks or 0) == max_money}
      losers_by_date[date_value] = {entry.player_name for entry in date_rows if int(entry.money_kopecks or 0) == min_money}

    all_time_winners_by_date: dict = {}
    by_date_all_time: dict = {}
    for item in all_rows:
      by_date_all_time.setdefault(item.date, []).append(item)
    for date_value, date_rows in by_date_all_time.items():
      max_money = max(int(entry.money_kopecks or 0) for entry in date_rows)
      all_time_winners_by_date[date_value] = {entry.player_name for entry in date_rows if int(entry.money_kopecks or 0) == max_money}
    all_time_win_streaks = {
      user: self._max_win_streak(user=user, winners_by_date=all_time_winners_by_date)
      for user in users
    }

    selected = indicators or []
    selected_pics = [indicator.pic for indicator in selected]
    if not selected_pics:
      selected_pics = ["💲"]

    result_rows: list[dict[str, str | int | float]] = []
    for user in users:
      user_rows = grouped[user]
      metric_row: dict[str, str | int | float] = {"👨": user}
      for pic in selected_pics:
        metric_row[pic] = self._calc_poker_metric(
          pic=pic,
          user=user,
          user_rows=user_rows,
          winners_by_date=winners_by_date,
          losers_by_date=losers_by_date,
        )
      result_rows.append(metric_row)

    sort_metric = sort_pic if sort_pic in selected_pics else selected_pics[0]
    result_rows.sort(key=lambda item: item.get(sort_metric, 0), reverse=True)
    result_rows = await self._apply_achievements(
      rows=result_rows,
      indicator_id_to_pic={int(ind.row_id): ind.pic for ind in selected},
      achievement_type="poker",
      all_time_win_streaks=all_time_win_streaks,
    )
    return self._to_text_table(rows=result_rows, headers=["👨"] + selected_pics)

  async def get_betting_stat(
    self,
    *,
    indicators: list[StatIndicator],
    mode: str = "all",
    year: int | None = None,
    years: list[int] | None = None,
    sort_pic: str | None = None,
  ) -> str:
    if self.bet_tournament_param_repository is not None:
      params = await self.bet_tournament_param_repository.list_all()
      self._tournament_percents_cache = {
        str(item.tournament_type): (
          int(item.percent_to_first),
          int(item.percent_to_second),
          int(item.percent_to_third),
        )
        for item in params
      }
    bets = await self.bet_repository.list_all()
    year_set = {int(item) for item in years} if years else set()
    if year_set:
      bets = [bet for bet in bets if bet.date is not None and int(bet.date.year) in year_set]
    elif year is not None:
      bets = [bet for bet in bets if bet.date is not None and int(bet.date.year) == int(year)]
    tournaments = await self._load_finished_tournaments()
    pokers_by_id = await self._load_pokers_by_id()

    if mode == "all":
      bets = [bet for bet in bets if self._bet_in_any_tournament(bet=bet, tournaments=tournaments)]
    elif mode in {"regular", "year"}:
      active_tournament = self._find_current_tournament_by_type(tournaments=tournaments, tournament_type=mode)
      if active_tournament is None:
        return "Нет данных по ставкам."
      bets = [bet for bet in bets if self._bet_in_tournament(bet=bet, tournament=active_tournament)]
    else:
      bets = [bet for bet in bets if self._bet_in_any_tournament(bet=bet, tournaments=tournaments)]

    if not bets:
      return "Нет данных по ставкам."

    users = sorted({bet.better_name for bet in bets})
    if not users:
      return "Нет данных по ставкам."

    selected = indicators or []
    selected_pics = [indicator.pic for indicator in selected]
    if not selected_pics:
      selected_pics = ["💯"]

    rows: list[dict[str, str | int | float]] = []
    for user in users:
      user_bets = [bet for bet in bets if bet.better_name == user]
      row: dict[str, str | int | float] = {"👨": user}
      for pic in selected_pics:
        row[pic] = self._calc_metric(
          pic=pic,
          user=user,
          user_bets=user_bets,
          all_bets=bets,
          pokers_by_id=pokers_by_id,
          tournaments=tournaments,
        )
      if mode in {"regular", "year"}:
        # Current tournaments only: mark users with no unpaid bets.
        row["🌟"] = "👮" if len([bet for bet in user_bets if not bool(bet.is_paid)]) == 0 else ""
      rows.append(row)

    sort_metric = sort_pic if sort_pic in selected_pics else selected_pics[0]
    rows.sort(key=lambda item: item.get(sort_metric, 0), reverse=True)
    if mode == "all":
      rows = await self._apply_achievements(
        rows=rows,
        indicator_id_to_pic={int(ind.row_id): ind.pic for ind in selected},
        achievement_type="betting",
      )

    report = self._to_text_table(rows=rows, headers=["👨"] + selected_pics)
    if mode in {"regular", "year"}:
      current_tournament = self._find_current_tournament_by_type(tournaments=tournaments, tournament_type=mode)
      if current_tournament is not None:
        report = f"{report}\n\n{self._format_current_tournament_money_block(tournament=current_tournament)}"
    return report

  @staticmethod
  def _to_text_table(*, rows: list[dict[str, str | int | float]], headers: list[str]) -> str:
    has_ach = any(str(row.get("🌟", "")).strip() for row in rows)
    if has_ach and "🌟" not in headers:
      headers = headers + ["🌟"]
    widths: dict[str, int] = {column: len(column) for column in headers}
    for row in rows:
      for column in headers:
        widths[column] = max(widths[column], len(str(row.get(column, ""))))

    def fmt_line(values: list[str]) -> str:
      return " | ".join(value.ljust(widths[headers[idx]]) for idx, value in enumerate(values))

    lines = [
      fmt_line(headers),
      "-+-".join("-" * widths[column] for column in headers),
    ]
    for row in rows:
      values = [str(row.get(column, "")) for column in headers]
      lines.append(fmt_line(values))
    return "\n".join(lines)

  async def _apply_achievements(
    self,
    *,
    rows: list[dict[str, str | int | float]],
    indicator_id_to_pic: dict[int, str],
    achievement_type: str,
    all_time_win_streaks: dict[str, int] | None = None,
  ) -> list[dict[str, str | int | float]]:
    if self.achievement_repository is None or not rows:
      return rows
    achievements = await self.achievement_repository.list_by_type(achievement_type=achievement_type)
    if not achievements:
      return rows

    for row in rows:
      row.setdefault("🌟", "")

    selected_indicator_ids = set(indicator_id_to_pic.keys())
    applicable = []
    for item in achievements:
      if int(item.stat_id) in selected_indicator_ids:
        applicable.append(item)
        continue
      # Permanent poker streak achievement (🎖️) must be checked for any poker stat selection.
      if achievement_type == "poker" and str(item.pic) == "🎖️":
        applicable.append(item)
    for ach in applicable:
      metric_pic = indicator_id_to_pic.get(int(ach.stat_id))
      if not metric_pic and not (achievement_type == "poker" and str(ach.pic) == "🎖️"):
        continue
      if ach.sort == "none":
        if all_time_win_streaks and (metric_pic == "🛡️💍" or str(ach.pic) in {"💪", "🦾", "🎖️"}):
          threshold = self._resolve_streak_threshold(achievement_pic=str(ach.pic), achievement_description=str(ach.description or ""))
          if threshold is None:
            continue
          for row in rows:
            user = str(row.get("👨", ""))
            if all_time_win_streaks.get(user, 0) >= threshold:
              row["🌟"] = f"{row.get('🌟', '')}{ach.pic}"
        continue
      ranked = sorted(
        rows,
        key=lambda data: float(data.get(metric_pic, 0)),
        reverse=(ach.sort == "desc"),
      )
      if ranked:
        ranked[0]["🌟"] = f"{ranked[0].get('🌟', '')}{ach.pic}"

    # Streak precedence: if user has 🦾, do not show weaker 💪.
    for row in rows:
      stars = str(row.get("🌟", ""))
      if "🦾" in stars and "💪" in stars:
        row["🌟"] = stars.replace("💪", "")
    return rows

  @staticmethod
  def _count_win_pairs(*, user: str, winners_by_date: dict) -> int:
    dates = sorted(winners_by_date.keys())
    if len(dates) < 2:
      return 0
    count = 0
    for index in range(1, len(dates)):
      if user in winners_by_date[dates[index]] and user in winners_by_date[dates[index - 1]]:
        count += 1
    return count

  @staticmethod
  def _max_win_streak(*, user: str, winners_by_date: dict) -> int:
    dates = sorted(winners_by_date.keys())
    best = 0
    current = 0
    for date_value in dates:
      if user in winners_by_date.get(date_value, set()):
        current += 1
        if current > best:
          best = current
      else:
        current = 0
    return best

  @staticmethod
  def _resolve_streak_threshold(*, achievement_pic: str, achievement_description: str) -> int | None:
    pic_to_threshold = {
      "💪": 2,
      "🦾": 3,
      "🎖️": 4,
    }
    if achievement_pic in pic_to_threshold:
      return pic_to_threshold[achievement_pic]
    match = re.search(r"(\d+)", achievement_description)
    if match is None:
      return None
    return int(match.group(1))

  def _calc_poker_metric(
    self,
    *,
    pic: str,
    user: str,
    user_rows: list[PokerData],
    winners_by_date: dict,
    losers_by_date: dict,
  ) -> int | float:
    if pic == "💲":
      return int(sum(int(item.money_kopecks or 0) for item in user_rows) // 100)
    if pic == "🎲":
      return len(user_rows)
    if pic == "🏦":
      return int(sum(int(item.buyins or 0) for item in user_rows))
    if pic == "❌":
      return len({item.date for item in user_rows if user in losers_by_date.get(item.date, set())})
    if pic == "💍":
      return len({item.date for item in user_rows if user in winners_by_date.get(item.date, set())})
    if pic == "🔝🏦":
      return max((int(item.buyins or 0) for item in user_rows), default=0)
    if pic == "🔝💲⬆️":
      return max((int(item.money_kopecks or 0) // 100 for item in user_rows if int(item.money_kopecks or 0) > 0), default=0)
    if pic == "🔝💲⬇️":
      return min((int(item.money_kopecks or 0) // 100 for item in user_rows if int(item.money_kopecks or 0) < 0), default=0)
    if pic == "💲/🎲":
      games = len(user_rows)
      if games == 0:
        return 0.0
      return round((sum(int(item.money_kopecks or 0) for item in user_rows) / 100) / games, 2)
    if pic == "💲/🏦":
      buyins = sum(int(item.buyins or 0) for item in user_rows)
      if buyins == 0:
        return 0.0
      return round((sum(int(item.money_kopecks or 0) for item in user_rows) / 100) / buyins, 2)
    if pic == "🏦/🎲":
      games = len(user_rows)
      if games == 0:
        return 0.0
      return round(sum(int(item.buyins or 0) for item in user_rows) / games, 2)
    if pic == "🛡️💍":
      return self._count_win_pairs(user=user, winners_by_date=winners_by_date)
    return 0

  async def _load_finished_tournaments(self):
    if self.bet_tournament_repository is None:
      return []
    items = await self.bet_tournament_repository.list_active()
    return [item for item in items if item.start_date is not None and item.end_date is not None]

  async def _load_pokers_by_id(self) -> dict[int, tuple[set[str], set[str]]]:
    if self.poker_repository is None:
      return {}
    data: dict[int, tuple[set[str], set[str]]] = {}
    pokers = await self.poker_repository.list_all()
    for poker in pokers:
      winners = {item.strip() for item in str(poker.winners or "").split(",") if item.strip()}
      losers = {item.strip() for item in str(poker.loosers or "").split(",") if item.strip()}
      data[int(poker.row_id)] = (winners, losers)
    return data

  @staticmethod
  def _bet_in_tournament(*, bet: Bet, tournament) -> bool:
    return bool(
      bet.date is not None
      and tournament.start_date is not None
      and tournament.end_date is not None
      and tournament.start_date <= bet.date <= tournament.end_date
    )

  def _bet_in_any_tournament(self, *, bet: Bet, tournaments: list) -> bool:
    return any(self._bet_in_tournament(bet=bet, tournament=tournament) for tournament in tournaments)

  @staticmethod
  def _find_current_tournament_by_type(*, tournaments: list, tournament_type: str):
    filtered = [item for item in tournaments if item.tournament_type == tournament_type]
    if not filtered:
      return None
    return sorted(filtered, key=lambda item: item.row_id, reverse=True)[0]

  def _calc_metric(
    self,
    *,
    pic: str,
    user: str,
    user_bets: list[Bet],
    all_bets: list[Bet],
    pokers_by_id: dict[int, tuple[set[str], set[str]]],
    tournaments: list,
  ) -> int | float:
    if pic == "💯":
      return int(sum(int(bet.score or 0) for bet in user_bets))
    if pic == "🐔🐤":
      return len(user_bets)
    if pic == "🔮🍀":
      return len([bet for bet in user_bets if int(bet.score or 0) > 0])
    if pic == "🔮🍀%":
      if not user_bets:
        return 0.0
      wins = len([bet for bet in user_bets if int(bet.score or 0) > 0])
      return round(100 * wins / len(user_bets), 2)
    if pic == "👍":
      return len([bet for bet in user_bets if bet.winner_name == bet.better_name])
    if pic == "👎":
      return len([bet for bet in user_bets if bet.loser_name == bet.better_name])
    if pic == "-💲":
      return int(sum(int(bet.amount_kopecks or 0) for bet in user_bets) // 100)
    if pic == "+💲":
      return self._calc_money_prizes(user=user, tournaments=tournaments)
    if pic == "+💲/-💲":
      spent = int(sum(int(bet.amount_kopecks or 0) for bet in user_bets) // 100)
      if spent == 0:
        return 0.0
      won = self._calc_money_prizes(user=user, tournaments=tournaments)
      return round(won / spent, 2)
    if pic == "👎/💍":
      return len([
        bet for bet in all_bets
        if bet.loser_name == user
        and bet.poker_id is not None
        and user in pokers_by_id.get(int(bet.poker_id), (set(), set()))[0]
      ])
    if pic == "👍/❌":
      return len([
        bet for bet in all_bets
        if bet.winner_name == user
        and bet.better_name != user
        and bet.poker_id is not None
        and user in pokers_by_id.get(int(bet.poker_id), (set(), set()))[1]
      ])
    if pic == "❌➡️💲":
      return self._calc_money_from_role(user=user, all_bets=all_bets, tournaments=tournaments, role="loser")
    if pic == "💍➡️💲":
      return self._calc_money_from_role(user=user, all_bets=all_bets, tournaments=tournaments, role="winner")
    if pic == "🏆":
      return self._count_tournament_titles(user=user, tournaments=tournaments, tournament_type="regular")
    if pic == "🎄🏆":
      return self._count_tournament_titles(user=user, tournaments=tournaments, tournament_type="year")
    if pic == "🚨":
      return len([bet for bet in user_bets if not bool(bet.is_paid)])
    if pic == "🍆✊💦":
      return len([bet for bet in user_bets if bet.winner_name == bet.better_name])
    return 0

  @staticmethod
  def _split_names(value: str | None) -> list[str]:
    if not value:
      return []
    return [item.strip() for item in value.split(",") if item.strip()]

  def _calc_money_prizes(self, *, user: str, tournaments: list) -> int:
    result = 0.0
    for tournament in tournaments:
      bank_rub = int(int(tournament.current_bank_kopecks or 0) // 100)
      if bank_rub <= 0:
        continue
      perc_first, perc_second, perc_third = self._get_tournament_percents(tournament_type=tournament.tournament_type)
      first = self._split_names(tournament.first_place_name)
      second = self._split_names(tournament.second_place_name)
      third = self._split_names(tournament.third_place_name)
      if user in first and first:
        result += (bank_rub * perc_first / 100) / len(first)
      if user in second and second:
        result += (bank_rub * perc_second / 100) / len(second)
      if user in third and third:
        result += (bank_rub * perc_third / 100) / len(third)
    return int(round(result))

  def _get_tournament_percents(self, *, tournament_type: str | None) -> tuple[int, int, int]:
    default = (50, 30, 20)
    if self.bet_tournament_param_repository is None or not tournament_type:
      return default
    # lightweight cache on instance
    cache = getattr(self, "_tournament_percents_cache", None)
    if cache is None:
      cache = {}
      setattr(self, "_tournament_percents_cache", cache)
    if tournament_type in cache:
      return cache[tournament_type]
    return default

  def _format_current_tournament_money_block(self, *, tournament) -> str:
    bank_rub = round(float(int(tournament.current_bank_kopecks or 0)) / 100, 2)
    first_p, second_p, third_p = self._get_tournament_percents(tournament_type=tournament.tournament_type)
    first_rub = round(bank_rub * first_p / 100, 2)
    second_rub = round(bank_rub * second_p / 100, 2)
    third_rub = round(bank_rub * third_p / 100, 2)
    title = "💰" if tournament.tournament_type == "regular" else "🎄💰"
    return (
      f"{title}: {bank_rub:.2f} ₽\n"
      f"🥇: {first_rub:.2f} ₽\n"
      f"🥈: {second_rub:.2f} ₽\n"
      f"🥉: {third_rub:.2f} ₽"
    )

  def _count_tournament_titles(self, *, user: str, tournaments: list, tournament_type: str) -> int:
    count = 0
    for tournament in tournaments:
      if tournament.tournament_type != tournament_type:
        continue
      if user in self._split_names(tournament.first_place_name):
        count += 1
    return count

  def _calc_money_from_role(self, *, user: str, all_bets: list[Bet], tournaments: list, role: str) -> float:
    total = 0.0
    for tournament in tournaments:
      relevant_bets = [bet for bet in all_bets if self._bet_in_tournament(bet=bet, tournament=tournament)]
      if not relevant_bets:
        continue
      by_better: dict[str, list[Bet]] = {}
      for bet in relevant_bets:
        by_better.setdefault(bet.better_name, []).append(bet)
      for better_name, better_bets in by_better.items():
        better_prize = float(self._calc_money_prizes(user=better_name, tournaments=[tournament]))
        better_score = float(sum(int(item.score or 0) for item in better_bets))
        if better_prize <= 0 or better_score <= 0:
          continue
        rel_score = 0.0
        for bet in better_bets:
          target = bet.loser_name if role == "loser" else bet.winner_name
          if target != user:
            continue
          if int(bet.score or 0) <= 0:
            continue
          rel_score += float(int(bet.score or 0))
        if rel_score > 0:
          total += better_prize * (rel_score / better_score)
    return round(total, 1)
