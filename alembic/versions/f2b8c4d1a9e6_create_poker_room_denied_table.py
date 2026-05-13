"""create poker_room_denied table

Revision ID: f2b8c4d1a9e6
Revises: e7a5c9d2b4f1
Create Date: 2026-05-13 14:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2b8c4d1a9e6"
down_revision: Union[str, None] = "e7a5c9d2b4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "poker_room_denied",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("date", sa.Date(), nullable=False),
    sa.Column("player_id", sa.BigInteger(), nullable=False),
    sa.Column("platform", sa.String(length=8), nullable=False),
    sa.PrimaryKeyConstraint("row_id"),
    sa.UniqueConstraint("date", "player_id", name="uq_poker_room_denied_date_player"),
  )
  op.create_index("ix_poker_room_denied_date", "poker_room_denied", ["date"], unique=False)
  op.create_index("ix_poker_room_denied_player_id", "poker_room_denied", ["player_id"], unique=False)


def downgrade() -> None:
  op.drop_index("ix_poker_room_denied_player_id", table_name="poker_room_denied")
  op.drop_index("ix_poker_room_denied_date", table_name="poker_room_denied")
  op.drop_table("poker_room_denied")

