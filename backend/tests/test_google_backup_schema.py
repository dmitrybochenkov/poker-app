from app.db.models.bet import Bet
from app.services.google_backup import _column_bindings


def test_bet_backup_keeps_legacy_sheet_columns_stable():
  columns = [column for column, _ in _column_bindings(Bet)]

  assert "winner_id" not in columns
  assert "loser_id" not in columns
  assert columns == [
    "row_id",
    "poker_id",
    "params_id",
    "date",
    "better_name",
    "better_id",
    "size_kopecks",
    "winner",
    "looser",
    "score",
    "is_paid",
    "created_at",
    "updated_at",
  ]
