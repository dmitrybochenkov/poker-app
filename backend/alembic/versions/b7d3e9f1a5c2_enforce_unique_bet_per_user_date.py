"""enforce one logical bet per user and date

Revision ID: b7d3e9f1a5c2
Revises: a4c8e2f6b1d9
Create Date: 2026-09-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b7d3e9f1a5c2"
down_revision: Union[str, Sequence[str], None] = "a4c8e2f6b1d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  bind = op.get_bind()
  duplicate = bind.execute(
    sa.text(
      """
      SELECT date, better_id, COUNT(*) AS row_count
      FROM bets
      WHERE date IS NOT NULL
      GROUP BY date, better_id
      HAVING COUNT(*) > 1
      LIMIT 1
      """
    )
  ).first()
  if duplicate is not None:
    raise RuntimeError(
      "Cannot enforce uq_bets_date_better_id: "
      f"duplicate bets exist for date={duplicate.date}, "
      f"better_id={duplicate.better_id}, count={duplicate.row_count}"
    )

  with op.batch_alter_table("bets") as batch_op:
    batch_op.create_unique_constraint(
      "uq_bets_date_better_id",
      ["date", "better_id"],
    )


def downgrade() -> None:
  with op.batch_alter_table("bets") as batch_op:
    batch_op.drop_constraint(
      "uq_bets_date_better_id",
      type_="unique",
    )
