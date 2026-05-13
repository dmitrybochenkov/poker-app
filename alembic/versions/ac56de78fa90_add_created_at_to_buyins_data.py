"""add created_at to buyins_data

Revision ID: ac56de78fa90
Revises: ab45cd67ef89
Create Date: 2026-05-13 16:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ac56de78fa90"
down_revision: Union[str, None] = "ab45cd67ef89"
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
  if not _table_exists("buyins_data"):
    return
  cols = _columns("buyins_data")
  if "created_at" not in cols:
    op.add_column(
      "buyins_data",
      sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
  if not _table_exists("buyins_data"):
    return
  cols = _columns("buyins_data")
  if "created_at" in cols:
    op.drop_column("buyins_data", "created_at")

