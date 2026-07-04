"""align buyins table to historical schema

Revision ID: fe21cd43ab65
Revises: fd98bc76a321
Create Date: 2026-05-13 13:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fe21cd43ab65"
down_revision: Union[str, None] = "fd98bc76a321"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
  bind = op.get_bind()
  row = bind.execute(
    sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
    {"name": table_name},
  ).fetchone()
  return row is not None


def _columns(table_name: str) -> set[str]:
  bind = op.get_bind()
  rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
  return {str(row[1]) for row in rows}


def upgrade() -> None:
  if _table_exists("buyin_data") and not _table_exists("buyins_data"):
    op.execute(sa.text("ALTER TABLE buyin_data RENAME TO buyins_data"))

  if not _table_exists("buyins_data"):
    return

  cols = _columns("buyins_data")

  if "poker_date" in cols and "date" not in cols:
    op.execute(sa.text("ALTER TABLE buyins_data RENAME COLUMN poker_date TO date"))
    cols.remove("poker_date")
    cols.add("date")

  if "buyins_count" in cols and "buyin" not in cols:
    op.execute(sa.text("ALTER TABLE buyins_data RENAME COLUMN buyins_count TO buyin"))


def downgrade() -> None:
  if not _table_exists("buyins_data"):
    return

  cols = _columns("buyins_data")

  if "buyin" in cols and "buyins_count" not in cols:
    op.execute(sa.text("ALTER TABLE buyins_data RENAME COLUMN buyin TO buyins_count"))
    cols.remove("buyin")
    cols.add("buyins_count")

  if "date" in cols and "poker_date" not in cols:
    op.execute(sa.text("ALTER TABLE buyins_data RENAME COLUMN date TO poker_date"))

  if _table_exists("buyins_data") and not _table_exists("buyin_data"):
    op.execute(sa.text("ALTER TABLE buyins_data RENAME TO buyin_data"))

