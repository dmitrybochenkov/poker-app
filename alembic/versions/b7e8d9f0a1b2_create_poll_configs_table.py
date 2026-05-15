"""create poll configs table

Revision ID: b7e8d9f0a1b2
Revises: a9b7c6d5e4f3
Create Date: 2026-05-14 18:25:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7e8d9f0a1b2"
down_revision: str | Sequence[str] | None = "a9b7c6d5e4f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.create_table(
    "poll_configs",
    sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
    sa.Column("poll_month", sa.Date(), nullable=True),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
  )


def downgrade() -> None:
  op.drop_table("poll_configs")
