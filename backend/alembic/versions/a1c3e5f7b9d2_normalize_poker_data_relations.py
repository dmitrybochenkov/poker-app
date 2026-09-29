"""normalize poker data relations

Revision ID: a1c3e5f7b9d2
Revises: f6a8b2c4d9e1
Create Date: 2026-09-29 21:30:00.000000
"""

from typing import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c3e5f7b9d2"
down_revision: str | Sequence[str] | None = "f6a8b2c4d9e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fail_on_invalid_data(bind) -> None:
  unmatched = bind.execute(
    sa.text(
      "SELECT pd.row_id, pd.date FROM poker_data pd "
      "LEFT JOIN pokers p ON p.date = pd.date "
      "WHERE p.row_id IS NULL LIMIT 1"
    )
  ).first()
  if unmatched is not None:
    raise RuntimeError(
      "Cannot normalize poker_data: "
      f"row_id={unmatched.row_id} date={unmatched.date} has no matching Poker"
    )

  ambiguous = bind.execute(
    sa.text(
      "SELECT pd.row_id, pd.date, COUNT(p.row_id) AS matches "
      "FROM poker_data pd JOIN pokers p ON p.date = pd.date "
      "GROUP BY pd.row_id, pd.date HAVING COUNT(p.row_id) <> 1 LIMIT 1"
    )
  ).first()
  if ambiguous is not None:
    raise RuntimeError(
      "Cannot normalize poker_data: "
      f"row_id={ambiguous.row_id} date={ambiguous.date} matches "
      f"{ambiguous.matches} Poker rows"
    )

  orphan = bind.execute(
    sa.text(
      "SELECT pd.row_id, pd.player_id FROM poker_data pd "
      "LEFT JOIN users u ON u.row_id = pd.player_id "
      "WHERE u.row_id IS NULL LIMIT 1"
    )
  ).first()
  if orphan is not None:
    raise RuntimeError(
      "Cannot normalize poker_data: "
      f"row_id={orphan.row_id} player_id={orphan.player_id} has no matching User"
    )

  duplicate = bind.execute(
    sa.text(
      "SELECT p.row_id AS poker_id, pd.player_id, COUNT(*) AS row_count "
      "FROM poker_data pd JOIN pokers p ON p.date = pd.date "
      "GROUP BY p.row_id, pd.player_id HAVING COUNT(*) > 1 LIMIT 1"
    )
  ).first()
  if duplicate is not None:
    raise RuntimeError(
      "Cannot normalize poker_data: duplicate target identity "
      f"poker_id={duplicate.poker_id}, player_id={duplicate.player_id}, "
      f"count={duplicate.row_count}"
    )


def upgrade() -> None:
  bind = op.get_bind()
  _fail_on_invalid_data(bind)

  with op.batch_alter_table("poker_data") as batch_op:
    batch_op.add_column(sa.Column("poker_id", sa.Integer(), nullable=True))

  bind.execute(
    sa.text(
      "UPDATE poker_data SET poker_id = "
      "(SELECT p.row_id FROM pokers p WHERE p.date = poker_data.date)"
    )
  )
  missing = bind.execute(
    sa.text("SELECT row_id FROM poker_data WHERE poker_id IS NULL LIMIT 1")
  ).first()
  if missing is not None:
    raise RuntimeError(
      f"Cannot normalize poker_data: row_id={missing.row_id} was not backfilled"
    )

  with op.batch_alter_table("poker_data") as batch_op:
    batch_op.alter_column("poker_id", existing_type=sa.Integer(), nullable=False)
    batch_op.create_foreign_key(
      "fk_poker_data_poker_id_pokers",
      "pokers",
      ["poker_id"],
      ["row_id"],
      ondelete="RESTRICT",
    )
    batch_op.create_foreign_key(
      "fk_poker_data_player_id_users",
      "users",
      ["player_id"],
      ["row_id"],
      ondelete="RESTRICT",
    )
    batch_op.create_unique_constraint(
      "uq_poker_data_poker_player", ["poker_id", "player_id"]
    )


def downgrade() -> None:
  with op.batch_alter_table("poker_data") as batch_op:
    batch_op.drop_constraint("uq_poker_data_poker_player", type_="unique")
    batch_op.drop_constraint("fk_poker_data_player_id_users", type_="foreignkey")
    batch_op.drop_constraint("fk_poker_data_poker_id_pokers", type_="foreignkey")
    batch_op.drop_column("poker_id")
