"""create poll votes table

Revision ID: a9b7c6d5e4f3
Revises: f1a2b3c4d5e6
Create Date: 2026-05-14 17:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9b7c6d5e4f3"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.create_table(
    "poll_votes",
    sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
    sa.Column("poll_date", sa.Date(), nullable=False),
    sa.Column("player_row_id", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.UniqueConstraint("poll_date", "player_row_id", name="uq_poll_votes_date_player"),
  )
  op.create_index("ix_poll_votes_poll_date", "poll_votes", ["poll_date"], unique=False)
  op.create_index("ix_poll_votes_player_row_id", "poll_votes", ["player_row_id"], unique=False)


def downgrade() -> None:
  op.drop_index("ix_poll_votes_player_row_id", table_name="poll_votes")
  op.drop_index("ix_poll_votes_poll_date", table_name="poll_votes")
  op.drop_table("poll_votes")
