"""add durable bet payment intent

Revision ID: e5b7c9d1f3a2
Revises: c8f4e1a2b7d9
Create Date: 2026-09-29 12:00:00.000000
"""

from typing import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5b7c9d1f3a2"
down_revision: str | Sequence[str] | None = "c8f4e1a2b7d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
  op.add_column(
    "bet_payment_receipts",
    sa.Column("expected_amount_kopecks", sa.Integer(), nullable=True),
  )
  op.create_table(
    "bet_payment_receipt_bets",
    sa.Column("receipt_id", sa.Integer(), nullable=False),
    sa.Column("bet_id", sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(
      ["receipt_id"], ["bet_payment_receipts.row_id"], ondelete="CASCADE"
    ),
    sa.ForeignKeyConstraint(["bet_id"], ["bets.row_id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("receipt_id", "bet_id"),
  )


def downgrade() -> None:
  op.drop_table("bet_payment_receipt_bets")
  op.drop_column("bet_payment_receipts", "expected_amount_kopecks")
