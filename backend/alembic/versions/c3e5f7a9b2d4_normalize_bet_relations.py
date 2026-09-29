"""normalize bet poker bettor and params relations

Revision ID: c3e5f7a9b2d4
Revises: b2d4f6a8c1e3
Create Date: 2026-09-29 23:30:00.000000
"""

from typing import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3e5f7a9b2d4"
down_revision: str | Sequence[str] | None = "b2d4f6a8c1e3"
branch_labels = None
depends_on = None


def _preflight(bind) -> None:
  checks = (
    ("SELECT b.row_id, b.date AS value FROM bets b LEFT JOIN pokers p ON p.date=b.date WHERE p.row_id IS NULL LIMIT 1", "date={value} has no matching Poker"),
    ("SELECT b.row_id, b.better_id AS value FROM bets b LEFT JOIN users u ON u.row_id=b.better_id WHERE u.row_id IS NULL LIMIT 1", "better_id={value} has no matching User"),
    ("SELECT b.row_id, b.params_id AS value FROM bets b LEFT JOIN bet_params p ON p.row_id=b.params_id WHERE p.row_id IS NULL LIMIT 1", "params_id={value} has no matching BetParam"),
  )
  for sql, message in checks:
    row = bind.execute(sa.text(sql)).first()
    if row is not None:
      raise RuntimeError(
        "Cannot normalize bets: " + f"row_id={row.row_id} " + message.format(value=row.value)
      )
  ambiguous = bind.execute(sa.text(
    "SELECT b.row_id, b.date, COUNT(p.row_id) AS matches FROM bets b JOIN pokers p ON p.date=b.date "
    "GROUP BY b.row_id,b.date HAVING COUNT(p.row_id)<>1 LIMIT 1"
  )).first()
  if ambiguous is not None:
    raise RuntimeError(f"Cannot normalize bets: row_id={ambiguous.row_id} date={ambiguous.date} matches {ambiguous.matches} Poker rows")
  duplicate = bind.execute(sa.text(
    "SELECT p.row_id AS poker_id,b.better_id,COUNT(*) AS row_count FROM bets b JOIN pokers p ON p.date=b.date "
    "GROUP BY p.row_id,b.better_id HAVING COUNT(*)>1 LIMIT 1"
  )).first()
  if duplicate is not None:
    raise RuntimeError(
      f"Cannot normalize bets: duplicate target identity poker_id={duplicate.poker_id}, "
      f"better_id={duplicate.better_id}, count={duplicate.row_count}"
    )


def upgrade() -> None:
  bind = op.get_bind()
  _preflight(bind)
  with op.batch_alter_table("bets") as batch_op:
    batch_op.add_column(sa.Column("poker_id", sa.Integer(), nullable=True))
  bind.execute(sa.text(
    "UPDATE bets SET poker_id=(SELECT p.row_id FROM pokers p WHERE p.date=bets.date)"
  ))
  missing = bind.execute(sa.text("SELECT row_id FROM bets WHERE poker_id IS NULL LIMIT 1")).first()
  if missing is not None:
    raise RuntimeError(f"Cannot normalize bets: row_id={missing.row_id} was not backfilled")
  with op.batch_alter_table("bets") as batch_op:
    batch_op.alter_column("poker_id", existing_type=sa.Integer(), nullable=False)
    batch_op.create_foreign_key("fk_bets_poker_id_pokers", "pokers", ["poker_id"], ["row_id"], ondelete="RESTRICT")
    batch_op.create_foreign_key("fk_bets_better_id_users", "users", ["better_id"], ["row_id"], ondelete="RESTRICT")
    batch_op.create_foreign_key("fk_bets_params_id_bet_params", "bet_params", ["params_id"], ["row_id"], ondelete="RESTRICT")
    batch_op.create_unique_constraint("uq_bets_poker_better_id", ["poker_id", "better_id"])


def downgrade() -> None:
  with op.batch_alter_table("bets") as batch_op:
    batch_op.drop_constraint("uq_bets_poker_better_id", type_="unique")
    batch_op.drop_constraint("fk_bets_params_id_bet_params", type_="foreignkey")
    batch_op.drop_constraint("fk_bets_better_id_users", type_="foreignkey")
    batch_op.drop_constraint("fk_bets_poker_id_pokers", type_="foreignkey")
    batch_op.drop_column("poker_id")
