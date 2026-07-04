"""create bet tournaments table

Revision ID: b9d2c4e6f1a0
Revises: a7c1d9e4b2f3
Create Date: 2026-05-11 23:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9d2c4e6f1a0"
down_revision: Union[str, Sequence[str], None] = "a7c1d9e4b2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "bet_tournaments",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("tournament_type", sa.String(length=16), nullable=False),
    sa.Column("current_bank_kopecks", sa.Integer(), nullable=False, server_default="0"),
    sa.PrimaryKeyConstraint("row_id"),
    sa.UniqueConstraint("tournament_type", name="uq_bet_tournaments_type"),
  )
  op.execute(
    sa.text(
      "INSERT INTO bet_tournaments (tournament_type, current_bank_kopecks) VALUES "
      "('regular', 0), ('year', 0)"
    )
  )


def downgrade() -> None:
  op.drop_table("bet_tournaments")
