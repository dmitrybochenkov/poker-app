"""add created_at/updated_at columns and sync_states table

Revision ID: d4e5f6a7b8c9
Revises: c8e3f9a1b2d4
Create Date: 2026-05-22 12:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c8e3f9a1b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_created_and_updated(table_name: str, add_created: bool = True, add_updated: bool = True) -> None:
  with op.batch_alter_table(table_name) as batch_op:
    if add_created:
      batch_op.add_column(
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))
      )
    if add_updated:
      batch_op.add_column(
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))
      )


def upgrade() -> None:
  _add_created_and_updated("users")
  _add_created_and_updated("pokers")
  _add_created_and_updated("poker_data")
  _add_created_and_updated("poker_params")
  _add_created_and_updated("bets")
  _add_created_and_updated("bet_tournaments")
  _add_created_and_updated("bet_params")
  _add_created_and_updated("bet_tournament_params")
  _add_created_and_updated("stat_indicators")
  _add_created_and_updated("achievements")
  _add_created_and_updated("poker_room_denied")
  _add_created_and_updated("poll_configs", add_created=True, add_updated=False)
  _add_created_and_updated("buyins_data", add_created=False, add_updated=True)

  op.create_table(
    "sync_states",
    sa.Column("table_name", sa.String(length=64), nullable=False),
    sa.Column("last_synced_row_id", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("last_synced_updated_at", sa.DateTime(), nullable=True),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.PrimaryKeyConstraint("table_name"),
  )


def downgrade() -> None:
  op.drop_table("sync_states")

  with op.batch_alter_table("buyins_data") as batch_op:
    batch_op.drop_column("updated_at")
  with op.batch_alter_table("poll_configs") as batch_op:
    batch_op.drop_column("created_at")
  with op.batch_alter_table("poker_room_denied") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
  with op.batch_alter_table("achievements") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
  with op.batch_alter_table("stat_indicators") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
  with op.batch_alter_table("bet_tournament_params") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
  with op.batch_alter_table("bet_params") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
  with op.batch_alter_table("bet_tournaments") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
  with op.batch_alter_table("bets") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
  with op.batch_alter_table("poker_params") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
  with op.batch_alter_table("poker_data") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
  with op.batch_alter_table("pokers") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
  with op.batch_alter_table("users") as batch_op:
    batch_op.drop_column("updated_at")
    batch_op.drop_column("created_at")
