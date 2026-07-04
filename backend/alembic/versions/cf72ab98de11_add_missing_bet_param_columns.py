"""add missing columns to bet_params

Revision ID: cf72ab98de11
Revises: bc41de77aa12
Create Date: 2026-05-13 14:48:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cf72ab98de11"
down_revision: Union[str, None] = "bc41de77aa12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set[str]:
  bind = op.get_bind()
  rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
  return {str(row[1]) for row in rows}


def upgrade() -> None:
  cols = _existing_columns("bet_params")
  if "small_pic" not in cols:
    op.execute("ALTER TABLE bet_params ADD COLUMN small_pic VARCHAR(16) NOT NULL DEFAULT '🐤'")
  if "big_pic" not in cols:
    op.execute("ALTER TABLE bet_params ADD COLUMN big_pic VARCHAR(16) NOT NULL DEFAULT '🐔'")
  if "percent_to_regular_bank_if_it_is_going" not in cols:
    op.execute(
      "ALTER TABLE bet_params ADD COLUMN percent_to_regular_bank_if_it_is_going INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
  # SQLite doesn't support dropping columns in-place.
  pass

