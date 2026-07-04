"""add bet params and scoring columns

Revision ID: c4e8f2a1b6d7
Revises: b9d2c4e6f1a0
Create Date: 2026-05-12 00:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4e8f2a1b6d7"
down_revision: Union[str, Sequence[str], None] = "b9d2c4e6f1a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "bet_params",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("small_size_kopecks", sa.Integer(), nullable=False),
    sa.Column("small_score", sa.Integer(), nullable=False),
    sa.Column("small_score_combo", sa.Integer(), nullable=False),
    sa.Column("big_size_kopecks", sa.Integer(), nullable=False),
    sa.Column("big_score", sa.Integer(), nullable=False),
    sa.Column("big_score_combo", sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint("row_id"),
  )

  op.create_table(
    "bet_tournament_params",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("tournament_type", sa.String(length=16), nullable=False),
    sa.Column("bet_param_id", sa.Integer(), nullable=False),
    sa.Column("percent_to_first", sa.Integer(), nullable=False, server_default="50"),
    sa.Column("percent_to_second", sa.Integer(), nullable=False, server_default="30"),
    sa.Column("percent_to_third", sa.Integer(), nullable=False, server_default="20"),
    sa.Column("duration_months", sa.Integer(), nullable=False, server_default="12"),
    sa.PrimaryKeyConstraint("row_id"),
    sa.UniqueConstraint("tournament_type", name="uq_bet_tournament_params_type"),
  )

  op.add_column("bet_tournaments", sa.Column("params_id", sa.Integer(), nullable=True))

  op.add_column("bets", sa.Column("params_id", sa.Integer(), nullable=True))
  op.add_column("bets", sa.Column("winner_name", sa.String(length=255), nullable=True))
  op.add_column("bets", sa.Column("loser_name", sa.String(length=255), nullable=True))
  op.add_column("bets", sa.Column("score", sa.Integer(), nullable=False, server_default="0"))

  op.execute(
    sa.text(
      "INSERT INTO bet_params "
      "(small_size_kopecks, small_score, small_score_combo, big_size_kopecks, big_score, big_score_combo) "
      "VALUES (50000, 1, 2, 100000, 2, 4)"
    )
  )
  op.execute(
    sa.text(
      "INSERT INTO bet_tournament_params (tournament_type, bet_param_id, percent_to_first, percent_to_second, percent_to_third, duration_months) "
      "VALUES ('regular', 1, 50, 30, 20, 12), ('year', 1, 50, 30, 20, 12)"
    )
  )
  op.execute(
    sa.text("UPDATE bet_tournaments SET params_id = 1 WHERE tournament_type IN ('regular', 'year')")
  )
  op.execute(
    sa.text("UPDATE bets SET params_id = 1 WHERE params_id IS NULL")
  )


def downgrade() -> None:
  op.drop_column("bets", "score")
  op.drop_column("bets", "loser_name")
  op.drop_column("bets", "winner_name")
  op.drop_column("bets", "params_id")
  op.drop_column("bet_tournaments", "params_id")
  op.drop_table("bet_tournament_params")
  op.drop_table("bet_params")
