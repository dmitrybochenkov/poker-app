from app.db.models.bet import Bet
from app.db.models.stat_indicator import StatIndicator
from app.db.repositories.bet_repository import BetRepository


class StatUseCases:
  def __init__(self, *, bet_repository: BetRepository) -> None:
    self.bet_repository = bet_repository

  async def get_poker_stat(self, *, filters: dict):
    raise NotImplementedError

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

    header = ["👨"] + selected_pics
    lines = [" | ".join(header), " | ".join(["---"] * len(header))]
    for row in rows:
      values = [str(row.get(column, "")) for column in header]
      lines.append(" | ".join(values))
    return "\n".join(lines)

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
