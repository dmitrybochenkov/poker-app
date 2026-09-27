"""add durable operation identity to buyin history

Revision ID: c8f4e1a2b7d9
Revises: b7d3e9f1a5c2
Create Date: 2026-09-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c8f4e1a2b7d9"
down_revision: Union[str, Sequence[str], None] = "b7d3e9f1a5c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("buyins_data") as batch_op:
        batch_op.add_column(sa.Column("operation_id", sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint("uq_buyins_data_operation_id", ["operation_id"])


def downgrade() -> None:
    with op.batch_alter_table("buyins_data") as batch_op:
        batch_op.drop_constraint("uq_buyins_data_operation_id", type_="unique")
        batch_op.drop_column("operation_id")
