"""normalize bet winner and loser identity

Revision ID: d4f6a8c1e3b5
Revises: c3e5f7a9b2d4
Create Date: 2026-09-30 01:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4f6a8c1e3b5"
down_revision: str | Sequence[str] | None = "c3e5f7a9b2d4"
branch_labels = None
depends_on = None


def _preflight_role(bind, *, column: str, label: str) -> None:
  missing = bind.execute(sa.text(
    f"SELECT row_id,{column} AS value FROM bets "
    f"WHERE {column} IS NULL OR trim({column})='' LIMIT 1"
  )).first()
  if missing is not None:
    raise RuntimeError(
      f"Cannot normalize bet outcomes: row_id={missing.row_id} {label} is NULL or empty"
    )

  invalid = bind.execute(sa.text(
    f"SELECT b.row_id,b.{column} AS value,COUNT(pd.row_id) AS matches "
    "FROM bets b LEFT JOIN poker_data pd "
    f"ON pd.poker_id=b.poker_id AND pd.player_name=b.{column} "
    f"GROUP BY b.row_id,b.{column} HAVING COUNT(pd.row_id)<>1 LIMIT 1"
  )).first()
  if invalid is not None:
    raise RuntimeError(
      f"Cannot normalize bet outcomes: row_id={invalid.row_id} {label}={invalid.value!r} "
      f"matches {invalid.matches} PokerData participants"
    )

  orphan = bind.execute(sa.text(
    f"SELECT b.row_id,pd.player_id AS value FROM bets b "
    f"JOIN poker_data pd ON pd.poker_id=b.poker_id AND pd.player_name=b.{column} "
    "LEFT JOIN users u ON u.row_id=pd.player_id WHERE u.row_id IS NULL LIMIT 1"
  )).first()
  if orphan is not None:
    raise RuntimeError(
      f"Cannot normalize bet outcomes: row_id={orphan.row_id} resolved {label} "
      f"player_id={orphan.value} has no User"
    )


def _preflight(bind) -> None:
  invalid_poker = bind.execute(sa.text(
    "SELECT b.row_id,b.poker_id FROM bets b LEFT JOIN pokers p ON p.row_id=b.poker_id "
    "WHERE p.row_id IS NULL LIMIT 1"
  )).first()
  if invalid_poker is not None:
    raise RuntimeError(
      f"Cannot normalize bet outcomes: row_id={invalid_poker.row_id} "
      f"poker_id={invalid_poker.poker_id} has no Poker"
    )
  _preflight_role(bind, column="winner", label="winner")
  _preflight_role(bind, column="looser", label="looser")


def upgrade() -> None:
  bind = op.get_bind()
  _preflight(bind)
  with op.batch_alter_table("bets") as batch_op:
    batch_op.add_column(sa.Column("winner_id", sa.Integer(), nullable=True))
    batch_op.add_column(sa.Column("loser_id", sa.Integer(), nullable=True))
  bind.execute(sa.text(
    "UPDATE bets SET winner_id=(SELECT pd.player_id FROM poker_data pd "
    "WHERE pd.poker_id=bets.poker_id AND pd.player_name=bets.winner), "
    "loser_id=(SELECT pd.player_id FROM poker_data pd "
    "WHERE pd.poker_id=bets.poker_id AND pd.player_name=bets.looser)"
  ))
  with op.batch_alter_table("bets") as batch_op:
    batch_op.alter_column("winner_id", existing_type=sa.Integer(), nullable=False)
    batch_op.alter_column("loser_id", existing_type=sa.Integer(), nullable=False)
    batch_op.create_foreign_key(
      "fk_bets_winner_id_users", "users", ["winner_id"], ["row_id"],
      ondelete="RESTRICT",
    )
    batch_op.create_foreign_key(
      "fk_bets_loser_id_users", "users", ["loser_id"], ["row_id"],
      ondelete="RESTRICT",
    )


def downgrade() -> None:
  with op.batch_alter_table("bets") as batch_op:
    batch_op.drop_constraint("fk_bets_loser_id_users", type_="foreignkey")
    batch_op.drop_constraint("fk_bets_winner_id_users", type_="foreignkey")
    batch_op.drop_column("loser_id")
    batch_op.drop_column("winner_id")
