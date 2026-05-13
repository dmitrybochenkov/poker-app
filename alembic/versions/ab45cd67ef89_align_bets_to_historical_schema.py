"""align bets to historical schema

Revision ID: ab45cd67ef89
Revises: ff34de56bc78
Create Date: 2026-05-13 14:08:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ab45cd67ef89"
down_revision: Union[str, None] = "ff34de56bc78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
  bind = op.get_bind()
  rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
  return {str(row[1]) for row in rows}


def upgrade() -> None:
  cols = _columns("bets")

  if "params_id" not in cols:
    op.add_column("bets", sa.Column("params_id", sa.Integer(), nullable=True))
    cols.add("params_id")

  if "date" not in cols:
    op.add_column("bets", sa.Column("date", sa.Date(), nullable=True))
    cols.add("date")

  if "size_kopecks" not in cols:
    if "amount_kopecks" in cols:
      op.execute(sa.text("ALTER TABLE bets RENAME COLUMN amount_kopecks TO size_kopecks"))
    else:
      op.add_column("bets", sa.Column("size_kopecks", sa.Integer(), nullable=False, server_default="0"))
    cols.add("size_kopecks")

  if "winner" not in cols:
    if "winner_name" in cols:
      op.execute(sa.text("ALTER TABLE bets RENAME COLUMN winner_name TO winner"))
    else:
      op.add_column("bets", sa.Column("winner", sa.String(length=255), nullable=True))
    cols.add("winner")

  if "looser" not in cols:
    if "loser_name" in cols:
      op.execute(sa.text("ALTER TABLE bets RENAME COLUMN loser_name TO looser"))
    else:
      op.add_column("bets", sa.Column("looser", sa.String(length=255), nullable=True))
    cols.add("looser")

  if "score" not in cols:
    op.add_column("bets", sa.Column("score", sa.Integer(), nullable=False, server_default="0"))
    cols.add("score")

  if "is_paid" not in cols:
    op.add_column("bets", sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()))
    cols.add("is_paid")

  # Best-effort index for date filtering used by current code.
  bind = op.get_bind()
  idx = bind.execute(
    sa.text("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_bets_date'")
  ).fetchone()
  if idx is None:
    op.create_index("ix_bets_date", "bets", ["date"], unique=False)


def downgrade() -> None:
  # Intentionally no-op: destructive rollback is unsafe for live historical data.
  pass

