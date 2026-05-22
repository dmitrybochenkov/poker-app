"""create bet_payment_receipts table

Revision ID: ea91b7c2d4f0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-22 15:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ea91b7c2d4f0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
    "bet_payment_receipts",
    sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("user_row_id", sa.Integer(), nullable=False),
    sa.Column("platform", sa.String(length=8), nullable=False),
    sa.Column("external_file_id", sa.String(length=255), nullable=True),
    sa.Column("operation_id", sa.String(length=255), nullable=True),
    sa.Column("amount_kopecks_ocr", sa.Integer(), nullable=True),
    sa.Column("recipient_tail4_ocr", sa.String(length=8), nullable=True),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.PrimaryKeyConstraint("row_id"),
    sa.UniqueConstraint("operation_id", name="uq_receipt_operation_id"),
    sa.UniqueConstraint("platform", "external_file_id", name="uq_receipt_platform_external_file_id"),
  )


def downgrade() -> None:
  op.drop_table("bet_payment_receipts")
