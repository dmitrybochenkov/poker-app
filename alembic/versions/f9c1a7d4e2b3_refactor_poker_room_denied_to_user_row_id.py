"""refactor poker_room_denied to user_row_id

Revision ID: f9c1a7d4e2b3
Revises: f2b8c4d1a9e6
Create Date: 2026-05-13 19:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9c1a7d4e2b3"
down_revision: Union[str, None] = "f2b8c4d1a9e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.add_column("poker_room_denied", sa.Column("user_row_id", sa.BigInteger(), nullable=True))
  op.execute("UPDATE poker_room_denied SET user_row_id = player_id")
  op.drop_index("ix_poker_room_denied_player_id", table_name="poker_room_denied")

  with op.batch_alter_table("poker_room_denied") as batch_op:
    batch_op.alter_column("user_row_id", existing_type=sa.BigInteger(), nullable=False)
    batch_op.drop_constraint("uq_poker_room_denied_date_player", type_="unique")
    batch_op.create_unique_constraint(
      "uq_poker_room_denied_date_user_row",
      ["date", "user_row_id"],
    )
    batch_op.drop_column("platform")
    batch_op.drop_column("player_id")

  op.create_index("ix_poker_room_denied_user_row_id", "poker_room_denied", ["user_row_id"], unique=False)


def downgrade() -> None:
  op.add_column("poker_room_denied", sa.Column("player_id", sa.BigInteger(), nullable=True))
  op.add_column("poker_room_denied", sa.Column("platform", sa.String(length=8), nullable=True))
  op.execute("UPDATE poker_room_denied SET player_id = user_row_id")
  op.execute("UPDATE poker_room_denied SET platform = 'tg'")
  op.drop_index("ix_poker_room_denied_user_row_id", table_name="poker_room_denied")

  with op.batch_alter_table("poker_room_denied") as batch_op:
    batch_op.alter_column("player_id", existing_type=sa.BigInteger(), nullable=False)
    batch_op.alter_column("platform", existing_type=sa.String(length=8), nullable=False)
    batch_op.drop_constraint("uq_poker_room_denied_date_user_row", type_="unique")
    batch_op.create_unique_constraint(
      "uq_poker_room_denied_date_player",
      ["date", "player_id"],
    )
    batch_op.drop_column("user_row_id")

  op.create_index("ix_poker_room_denied_player_id", "poker_room_denied", ["player_id"], unique=False)
