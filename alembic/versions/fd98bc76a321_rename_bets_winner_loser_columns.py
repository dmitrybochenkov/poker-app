"""rename bets winner/loser columns to winner/looser

Revision ID: fd98bc76a321
Revises: fc12ab34de56
Create Date: 2026-05-13 13:27:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fd98bc76a321"
down_revision: Union[str, None] = "fc12ab34de56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_bets_columns() -> set[str]:
  bind = op.get_bind()
  rows = bind.execute(sa.text("PRAGMA table_info(bets)")).fetchall()
  return {str(row[1]) for row in rows}


def upgrade() -> None:
  columns = _get_bets_columns()

  if "winner_name" in columns and "winner" not in columns:
    op.execute(sa.text("ALTER TABLE bets RENAME COLUMN winner_name TO winner"))
    columns.remove("winner_name")
    columns.add("winner")

  if "loser_name" in columns and "looser" not in columns:
    op.execute(sa.text("ALTER TABLE bets RENAME COLUMN loser_name TO looser"))


def downgrade() -> None:
  columns = _get_bets_columns()

  if "winner" in columns and "winner_name" not in columns:
    op.execute(sa.text("ALTER TABLE bets RENAME COLUMN winner TO winner_name"))
    columns.remove("winner")
    columns.add("winner_name")

  if "looser" in columns and "loser_name" not in columns:
    op.execute(sa.text("ALTER TABLE bets RENAME COLUMN looser TO loser_name"))

