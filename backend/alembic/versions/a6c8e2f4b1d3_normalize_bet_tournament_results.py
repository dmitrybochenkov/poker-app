"""normalize canonical betting tournament results

Revision ID: a6c8e2f4b1d3
Revises: d4f6a8c1e3b5
Create Date: 2026-09-30 22:30:00.000000
"""

from collections import Counter, defaultdict
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a6c8e2f4b1d3"
down_revision: str | Sequence[str] | None = "d4f6a8c1e3b5"
branch_labels = None
depends_on = None
SQLITE_INTEGER_MIN = -(2**63)
SQLITE_INTEGER_MAX = 2**63 - 1


def _fail(tournament_id: int, message: str) -> None:
  raise RuntimeError(f"Cannot normalize tournament {tournament_id}: {message}")


def _split_legacy(value: str | None) -> tuple[str, ...]:
  if not value:
    return ()
  return tuple(part.strip() for part in value.split(",") if part.strip())


def _sqlite_integer(tournament_id: int, label: str, value: int) -> int:
  result = int(value)
  if not SQLITE_INTEGER_MIN <= result <= SQLITE_INTEGER_MAX:
    _fail(tournament_id, f"{label} exceeds SQLite INTEGER range")
  return result


def _reconstruct(bind, tournament) -> tuple[list[dict], list[dict], int]:
  tournament_id = int(tournament.row_id)
  if tournament.start_date is None or tournament.end_date is None:
    _fail(tournament_id, "start_date and end_date are required")
  if tournament.start_date > tournament.end_date:
    _fail(tournament_id, "invalid date interval")
  bank = _sqlite_integer(tournament_id, "bank", tournament.current_bank_size_kopecks)
  if bank < 0:
    _fail(tournament_id, "bank must be nonnegative")

  params = bind.execute(sa.text(
    "SELECT row_id,percent_to_first,percent_to_second,percent_to_third "
    "FROM bet_tournament_params WHERE row_id=:params_id"
  ), {"params_id": tournament.params_id}).fetchall()
  if len(params) != 1:
    _fail(tournament_id, "referenced tournament parameter row is missing or ambiguous")
  percents = tuple(int(value) for value in params[0][1:4])
  if any(value < 0 for value in percents) or sum(percents) > 100:
    _fail(tournament_id, "invalid prize percentages")

  bets = bind.execute(sa.text(
    "SELECT b.row_id,b.poker_id,b.date,b.better_id,b.better_name,b.winner_id,b.loser_id,"
    "b.score,u.row_id AS user_row_id "
    "FROM bets b LEFT JOIN users u ON u.row_id=b.better_id "
    "WHERE b.date>=:start_date AND b.date<=:end_date ORDER BY b.row_id"
  ), {"start_date": tournament.start_date, "end_date": tournament.end_date}).fetchall()
  scores: dict[int, int] = defaultdict(int)
  snapshots: dict[int, tuple] = {}
  historical_names: dict[str, set[int]] = defaultdict(set)
  for bet in bets:
    if bet.better_id is None or bet.user_row_id is None:
      _fail(tournament_id, f"Bet row_id={bet.row_id} has orphan canonical bettor")
    name = str(bet.better_name or "")
    if not name.strip():
      _fail(tournament_id, f"Bet row_id={bet.row_id} has empty better_name")
    if "," in name:
      _fail(tournament_id, f"Bet row_id={bet.row_id} has comma-ambiguous better_name")
    user_id = int(bet.better_id)
    scores[user_id] = _sqlite_integer(
      tournament_id, f"aggregate score for user_id={user_id}",
      scores[user_id] + int(bet.score or 0),
    )
    historical_names[name.strip()].add(user_id)
    order = (bet.date, int(bet.row_id))
    if user_id not in snapshots or order > snapshots[user_id][:2]:
      snapshots[user_id] = (bet.date, int(bet.row_id), name)

  ranked = sorted(scores, key=lambda user_id: (-scores[user_id], snapshots[user_id][2], user_id))
  places: list[tuple[int, ...]] = [(), (), ()]
  cursor = 0
  while cursor < len(ranked) and cursor < 3:
    score = scores[ranked[cursor]]
    group = tuple(user_id for user_id in ranked if scores[user_id] == score)
    for position in range(cursor, min(cursor + len(group), 3)):
      places[position] = group
    cursor += len(group)

  legacy = (
    _split_legacy(tournament.first_place_name),
    _split_legacy(tournament.second_place_name),
    _split_legacy(tournament.third_place_name),
  )
  expected_names = tuple(tuple(snapshots[user_id][2].strip() for user_id in group) for group in places)
  for position, (actual, expected) in enumerate(zip(legacy, expected_names, strict=True), start=1):
    if Counter(actual) != Counter(expected):
      _fail(tournament_id, f"legacy place {position} membership is inconsistent")
    for name in actual:
      if not historical_names.get(name):
        _fail(tournament_id, f"legacy place {position} name {name!r} has no historical bettor")
      if len(historical_names[name]) > 1 and Counter(expected)[name] != len(historical_names[name]):
        _fail(tournament_id, f"legacy place {position} name {name!r} is ambiguous")

  amounts: dict[int, int] = {}
  position_by_user: dict[int, int] = {}
  slot = 0
  while slot < 3:
    group = places[slot]
    if not group:
      slot += 1
      continue
    occupied = [slot]
    next_slot = slot + 1
    while next_slot < 3 and places[next_slot] == group:
      occupied.append(next_slot)
      next_slot += 1
    pool = sum((bank * percents[index]) // 100 for index in occupied)
    individual = pool // len(group)
    for user_id in group:
      amounts[user_id] = amounts.get(user_id, 0) + individual
      position_by_user.setdefault(user_id, slot + 1)
    slot = next_slot

  distributed = sum(amounts.values())
  if distributed > bank:
    _fail(tournament_id, "distributed payout exceeds bank")
  remainder = bank - distributed
  if distributed + remainder != bank:
    _fail(tournament_id, "payout and bank do not reconcile")
  rows = [
    {
      "tournament_id": tournament_id,
      "user_id": user_id,
      "position": position_by_user[user_id],
      "score": scores[user_id],
      "payout_kopecks": amounts[user_id],
      "name_snapshot": snapshots[user_id][2],
    }
    for user_id in ranked if user_id in amounts
  ]
  if len(rows) != len(amounts) or len({row["user_id"] for row in rows}) != len(rows):
    _fail(tournament_id, "canonical payout recipients are not unique")
  for row in rows:
    for field in ("tournament_id", "user_id", "position", "score", "payout_kopecks"):
      _sqlite_integer(tournament_id, field, row[field])
  _sqlite_integer(tournament_id, "distributed payout", distributed)
  _sqlite_integer(tournament_id, "remainder", remainder)

  paid_user_ids = set(amounts)
  role_units: dict[tuple[int, int, str], int] = {}
  poker_facts: dict[int, tuple[set[int], set[int]]] = {}
  for bet in bets:
    bettor_id = int(bet.better_id)
    score = int(bet.score or 0)
    if bettor_id not in paid_user_ids or score <= 0:
      continue
    poker_id = int(bet.poker_id)
    if poker_id not in poker_facts:
      players = bind.execute(sa.text(
        "SELECT player_id,money_kopecks FROM poker_data WHERE poker_id=:poker_id"
      ), {"poker_id": poker_id}).fetchall()
      if not players:
        _fail(tournament_id, f"Poker outcome facts are missing for Poker {poker_id}")
      max_money = max(int(player.money_kopecks) for player in players)
      min_money = min(int(player.money_kopecks) for player in players)
      poker_facts[poker_id] = (
        {int(player.player_id) for player in players if int(player.money_kopecks) == max_money},
        {int(player.player_id) for player in players if int(player.money_kopecks) == min_money},
      )
    winners, losers = poker_facts[poker_id]
    winner_id = int(bet.winner_id)
    loser_id = int(bet.loser_id)
    winner_hit = winner_id in winners
    loser_hit = loser_id in losers
    units = score if winner_hit and loser_hit else score * 2
    if loser_hit:
      key = (bettor_id, loser_id, "loser")
      role_units[key] = _sqlite_integer(tournament_id, "loser role score units", role_units.get(key, 0) + units)
    if winner_hit and bettor_id != winner_id:
      key = (bettor_id, winner_id, "winner")
      role_units[key] = _sqlite_integer(tournament_id, "winner role score units", role_units.get(key, 0) + units)
  role_rows = [
    {
      "tournament_id": tournament_id,
      "bettor_user_id": bettor_id,
      "target_user_id": target_id,
      "role": role,
      "score_units": units,
    }
    for (bettor_id, target_id, role), units in sorted(role_units.items()) if units > 0
  ]
  return rows, role_rows, remainder


def upgrade() -> None:
  bind = op.get_bind()
  existing_tables = {
    str(row.name) for row in bind.execute(sa.text(
      "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
      "('bet_tournament_results','bet_tournament_role_results')"
    ))
  }
  if existing_tables:
    raise RuntimeError(f"Cannot normalize tournament results: target tables already exist: {sorted(existing_tables)}")
  finalized = bind.execute(sa.text(
    "SELECT row_id,params_id,start_date,end_date,current_bank_size_kopecks,"
    "first_place_name,second_place_name,third_place_name "
    "FROM bet_tournaments WHERE is_paid=1 ORDER BY row_id"
  )).fetchall()
  reconstructed = [(tournament, *_reconstruct(bind, tournament)) for tournament in finalized]

  created_results = False
  created_roles = False
  try:
    op.create_table(
    "bet_tournament_results",
    sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
    sa.Column("tournament_id", sa.Integer(), nullable=False),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.Column("score", sa.Integer(), nullable=False),
    sa.Column("payout_kopecks", sa.Integer(), nullable=False),
    sa.Column("name_snapshot", sa.String(length=255), nullable=False),
    sa.CheckConstraint("position BETWEEN 1 AND 3", name="ck_bet_tournament_results_position"),
    sa.CheckConstraint("payout_kopecks >= 0", name="ck_bet_tournament_results_payout_nonnegative"),
    sa.ForeignKeyConstraint(["tournament_id"], ["bet_tournaments.row_id"], name="fk_bet_tournament_results_tournament", ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["user_id"], ["users.row_id"], name="fk_bet_tournament_results_user", ondelete="RESTRICT"),
    sa.UniqueConstraint("tournament_id", "user_id", name="uq_bet_tournament_results_tournament_user"),
    )
    created_results = True
    op.create_index("ix_bet_tournament_results_user_id", "bet_tournament_results", ["user_id"])
    op.create_index("ix_bet_tournament_results_tournament_position", "bet_tournament_results", ["tournament_id", "position"])
    op.create_table(
      "bet_tournament_role_results",
      sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
      sa.Column("tournament_id", sa.Integer(), nullable=False),
      sa.Column("bettor_user_id", sa.Integer(), nullable=False),
      sa.Column("target_user_id", sa.Integer(), nullable=False),
      sa.Column("role", sa.String(length=6), nullable=False),
      sa.Column("score_units", sa.Integer(), nullable=False),
      sa.CheckConstraint("role IN ('winner', 'loser')", name="ck_bet_tournament_role_results_role"),
      sa.CheckConstraint("score_units > 0", name="ck_bet_tournament_role_results_score_units"),
      sa.ForeignKeyConstraint(["tournament_id"], ["bet_tournaments.row_id"], ondelete="RESTRICT"),
      sa.ForeignKeyConstraint(["bettor_user_id"], ["users.row_id"], ondelete="RESTRICT"),
      sa.ForeignKeyConstraint(["target_user_id"], ["users.row_id"], ondelete="RESTRICT"),
      sa.UniqueConstraint("tournament_id", "bettor_user_id", "target_user_id", "role", name="uq_bet_tournament_role_results_identity"),
    )
    created_roles = True
    op.create_index("ix_bet_tournament_role_results_target_role", "bet_tournament_role_results", ["target_user_id", "role"])

    result_table = sa.table(
    "bet_tournament_results",
    sa.column("tournament_id", sa.Integer()), sa.column("user_id", sa.Integer()),
    sa.column("position", sa.Integer()), sa.column("score", sa.Integer()),
    sa.column("payout_kopecks", sa.Integer()), sa.column("name_snapshot", sa.String()),
    )
    role_table = sa.table(
      "bet_tournament_role_results",
      sa.column("tournament_id", sa.Integer()), sa.column("bettor_user_id", sa.Integer()),
      sa.column("target_user_id", sa.Integer()), sa.column("role", sa.String()),
      sa.column("score_units", sa.Integer()),
    )
    for tournament, rows, role_rows, remainder in reconstructed:
      if rows:
        op.bulk_insert(result_table, rows)
      if role_rows:
        op.bulk_insert(role_table, role_rows)
      stored = bind.execute(sa.text(
      "SELECT COUNT(*),COALESCE(SUM(payout_kopecks),0) FROM bet_tournament_results "
      "WHERE tournament_id=:tournament_id"
      ), {"tournament_id": tournament.row_id}).one()
      if int(stored[0]) != len(rows):
        _fail(int(tournament.row_id), "backfill row count mismatch")
      if int(stored[1]) + remainder != int(tournament.current_bank_size_kopecks):
        _fail(int(tournament.row_id), "stored payout and bank do not reconcile")
  except Exception:
    if created_roles:
      op.drop_table("bet_tournament_role_results")
    if created_results:
      op.drop_table("bet_tournament_results")
    raise


def downgrade() -> None:
  op.drop_index("ix_bet_tournament_role_results_target_role", table_name="bet_tournament_role_results")
  op.drop_table("bet_tournament_role_results")
  op.drop_index("ix_bet_tournament_results_tournament_position", table_name="bet_tournament_results")
  op.drop_index("ix_bet_tournament_results_user_id", table_name="bet_tournament_results")
  op.drop_table("bet_tournament_results")
