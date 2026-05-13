"""migrate poker_data player_id to users.row_id

Revision ID: bc41de77aa12
Revises: ac56de78fa90
Create Date: 2026-05-13 14:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bc41de77aa12"
down_revision: Union[str, None] = "ac56de78fa90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "poker_data_new",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("date", sa.Date(), nullable=False),
    sa.Column("player_name", sa.String(length=255), nullable=False),
    sa.Column("player_id", sa.Integer(), nullable=False),
    sa.Column("is_prev_winner", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("buyins", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("big_buyin_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("super_buyin_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("chips", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("money_kopecks", sa.BigInteger(), nullable=False, server_default="0"),
    sa.PrimaryKeyConstraint("row_id"),
    sa.UniqueConstraint("date", "player_id", name="uq_poker_data_date_player"),
  )
  op.create_index("ix_poker_data_new_date", "poker_data_new", ["date"], unique=False)
  op.execute(
    """
    INSERT OR IGNORE INTO poker_data_new (
      row_id, date, player_name, player_id, is_prev_winner, buyins,
      big_buyin_count, super_buyin_count, chips, money_kopecks
    )
    SELECT
      pd.row_id,
      pd.date,
      pd.player_name,
      COALESCE(u.row_id, pd.player_id) AS mapped_player_id,
      pd.is_prev_winner,
      pd.buyins,
      pd.big_buyin_count,
      pd.super_buyin_count,
      pd.chips,
      pd.money_kopecks
    FROM poker_data pd
    LEFT JOIN users u
      ON u.telegram_id = pd.player_id
      OR u.vk_id = pd.player_id
    """
  )
  op.drop_table("poker_data")
  op.rename_table("poker_data_new", "poker_data")
  op.execute("DROP INDEX IF EXISTS ix_poker_data_new_date")
  op.create_index("ix_poker_data_date", "poker_data", ["date"], unique=False)


def downgrade() -> None:
  op.create_table(
    "poker_data_old",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("date", sa.Date(), nullable=False),
    sa.Column("player_name", sa.String(length=255), nullable=False),
    sa.Column("player_id", sa.BigInteger(), nullable=False),
    sa.Column("is_prev_winner", sa.Boolean(), nullable=False),
    sa.Column("buyins", sa.Integer(), nullable=False),
    sa.Column("big_buyin_count", sa.Integer(), nullable=False),
    sa.Column("super_buyin_count", sa.Integer(), nullable=False),
    sa.Column("chips", sa.Integer(), nullable=False),
    sa.Column("money_kopecks", sa.BigInteger(), nullable=False),
    sa.PrimaryKeyConstraint("row_id"),
    sa.UniqueConstraint("date", "player_id", name="uq_poker_data_date_player"),
  )
  op.create_index("ix_poker_data_old_date", "poker_data_old", ["date"], unique=False)
  op.execute(
    """
    INSERT INTO poker_data_old (
      row_id, date, player_name, player_id, is_prev_winner, buyins,
      big_buyin_count, super_buyin_count, chips, money_kopecks
    )
    SELECT
      pd.row_id,
      pd.date,
      pd.player_name,
      COALESCE(u.telegram_id, u.vk_id, pd.player_id) AS mapped_player_id,
      pd.is_prev_winner,
      pd.buyins,
      pd.big_buyin_count,
      pd.super_buyin_count,
      pd.chips,
      pd.money_kopecks
    FROM poker_data pd
    LEFT JOIN users u ON u.row_id = pd.player_id
    """
  )
  op.drop_table("poker_data")
  op.rename_table("poker_data_old", "poker_data")
  op.execute("DROP INDEX IF EXISTS ix_poker_data_old_date")
  op.create_index("ix_poker_data_date", "poker_data", ["date"], unique=False)
