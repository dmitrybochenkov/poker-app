"""create stat indicators and achievements

Revision ID: e7a5c9d2b4f1
Revises: d1f7a9c3e5b2
Create Date: 2026-05-12 14:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7a5c9d2b4f1"
down_revision: Union[str, None] = "d1f7a9c3e5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "stat_indicators",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("type", sa.String(length=16), nullable=False),
    sa.Column("description", sa.String(length=255), nullable=False),
    sa.Column("description_full", sa.String(length=1024), nullable=False),
    sa.Column("pic", sa.String(length=32), nullable=False),
    sa.Column("for_current_tournaments", sa.String(length=16), nullable=False),
    sa.Column("is_for_achievement", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.PrimaryKeyConstraint("row_id"),
  )

  op.create_table(
    "achievements",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("type", sa.String(length=16), nullable=False),
    sa.Column("sort", sa.String(length=16), nullable=False),
    sa.Column("description", sa.String(length=255), nullable=False),
    sa.Column("pic", sa.String(length=32), nullable=False),
    sa.Column("stat_id", sa.Integer(), nullable=False),
    sa.Column("is_permanent", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.PrimaryKeyConstraint("row_id"),
  )


def downgrade() -> None:
  op.drop_table("achievements")
  op.drop_table("stat_indicators")
