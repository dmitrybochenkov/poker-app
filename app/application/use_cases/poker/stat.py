from app.db.models.bet import Bet
from app.db.models.poker_data import PokerData
from app.db.models.stat_indicator import StatIndicator
from app.db.repositories.achievement_repository import AchievementRepository
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.poker_data_repository import PokerDataRepository


class StatUseCases:
  def __init__(
    self,
    *,
    bet_repository: BetRepository,
    poker_data_repository: PokerDataRepository | None = None,
    achievement_repository: AchievementRepository | None = None,
  ) -> None:
    self.bet_repository = bet_repository
    self.poker_data_repository = poker_data_repository
    self.achievement_repository = achievement_repository

  async def get_poker_stat(self, *, indicators: list[StatIndicator]) -> str:
    if self.poker_data_repository is None:
      return "Нет данных по покеру."

    rows = await self.poker_data_repository.list_all()
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

    sort_pic = selected_pics[0]
    result_rows.sort(key=lambda item: item.get(sort_pic, 0), reverse=True)
    result_rows = await self._apply_achievements(
      rows=result_rows,
      indicator_id_to_pic={int(ind.row_id): ind.pic for ind in selected},
      achievement_type="poker",
    )
    return self._to_markdown_table(rows=result_rows, headers=["👨"] + selected_pics)

  async def get_betting_stat(self, *, indicators: list[StatIndicator]) -> str:
    bets = await self.bet_repository.list_for_latest_poker()
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
        row[pic] = self._calc_metric(pic=pic, user_bets=user_bets)
      rows.append(row)

    sort_pic = selected_pics[0]
    rows.sort(key=lambda item: item.get(sort_pic, 0), reverse=True)
    rows = await self._apply_achievements(
      rows=rows,
      indicator_id_to_pic={int(ind.row_id): ind.pic for ind in selected},
      achievement_type="betting",
    )

    return self._to_markdown_table(rows=rows, headers=["👨"] + selected_pics)

  @staticmethod
  def _to_markdown_table(*, rows: list[dict[str, str | int | float]], headers: list[str]) -> str:
    has_ach = any(str(row.get("🌟", "")).strip() for row in rows)
    if has_ach and "🌟" not in headers:
      headers = headers + ["🌟"]
    lines = [" | ".join(headers), " | ".join(["---"] * len(headers))]
    for row in rows:
      values = [str(row.get(column, "")) for column in headers]
      lines.append(" | ".join(values))
    return "\n".join(lines)

  async def _apply_achievements(
    self,
    *,
    rows: list[dict[str, str | int | float]],
    indicator_id_to_pic: dict[int, str],
    achievement_type: str,
  ) -> list[dict[str, str | int | float]]:
    if self.achievement_repository is None or not rows:
      return rows
    achievements = await self.achievement_repository.list_by_type(achievement_type=achievement_type)
    if not achievements:
      return rows

    for row in rows:
      row.setdefault("🌟", "")

    applicable = [item for item in achievements if int(item.stat_id) in set(indicator_id_to_pic.keys())]
    for ach in applicable:
      if ach.sort == "none":
        continue
      metric_pic = indicator_id_to_pic.get(int(ach.stat_id))
      if not metric_pic:
        continue
      ranked = sorted(
        rows,
        key=lambda data: float(data.get(metric_pic, 0)),
        reverse=(ach.sort == "desc"),
      )
      if ranked:
        ranked[0]["🌟"] = f"{ranked[0].get('🌟', '')}{ach.pic}"
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

  @staticmethod
  def _calc_metric(*, pic: str, user_bets: list[Bet]) -> int | float:
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
    if pic == "🚨":
      return len([bet for bet in user_bets if not bool(bet.is_paid)])
    if pic == "🍆✊💦":
      return len([bet for bet in user_bets if bet.winner_name == bet.better_name])
    return 0
