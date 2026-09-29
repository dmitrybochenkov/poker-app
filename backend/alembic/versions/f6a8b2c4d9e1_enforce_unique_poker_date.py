"""enforce one poker per calendar date

Revision ID: f6a8b2c4d9e1
Revises: e5b7c9d1f3a2
Create Date: 2026-09-29 18:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a8b2c4d9e1"
down_revision: str | Sequence[str] | None = "e5b7c9d1f3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  bind = op.get_bind()
  duplicate = bind.execute(
    sa.text(
      """
      SELECT date, COUNT(*) AS row_count
      FROM pokers
      GROUP BY date
      HAVING COUNT(*) > 1
      LIMIT 1
      """
    )
  ).first()
  if duplicate is not None:
    raise RuntimeError(
      "Cannot enforce uq_pokers_date: "
      f"duplicate pokers exist for date={duplicate.date}, count={duplicate.row_count}. "
      "Resolve the duplicate game rows before retrying the migration."
    )

  op.create_index("uq_pokers_date", "pokers", ["date"], unique=True)


def downgrade() -> None:
  op.drop_index("uq_pokers_date", table_name="pokers")
