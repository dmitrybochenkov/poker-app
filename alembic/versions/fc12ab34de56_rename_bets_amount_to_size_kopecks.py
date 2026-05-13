"""rename bets amount_kopecks to size_kopecks

Revision ID: fc12ab34de56
Revises: fab4d2c1e9a7
Create Date: 2026-05-13 13:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fc12ab34de56"
down_revision: Union[str, None] = "fab4d2c1e9a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_bets_columns() -> set[str]:
  bind = op.get_bind()
  rows = bind.execute(sa.text("PRAGMA table_info(bets)")).fetchall()
  return {str(row[1]) for row in rows}


def upgrade() -> None:
  columns = _get_bets_columns()
  if "amount_kopecks" in columns and "size_kopecks" not in columns:
    op.execute(sa.text("ALTER TABLE bets RENAME COLUMN amount_kopecks TO size_kopecks"))


def downgrade() -> None:
  columns = _get_bets_columns()
  if "size_kopecks" in columns and "amount_kopecks" not in columns:
    op.execute(sa.text("ALTER TABLE bets RENAME COLUMN size_kopecks TO amount_kopecks"))

