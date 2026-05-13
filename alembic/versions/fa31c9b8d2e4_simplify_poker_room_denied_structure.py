"""simplify poker_room_denied structure

Revision ID: fa31c9b8d2e4
Revises: f9c1a7d4e2b3
Create Date: 2026-05-13 20:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fa31c9b8d2e4"
down_revision: Union[str, None] = "f9c1a7d4e2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "poker_room_denied_new",
    sa.Column("user_row_id", sa.BigInteger(), nullable=False),
    sa.PrimaryKeyConstraint("user_row_id"),
  )
  op.execute(
    """
    INSERT OR IGNORE INTO poker_room_denied_new (user_row_id)
    SELECT DISTINCT user_row_id
    FROM poker_room_denied
    """
  )
  op.drop_table("poker_room_denied")
  op.rename_table("poker_room_denied_new", "poker_room_denied")


def downgrade() -> None:
  op.create_table(
    "poker_room_denied_old",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("date", sa.Date(), nullable=False),
    sa.Column("user_row_id", sa.BigInteger(), nullable=False),
    sa.PrimaryKeyConstraint("row_id"),
    sa.UniqueConstraint("date", "user_row_id", name="uq_poker_room_denied_date_user_row"),
  )
  op.create_index("ix_poker_room_denied_date", "poker_room_denied_old", ["date"], unique=False)
  op.create_index("ix_poker_room_denied_user_row_id", "poker_room_denied_old", ["user_row_id"], unique=False)
  op.execute(
    """
    INSERT INTO poker_room_denied_old (date, user_row_id)
    SELECT CURRENT_DATE, user_row_id
    FROM poker_room_denied
    """
  )
  op.drop_table("poker_room_denied")
  op.rename_table("poker_room_denied_old", "poker_room_denied")

