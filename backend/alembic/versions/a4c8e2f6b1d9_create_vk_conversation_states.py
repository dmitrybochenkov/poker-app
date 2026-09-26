"""create vk conversation states

Revision ID: a4c8e2f6b1d9
Revises: d9e8f7a6b5c4
Create Date: 2026-09-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a4c8e2f6b1d9"
down_revision: Union[str, Sequence[str], None] = "d9e8f7a6b5c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "vk_conversation_states",
    sa.Column("vk_user_id", sa.BigInteger(), nullable=False),
    sa.Column("user_row_id", sa.Integer(), nullable=True),
    sa.Column("state_type", sa.String(length=64), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("updated_at", sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(["user_row_id"], ["users.row_id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("vk_user_id"),
  )
  op.create_index(
    "ix_vk_conversation_states_user_row_id",
    "vk_conversation_states",
    ["user_row_id"],
  )


def downgrade() -> None:
  op.drop_index(
    "ix_vk_conversation_states_user_row_id",
    table_name="vk_conversation_states",
  )
  op.drop_table("vk_conversation_states")
