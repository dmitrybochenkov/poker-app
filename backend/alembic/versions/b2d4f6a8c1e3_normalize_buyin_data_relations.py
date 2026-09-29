"""normalize buyin data relations

Revision ID: b2d4f6a8c1e3
Revises: a1c3e5f7b9d2
Create Date: 2026-09-29 22:30:00.000000
"""

from typing import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2d4f6a8c1e3"
down_revision: str | Sequence[str] | None = "a1c3e5f7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fail_on_invalid_data(bind) -> None:
  unmatched = bind.execute(
    sa.text(
      "SELECT b.row_id, b.date FROM buyins_data b "
      "LEFT JOIN pokers p ON p.date = b.date "
      "WHERE p.row_id IS NULL LIMIT 1"
    )
  ).first()
  if unmatched is not None:
    raise RuntimeError(
      "Cannot normalize buyins_data: "
      f"row_id={unmatched.row_id} date={unmatched.date} has no matching Poker"
    )

  ambiguous = bind.execute(
    sa.text(
      "SELECT b.row_id, b.date, COUNT(p.row_id) AS matches "
      "FROM buyins_data b JOIN pokers p ON p.date = b.date "
      "GROUP BY b.row_id, b.date HAVING COUNT(p.row_id) <> 1 LIMIT 1"
    )
  ).first()
  if ambiguous is not None:
    raise RuntimeError(
      "Cannot normalize buyins_data: "
      f"row_id={ambiguous.row_id} date={ambiguous.date} matches "
      f"{ambiguous.matches} Poker rows"
    )

  orphan = bind.execute(
    sa.text(
      "SELECT b.row_id, b.player_id FROM buyins_data b "
      "LEFT JOIN users u ON u.row_id = b.player_id "
      "WHERE u.row_id IS NULL LIMIT 1"
    )
  ).first()
  if orphan is not None:
    raise RuntimeError(
      "Cannot normalize buyins_data: "
      f"row_id={orphan.row_id} player_id={orphan.player_id} has no matching User"
    )


def upgrade() -> None:
  bind = op.get_bind()
  _fail_on_invalid_data(bind)

  with op.batch_alter_table("buyins_data") as batch_op:
    batch_op.add_column(sa.Column("poker_id", sa.Integer(), nullable=True))

  bind.execute(
    sa.text(
      "UPDATE buyins_data SET poker_id = "
      "(SELECT p.row_id FROM pokers p WHERE p.date = buyins_data.date)"
    )
  )
  missing = bind.execute(
    sa.text("SELECT row_id FROM buyins_data WHERE poker_id IS NULL LIMIT 1")
  ).first()
  if missing is not None:
    raise RuntimeError(
      f"Cannot normalize buyins_data: row_id={missing.row_id} was not backfilled"
    )

  with op.batch_alter_table("buyins_data") as batch_op:
    batch_op.alter_column("poker_id", existing_type=sa.Integer(), nullable=False)
    batch_op.create_foreign_key(
      "fk_buyins_data_poker_id_pokers",
      "pokers",
      ["poker_id"],
      ["row_id"],
      ondelete="RESTRICT",
    )
    batch_op.create_foreign_key(
      "fk_buyins_data_player_id_users",
      "users",
      ["player_id"],
      ["row_id"],
      ondelete="RESTRICT",
    )


def downgrade() -> None:
  with op.batch_alter_table("buyins_data") as batch_op:
    batch_op.drop_constraint("fk_buyins_data_player_id_users", type_="foreignkey")
    batch_op.drop_constraint("fk_buyins_data_poker_id_pokers", type_="foreignkey")
    batch_op.drop_column("poker_id")
