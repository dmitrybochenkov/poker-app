"""add date to bets

Revision ID: fab4d2c1e9a7
Revises: fa31c9b8d2e4
Create Date: 2026-05-13 20:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fab4d2c1e9a7"
down_revision: Union[str, None] = "fa31c9b8d2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.add_column("bets", sa.Column("date", sa.Date(), nullable=True))
  op.create_index("ix_bets_date", "bets", ["date"], unique=False)


def downgrade() -> None:
  op.drop_index("ix_bets_date", table_name="bets")
  op.drop_column("bets", "date")

